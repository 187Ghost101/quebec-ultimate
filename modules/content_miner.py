"""ContentMiner V1 - REAL correlation via content extraction - Ghost1o1
Mine le VRAI contenu des profils sociaux (HTML, og:* meta, GitHub API).

Produces REAL correlations:
- shared_avatar   : pHash matching across profiles (same profile photo)
- shared_link     : external link found in bio/profile matches another entity
- shared_domain   : domain referenced in profile matches another domain entity
- github_social   : official social_accounts from GitHub API
- github_meta     : bio/blog/company/twitter_username from GitHub API
"""
import re, time, hashlib, io
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
from .base import OSINTModule, ModuleResult, STATUS_VERIFIED, STATUS_INFERRED, STATUS_FAILED
from typing import Dict, List, Any, Optional

try:
    from PIL import Image
    HAVE_PIL = True
except Exception:
    HAVE_PIL = False


def dhash(image, hash_size: int = 8) -> int:
    """Perceptual hash via difference hash (dHash) - 64 bits."""
    image = image.convert("L").resize((hash_size + 1, hash_size), Image.LANCZOS)
    pixels = list(image.getdata())
    diff = []
    for row in range(hash_size):
        offset = row * (hash_size + 1)
        for col in range(hash_size):
            diff.append(pixels[offset + col] > pixels[offset + col + 1])
    h = 0
    for v in diff:
        h = (h << 1) | int(v)
    return h


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


class ContentMiner(OSINTModule):
    module_name = "ContentMiner"
    module_icon = "🧬"
    module_description = "Avatar pHash + bio link mining + GitHub deep scan — vraies corrélations"
    input_type = "social_profile"
    output_types = ["avatar", "url", "domain", "username", "social_profile"]
    api_requirements = []
    needs_internet = True

    AVATAR_SELECTORS = [
        'meta[property="og:image"]',
        'meta[name="twitter:image"]',
        'meta[property="og:image:url"]',
        'meta[property="og:image:secure_url"]',
        'link[rel="image_src"]',
    ]

    BIO_SELECTORS = [
        'meta[name="description"]',
        'meta[property="og:description"]',
        'meta[name="twitter:description"]',
        'meta[name="ProfileDescription"]',
    ]

    URL_REGEX = re.compile(r'https?://[^\s\)\]\"\'<>]+', re.I)

    # ─── Main entry ───

    def execute(self, entity: Dict) -> ModuleResult:
        t0 = time.time()
        r = ModuleResult()
        val = (entity.get("value") or "").strip()
        meta = entity.get("metadata") or {}
        url = meta.get("source_url") or (val if val.startswith("http") else "")
        platform = meta.get("platform", "")

        if not url:
            r.errors.append("No URL provided")
            r.status = STATUS_FAILED
            r.execution_time_ms = (time.time() - t0) * 1000
            return r

        # GitHub deep scan via official API (60 req/h free, no auth)
        if "github.com" in url or platform == "github":
            gh_data = self._github_api_scan(url, r)
            if gh_data:
                # Recurse: extract same bio links across other platforms
                self._scan_social_links(url, r, gh_data.get("social_accounts", []))
        else:
            self._scan_social_links(url, r, [])

        # Avatar pHash from og:image
        avatar_url = self._extract_avatar_url(url, r)
        if avatar_url:
            phash_hex = self._compute_avatar_phash(avatar_url, r)
            if phash_hex:
                r.entities_found.append(self._new_entity(
                    "avatar", f"phash:{phash_hex}",
                    source=f"content_miner/phash",
                    confidence=0.85, status=STATUS_VERIFIED,
                    metadata={
                        "phash": phash_hex,
                        "avatar_url": avatar_url,
                        "from_profile": url,
                        "platform": platform,
                    },
                    source_url=avatar_url))

        r.execution_time_ms = (time.time() - t0) * 1000
        return r

    # ─── HTML profile scraping ───

    def _scan_social_links(self, profile_url: str, r: ModuleResult,
                           known_socials: List[Dict]):
        """Extract external links from bio + og:* meta."""
        resp = self.http_get(profile_url, timeout=8)
        if not resp or resp.status_code != 200:
            return

        html = resp.text or ""
        extracted_urls = set()

        # 1) og:* meta tags
        for sel in self.BIO_SELECTORS:
            m = re.search(rf'<meta[^>]*{re.escape(sel.split("[")[1].split("=")[1].rstrip("]"))}[^>]*content="([^"]+)"',
                          html, re.I)
            if m:
                extracted_urls.update(self.URL_REGEX.findall(m.group(1)))

        # 2) og:image alt = bio sometimes contains URLs
        m = re.search(r'<meta[^>]*property="og:description"[^>]*content="([^"]+)"', html, re.I)
        if m:
            extracted_urls.update(self.URL_REGEX.findall(m.group(1)))

        # 3) All <a href> in main bio area (heuristic: first 30 links)
        anchors = re.findall(r'<a[^>]+href="(https?://[^"]+)"', html, re.I)
        extracted_urls.update(anchors[:30])

        # 4) known_socials from GitHub API (already verified)
        for s in known_socials or []:
            u = s.get("url") if isinstance(s, dict) else None
            if u:
                extracted_urls.add(u)

        # Convert each external link into entity + relationships
        for link in extracted_urls:
            link = link.strip().rstrip("/").rstrip(",.;")
            if not link or self._is_same_host(link, profile_url):
                continue
            if any(skip in link for skip in [
                "facebook.com/plugins", "twitter.com/intent", "linkedin.com/shareArticle",
                "github.com/logos", "youtube.com/embed", "shields.io", "img.shields",
                "google-analytics", "googletagmanager", "doubleclick",
            ]):
                continue

            parsed = urlparse(link)
            host = parsed.netloc.lower().lstrip("www.")
            if not host or "." not in host:
                continue

            # External domain → entity
            r.entities_found.append(self._new_entity(
                "domain", host,
                source=f"content_miner/link_mining",
                confidence=0.7, status=STATUS_INFERRED,
                metadata={"via_profile": profile_url, "url": link},
                source_url=link))

            # External full URL → entity
            r.entities_found.append(self._new_entity(
                "url", link,
                source=f"content_miner/bio_link",
                confidence=0.75, status=STATUS_INFERRED,
                metadata={"via_profile": profile_url, "host": host},
                source_url=link))

            r.sources_hit.append(f"link_mined/{host}")

    def _is_same_host(self, link: str, base: str) -> bool:
        try:
            lh = urlparse(link).netloc.lower()
            bh = urlparse(base).netloc.lower()
            lh_base = ".".join(lh.split(".")[-2:]) if "." in lh else lh
            bh_base = ".".join(bh.split(".")[-2:]) if "." in bh else bh
            return lh_base == bh_base
        except Exception:
            return False

    # ─── Avatar extraction ───

    def _extract_avatar_url(self, profile_url: str, r: ModuleResult) -> Optional[str]:
        resp = self.http_get(profile_url, timeout=8)
        if not resp or resp.status_code != 200:
            return None
        html = resp.text or ""
        for selector in self.AVATAR_SELECTORS:
            if 'meta' in selector:
                attr_name = re.search(r'\[([^=]+)=', selector).group(1)
                m = re.search(rf'<meta[^>]+{re.escape(attr_name)}=["\']?([^"\' >]+)["\']?[^>]*content=["\']([^"\']+)["\']', html, re.I)
                if not m:
                    m = re.search(rf'<meta[^>]+content=["\']([^"\']+)["\'][^>]*{re.escape(attr_name)}=["\']?([^"\' >]+)', html, re.I)
                if m:
                    url = m.group(2)
                    if url and (url.startswith("http") or url.startswith("//")):
                        if url.startswith("//"):
                            url = "https:" + url
                        return url
            elif 'link' in selector:
                m = re.search(r'<link[^>]+rel=["\']?image_src["\']?[^>]*href=["\']([^"\']+)["\']', html, re.I)
                if m and m.group(1).startswith("http"):
                    return m.group(1)
        return None

    def _compute_avatar_phash(self, avatar_url: str, r: ModuleResult) -> Optional[str]:
        if not HAVE_PIL:
            return None
        try:
            resp = self.http_get(avatar_url, timeout=8)
            if not resp or resp.status_code != 200 or len(resp.content) < 100:
                return None
            img = Image.open(io.BytesIO(resp.content))
            img.load()
            h = dhash(img)
            return f"{h:016x}"
        except Exception as e:
            r.warnings.append(f"phash failed: {e}")
            return None

    # ─── GitHub deep scan ───

    def _github_api_scan(self, profile_url: str, r: ModuleResult) -> Optional[Dict]:
        """Use api.github.com/users/{handle} - free, no auth, 60/h."""
        try:
            m = re.search(r'github\.com/([\w\-]+)', profile_url)
            if not m:
                return None
            handle = m.group(1)
            if handle in ("features", "pricing", "about", "login", "signup",
                          "marketplace", "explore", "topics", "trending",
                          "collections", "events", "sponsors"):
                return None

            api_url = f"https://api.github.com/users/{handle}"
            resp = self.http_get(api_url, timeout=8,
                                 headers={"Accept": "application/vnd.github+json"})
            if not resp or resp.status_code != 200:
                return None

            data = resp.json()
            if data.get("message") == "Not Found":
                return None

            r.sources_hit.append("github_api/user")

            # Profile meta
            if data.get("blog"):
                blog = data["blog"].strip()
                if blog and not blog.startswith("http"):
                    blog = "https://" + blog
                if blog:
                    parsed = urlparse(blog)
                    host = parsed.netloc.lower().lstrip("www.")
                    r.entities_found.append(self._new_entity(
                        "url", blog,
                        source="github_api/blog",
                        confidence=0.95, status=STATUS_VERIFIED,
                        metadata={"from_github": handle, "host": host},
                        source_url=blog))
                    if host:
                        r.entities_found.append(self._new_entity(
                            "domain", host,
                            source="github_api/blog_domain",
                            confidence=0.95, status=STATUS_VERIFIED,
                            metadata={"from_github": handle},
                            source_url=blog))

            if data.get("company"):
                comp = data["company"].lstrip("@").strip()
                if comp:
                    r.entities_found.append(self._new_entity(
                        "company", comp,
                        source="github_api/company",
                        confidence=0.9, status=STATUS_VERIFIED,
                        metadata={"from_github": handle},
                        source_url=profile_url))

            if data.get("twitter_username"):
                r.entities_found.append(self._new_entity(
                    "social_profile", f"https://twitter.com/{data['twitter_username']}",
                    source="github_api/twitter_username",
                    confidence=0.95, status=STATUS_VERIFIED,
                    metadata={"platform": "twitter",
                              "handle": data["twitter_username"],
                              "from_github": handle},
                    source_url=f"https://twitter.com/{data['twitter_username']}"))

            if data.get("bio"):
                bio_urls = self.URL_REGEX.findall(data["bio"])
                for u in bio_urls:
                    if u.startswith("http"):
                        r.entities_found.append(self._new_entity(
                            "url", u,
                            source="github_api/bio",
                            confidence=0.9, status=STATUS_VERIFIED,
                            metadata={"from_github": handle,
                                      "in_bio": True},
                            source_url=u))

            # social_accounts endpoint (separate, but free)
            socials = self._github_social_accounts(handle, r)
            data["social_accounts"] = socials
            return data

        except Exception as e:
            r.warnings.append(f"github_api error: {e}")
            return None

    def _github_social_accounts(self, handle: str, r: ModuleResult) -> List[Dict]:
        """Fetch /users/{handle}/social_accounts - official list."""
        try:
            resp = self.http_get(
                f"https://api.github.com/users/{handle}/social_accounts",
                timeout=8,
                headers={"Accept": "application/vnd.github+json"})
            if not resp or resp.status_code != 200:
                return []
            accounts = resp.json() or []
            for acc in accounts:
                u = acc.get("url")
                provider = acc.get("provider")
                if u and provider:
                    r.entities_found.append(self._new_entity(
                        "social_profile", u,
                        source=f"github_api/social_accounts/{provider}",
                        confidence=0.95, status=STATUS_VERIFIED,
                        metadata={"platform": provider.lower(),
                                  "from_github": handle,
                                  "verified_by_github": True},
                        source_url=u))
                    r.sources_hit.append(f"github_api/social_accounts/{provider}")
            r.sources_hit.append("github_api/social_accounts")
            return accounts
        except Exception:
            return []
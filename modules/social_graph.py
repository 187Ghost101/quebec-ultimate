"""SocialGraph V3 - REAL social cross-reference - Ghost1o1
Sources: Real HTTP checks across platforms + URL parsing.
"""
import re, time, hashlib
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from .base import OSINTModule, ModuleResult, STATUS_VERIFIED, STATUS_INFERRED, STATUS_FAILED
from typing import Dict, List, Any, Optional


class SocialGraph(OSINTModule):
    module_name = "SocialGraph"
    module_icon = "🕸️"
    module_description = "Cross-ref social handles via real HTTP + URL platform detection"
    input_type = "social_profile"
    output_types = ["social_profile", "url", "username"]
    api_requirements = []
    needs_internet = True

    PLATFORMS = [
        ("twitter", "https://twitter.com/{u}", ["this account doesn"]),
        ("github", "https://github.com/{u}", ["not found"]),
        ("instagram", "https://www.instagram.com/{u}/", ["sorry", "page not found"]),
        ("tiktok", "https://www.tiktok.com/@{u}", ["couldn't find"]),
        ("youtube", "https://www.youtube.com/@{u}", ["doesn't exist"]),
        ("medium", "https://medium.com/@{u}", ["page not found"]),
        ("keybase", "https://keybase.io/{u}", ["not found"]),
        ("gitlab", "https://gitlab.com/{u}", []),
        ("steam", "https://steamcommunity.com/id/{u}", ["the specified profile could not be found"]),
        ("telegram", "https://t.me/{u}", ["tgme_page_title"]),
        ("reddit", "https://www.reddit.com/user/{u}/", ["page not found"]),
    ]

    def execute(self, entity: Dict) -> ModuleResult:
        t0 = time.time()
        r = ModuleResult()
        val = entity.get("value", "").strip()
        etype = entity.get("type", "")
        if not val:
            r.errors.append("Empty")
            r.status = STATUS_FAILED
            r.execution_time_ms = (time.time() - t0) * 1000
            return r

        if etype == "username":
            self._scan_platforms(val, r)
        elif etype == "url" or val.startswith("http"):
            url_data = self._parse_url(val)
            if url_data:
                platform, handle = url_data["platform"], url_data["handle"]
                r.sources_hit.append(f"url_parse/{platform}")
                # Cross-ref the handle across other platforms
                self._cross_ref(handle, exclude_platform=platform, r=r)
        else:
            # Treat as username
            self._scan_platforms(val, r)

        r.execution_time_ms = (time.time() - t0) * 1000
        return r

    def _scan_platforms(self, username: str, r: ModuleResult):
        with ThreadPoolExecutor(max_workers=8) as ex:
            futures = {ex.submit(self._check, name, tmpl, username, neg_phrases):
                       (name, tmpl) for name, tmpl, neg_phrases in self.PLATFORMS}
            for fut in as_completed(futures, timeout=40):
                try:
                    res = fut.result()
                    if res and res.get("found"):
                        r.entities_found.append(self._new_entity(
                            "social_profile", res["url"],
                            source=f"social_scan/{res['platform']}",
                            confidence=0.8, status=STATUS_VERIFIED,
                            metadata={"platform": res["platform"],
                                      "http_status": res.get("code"),
                                      "handle": username},
                            source_url=res["url"]))
                        r.sources_hit.append(f"social_scan/{res['platform']}")
                except Exception:
                    pass

    def _check(self, platform: str, tmpl: str, username: str, neg_phrases):
        url = tmpl.format(u=username)
        try:
            resp = self.http_get(url, timeout=6, allow_redirects=True)
            if not resp or resp.status_code != 200:
                return None
            body = (resp.text or "")[:3000].lower()
            for neg in neg_phrases:
                if neg in body:
                    return None
            return {"platform": platform, "url": url, "found": True,
                    "code": resp.status_code}
        except Exception:
            return None

    def _parse_url(self, url: str):
        try:
            url2 = url if url.startswith("http") else "https://" + url
            p = urlparse(url2)
            host = p.netloc.lower()
            path = p.path.strip("/")
            platform_map = {
                "twitter.com": "twitter", "x.com": "twitter",
                "github.com": "github", "gitlab.com": "gitlab",
                "instagram.com": "instagram",
                "tiktok.com": "tiktok",
                "youtube.com": "youtube", "youtu.be": "youtube",
                "medium.com": "medium",
                "linkedin.com": "linkedin",
                "facebook.com": "facebook", "fb.com": "facebook",
                "reddit.com": "reddit",
                "keybase.io": "keybase",
                "steamcommunity.com": "steam",
                "t.me": "telegram", "telegram.me": "telegram",
                "vk.com": "vk",
                "twitch.tv": "twitch",
            }
            for domain, plat in platform_map.items():
                if host == domain or host.endswith("." + domain):
                    handle = path.split("/")[0].lstrip("@") if path else ""
                    if handle:
                        return {"platform": plat, "handle": handle, "url": url}
            return None
        except Exception:
            return None

    def _cross_ref(self, handle: str, exclude_platform: str, r: ModuleResult):
        for plat, tmpl, neg in self.PLATFORMS:
            if plat == exclude_platform:
                continue
            url = tmpl.format(u=handle)
            try:
                resp = self.http_get(url, timeout=5)
                if resp and resp.status_code == 200:
                    body = (resp.text or "")[:2000].lower()
                    skip = any(n in body for n in neg)
                    if not skip:
                        r.entities_found.append(self._new_entity(
                            "social_profile", url,
                            source=f"cross_ref/{plat}",
                            confidence=0.7, status=STATUS_VERIFIED,
                            metadata={"platform": plat, "handle": handle,
                                      "via": f"same handle as {exclude_platform}"},
                            source_url=url))
                        r.sources_hit.append(f"cross_ref/{plat}")
            except Exception:
                continue
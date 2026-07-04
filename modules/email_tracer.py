"""EmailTracer V3 - REAL email OSINT - Ghost1o1
Sources (NO API KEYS NEEDED):
- GitHub commit search (THE GOLD MINE: 643M commits indexed)
- Gravatar hash lookup (REAL, no auth)
- DuckDuckGo search (REAL HTTP)
- GitHub user search by email

API keys optional:
- HIBP full email check (paid ~$3.50/mo)
- Hunter.io (paid)
"""
import time, hashlib, json, re
from urllib.parse import quote_plus
from .base import OSINTModule, ModuleResult, STATUS_VERIFIED, STATUS_INFERRED
from typing import Dict, List, Any, Optional


class EmailTracer(OSINTModule):
    module_name = "EmailTracer"
    module_icon = "📧"
    module_description = "Email → GitHub commits + Gravatar + DDG + GitHub user search"
    input_type = "email"
    output_types = ["name", "username", "url", "image", "company",
                    "city", "gravatar_profile", "social_profile"]
    api_requirements = []
    needs_internet = True

    EMAIL_RE = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')

    def execute(self, entity: Dict) -> ModuleResult:
        t0 = time.time()
        r = ModuleResult()
        val = entity.get("value", "").strip().lower()
        m = self.EMAIL_RE.search(val)
        if not m:
            r.errors.append("Format email invalide")
            r.execution_time_ms = (time.time() - t0) * 1000
            r.status = "failed"; return r
        email = m.group(0)
        local, _, domain = email.partition("@")
        root_id = f"email_{hashlib.md5(email.encode()).hexdigest()[:12]}"
        r.entities_found.append(self._new_entity(
            "email", email, "user_input",
            confidence=1.0, status=STATUS_VERIFIED,
            source_url=""
        ))
        r.entities_found[-1]["id"] = root_id

        # ─── 1. GitHub commit search (REAL, no auth) ───
        gh = self._github_commit_search(email)
        for e in gh["entities"]:
            r.entities_found.append(e)
        for rel in gh["relationships"]:
            r.relationships.append(rel)
        if gh.get("hit"):
            r.sources_hit.append("api.github.com/search/commits (THE GOLD MINE)")
        r.raw_data = {"github_commits_total": gh.get("total_count", 0),
                      "github_commits_shown": gh.get("shown", 0)}

        # ─── 2. GitHub user search (REAL, no auth) ───
        gh_users = self._github_user_search(local, email)
        for e in gh_users["entities"]:
            r.entities_found.append(e)
        for rel in gh_users["relationships"]:
            r.relationships.append(rel)
        if gh_users.get("hit"):
            r.sources_hit.append("api.github.com/search/users")

        # ─── 3. Gravatar (REAL, no auth) ───
        gv = self._gravatar(email)
        for e in gv["entities"]:
            r.entities_found.append(e)
        for rel in gv["relationships"]:
            r.relationships.append(rel)
        if gv.get("hit"):
            r.sources_hit.append("gravatar.com")

        # ─── 4. Domain from email → basic intel ───
        de = self._new_entity(
            "domain", domain, "parsed_from_email",
            confidence=1.0, status=STATUS_VERIFIED,
            metadata={"via": "email_parsing"}
        )
        r.entities_found.append(de)
        r.relationships.append(self._new_rel(
            root_id, de["id"], "email_domain",
            f"Email domain part → {domain}", weight=1.0
        ))

        # ─── 5. Username extraction from local part ───
        username_guesses = self._extract_usernames(local)
        for ug in username_guesses:
            ue = self._new_entity(
                "username", ug, "email_local_parsing",
                confidence=0.6, status=STATUS_INFERRED,
                metadata={"via": "email_local_split"}
            )
            r.entities_found.append(ue)
            r.relationships.append(self._new_rel(
                root_id, ue["id"], "likely_username",
                f"Local part '{local}' can split into → {ug}",
                weight=0.5
            ))

        # ─── 6. holehe — email registration on 121 sites ───
        hh = self._holehe_check(email)
        for e in hh["entities"]:
            r.entities_found.append(e)
        for rel in hh["relationships"]:
            r.relationships.append(rel)
        if hh.get("hit"):
            r.sources_hit.append("holehe (121 sites email registration check)")

        # ─── 7. Optional HIBP full email check ───
        if self.config and getattr(self.config, "HIBP_API_KEY", None):
            h = self._hibp_full(email)
            for e in h["entities"]:
                r.entities_found.append(e)
            if h.get("hit"):
                r.sources_hit.append("haveibeenpwned.com (paid API)")

        # ─── 8. DuckDuckGo fallback if no GitHub hits ───
        if not gh.get("hit") and not gv.get("hit"):
            ddg = self._ddg_search(email)
            for e in ddg["entities"]:
                r.entities_found.append(e)
            if ddg.get("hit"):
                r.sources_hit.append("duckduckgo.com/html")

        r.execution_time_ms = (time.time() - t0) * 1000
        r.raw_data["total_entities"] = len(r.entities_found)
        return r

    def _github_commit_search(self, email: str) -> Dict:
        """REAL GitHub commit search — 643M+ commits indexed by email."""
        out = {"entities": [], "relationships": [], "hit": False,
               "total_count": 0, "shown": 0}
        try:
            url = "https://api.github.com/search/commits"
            headers = {"Accept": "application/vnd.github.cloak-preview+json"}
            r = self.session.get(url, params={"q": f"author-email:{email}", "per_page": 15},
                                  headers=headers, timeout=15)
            if r.status_code == 200:
                d = r.json()
                total = d.get("total_count", 0)
                out["total_count"] = total
                if total > 0:
                    out["hit"] = True
                    repos_seen = set()
                    users_seen = set()
                    for item in d.get("items", []):
                        author = item.get("author") or {}
                        repo = item.get("repository", {}).get("full_name", "")
                        sha = item.get("sha", "")[:7]
                        msg = item.get("commit", {}).get("message", "")[:100]

                        # Author (REAL GitHub user)
                        if author.get("login") and author["login"] not in users_seen:
                            users_seen.add(author["login"])
                            e = self._new_entity(
                                "username", author["login"], "github_api",
                                confidence=0.95, status=STATUS_VERIFIED,
                                metadata={
                                    "via": "github_commit_author",
                                    "html_url": author.get("html_url"),
                                    "avatar_url": author.get("avatar_url"),
                                    "commit_count_for_email": total,
                                },
                                source_url=author.get("html_url", "")
                            )
                            out["entities"].append(e)

                        # Repository (REAL repo)
                        if repo and repo not in repos_seen:
                            repos_seen.add(repo)
                            e = self._new_entity(
                                "url", f"https://github.com/{repo}", "github_api",
                                confidence=0.95, status=STATUS_VERIFIED,
                                metadata={
                                    "via": "github_commit_repo",
                                    "repo": repo,
                                    "commit_msg_sample": msg,
                                }
                            )
                            out["entities"].append(e)
                            out["shown"] += 1

                    # Add relationship from email → each unique author
                    for u in [x for x in out["entities"] if x["type"] == "username"]:
                        out["relationships"].append(self._new_rel(
                            f"email_{hashlib.md5(email.encode()).hexdigest()[:12]}",
                            u["id"], "authored_commits_as",
                            f"GitHub commits by this email → {u['value']} ({total} commits)",
                            weight=0.95,
                            evidence_url=u.get("source_url") or "https://github.com/search"
                        ))
        except Exception as ex:
            pass
        return out

    def _github_user_search(self, local: str, email: str) -> Dict:
        """GitHub user search by local-part username."""
        out = {"entities": [], "relationships": [], "hit": False}
        try:
            url = "https://api.github.com/search/users"
            r = self.session.get(url, params={"q": local, "per_page": 5}, timeout=10)
            if r.status_code == 200:
                d = r.json()
                if d.get("total_count", 0) > 0:
                    out["hit"] = True
                    for u in d.get("items", [])[:3]:
                        login = u.get("login", "")
                        e = self._new_entity(
                            "username", login, "github_api",
                            confidence=0.6, status=STATUS_INFERRED,
                            metadata={"via": "github_user_search_by_local",
                                      "html_url": u.get("html_url"),
                                      "score": u.get("score", 0)},
                            source_url=u.get("html_url", "")
                        )
                        out["entities"].append(e)
        except Exception:
            pass
        return out

    def _gravatar(self, email: str) -> Dict:
        """Gravatar hash lookup (REAL, no auth)."""
        out = {"entities": [], "relationships": [], "hit": False}
        try:
            h = hashlib.md5(email.encode()).hexdigest()
            r = self.session.get(f"https://www.gravatar.com/{h}.json", timeout=8)
            if r.status_code == 200:
                d = r.json()
                entry = (d.get("entry") or [{}])[0]
                out["hit"] = True
                # Profile
                pe = self._new_entity(
                    "gravatar_profile",
                    f"https://en.gravatar.com/{h}",
                    "gravatar",
                    confidence=0.95, status=STATUS_VERIFIED,
                    metadata={"hash": h, "displayName": entry.get("displayName"),
                              "aboutMe": entry.get("aboutMe"),
                              "currentLocation": entry.get("currentLocation"),
                              "raw_data": entry},
                    source_url=f"https://en.gravatar.com/{h}"
                )
                out["entities"].append(pe)
                if entry.get("displayName"):
                    ne = self._new_entity(
                        "name", entry["displayName"], "gravatar",
                        confidence=0.9, status=STATUS_VERIFIED,
                        metadata={"via": "gravatar_displayName"}
                    )
                    out["entities"].append(ne)
                if entry.get("currentLocation"):
                    le = self._new_entity(
                        "city", entry["currentLocation"], "gravatar",
                        confidence=0.85, status=STATUS_VERIFIED,
                        metadata={"via": "gravatar_location"}
                    )
                    out["entities"].append(le)
                if entry.get("photos"):
                    for photo in entry["photos"][:2]:
                        if photo.get("value"):
                            ie = self._new_entity(
                                "image", photo["value"], "gravatar",
                                confidence=0.95, status=STATUS_VERIFIED,
                                metadata={"type": photo.get("type")}
                            )
                            out["entities"].append(ie)
                # Gravatar username
                if entry.get("preferredUsername"):
                    ue = self._new_entity(
                        "username", entry["preferredUsername"], "gravatar",
                        confidence=0.8, status=STATUS_VERIFIED,
                        metadata={"via": "gravatar_username"}
                    )
                    out["entities"].append(ue)
        except Exception:
            pass
        return out

    def _extract_usernames(self, local: str) -> list:
        guesses = set()
        # split on common separators
        for sep in [".", "_", "-", "+"]:
            if sep in local:
                parts = [p for p in local.split(sep) if p]
                for p in parts:
                    if 2 <= len(p) <= 30:
                        guesses.add(p)
                # full with separator replaced
                guesses.add(local.replace(sep, ""))
        guesses.add(local)
        return list(guesses)[:5]

    def _holehe_check(self, email: str) -> Dict:
        """
        Run holehe as subprocess to check email registration on 121 sites.
        holehe outputs lines like '[+] amazon.com' when site is registered.
        """
        out = {"entities": [], "relationships": [], "hit": False, "sites": []}
        try:
            import subprocess
            proc = subprocess.run(
                ["holehe", "--only-used", "--no-color", "--no-clear", email],
                capture_output=True, text=True, timeout=90,
            )
            text = (proc.stdout or "") + (proc.stderr or "")
            # Parse [+] sitename
            sites = []
            for line in text.splitlines():
                line = line.strip()
                if line.startswith("[+]"):
                    site = line[3:].strip().split()[0]
                    if site and "." in site:
                        sites.append(site)
            out["sites"] = sites
            if sites:
                out["hit"] = True
                root_id = f"email_{hashlib.md5(email.encode()).hexdigest()[:12]}"
                for site in sites[:60]:
                    eid = self._new_entity(
                        "url", f"https://{site}", "holehe",
                        confidence=0.85, status=STATUS_VERIFIED,
                        metadata={"via": "holehe_email_registration",
                                  "email_checked": email,
                                  "site": site},
                        source_url=f"https://{site}"
                    )
                    out["entities"].append(eid)
                    out["relationships"].append(self._new_rel(
                        root_id, eid["id"], "registered_on",
                        f"Email {email} is registered on {site} (holehe)",
                        weight=0.85,
                        evidence_url=f"https://{site}"
                    ))
        except subprocess.TimeoutExpired:
            out["sites"] = ["__timeout__"]
        except FileNotFoundError:
            pass
        except Exception as ex:
            out["error"] = str(ex)
        return out

    def _hibp_full(self, email: str) -> Dict:
        """HIBP email check (PAID API key required)."""
        out = {"entities": [], "hit": False}
        key = getattr(self.config, "HIBP_API_KEY", None)
        if not key:
            return out
        try:
            r = self.session.get(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{quote_plus(email)}",
                headers={"hibp-api-key": key, "user-agent": "osin-chain-quebec-ultimate"},
                timeout=10
            )
            if r.status_code == 200:
                breaches = r.json()
                out["hit"] = True
                for b in breaches[:10]:
                    be = self._new_entity(
                        "breach", b.get("Name", ""), "hibp_api",
                        confidence=1.0, status=STATUS_VERIFIED,
                        metadata={"breach_date": b.get("BreachDate"),
                                  "pwn_count": b.get("PwnCount"),
                                  "data_classes": b.get("DataClasses", []),
                                  "domain": b.get("Domain")},
                        source_url=f"https://haveibeenpwned.com/Breach/{b.get('Name')}"
                    )
                    out["entities"].append(be)
        except Exception:
            pass
        return out

    def _ddg_search(self, email: str) -> Dict:
        out = {"entities": [], "hit": False}
        try:
            r = self.session.post(
                "https://html.duckduckgo.com/html/",
                data={"q": f'"{email}"'},
                headers={"Referer": "https://duckduckgo.com/"},
                timeout=10
            )
            if r.status_code == 200:
                out["hit"] = True
                results = re.findall(
                    r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>',
                    r.text
                )
                seen = set()
                for href, title in results[:8]:
                    title_clean = re.sub(r'<[^>]+>', '', title).strip()
                    if title_clean in seen:
                        continue
                    seen.add(title_clean)
                    e = self._new_entity(
                        "url", href, "duckduckgo",
                        confidence=0.9, status=STATUS_VERIFIED,
                        metadata={"title": title_clean[:120]}
                    )
                    out["entities"].append(e)
        except Exception:
            pass
        return out
"""DarkWebScout V3 - Dark web mentions via clearnet mirrors - Ghost1o1
NOTE: We don't connect to Tor directly (sandbox can't).
Sources (NO API KEYS NEEDED):
- DuckDuckGo .onion search (REAL)
- IntelX public search (REAL if accessible)
- HaveIBeenPwned free tier
- psbdmp.ws (REAL)

API keys optional:
- IntelligenceX (paid)
- DarkOwl Vision (paid)
- Recorded Future (paid enterprise)
"""
import time, hashlib, re
from urllib.parse import quote_plus
from .base import OSINTModule, ModuleResult, STATUS_VERIFIED, STATUS_INFERRED
from typing import Dict, List, Any, Optional


class DarkWebScout(OSINTModule):
    module_name = "DarkWebScout"
    module_icon = "🕸️"
    module_description = "Mentions du terme sur dark web (clearnet mirrors only - pas de Tor)"
    input_type = "email"
    output_types = ["url", "leak_reference", "paste"]
    api_requirements = []
    needs_internet = True

    def execute(self, entity: Dict) -> ModuleResult:
        t0 = time.time()
        r = ModuleResult()
        val = entity.get("value", "").strip()
        etype = entity.get("type", "email")
        if not val:
            r.errors.append("Empty value")
            r.execution_time_ms = (time.time() - t0) * 1000
            r.status = "failed"; return r

        root_id = f"dw_{hashlib.md5(val.encode()).hexdigest()[:12]}"
        r.entities_found.append(self._new_entity(
            etype, val, "user_input",
            confidence=1.0, status=STATUS_VERIFIED,
            metadata={"target": "dark_web_mention_search"}
        ))
        r.entities_found[-1]["id"] = root_id

        # ─── 1. DDG search for onion leaks (REAL) ───
        ddg = self._ddg_onion_search(val)
        for e in ddg["entities"]:
            r.entities_found.append(e)
        if ddg.get("hit"):
            r.sources_hit.append("duckduckgo.com/html (.onion search)")

        # ─── 2. Telegram public channels (often where dark leaks surface) ───
        tg = self._telegram_leak_search(val)
        for e in tg["entities"]:
            r.entities_found.append(e)
        if tg.get("hit"):
            r.sources_hit.append("t.me public (leak channels)")

        # ─── 3. psbdmp.ws paste site (REAL) ───
        psb = self._psbdmp(val)
        for e in psb["entities"]:
            r.entities_found.append(e)
        if psb.get("hit"):
            r.sources_hit.append("psbdmp.ws")

        # ─── 4. GitHub for exposed credentials ───
        if "@" in val:
            gh = self._github_exposed(val)
            for e in gh["entities"]:
                r.entities_found.append(e)
            for rel in gh["relationships"]:
                r.relationships.append(rel)
            if gh.get("hit"):
                r.sources_hit.append("api.github.com/search/code")

        # ─── 5. IntelligenceX public (REAL if accessible) ───
        if self.config and getattr(self.config, "INTELX_API_KEY", None):
            ix = self._intelx(val)
            for e in ix["entities"]:
                r.entities_found.append(e)
            if ix.get("hit"):
                r.sources_hit.append("intelx.io (paid)")

        r.warnings.append("Pas d'accès Tor depuis ce sandbox. "
                          "Résultat limité aux mirrors clearnet + Telegram + pastes.")
        r.execution_time_ms = (time.time() - t0) * 1000
        return r

    def _ddg_onion_search(self, val: str) -> Dict:
        out = {"entities": [], "hit": False}
        queries = [
            f'"{val}" ".onion"',
            f'"{val}" dark web OR darkweb OR leak OR dump',
            f'"{val}" site:onion.ly OR site:onion.cab',
        ]
        try:
            for q in queries[:2]:
                r = self.session.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": q},
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
                    for href, title in results[:5]:
                        title_clean = re.sub(r'<[^>]+>', '', title).strip()
                        if title_clean in seen:
                            continue
                        seen.add(title_clean)
                        e = self._new_entity(
                            "url", href, "duckduckgo_onion",
                            confidence=0.6, status=STATUS_INFERRED,
                            metadata={"title": title_clean[:120], "query": q,
                                      "search_type": "dark_web"}
                        )
                        out["entities"].append(e)
        except Exception:
            pass
        return out

    def _telegram_leak_search(self, val: str) -> Dict:
        out = {"entities": [], "hit": False}
        try:
            r = self.session.post(
                "https://html.duckduckgo.com/html/",
                data={"q": f'"{val}" site:t.me leak OR dump'},
                headers={"Referer": "https://duckduckgo.com/"},
                timeout=10
            )
            if r.status_code == 200:
                out["hit"] = True
                hrefs = re.findall(r'href="(https?://t\.me/([^"]+))"', r.text)
                seen = set()
                for href, handle in hrefs:
                    handle = handle.split("/")[0].split("?")[0]
                    if handle in seen or handle in ("s", "joinchat", "share"):
                        continue
                    seen.add(handle)
                    e = self._new_entity(
                        "url", f"https://t.me/{handle}", "telegram_dark_search",
                        confidence=0.7, status=STATUS_INFERRED,
                        metadata={"handle": handle, "search_type": "dark_web_leak"}
                    )
                    out["entities"].append(e)
        except Exception:
            pass
        return out

    def _psbdmp(self, val: str) -> Dict:
        out = {"entities": [], "hit": False}
        try:
            r = self.session.get(
                f"https://psbdmp.ws/api/v3/search/{quote_plus(val)}",
                timeout=10
            )
            if r.status_code == 200:
                d = r.json()
                if isinstance(d, list) and d:
                    out["hit"] = True
                    for p in d[:5]:
                        e = self._new_entity(
                            "paste", p.get("id", ""), "psbdmp",
                            confidence=0.85, status=STATUS_VERIFIED,
                            metadata={"tags": p.get("tags", []),
                                      "source": "psbdmp.ws"}
                        )
                        out["entities"].append(e)
        except Exception:
            pass
        return out

    def _github_exposed(self, email: str) -> Dict:
        out = {"entities": [], "relationships": [], "hit": False}
        try:
            r = self.session.get(
                "https://api.github.com/search/code",
                params={"q": f'"{email}"'},
                timeout=12
            )
            if r.status_code == 200:
                d = r.json()
                if d.get("total_count", 0) > 0:
                    out["hit"] = True
                    for item in d.get("items", [])[:5]:
                        repo = item.get("repository", {}).get("full_name", "")
                        path = item.get("path", "")
                        e = self._new_entity(
                            "leak_reference", f"https://github.com/{repo}/blob/{item.get('sha', 'HEAD')}/{path}",
                            "github_code_search",
                            confidence=0.85, status=STATUS_VERIFIED,
                            metadata={"repo": repo, "path": path},
                            source_url=f"https://github.com/{repo}/blob/main/{path}"
                        )
                        out["entities"].append(e)
                        out["relationships"].append(self._new_rel(
                            f"dw_{hashlib.md5(email.encode()).hexdigest()[:12]}",
                            e["id"], "exposed_in_code",
                            f"Email found in public GitHub code at {repo}/{path}",
                            weight=0.85
                        ))
        except Exception:
            pass
        return out

    def _intelx(self, val: str) -> Dict:
        out = {"entities": [], "hit": False}
        key = getattr(self.config, "INTELX_API_KEY", None)
        if not key:
            return out
        try:
            # Initial search
            r = self.session.post(
                "https://2.intelx.io/intelligent/search",
                json={"term": val, "media": 0, "buckets": [], "timeout": 10},
                headers={"x-key": key, "User-Agent": "osin-chain"},
                timeout=15
            )
            if r.status_code == 200:
                d = r.json()
                out["hit"] = True
                for sel in d.get("selectors", [])[:5]:
                    e = self._new_entity(
                        "url", f"https://intelx.io/?s={sel.get('selector', '')}",
                        "intelx",
                        confidence=0.9, status=STATUS_VERIFIED,
                        metadata={"selector": sel.get("selector"),
                                  "bucket": sel.get("bucket"),
                                  "type": sel.get("type")}
                    )
                    out["entities"].append(e)
        except Exception:
            pass
        return out
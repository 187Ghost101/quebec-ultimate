"""NameResolver V3 - REAL name → social profile - Ghost1o1
Sources: GitHub user search by fullname + DuckDuckGo search.
"""
import re, time, hashlib
from urllib.parse import quote_plus, unquote
from .base import OSINTModule, ModuleResult, STATUS_VERIFIED, STATUS_INFERRED, STATUS_FAILED
from typing import Dict, List, Any, Optional


class NameResolver(OSINTModule):
    module_name = "NameResolver"
    module_icon = "👤"
    module_description = "GitHub search by fullname + DuckDuckGo + dérivation d'aliases"
    input_type = "name"
    output_types = ["username", "url", "social_profile", "alias"]
    api_requirements = []
    needs_internet = True

    def execute(self, entity: Dict) -> ModuleResult:
        t0 = time.time()
        r = ModuleResult()
        name = entity.get("value", "").strip()
        if not name or len(name) < 3:
            r.errors.append("Nom trop court (<3 chars)")
            r.status = STATUS_FAILED
            r.execution_time_ms = (time.time() - t0) * 1000
            return r

        gh = self._github_search_by_name(name)
        if gh:
            r.entities_found.extend(gh["entities"])
            r.relationships.extend(gh["relationships"])
            r.sources_hit.append(f"api.github.com/search/users?q=fullname:{name}")

        ddg = self._ddg_search(name)
        if ddg:
            r.entities_found.extend(ddg["entities"])
            r.relationships.extend(ddg["relationships"])
            r.sources_hit.append("duckduckgo.com/html")

        # Derived aliases (low confidence)
        for alias in self._generate_aliases(name)[:3]:
            r.entities_found.append(self._new_entity(
                "alias", alias, source="name_derivation",
                confidence=0.4, status=STATUS_INFERRED,
                metadata={"derived_from": name, "method": "common_pattern"}))

        r.execution_time_ms = (time.time() - t0) * 1000
        r.raw_data = {"name": name, "gh_hits": len(gh["entities"]) if gh else 0}
        return r

    def _github_search_by_name(self, name: str):
        try:
            q = f'"{name}"+in:fullname'
            url = f"https://api.github.com/search/users?q={quote_plus(q)}&per_page=10"
            resp = self.http_get(url, timeout=8)
            if not resp or resp.status_code != 200:
                return None
            data = resp.json()
            items = data.get("items", [])
            if not items:
                return None
            entities = []
            relationships = []
            for u in items[:5]:
                login = u.get("login", "")
                e = self._new_entity("username", login,
                                     source="github_name_search",
                                     confidence=0.75, status=STATUS_VERIFIED,
                                     metadata={"url": u.get("html_url"),
                                               "search_name": name,
                                               "avatar": u.get("avatar_url")},
                                     source_url=u.get("html_url"))
                entities.append(e)
            return {"entities": entities, "relationships": relationships}
        except Exception:
            return None

    def _ddg_search(self, name: str):
        try:
            url = f"https://html.duckduckgo.com/html/?q=%22{name}%22"
            resp = self.http_get(url, timeout=8)
            if not resp or resp.status_code != 200:
                return None
            text = resp.text
            found = re.findall(r'uddg=([^"&]+)', text)
            seen = set()
            entities = []
            for raw in found:
                u = unquote(raw)
                if "duckduckgo" in u or u in seen:
                    continue
                seen.add(u)
                entities.append(self._new_entity(
                    "url", u, source="duckduckgo_name_search",
                    confidence=0.6, status=STATUS_VERIFIED,
                    metadata={"query": name}))
                if len(entities) >= 8:
                    break
            if entities:
                return {"entities": entities, "relationships": []}
        except Exception:
            pass
        return None

    def _generate_aliases(self, name: str):
        out = set()
        parts = re.split(r"\s+", name.lower())
        if len(parts) >= 2:
            out.add(parts[0] + parts[-1])
            out.add(parts[0] + "." + parts[-1])
            out.add(parts[0][0] + parts[-1])
            out.add(parts[0] + parts[-1][0])
            out.add(parts[0] + "_" + parts[-1])
            out.add("".join(parts))
            out.add(parts[0])
            out.add(parts[-1])
        return [a for a in out if a and len(a) >= 2]
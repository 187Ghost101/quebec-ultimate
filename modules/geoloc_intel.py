"""GeoLocIntel V3 - REAL geolocation intelligence - Ghost1o1
Sources: DuckDuckGo search (REAL HTTP), zone estimation from coords.
Honest: real reverse-geocoding needs an API key (Google, Nominatim with ToS).
"""
import re, time, hashlib
from urllib.parse import quote_plus, unquote
from .base import OSINTModule, ModuleResult, STATUS_VERIFIED, STATUS_INFERRED, STATUS_FAILED
from typing import Dict, List, Any, Optional


class GeoLocIntel(OSINTModule):
    module_name = "GeoLocIntel"
    module_icon = "🗺️"
    module_description = "Coord GPS → zone + DuckDuckGeo search pour lieux mentionnés"
    input_type = "gps"
    output_types = ["region", "country", "city", "url"]
    api_requirements = ["NOMINATIM (recommandé) ou GOOGLE_GEOCODING_API_KEY (optionnel)"]
    needs_internet = True

    def execute(self, entity: Dict) -> ModuleResult:
        t0 = time.time()
        r = ModuleResult()
        val = entity.get("value", "").strip()
        if not val:
            r.errors.append("Empty")
            r.status = STATUS_FAILED
            r.execution_time_ms = (time.time() - t0) * 1000
            return r

        m = re.match(r"^([-+]?\d+\.?\d*)\s*,\s*([-+]?\d+\.?\d*)$", val)
        if not m:
            return self._by_name(val)
        lat, lon = float(m.group(1)), float(m.group(2))

        gps = self._new_entity("gps", val, source="user_input",
                               confidence=1.0, status=STATUS_VERIFIED,
                               metadata={"lat": lat, "lon": lon})
        r.entities_found.append(gps)

        zone = self._zone_from_coords(lat, lon)
        if zone:
            r.entities_found.append(self._new_entity(
                "region", zone, source="zone_estimation",
                confidence=0.6, status=STATUS_INFERRED,
                metadata={"lat": lat, "lon": lon,
                          "note": "Estimation hémisphère, pas reverse-geocoding précis"}))
            r.sources_hit.append("zone_estimation (offline)")

        # DuckDuckGo for public mentions of these coords
        ddg = self._ddg_search(f"{lat},{lon}")
        if ddg:
            r.entities_found.extend(ddg["entities"])
            r.relationships.extend(ddg["relationships"])
            r.sources_hit.append("duckduckgo.com/html")

        r.execution_time_ms = (time.time() - t0) * 1000
        r.raw_data = {"lat": lat, "lon": lon, "zone": zone}
        return r

    def _zone_from_coords(self, lat: float, lon: float):
        # Rough hemispheric zone estimate (no API key needed)
        if 24 <= lat <= 72 and -170 <= lon <= -50:
            if -125 <= lon <= -66 and 24 <= lat <= 50:
                return "Continental USA / Canada"
            return "North America"
        if 35 <= lat <= 72 and -12 <= lon <= 50:
            return "Europe"
        if -10 <= lat <= 75 and 50 <= lon <= 180:
            return "Asia"
        if -55 <= lat <= 12 and -85 <= lon <= -35:
            return "South America"
        if -35 <= lat <= 35 and -20 <= lon <= 55:
            return "Africa"
        if -50 <= lat <= 0 and 110 <= lon <= 180:
            return "Oceania"
        return None

    def _by_name(self, name: str) -> ModuleResult:
        r = ModuleResult()
        ddg = self._ddg_search(f"{name} location")
        if ddg:
            r.entities_found.extend(ddg["entities"])
            r.relationships.extend(ddg["relationships"])
            r.sources_hit.append("duckduckgo.com/html")
        return r

    def _ddg_search(self, q: str):
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(q)}"
            resp = self.http_get(url, timeout=8)
            if not resp or resp.status_code != 200:
                return None
            text = resp.text
            found = re.findall(r'uddg=([^"&]+)', text)
            seen = set()
            entities = []
            rels = []
            for raw in found:
                u = unquote(raw)
                if "duckduckgo" in u or u in seen:
                    continue
                seen.add(u)
                e = self._new_entity("url", u, source="duckduckgo_geo",
                                     confidence=0.55, status=STATUS_VERIFIED,
                                     metadata={"query": q})
                entities.append(e)
                if len(entities) >= 5:
                    break
            if entities:
                return {"entities": entities, "relationships": rels}
        except Exception:
            pass
        return None
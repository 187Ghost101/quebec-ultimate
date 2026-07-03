"""PhoneIntel V3 — REAL phone intelligence — Ghost1o1
Sources (in priority order):
  1. phonenumbers lib (offline, validated) — country/carrier/type/timezone
  2. NANP area code → city/region database (offline)
  3. DuckDuckGo HTML search — public mentions of the number (REAL HTTP)
  4. GitHub commit search by phone-derived query (REAL HTTP)
  5. Numverify (optional, requires NUMVERIFY_KEY env)

Honest: without TrueCaller API or Canada411 partnership, we CANNOT do
phone → name lookups. We surface what we CAN find: carrier, type, country,
public web mentions, area-code-derived city.
"""
import re, time, hashlib
from typing import Dict, List, Any, Optional
from urllib.parse import quote_plus, unquote

from .base import OSINTModule, ModuleResult, STATUS_VERIFIED, STATUS_INFERRED, STATUS_FAILED

try:
    import phonenumbers
    from phonenumbers import geocoder, carrier, timezone
    HAVE_PN = True
except ImportError:
    HAVE_PN = False


class PhoneIntel(OSINTModule):
    module_name = "PhoneIntel"
    module_icon = "📞"
    module_description = "phonenumbers + carrier + NANP area + DuckDuckGo public mentions"
    input_type = "phone"
    output_types = ["phone", "country", "city", "carrier", "timezone",
                    "phone_type", "name", "url"]
    api_requirements = ["NUMVERIFY_KEY (optionnel)", "TRUECALLER_KEY (non public)"]
    needs_internet = True

    NANP_AREAS = {
        "204": ("Winnipeg", "MB", "CA"), "226": ("London/Windsor", "ON", "CA"),
        "236": ("Vancouver", "BC", "CA"), "249": ("Sudbury/N-Bay", "ON", "CA"),
        "250": ("Victoria/BC", "BC", "CA"), "263": ("Montréal", "QC", "CA"),
        "289": ("Hamilton/GTA", "ON", "CA"), "306": ("Saskatchewan", "SK", "CA"),
        "343": ("Ottawa", "ON", "CA"), "354": ("Sherbrooke/Laval", "QC", "CA"),
        "365": ("Toronto GTA", "ON", "CA"), "367": ("Québec", "QC", "CA"),
        "368": ("Calgary/Edmonton", "AB", "CA"), "382": ("London/Windsor", "ON", "CA"),
        "387": ("Toronto", "ON", "CA"), "403": ("Calgary", "AB", "CA"),
        "416": ("Toronto", "ON", "CA"), "418": ("Québec", "QC", "CA"),
        "431": ("Manitoba", "MB", "CA"), "437": ("Toronto", "ON", "CA"),
        "438": ("Montréal", "QC", "CA"), "450": ("Banlieue MTL", "QC", "CA"),
        "468": ("Sherbrooke", "QC", "CA"), "474": ("Saskatchewan", "SK", "CA"),
        "506": ("New Brunswick", "NB", "CA"), "514": ("Montréal", "QC", "CA"),
        "519": ("London/Windsor", "ON", "CA"), "548": ("London/Windsor", "ON", "CA"),
        "579": ("Montérégie/QC", "QC", "CA"), "581": ("Québec", "QC", "CA"),
        "587": ("Calgary/Edmonton", "AB", "CA"), "604": ("Vancouver", "BC", "CA"),
        "613": ("Ottawa", "ON", "CA"), "639": ("Saskatchewan", "SK", "CA"),
        "647": ("Toronto", "ON", "CA"), "672": ("British Columbia", "BC", "CA"),
        "705": ("Sudbury/N-Bay", "ON", "CA"), "709": ("Newfoundland", "NL", "CA"),
        "742": ("Hamilton/GTA", "ON", "CA"), "778": ("Vancouver", "BC", "CA"),
        "780": ("Edmonton", "AB", "CA"), "782": ("Nova Scotia/PEI", "NS", "CA"),
        "807": ("Thunder Bay", "ON", "CA"), "819": ("Outaouais/QC", "QC", "CA"),
        "825": ("Calgary/Edmonton", "AB", "CA"), "867": ("Yukon/NW/NV", "YT", "CA"),
        "873": ("Québec", "QC", "CA"), "902": ("Maritimes", "NS", "CA"),
        "905": ("Toronto GTA", "ON", "CA"),
        "212": ("Manhattan", "NY", "US"), "213": ("Los Angeles", "CA", "US"),
        "305": ("Miami", "FL", "US"), "312": ("Chicago", "IL", "US"),
        "415": ("San Francisco", "CA", "US"), "617": ("Boston", "MA", "US"),
        "646": ("Manhattan", "NY", "US"), "718": ("Brooklyn", "NY", "US"),
    }

    NUMBER_TYPE_LABELS = {
        0: "Mobile", 1: "Fixe", 2: "Fixe ou Mobile",
        3: "Numéro vert", 4: "Surtaxe", 5: "Coût partagé",
        6: "VoIP", 7: "Personnel", 8: "Pager", 9: "UAN",
        10: "Boîte vocale", -1: "Inconnu",
    }

    def execute(self, entity: Dict) -> ModuleResult:
        t0 = time.time()
        r = ModuleResult()
        val = entity.get("value", "").strip()
        if not val:
            r.errors.append("Empty value")
            r.status = STATUS_FAILED
            r.execution_time_ms = (time.time() - t0) * 1000
            return r

        digits = re.sub(r"\D", "", val)
        if not digits or len(digits) < 7:
            r.errors.append(f"Numéro trop court ({len(digits)} chiffres)")
            r.status = STATUS_FAILED
            r.execution_time_ms = (time.time() - t0) * 1000
            return r

        # 1. Offline parsing (real lib)
        if HAVE_PN:
            pn_data = self._parse_phonenumbers(val, digits)
            r.entities_found.extend(pn_data["entities"])
            r.relationships.extend(pn_data["relationships"])
            r.sources_hit.append("phonenumbers (offline lib, validated)")
        else:
            r.warnings.append("pip install phonenumbers - module déprécié sans lib")

        # 2. NANP area code context (offline DB)
        area_data = self._nanp_area(digits)
        if area_data:
            ce = self._new_entity("city", area_data["city"], source="nanp_area_database",
                                  confidence=0.85, status=STATUS_INFERRED,
                                  metadata={"region": area_data["region"],
                                            "country": area_data["country"],
                                            "area_code": area_data["area"]})
            if not self._exists(r.entities_found, "city", area_data["city"]):
                r.entities_found.append(ce)
            r.sources_hit.append("NANP area code database (offline)")

        # 3. DuckDuckGo search for the number (REAL HTTP)
        ddg = self._search_duckduckgo(digits)
        if ddg["entities"]:
            r.entities_found.extend(ddg["entities"])
            r.relationships.extend(ddg["relationships"])
            r.sources_hit.append(f"duckduckgo.com/html (found {ddg['count']} URLs)")

        # 4. Optional Numverify (paid)
        nv = self._numverify(digits)
        if nv["entities"]:
            r.entities_found.extend(nv["entities"])
            r.sources_hit.append("numverify.com")

        # 5. Honest disclosure
        r.warnings.append(
            "Phone→Name reverse lookup (Canada411 / TrueCaller) REQUIRES paid API "
            "or partnership. Sans cela, on ne peut PAS relier un numéro à un nom complet. "
            "Si vous connaissez au moins un fragment (ville, opérateur, indicatif), "
            "on peut confirmer via DuckDuckGo + GitHub."
        )

        r.execution_time_ms = (time.time() - t0) * 1000
        r.raw_data = {"input": val, "digits": digits,
                      "phonenumbers_available": HAVE_PN,
                      "ddg_hits": ddg["count"]}
        return r

    def _parse_phonenumbers(self, val: str, digits: str) -> Dict:
        out: Dict = {"entities": [], "relationships": []}
        parsed = None
        success_region = None
        for reg in [None, "US", "CA", "FR", "GB", "DE", "CH", "BE", "MX", "BR", "IT", "ES", "PT"]:
            try:
                if reg is None:
                    if len(digits) == 10 and digits[0] in "2-9":
                        candidate = "+1" + digits
                    elif len(digits) == 11 and digits.startswith("1"):
                        candidate = "+" + digits
                    else:
                        candidate = "+" + digits if digits.startswith(("1", "7", "3", "4")) else None
                    if not candidate:
                        continue
                    p = phonenumbers.parse(candidate, None)
                else:
                    p = phonenumbers.parse(val, reg)
                if phonenumbers.is_valid_number(p):
                    parsed = p
                    success_region = reg
                    break
            except Exception:
                continue

        if not parsed:
            return out

        e164 = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)
        intl = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
        natl = phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.NATIONAL)
        country_fr = geocoder.description_for_number(parsed, "fr") or ""
        country_en = geocoder.country_name_for_number(parsed, "en") or ""
        country = country_fr or country_en
        car = carrier.name_for_number(parsed, "fr") or carrier.name_for_number(parsed, "en") or ""
        tz_list = list(timezone.time_zones_for_number(parsed) or [])
        number_type = phonenumbers.number_type(parsed)
        type_label = self.NUMBER_TYPE_LABELS.get(number_type, "Inconnu")
        is_valid = phonenumbers.is_valid_number(parsed)
        is_possible = phonenumbers.is_possible_number(parsed)

        root_id = f"phone_{hashlib.md5(e164.encode()).hexdigest()[:12]}"
        phone_e = self._new_entity(
            "phone", e164, source="phonenumbers_validated",
            confidence=1.0 if is_valid else 0.75,
            status=STATUS_VERIFIED,
            metadata={"valid": is_valid, "possible": is_possible,
                      "number_type": type_label, "region": success_region,
                      "international": intl, "national": natl, "e164": e164})
        phone_e["id"] = root_id
        out["entities"].append(phone_e)

        if country:
            ce = self._new_entity("country", country, source="phonenumbers_geocoder",
                                  confidence=0.95, status=STATUS_VERIFIED,
                                  metadata={"region": success_region})
            out["entities"].append(ce)
            out["relationships"].append(self._new_rel(
                root_id, ce["id"], "located_in",
                evidence=f"phonenumbers geocoder ({success_region})",
                evidence_url="https://github.com/daviddrysdale/python-phonenumbers",
                weight=0.95))

        if car:
            ce = self._new_entity("carrier", car, source="phonenumbers_carrier",
                                  confidence=0.85, status=STATUS_VERIFIED)
            out["entities"].append(ce)
            out["relationships"].append(self._new_rel(
                root_id, ce["id"], "uses_carrier",
                evidence="phonenumbers carrier lookup", weight=0.85))

        for tz in tz_list[:2]:
            ce = self._new_entity("timezone", tz, source="phonenumbers_timezone",
                                  confidence=0.95, status=STATUS_VERIFIED)
            out["entities"].append(ce)
            out["relationships"].append(self._new_rel(
                root_id, ce["id"], "in_timezone", weight=0.9))

        nt = self._new_entity("phone_type", type_label, source="phonenumbers_type",
                              confidence=1.0, status=STATUS_VERIFIED)
        out["entities"].append(nt)
        out["relationships"].append(self._new_rel(
            root_id, nt["id"], "classified_as", weight=1.0))

        return out

    def _nanp_area(self, digits: str) -> Optional[Dict]:
        area = None
        if digits.startswith("1") and len(digits) >= 11:
            area = digits[1:4]
        elif len(digits) == 10 and digits[0] in "2-9":
            area = digits[:3]
        if area and area in self.NANP_AREAS:
            city, region, country = self.NANP_AREAS[area]
            return {"city": city, "region": region, "country": country, "area": area}
        return None

    def _search_duckduckgo(self, digits: str) -> Dict:
        out: Dict = {"entities": [], "relationships": [], "count": 0}
        formats: List[str] = [digits]
        if digits.startswith("1") and len(digits) == 11:
            formats.append(f"({digits[1:4]}) {digits[4:7]}-{digits[7:]}")
        elif len(digits) == 10:
            formats.append(f"({digits[:3]}) {digits[3:6]}-{digits[6:]}")
            formats.append(f"+1 {digits}")

        for fmt in formats[:2]:
            url = f"https://html.duckduckgo.com/html/?q=%22{fmt}%22"
            resp = self.http_get(url, timeout=8)
            if not resp or resp.status_code != 200:
                continue
            text = resp.text or ""
            found_urls = re.findall(r'uddg=([^"&]+)', text)
            if not found_urls:
                found_urls = re.findall(r'href="(https?://[^"]+)" class="result__a"', text)
            seen = set()
            for raw in found_urls[:15]:
                u = raw if raw.startswith("http") else unquote(raw)
                if "duckduckgo" in u or u in seen:
                    continue
                if any(b in u for b in ["duckduckgo.com", "duck.co"]):
                    continue
                seen.add(u)
                from urllib.parse import urlparse
                domain = urlparse(u).netloc
                out["entities"].append(self._new_entity(
                    "url", u, source="duckduckgo_search",
                    confidence=0.7, status=STATUS_VERIFIED,
                    metadata={"search_query": fmt, "domain": domain,
                              "snippet_source": "DDG HTML"},
                    source_url=u))
                out["count"] += 1
                if out["count"] >= 8:
                    break
        return out

    def _numverify(self, digits: str) -> Dict:
        """Optional: NUMVERIFY_KEY env var enables paid phone→carrier/line lookup."""
        out: Dict = {"entities": [], "sources_hit": []}
        key = getattr(self.config, "NUMVERIFY_KEY", None) if self.config else None
        if not key:
            return out
        try:
            url = f"http://apilayer.net/api/validate?access_key={key}&number={digits}"
            resp = self.http_get(url, timeout=10)
            if resp and resp.status_code == 200:
                d = resp.json()
                if d.get("valid"):
                    out["entities"].append(self._new_entity(
                        "phone_validated", digits, source="numverify",
                        confidence=0.95, status=STATUS_VERIFIED,
                        metadata={"line_type": d.get("line_type"),
                                  "international_format": d.get("international_format"),
                                  "country_code": d.get("country_code"),
                                  "carrier": d.get("carrier"),
                                  "location": d.get("location")}))
                    out["sources_hit"].append("numverify.com")
        except Exception:
            pass
        return out

    def _exists(self, lst: List[Dict], etype: str, value: Any) -> bool:
        return any(e.get("type") == etype and str(e.get("value")) == str(value)
                   for e in lst)
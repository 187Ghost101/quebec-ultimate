"""IPTracker V3 - REAL IP geolocation + ISP + ASN - Ghost1o1
Sources (NO API KEYS NEEDED):
- ip-api.com (REAL, free, no auth)
- ipapi.co (REAL, free, no auth)
- HackerTarget reverse DNS (free)
- rdap.org (REAL, free, no auth)
- DNS reverse via dnspython

API keys optional:
- Shodan (paid, ~$50/mo)
- IPinfo (paid, free tier)
- MaxMind (paid)
"""
import time, hashlib, json, socket, re
from urllib.parse import quote_plus
from .base import OSINTModule, ModuleResult, STATUS_VERIFIED, STATUS_INFERRED
from typing import Dict, List, Any, Optional

try:
    import dns.resolver as dns_resolver
    import dns.reversename as dns_reversename
    HAVE_DNS = True
except ImportError:
    HAVE_DNS = False


class IPTracker(OSINTModule):
    module_name = "IPTracker"
    module_icon = "🌐"
    module_description = "IP → geo + ISP + ASN + reverse DNS + RDAP + DNS forward"
    input_type = "ip"
    output_types = ["country", "city", "asn", "url", "domain", "company",
                    "timezone", "gps", "isp", "org"]
    api_requirements = []
    needs_internet = True

    IP_RE = re.compile(r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}'
                        r'(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$')

    def execute(self, entity: Dict) -> ModuleResult:
        t0 = time.time()
        r = ModuleResult()
        val = entity.get("value", "").strip()
        if not self.IP_RE.match(val):
            r.errors.append(f"Format IP invalide: {val}")
            r.execution_time_ms = (time.time() - t0) * 1000
            r.status = "failed"; return r

        root_id = f"ip_{hashlib.md5(val.encode()).hexdigest()[:12]}"
        r.entities_found.append(self._new_entity(
            "ip", val, "user_input",
            confidence=1.0, status=STATUS_VERIFIED
        ))
        r.entities_found[-1]["id"] = root_id

        # ─── 1. ip-api.com (REAL, free) ───
        ipapi = self._ipapi_com(val)
        if ipapi.get("hit"):
            self._emit_geo_entities(r, root_id, ipapi["data"], source="ip-api.com")
            r.sources_hit.append("ip-api.com/json")
        else:
            r.warnings.append("ip-api.com: pas de réponse")

        # ─── 2. ipapi.co (REAL, free, fallback + extras) ───
        ipapi2 = self._ipapi_co(val)
        if ipapi2.get("hit"):
            self._emit_geo_entities(r, root_id, ipapi2["data"], source="ipapi.co",
                                    prefix="ipapi2_")
            r.sources_hit.append("ipapi.co/json")

        # ─── 3. Reverse DNS (REAL) ───
        rev = self._reverse_dns(val)
        if rev.get("hostname"):
            de = self._new_entity(
                "domain", rev["hostname"], "dns_reverse",
                confidence=0.95, status=STATUS_VERIFIED,
                metadata={"via": "PTR record"}
            )
            r.entities_found.append(de)
            r.relationships.append(self._new_rel(
                root_id, de["id"], "reverse_dns",
                f"PTR record → {rev['hostname']}", weight=0.95
            ))
            r.sources_hit.append("DNS PTR record")
        elif HAVE_DNS:
            r.warnings.append("Reverse DNS: pas de PTR record")

        # ─── 4. RDAP (REAL, free, no auth) ───
        rdap = self._rdap(val)
        if rdap.get("hit"):
            for k, v in rdap["data"].items():
                if v:
                    e = self._new_entity(
                        "rdap_" + k, str(v)[:100], "rdap_org",
                        confidence=0.95, status=STATUS_VERIFIED,
                        metadata={"source": "rdap.org"}
                    )
                    r.entities_found.append(e)
                    r.relationships.append(self._new_rel(
                        root_id, e["id"], "rdap_info",
                        f"RDAP {k} → {str(v)[:80]}", weight=0.9
                    ))
            r.sources_hit.append("rdap.org")

        # ─── 5. HackerTarget reverse IP → other domains on same IP ───
        ht = self._hackertarget_reverse_ip(val)
        for dom in ht:
            e = self._new_entity(
                "domain", dom, "hackertarget",
                confidence=0.8, status=STATUS_VERIFIED,
                metadata={"via": "shared_hosting"}
            )
            r.entities_found.append(e)
            r.relationships.append(self._new_rel(
                root_id, e["id"], "shared_hosting_with",
                f"Same IP hosts → {dom}", weight=0.7
            ))
        if ht:
            r.sources_hit.append("hackertarget.com/reverseiplookup")

        # ─── 6. Optional Shodan ───
        if self.config and getattr(self.config, "SHODAN_API_KEY", None):
            sh = self._shodan(val)
            for e in sh["entities"]:
                r.entities_found.append(e)
            if sh.get("hit"):
                r.sources_hit.append("shodan.io (paid API)")

        r.execution_time_ms = (time.time() - t0) * 1000
        r.raw_data = {"ip": val, "entities": len(r.entities_found)}
        return r

    def _ipapi_com(self, ip: str) -> Dict:
        try:
            r = self.session.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,country,countryCode,region,regionName,city,zip,"
                                  "lat,lon,timezone,isp,org,as,query,reverse,proxy,hosting,"
                                  "mobile,district"},
                timeout=10
            )
            if r.status_code == 200:
                d = r.json()
                if d.get("status") == "success":
                    return {"hit": True, "data": d}
        except Exception:
            pass
        return {"hit": False}

    def _ipapi_co(self, ip: str) -> Dict:
        try:
            r = self.session.get(f"https://ipapi.co/{ip}/json/", timeout=10)
            if r.status_code == 200:
                d = r.json()
                if not d.get("error"):
                    return {"hit": True, "data": d}
        except Exception:
            pass
        return {"hit": False}

    def _reverse_dns(self, ip: str) -> Dict:
        # Try dnspython first
        if HAVE_DNS:
            try:
                rev_name = dns_reversename.from_address(ip)
                answers = dns_resolver.resolve(rev_name, "PTR")
                hostnames = [str(a.target).rstrip(".") for a in answers]
                if hostnames:
                    return {"hostname": hostnames[0], "all": hostnames}
            except Exception:
                pass
        # socket fallback
        try:
            h = socket.gethostbyaddr(ip)
            return {"hostname": h[0], "all": [h[0]]}
        except Exception:
            return {}

    def _rdap(self, ip: str) -> Dict:
        try:
            r = self.session.get(f"https://rdap.org/ip/{ip}", timeout=10)
            if r.status_code == 200:
                d = r.json()
                return {"hit": True, "data": {
                    "handle": d.get("handle", ""),
                    "name": d.get("name", ""),
                    "country": d.get("country", ""),
                    "start_address": (d.get("startAddress") or ""),
                    "end_address": (d.get("endAddress") or ""),
                }}
        except Exception:
            pass
        return {"hit": False}

    def _hackertarget_reverse_ip(self, ip: str) -> list:
        try:
            r = self.session.get(
                f"https://api.hackertarget.com/reverseiplookup/?q={ip}",
                timeout=12
            )
            if r.status_code == 200:
                lines = [l.strip() for l in r.text.splitlines() if l.strip()
                         and "error" not in l.lower()]
                return lines[:20]
        except Exception:
            pass
        return []

    def _shodan(self, ip: str) -> Dict:
        out = {"entities": [], "hit": False}
        key = getattr(self.config, "SHODAN_API_KEY", None)
        if not key:
            return out
        try:
            r = self.session.get(
                f"https://api.shodan.io/shodan/host/{ip}?key={key}",
                timeout=10
            )
            if r.status_code == 200:
                d = r.json()
                out["hit"] = True
                for port in d.get("ports", []):
                    e = self._new_entity(
                        "port", f"{ip}:{port}", "shodan",
                        confidence=1.0, status=STATUS_VERIFIED,
                        metadata={"port": port, "ip": ip}
                    )
                    out["entities"].append(e)
                for v in d.get("vulns", [])[:5]:
                    e = self._new_entity(
                        "cve", v, "shodan",
                        confidence=0.9, status=STATUS_VERIFIED,
                        metadata={"source": "shodan_vulns"}
                    )
                    out["entities"].append(e)
        except Exception:
            pass
        return out

    def _emit_geo_entities(self, r: ModuleResult, root_id: str,
                            data: Dict, source: str, prefix: str = ""):
        # Country
        if data.get("country"):
            e = self._new_entity(
                "country", data["country"], source,
                confidence=0.95, status=STATUS_VERIFIED,
                metadata={"code": data.get("countryCode") or data.get("country_code")}
            )
            r.entities_found.append(e)
            r.relationships.append(self._new_rel(
                root_id, e["id"], "located_in",
                f"{source} country → {data['country']}", weight=0.95
            ))
        # City
        if data.get("city"):
            e = self._new_entity(
                "city", data["city"], source,
                confidence=0.9, status=STATUS_VERIFIED,
                metadata={"region": data.get("regionName") or data.get("region"),
                          "postal": data.get("zip") or data.get("postal")}
            )
            r.entities_found.append(e)
            r.relationships.append(self._new_rel(
                root_id, e["id"], "located_in",
                f"{source} city → {data['city']}", weight=0.9
            ))
        # ISP / Org
        for fld, etype in [("isp", "isp"), ("org", "company"), ("as", "asn")]:
            v = data.get(fld)
            if v:
                e = self._new_entity(
                    etype, str(v)[:100], source,
                    confidence=0.95, status=STATUS_VERIFIED,
                    metadata={"via": source}
                )
                r.entities_found.append(e)
                r.relationships.append(self._new_rel(
                    root_id, e["id"], f"served_by_{etype}",
                    f"{source} {fld} → {v}", weight=0.95
                ))
        # Timezone
        if data.get("timezone"):
            e = self._new_entity(
                "timezone", data["timezone"], source,
                confidence=0.9, status=STATUS_VERIFIED,
                metadata={"via": source}
            )
            r.entities_found.append(e)
            r.relationships.append(self._new_rel(
                root_id, e["id"], "in_timezone", f"{source} tz → {data['timezone']}",
                weight=0.9
            ))
        # GPS
        lat = data.get("lat")
        lon = data.get("lon") or data.get("longitude")
        if lat is not None and lon is not None:
            try:
                gps_str = f"{float(lat):.6f},{float(lon):.6f}"
                e = self._new_entity(
                    "gps", gps_str, source,
                    confidence=0.9, status=STATUS_VERIFIED,
                    metadata={"lat": float(lat), "lon": float(lon),
                              "source": source}
                )
                r.entities_found.append(e)
                r.relationships.append(self._new_rel(
                    root_id, e["id"], "geolocated_at",
                    f"{source} coords → {gps_str}", weight=0.9
                ))
            except Exception:
                pass
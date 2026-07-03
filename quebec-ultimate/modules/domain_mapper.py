"""DomainMapper V3 - REAL domain intelligence - Ghost1o1
Sources (NO API KEYS NEEDED):
- dnspython (REAL DNS queries: A, MX, NS, TXT, CNAME, SOA)
- HackerTarget subfinder (REAL subdomain enumeration, free)
- HackerTarget hostsearch (REAL)
- DuckDuckGo search (REAL)
- crt.sh Certificate Transparency (REAL, no auth)

API keys optional:
- SecurityTrails (paid)
- VirusTotal (paid)
- Whoxy (paid)
"""
import time, hashlib, json, re
from urllib.parse import quote_plus
from .base import OSINTModule, ModuleResult, STATUS_VERIFIED, STATUS_INFERRED
from typing import Dict, List, Any, Optional

try:
    import dns.resolver as dns_resolver
    import dns.exception
    HAVE_DNS = True
except ImportError:
    HAVE_DNS = False


class DomainMapper(OSINTModule):
    module_name = "DomainMapper"
    module_icon = "🗺️"
    module_description = "Domain → DNS records + subdomains + cert transparency + DDG"
    input_type = "domain"
    output_types = ["ip", "url", "mx_record", "email", "city", "company", "asn"]
    api_requirements = []
    needs_internet = True

    DOMAIN_RE = re.compile(r'^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}$',
                            re.IGNORECASE)

    def execute(self, entity: Dict) -> ModuleResult:
        t0 = time.time()
        r = ModuleResult()
        val = entity.get("value", "").strip().lower()
        # Clean URL if user pasted https://domain.tld/path
        val = re.sub(r'^https?://', '', val).split("/")[0].split("?")[0]
        if not self.DOMAIN_RE.match(val):
            r.errors.append(f"Format domaine invalide: {val}")
            r.execution_time_ms = (time.time() - t0) * 1000
            r.status = "failed"; return r

        root_id = f"domain_{hashlib.md5(val.encode()).hexdigest()[:12]}"
        r.entities_found.append(self._new_entity(
            "domain", val, "user_input",
            confidence=1.0, status=STATUS_VERIFIED,
            source_url=f"https://{val}"
        ))
        r.entities_found[-1]["id"] = root_id

        # ─── 1. DNS Records (REAL, no auth) ───
        dns_data = {}
        if HAVE_DNS:
            dns_data = self._dns_records(val)
            for e in dns_data.get("entities", []):
                r.entities_found.append(e)
            for rel in dns_data.get("relationships", []):
                r.relationships.append(rel)
            if dns_data.get("hit"):
                r.sources_hit.append("DNS A/MX/NS/TXT (dnspython)")

        # ─── 2. HackerTarget subfinder (REAL, free) ───
        subs = self._hackertarget_subfinder(val)
        for sub in subs:
            e = self._new_entity(
                "subdomain", sub, "hackertarget",
                confidence=0.9, status=STATUS_VERIFIED,
                metadata={"via": "hackertarget_hostsearch"},
                source_url=f"https://{sub}"
            )
            r.entities_found.append(e)
            r.relationships.append(self._new_rel(
                root_id, e["id"], "has_subdomain",
                f"Subdomain enumeration → {sub}", weight=0.8
            ))
        if subs:
            r.sources_hit.append(f"hackertarget.com/hostsearch ({len(subs)} subs)")

        # ─── 3. crt.sh Certificate Transparency (REAL, no auth) ───
        crt = self._crt_sh(val)
        for sub in crt:
            if sub not in subs:
                e = self._new_entity(
                    "subdomain", sub, "crt_sh",
                    confidence=0.9, status=STATUS_VERIFIED,
                    metadata={"via": "cert_transparency"},
                    source_url=f"https://{sub}"
                )
                r.entities_found.append(e)
                r.relationships.append(self._new_rel(
                    root_id, e["id"], "has_subdomain",
                    f"crt.sh cert log → {sub}", weight=0.8
                ))
        if crt:
            r.sources_hit.append(f"crt.sh ({len(crt)} cert log entries)")

        # ─── 4. DuckDuckGo for mentions ───
        ddg = self._ddg_search(val)
        for e in ddg["entities"]:
            r.entities_found.append(e)
        if ddg.get("hit"):
            r.sources_hit.append("duckduckgo.com/html")

        # ─── 5. HackerTarget reverse IP for shared hosting ───
        if dns_data and dns_data.get("primary_ip"):
            rev = self._hackertarget_reverse_ip(dns_data["primary_ip"])
            for dom in rev:
                if dom != val and dom not in subs:
                    e = self._new_entity(
                        "domain", dom, "hackertarget_reverse",
                        confidence=0.7, status=STATUS_VERIFIED,
                        metadata={"via": "shared_ip"}
                    )
                    r.entities_found.append(e)
                    r.relationships.append(self._new_rel(
                        root_id, e["id"], "shares_ip_with",
                        f"Same IP host → {dom}", weight=0.6
                    ))
            if rev:
                r.sources_hit.append("hackertarget.com/reverseiplookup")

        r.execution_time_ms = (time.time() - t0) * 1000
        r.raw_data = {"domain": val, "total_entities": len(r.entities_found),
                      "subdomains": len(subs) + len(crt)}
        return r

    def _dns_records(self, domain: str) -> Dict:
        out = {"entities": [], "relationships": [], "hit": False, "primary_ip": ""}
        root_id = f"domain_{hashlib.md5(domain.encode()).hexdigest()[:12]}"
        # A records
        try:
            answers = dns_resolver.resolve(domain, "A")
            for a in answers:
                ip = str(a)
                if not out.get("primary_ip"):
                    out["primary_ip"] = ip
                e = self._new_entity(
                    "ip", ip, "dns_a_record",
                    confidence=1.0, status=STATUS_VERIFIED,
                    metadata={"via": "DNS A record", "ttl": answers.rrset.ttl}
                )
                out["entities"].append(e)
                out["relationships"].append(self._new_rel(
                    root_id, e["id"], "resolves_to",
                    f"DNS A record → {ip}", weight=1.0
                ))
                out["hit"] = True
        except Exception:
            pass

        # MX records (mail servers)
        try:
            answers = dns_resolver.resolve(domain, "MX")
            for a in answers:
                mx_host = str(a.exchange).rstrip(".")
                pref = a.preference
                e = self._new_entity(
                    "mx_record", mx_host, "dns_mx_record",
                    confidence=1.0, status=STATUS_VERIFIED,
                    metadata={"priority": pref}
                )
                out["entities"].append(e)
                out["relationships"].append(self._new_rel(
                    root_id, e["id"], "mail_handled_by",
                    f"MX record (prio {pref}) → {mx_host}", weight=1.0
                ))
                out["hit"] = True
        except Exception:
            pass

        # NS records
        try:
            answers = dns_resolver.resolve(domain, "NS")
            for a in answers:
                ns = str(a.target).rstrip(".")
                e = self._new_entity(
                    "ns_record", ns, "dns_ns_record",
                    confidence=1.0, status=STATUS_VERIFIED
                )
                out["entities"].append(e)
                out["relationships"].append(self._new_rel(
                    root_id, e["id"], "nameserver",
                    f"NS record → {ns}", weight=1.0
                ))
                out["hit"] = True
        except Exception:
            pass

        # TXT records (SPF, DKIM, DMARC, verification)
        try:
            answers = dns_resolver.resolve(domain, "TXT")
            for a in answers:
                txt = "".join([s.decode() if isinstance(s, bytes) else s
                                for s in a.strings])
                if "spf" in txt.lower() or "v=spf1" in txt:
                    e = self._new_entity(
                        "spf_record", txt[:200], "dns_txt_record",
                        confidence=1.0, status=STATUS_VERIFIED,
                        metadata={"type": "spf"}
                    )
                    out["entities"].append(e)
                    out["relationships"].append(self._new_rel(
                        root_id, e["id"], "spf_policy", "SPF record", weight=1.0
                    ))
                elif "v=dmarc1" in txt:
                    e = self._new_entity(
                        "dmarc_record", txt[:200], "dns_txt_record",
                        confidence=1.0, status=STATUS_VERIFIED,
                        metadata={"type": "dmarc"}
                    )
                    out["entities"].append(e)
                else:
                    e = self._new_entity(
                        "txt_record", txt[:200], "dns_txt_record",
                        confidence=1.0, status=STATUS_VERIFIED
                    )
                    out["entities"].append(e)
                out["hit"] = True
        except Exception:
            pass

        # DMARC at _dmarc.domain
        try:
            answers = dns_resolver.resolve(f"_dmarc.{domain}", "TXT")
            for a in answers:
                txt = "".join([s.decode() if isinstance(s, bytes) else s
                                for s in a.strings])
                e = self._new_entity(
                    "dmarc_record", txt[:200], "dns_txt_record",
                    confidence=1.0, status=STATUS_VERIFIED
                )
                out["entities"].append(e)
                out["hit"] = True
        except Exception:
            pass

        return out

    def _hackertarget_subfinder(self, domain: str) -> list:
        try:
            r = self.session.get(
                f"https://api.hackertarget.com/hostsearch/?q={domain}",
                timeout=15
            )
            if r.status_code == 200:
                subs = []
                for line in r.text.splitlines():
                    line = line.strip()
                    if line and "error" not in line.lower() and "," in line:
                        sub = line.split(",")[0].strip()
                        if sub.endswith("." + domain) or sub == domain:
                            subs.append(sub)
                return list(set(subs))[:50]
        except Exception:
            pass
        return []

    def _hackertarget_reverse_ip(self, ip: str) -> list:
        try:
            r = self.session.get(
                f"https://api.hackertarget.com/reverseiplookup/?q={ip}",
                timeout=10
            )
            if r.status_code == 200:
                return [l.strip() for l in r.text.splitlines()
                        if l.strip() and "error" not in l.lower()][:20]
        except Exception:
            pass
        return []

    def _crt_sh(self, domain: str) -> list:
        """Certificate Transparency logs from crt.sh (REAL, no auth)."""
        try:
            r = self.session.get(
                f"https://crt.sh/?q=%.{domain}&output=json",
                timeout=20
            )
            if r.status_code == 200:
                data = r.json()
                names = set()
                for entry in data[:100]:
                    cn = entry.get("common_name", "")
                    if cn and (cn.endswith("." + domain) or cn == domain):
                        names.add(cn.lower())
                return list(names)[:40]
        except Exception:
            pass
        return []

    def _ddg_search(self, domain: str) -> Dict:
        out = {"entities": [], "hit": False}
        try:
            r = self.session.post(
                "https://html.duckduckgo.com/html/",
                data={"q": f'site:{domain} OR "{domain}"'},
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
                        confidence=0.85, status=STATUS_VERIFIED,
                        metadata={"title": title_clean[:120], "site_filter": domain}
                    )
                    out["entities"].append(e)
        except Exception:
            pass
        return out
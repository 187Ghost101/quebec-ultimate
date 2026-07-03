"""OSIN CHAIN QUEBEC ULTIMATE - Module Base - Ghost1o1"""
import time, hashlib, json
import requests
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone

STATUS_VERIFIED = "verified"
STATUS_INFERRED = "inferred"
STATUS_PATTERNGUESS = "pattern"
STATUS_FAILED = "failed"
STATUS_API_REQUIRED = "api_required"


@dataclass
class ModuleResult:
    status: str = STATUS_VERIFIED
    entities_found: List[Dict] = field(default_factory=list)
    relationships: List[Dict] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    execution_time_ms: float = 0.0
    raw_data: Dict = field(default_factory=dict)
    sources_hit: List[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


class OSINTModule(ABC):
    module_name = "Base"
    module_icon = "?"
    module_description = "Base module"
    input_type = "generic"
    output_types: List[str] = []
    api_requirements: List[str] = []
    is_passive: bool = True
    needs_internet: bool = True

    def __init__(self, config=None, rate_limiter=None, timeout: int = 12):
        self.config = config
        self.rate_limiter = rate_limiter
        self.timeout = timeout
        self._last_error = None
        self.session = self._build_session()

    def _build_session(self):
        import requests as r
        s = r.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 "
                          "OSIN-CHAIN-QUEBEC-ULTIMATE/3.0",
            "Accept": "application/json, text/html;q=0.9, */*;q=0.8",
            "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
        })
        return s

    @abstractmethod
    def execute(self, entity: Dict) -> ModuleResult:
        raise NotImplementedError

    def http_get(self, url, timeout=None, params=None, headers=None,
                 allow_redirects=True):
        try:
            t = timeout or self.timeout
            h = dict(self.session.headers)
            if headers:
                h.update(headers)
            return self.session.get(url, params=params, headers=h, timeout=t,
                                    allow_redirects=allow_redirects)
        except Exception as e:
            self._last_error = str(e)
            return None

    def http_head(self, url, timeout=None, allow_redirects=True):
        try:
            t = timeout or self.timeout
            r = self.session.head(url, headers=dict(self.session.headers),
                                  timeout=t, allow_redirects=allow_redirects)
            return r.status_code
        except Exception as e:
            self._last_error = str(e)
            return None

    def http_post(self, url, data=None, json_body=None, headers=None,
                  timeout=None):
        try:
            t = timeout or self.timeout
            h = dict(self.session.headers)
            if headers:
                h.update(headers)
            return self.session.post(url, data=data, json=json_body,
                                     headers=h, timeout=t)
        except Exception as e:
            self._last_error = str(e)
            return None

    def _new_entity(self, etype, value, source, confidence=0.85,
                    status=STATUS_VERIFIED, metadata=None, source_url=""):
        eid = f"{etype}_{hashlib.md5(str(value).encode()).hexdigest()[:12]}"
        return {
            "id": eid,
            "type": etype,
            "value": str(value),
            "source": source,
            "source_url": source_url,
            "confidence": float(confidence),
            "status": status,
            "metadata": metadata or {},
            "discovered_by": self.module_name,
            "discovered_at": datetime.now(timezone.utc).isoformat(),
        }

    def _new_rel(self, src, tgt, rtype, evidence="", weight=1.0,
                 evidence_url=""):
        return {
            "source": src, "target": tgt, "type": rtype,
            "evidence": evidence, "evidence_url": evidence_url,
            "weight": weight,
        }

    def gravatar_hash(self, email):
        return hashlib.md5(email.strip().lower().encode()).hexdigest()

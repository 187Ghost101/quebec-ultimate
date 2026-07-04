"""Input dispatcher - auto-detect + pipeline mapping"""
import re, uuid
from enum import Enum
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Tuple, Optional


class EntityType(str, Enum):
    PHONE = "phone"; EMAIL = "email"; USERNAME = "username"; DOMAIN = "domain"
    IP = "ip"; NAME = "name"; IMAGE = "image"; DOCUMENT = "document"
    GPS = "gps"; ADDRESS = "address"; URL = "url"; HASH = "hash"
    COMPANY = "company"; UNKNOWN = "unknown"


P = {
    EntityType.EMAIL: re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    EntityType.IP: re.compile(r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b'),
    EntityType.URL: re.compile(r'https?://[^\s]+'),
    EntityType.PHONE: re.compile(r'(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}'),
    EntityType.GPS: re.compile(r'[-+]?\d{1,2}\.\d{4,}\s*,\s*[-+]?\d{1,3}\.\d{4,}'),
    EntityType.HASH: re.compile(r'\b[a-fA-F0-9]{32,64}\b'),
    EntityType.DOMAIN: re.compile(r'\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,}\b'),
}


@dataclass
class Entity:
    id: str
    type: EntityType
    value: str
    metadata: Dict = field(default_factory=dict)
    confidence: float = 1.0

    def to_dict(self):
        d = asdict(self); d["type"] = self.type.value; return d


class InputDispatcher:
    """When user gives X → what modules to run first."""
    # ALL 12 modules available per type for full cascade
    pipeline_map: Dict = {
        EntityType.PHONE: [1, 8, 11, 9, 7, 13],
        EntityType.EMAIL: [3, 4, 9, 12, 8, 11, 13],
        EntityType.USERNAME: [4, 8, 13, 9, 7, 3, 1],
        EntityType.DOMAIN: [5, 6, 9, 4, 11, 8, 13],
        EntityType.IP: [6, 11, 5, 1, 7],
        EntityType.NAME: [7, 4, 8, 13, 3, 11],
        EntityType.IMAGE: [2, 14, 12, 11, 9, 13],
        EntityType.DOCUMENT: [12, 9, 3, 4],
        EntityType.GPS: [11, 8, 7],
        EntityType.ADDRESS: [11, 7, 8],
        EntityType.URL: [5, 13, 4, 9, 11, 8],
        EntityType.HASH: [9, 12, 4],
        EntityType.COMPANY: [7, 5, 3, 8, 11, 13],
        EntityType.UNKNOWN: [7, 9, 4, 8, 5, 13],
    }

    # When we DISCOVER an entity of type X → what modules to cascade
    # Comprehensive map - covers ALL entity types modules can produce
    discovered_pipeline_map: Dict = {
        "username": [4, 8, 9, 7, 3, 1],
        "email": [3, 4, 9, 12, 8, 11],
        "phone": [1, 8, 11, 9, 7],
        "domain": [5, 6, 9, 4, 11, 8],
        "subdomain": [5, 6, 4, 9, 11],
        "ip": [6, 11, 5, 1, 7],
        "name": [7, 4, 8, 3, 11],
        "url": [5, 4, 9, 11, 8],
        "social_profile": [13, 8, 4, 7, 11, 9],
        "github_profile": [13, 4, 8, 7, 11, 9, 3],
        "image": [14, 2, 12, 11, 9, 13],
        "image_url": [14, 2, 12, 11, 9, 13],
        "avatar": [14, 13, 2, 4],
        "repository": [4, 8, 9, 7],
        "carrier": [7, 11, 8],
        "isp": [7, 11, 6],
        "asn": [6, 11, 7],
        "city": [11, 7, 8],
        "country": [11, 7],
        "company": [7, 5, 3, 8, 11],
        "mx_record": [5, 3, 11],
        "ns_record": [5, 11],
        "spf_record": [5],
        "txt_record": [5, 7],
        "phone_type": [1, 8, 11],
        "timezone": [11, 7],
        "rdap_handle": [7, 11],
        "rdap_name": [7, 8],
        "hash": [9, 12, 4],
        "camera": [4, 7],
        "face_cluster": [4, 8, 7],
        "geo": [11, 8],
        "exif_gps": [11, 8],
        "alias": [7, 4, 8],
        "credential": [9, 4, 3],
        "breach": [9, 4, 3],
        "leak": [9, 4, 3],
        "paste": [9, 4],
        "document": [12, 9, 4, 3],
        "file": [12, 9, 4],
        "bitcoin_address": [9, 7, 4],
        "ethereum_address": [9, 7, 4],
        "darkweb_url": [10, 9, 4, 7],
        "forum_post": [10, 4, 7],
        "market": [10, 7],
        "tor_relay": [10, 6],
        "gps": [11, 7, 8],
        "address": [11, 7, 8],
        "ocr_text": [12, 4, 7],
        "metadata": [12, 7],
    }

    def detect_type(self, value: str) -> Tuple[EntityType, float]:
        v = value.strip()
        if not v:
            return EntityType.UNKNOWN, 0.0
        scores: Dict = {}
        if P[EntityType.EMAIL].match(v): scores[EntityType.EMAIL] = 1.0
        if P[EntityType.IP].match(v): scores[EntityType.IP] = 1.0
        if P[EntityType.GPS].match(v): scores[EntityType.GPS] = 1.0
        if P[EntityType.URL].match(v): scores[EntityType.URL] = 0.95
        if P[EntityType.HASH].match(v): scores[EntityType.HASH] = 0.9
        if P[EntityType.PHONE].search(v): scores[EntityType.PHONE] = 0.85
        if P[EntityType.DOMAIN].match(v): scores[EntityType.DOMAIN] = 0.8
        if re.match(r'^[a-zA-Z0-9_.\-]{3,30}$', v) and ' ' not in v and '@' not in v and '.' not in v:
            scores[EntityType.USERNAME] = 0.6
        if re.match(r'^[A-Z][a-zéèêàîôûç-]+(?:\s[A-Z][a-zéèêàîôûç-]+){1,3}$', v):
            scores[EntityType.NAME] = 0.7
        if re.search(r'\.(jpg|jpeg|png|gif|webp|bmp)$', v, re.I):
            scores[EntityType.IMAGE] = 0.9
        if re.search(r'\.(pdf|docx?|xlsx?|txt)$', v, re.I):
            scores[EntityType.DOCUMENT] = 0.9
        if not scores:
            return EntityType.UNKNOWN, 0.0
        return max(scores.items(), key=lambda x: x[1])

    def create_root_entity(self, value: str, etype: EntityType,
                           metadata: Optional[Dict] = None) -> Entity:
        return Entity(id=f"{etype.value}_{uuid.uuid4().hex[:10]}",
                      type=etype, value=value.strip(),
                      metadata=metadata or {}, confidence=1.0)

    def get_module_pipeline(self, etype: EntityType) -> List[int]:
        return self.pipeline_map.get(etype, [7, 9, 4])

    def get_modules_for_discovered_type(self, entity_type_str: str) -> List[int]:
        return self.discovered_pipeline_map.get(entity_type_str, [])

    def get_entity_by_id(self, entity_id: str, graph_manager) -> Optional[Dict]:
        return graph_manager.get_entity(entity_id)

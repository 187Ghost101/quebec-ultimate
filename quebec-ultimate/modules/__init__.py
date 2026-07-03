"""OSIN CHAIN QUEBEC ULTIMATE — Module Registry - Ghost1o1"""
from typing import Dict, Type, Any
from .base import OSINTModule, ModuleResult
from config import config

# ─── Module imports ───
from .phone_intel import PhoneIntel
from .image_deepscan import ImageDeepScan
from .email_tracer import EmailTracer
from .username_sherlock import UsernameSherlock
from .domain_mapper import DomainMapper
from .ip_tracker import IPTracker
from .name_resolver import NameResolver
from .social_graph import SocialGraph
from .breach_hunter import BreachHunter
from .darkweb_scout import DarkWebScout
from .geoloc_intel import GeoLocIntel
from .doc_analyzer import DocAnalyzer
from .content_miner import ContentMiner
from .face_match import FaceMatch

# ─── Module Registry ───
MODULE_REGISTRY: Dict[int, Type[OSINTModule]] = {
    1: PhoneIntel,
    2: ImageDeepScan,
    3: EmailTracer,
    4: UsernameSherlock,
    5: DomainMapper,
    6: IPTracker,
    7: NameResolver,
    8: SocialGraph,
    9: BreachHunter,
    10: DarkWebScout,
    11: GeoLocIntel,
    12: DocAnalyzer,
    13: ContentMiner,
    14: FaceMatch,
}

_module_instances: Dict[int, OSINTModule] = {}


def get_module_instance(module_id: int, config_obj: Any = None,
                        rate_limiter: Any = None) -> OSINTModule:
    if module_id not in MODULE_REGISTRY:
        raise ValueError(f"Module {module_id} invalide. Valides: {list(MODULE_REGISTRY.keys())}")
    if module_id in _module_instances and config_obj is None and rate_limiter is None:
        return _module_instances[module_id]
    cls = MODULE_REGISTRY[module_id]
    inst = cls(config=config_obj or config, rate_limiter=rate_limiter)
    if config_obj is None and rate_limiter is None:
        _module_instances[module_id] = inst
    return inst


def get_modules_for_input_type(input_type: str) -> Dict[int, Type[OSINTModule]]:
    return {mid: cls for mid, cls in MODULE_REGISTRY.items()
            if cls.input_type == input_type}


def get_modules_producing_output(output_type: str) -> Dict[int, Type[OSINTModule]]:
    return {mid: cls for mid, cls in MODULE_REGISTRY.items()
            if output_type in cls.output_types}


def list_all_modules() -> list:
    return [
        {"id": mid, "name": cls.module_name, "icon": cls.module_icon,
         "description": cls.module_description, "input_type": cls.input_type,
         "output_types": cls.output_types,
         "api_requirements": cls.api_requirements,
         "is_passive": cls.is_passive,
         "needs_internet": cls.needs_internet}
        for mid, cls in MODULE_REGISTRY.items()
    ]


__all__ = [
    "OSINTModule", "ModuleResult", "MODULE_REGISTRY",
    "get_module_instance", "get_modules_for_input_type",
    "list_all_modules",
    "PhoneIntel", "ImageDeepScan", "EmailTracer", "UsernameSherlock",
    "DomainMapper", "IPTracker", "NameResolver", "SocialGraph",
    "BreachHunter", "DarkWebScout", "GeoLocIntel", "DocAnalyzer",
    "ContentMiner", "FaceMatch",
]
"""OSIN CHAIN QUEBEC ULTIMATE - Sync task executor - Ghost1o1"""
import logging
from typing import Dict, Any

logger = logging.getLogger("osin_chain")


def execute_module_sync(module_id: int, entity: Dict, rate_limiter=None) -> Dict:
    """
    Synchronous module execution. Used by ChainEngine in thread executor.
    Returns full ModuleResult dict.
    """
    from modules import get_module_instance
    try:
        if rate_limiter:
            rate_limiter.check(f"module_{module_id}")
        module = get_module_instance(module_id, rate_limiter=rate_limiter)
        result = module.execute(entity)
        return {
            "module_id": module_id,
            "module_name": module.module_name,
            "status": result.status,
            "entities_found": result.entities_found,
            "relationships": result.relationships,
            "warnings": result.warnings,
            "errors": result.errors,
            "raw_data": result.raw_data,
            "sources_hit": result.sources_hit,
            "execution_time_ms": result.execution_time_ms,
        }
    except Exception as ex:
        logger.error(f"Module {module_id} error: {ex}", exc_info=True)
        return {
            "module_id": module_id,
            "module_name": f"Module {module_id}",
            "status": "failed",
            "entities_found": [],
            "relationships": [],
            "warnings": [],
            "errors": [str(ex)],
            "raw_data": {},
            "sources_hit": [],
            "execution_time_ms": 0,
        }
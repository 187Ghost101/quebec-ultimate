"""OSIN CHAIN QUEBEC ULTIMATE — Chain Engine V3
Recursive cascade with WS broadcasts, graph persistence, footprint + geo hooks.
"""
import asyncio
import time
from typing import Dict, List, Set, Tuple, Optional, Any
from collections import deque
from dataclasses import dataclass, field

from modules import get_module_instance
from core.dispatcher import InputDispatcher, EntityType
from core.logger import logger


@dataclass
class ChainStep:
    depth: int = 0
    entity_type: str = ""
    entity_value: str = ""
    module_id: int = 0
    module_name: str = ""
    status: str = "pending"
    entities_found: int = 0
    rels_found: int = 0
    execution_time_ms: float = 0.0
    errors: List[str] = field(default_factory=list)
    discovered_entities: List[Dict] = field(default_factory=list)
    relationships: List[Dict] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)


class ChainEngine:
    def __init__(self, max_depth: int = 3, max_entities: int = 800,
                 max_modules_per_type: int = 8,
                 ws_broadcast=None, graph_manager=None, rate_limiter=None,
                 footprint_tracker=None, geo_manager=None,
                 snapshot_pacing_seconds: float = 0.0):
        self.max_depth = max_depth
        self.max_entities = max_entities
        self.max_modules_per_type = max_modules_per_type
        self.visited_values: Set[str] = set()
        self.visited_pairs: Set[Tuple[int, str]] = set()
        self.steps: List[ChainStep] = []
        self.dispatcher = InputDispatcher()
        self.ws_broadcast = ws_broadcast
        self.graph_manager = graph_manager
        self.rate_limiter = rate_limiter
        self.footprint_tracker = footprint_tracker
        self.geo_manager = geo_manager
        self.snapshot_pacing_seconds = float(snapshot_pacing_seconds or 0.0)
        self.total_entities = 0
        self.total_relationships = 0
        self.depth_reached = 0

    def _vk(self, etype: str, value: str) -> str:
        return f"{etype}:{str(value).lower().strip()}"

    def _should_trigger(self, etype: str, value: str, mid: int) -> bool:
        vk = self._vk(etype, value)
        if (mid, vk) in self.visited_pairs:
            return False
        if self.total_entities >= self.max_entities:
            return False
        return True

    async def run(self, root_entity: Dict, initial_modules: List[int],
                  session_id: str = "") -> Dict:
        queue = deque()
        queue.append((0, root_entity, initial_modules))

        while queue and self.total_entities < self.max_entities:
            depth, entity, modules = queue.popleft()
            if depth > self.max_depth:
                continue
            if not modules:
                continue
            etype = entity.get("type", "unknown")
            evalue = str(entity.get("value", "")).strip()
            if not evalue:
                continue

            for mid in modules[:self.max_modules_per_type]:
                if not self._should_trigger(etype, evalue, mid):
                    continue
                self.visited_pairs.add((mid, self._vk(etype, evalue)))

                if self.rate_limiter and not self.rate_limiter.check(f"chain_m{mid}"):
                    await asyncio.sleep(0.3)

                step = await self._execute_module(mid, entity, depth, session_id)
                self.steps.append(step)
                self.depth_reached = max(self.depth_reached, depth)
                self.visited_values.add(self._vk(etype, evalue))

                # Pacing: spread snapshots in time so the timeline shows real progression
                if self.snapshot_pacing_seconds > 0:
                    await asyncio.sleep(self.snapshot_pacing_seconds)

                # ─── FOOTPRINT SNAPSHOT after each module ───
                if self.footprint_tracker and self.graph_manager:
                    try:
                        self.footprint_tracker.record_change(
                            session_id, self.graph_manager,
                            trigger=f"module_{mid}_{etype}",
                            extra_metadata={
                                "module_id": mid,
                                "module_name": step.module_name,
                                "trigger_entity": evalue[:60],
                                "entities_added": step.entities_found,
                                "depth": depth,
                            },
                        )
                    except Exception as ex:
                        logger.warning(f"[Chain] footprint: {ex}")

                # CASCADE: propagate to discovered entities
                if step.status == "success" and step.discovered_entities:
                    for child in step.discovered_entities[:25]:
                        try:
                            child_vk = self._vk(child["type"], child["value"])
                            if child_vk in self.visited_values:
                                continue
                            child_modules = self.dispatcher.get_modules_for_discovered_type(
                                child["type"])
                            if child_modules:
                                queue.append((depth + 1, child, child_modules))
                                # mark value as visited only AFTER queueing to avoid blocking
                                self.visited_values.add(child_vk)
                        except Exception as e:
                            logger.warning(f"[Chain] Cascade skip: {e}")

        # Final snapshot
        if self.footprint_tracker and self.graph_manager:
            try:
                self.footprint_tracker.record_change(
                    session_id, self.graph_manager,
                    trigger="chain_complete",
                    extra_metadata={
                        "total_entities": self.total_entities,
                        "total_relationships": self.total_relationships,
                        "depth_reached": self.depth_reached,
                    },
                )
            except Exception:
                pass

        if self.ws_broadcast:
            try:
                await self.ws_broadcast(session_id, {
                    "event": "chain_complete",
                    "session_id": session_id,
                    "total_entities": self.total_entities,
                    "total_relationships": self.total_relationships,
                    "depth_reached": self.depth_reached,
                })
            except Exception:
                pass

        return {
            "steps": [s.__dict__ for s in self.steps],
            "total_entities": self.total_entities,
            "total_relationships": self.total_relationships,
            "depth_reached": self.depth_reached,
        }

    async def _execute_module(self, module_id: int, entity: Dict,
                              depth: int, session_id: str) -> ChainStep:
        step = ChainStep(
            depth=depth,
            entity_type=entity.get("type", "unknown"),
            entity_value=entity.get("value", ""),
            module_id=module_id,
            module_name="",
            status="pending",
        )
        try:
            module = get_module_instance(module_id, rate_limiter=self.rate_limiter)
            step.module_name = module.module_name

            if self.ws_broadcast:
                try:
                    await self.ws_broadcast(session_id, {
                        "event": "module_started",
                        "module_id": module_id,
                        "module_name": module.module_name,
                        "entity": {"type": entity["type"], "value": entity["value"]},
                        "depth": depth,
                    })
                except Exception:
                    pass

            loop = asyncio.get_event_loop()
            t0 = time.time()
            result = await loop.run_in_executor(None, module.execute, entity)
            step.execution_time_ms = (time.time() - t0) * 1000

            if result.status == "failed":
                step.status = "failed"
                step.errors = result.errors
                if self.ws_broadcast:
                    try:
                        await self.ws_broadcast(session_id, {
                            "event": "module_failed",
                            "module_id": module_id,
                            "errors": result.errors,
                        })
                    except Exception:
                        pass
                return step

            step.status = "success"
            step.entities_found = len(result.entities_found)
            step.rels_found = len(result.relationships)

            # Enrich each entity with geo BEFORE saving
            entities_found = list(result.entities_found)
            if self.geo_manager:
                for ent in entities_found:
                    try:
                        self.geo_manager.enrich_entity(ent)
                    except Exception:
                        pass

            step.discovered_entities = entities_found
            step.relationships = list(result.relationships)
            step.sources = list(result.sources_hit)

            # Save to graph
            if self.graph_manager:
                for ent in entities_found:
                    try:
                        self.graph_manager.create_entity(
                            entity_id=ent["id"],
                            entity_type=ent["type"],
                            value=ent["value"],
                            source=ent.get("source", f"module_{module_id}"),
                            confidence=ent.get("confidence", 0.8),
                            metadata={**ent.get("metadata", {}),
                                      "source_url": ent.get("source_url", ""),
                                      "status": ent.get("status", "verified"),
                                      "discovered_by": ent.get("discovered_by", module.module_name),
                                      "session": session_id, "depth": depth + 1},
                        )
                    except Exception as e:
                        logger.warning(f"[Chain] entity: {e}")
                self.total_entities += len(entities_found)
                for rel in result.relationships:
                    try:
                        self.graph_manager.create_relationship(
                            source_id=rel["source"],
                            target_id=rel["target"],
                            rel_type=rel["type"],
                            weight=rel.get("weight", 1.0),
                            evidence=rel.get("evidence", ""),
                        )
                        self.total_relationships += 1
                    except Exception as e:
                        logger.warning(f"[Chain] rel: {e}")

            if self.ws_broadcast:
                try:
                    await self.ws_broadcast(session_id, {
                        "event": "entity_discovered",
                        "entity": entities_found[0] if entities_found else {},
                        "all_entities": entities_found[:5],
                        "module_name": step.module_name,
                        "module_id": module_id,
                        "depth": depth,
                    })
                except Exception:
                    pass
                try:
                    await self.ws_broadcast(session_id, {
                        "event": "chain_step_done",
                        "depth": depth,
                        "module_id": module_id,
                        "module_name": step.module_name,
                        "entities_added": len(entities_found),
                        "total_entities": self.total_entities,
                    })
                except Exception:
                    pass

        except Exception as e:
            step.status = "failed"
            step.errors = [str(e)]
            logger.error(f"[Chain] Module {module_id} error: {e}")

        return step
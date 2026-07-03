"""OSIN CHAIN QUEBEC ULTIMATE — API Routes - Ghost1o1
FastAPI routes with footprint + movement + geo endpoints.
"""
import multiprocessing
import time
try:
    import python_multipart
except ImportError:
    pass  # FastAPI checks at runtime

from fastapi import APIRouter, HTTPException, BackgroundTasks, Request, UploadFile, File
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, Field
from typing import Dict, Optional
import uuid
import os
import shutil
import base64
import asyncio
import sys


class SearchRequest(BaseModel):
    input_value: str = Field(..., min_length=1, max_length=500)
    session_id: Optional[str] = None
    max_depth: int = Field(default=3, ge=1, le=5)
    auto_cascade: bool = True
    snapshot_pacing_seconds: float = Field(default=0.0, ge=0.0, le=10.0,
                                          description="Wait between modules (timeline pacing)")


class ExportRequest(BaseModel):
    entity_id: Optional[str] = None
    session_id: Optional[str] = None
    format: str = Field(default="json", pattern="^(json|pdf|png)$")
    include_footprint: bool = True


def create_router(app, dispatcher, graph_manager, correlation_engine,
                  rate_limiter, ws_manager=None,
                  footprint_tracker=None, geo_manager=None):
    router = APIRouter(prefix="/api/v1", tags=["OSINT"])

    @router.post("/search")
    async def search(request: SearchRequest, background_tasks: BackgroundTasks, req: Request):
        client_ip = req.client.host if req and req.client else "unknown"
        if not rate_limiter.check(client_ip):
            raise HTTPException(status_code=429, detail="Rate limit atteint")
        session_id = request.session_id or uuid.uuid4().hex[:12]
        entity_type, confidence = dispatcher.detect_type(request.input_value)
        root_entity = dispatcher.create_root_entity(request.input_value, entity_type)
        root_entity.metadata["session"] = session_id

        # Enrich root with geo if possible
        if geo_manager:
            geo_manager.enrich_entity({
                "id": root_entity.id, "type": root_entity.type.value,
                "value": root_entity.value, "metadata": root_entity.metadata,
            })

        if graph_manager.connected:
            graph_manager.create_entity(
                entity_id=root_entity.id,
                entity_type=root_entity.type.value,
                value=root_entity.value,
                source="user_input",
                confidence=confidence,
                metadata={
                    "root": True, "session": session_id,
                    "lat": root_entity.metadata.get("lat"),
                    "lon": root_entity.metadata.get("lon"),
                    "geo_source": root_entity.metadata.get("geo_source"),
                },
            )

        if footprint_tracker:
            footprint_tracker.record_change(session_id, graph_manager,
                                            trigger="search_start",
                                            extra_metadata={"input": request.input_value,
                                                            "type": entity_type.value})

        pipeline = dispatcher.get_module_pipeline(entity_type)
        if request.auto_cascade and pipeline:
            background_tasks.add_task(
                _run_chain, pipeline, root_entity, session_id, request.max_depth,
                graph_manager, correlation_engine, rate_limiter,
                ws_manager, footprint_tracker, geo_manager,
                request.snapshot_pacing_seconds,
            )

        neighborhood = {}
        if graph_manager.connected:
            neighborhood = graph_manager.get_neighborhood(root_entity.id)

        return {
            "status": "processing",
            "session_id": session_id,
            "root_entity": {
                "id": root_entity.id, "type": entity_type.value,
                "value": request.input_value, "confidence": confidence,
                "geo": {
                    "lat": root_entity.metadata.get("lat"),
                    "lon": root_entity.metadata.get("lon"),
                    "source": root_entity.metadata.get("geo_source"),
                },
            },
            "detected_type": {"type": entity_type.value, "confidence": confidence},
            "pipeline": [{"module_id": mid, "status": "queued"} for mid in pipeline],
            "graph": neighborhood,
            "footprint_url": f"/api/v1/footprint/{session_id}",
        }

    # ─── FOOTPRINT ───

    @router.get("/footprint/{session_id}")
    async def get_footprint(session_id: str):
        if not footprint_tracker:
            return {"error": "footprint_tracker not configured"}
        footprint_tracker.load_session(session_id)
        return footprint_tracker.get_footprint_summary(session_id)

    @router.get("/footprint/{session_id}/timeline")
    async def get_timeline(session_id: str):
        if not footprint_tracker:
            return {"error": "footprint_tracker not configured"}
        footprint_tracker.load_session(session_id)
        return {"snapshots": footprint_tracker.get_timeline(session_id)}

    @router.get("/footprint/{session_id}/movement")
    async def get_movement(session_id: str):
        if not footprint_tracker:
            return {"error": "footprint_tracker not configured"}
        footprint_tracker.load_session(session_id)
        from core.movement import MovementDetector
        return MovementDetector().analyze(footprint_tracker.get_timeline(session_id))

    @router.get("/footprint/{session_id}/geo")
    async def get_geo_trail(session_id: str):
        if not footprint_tracker:
            return {"error": "footprint_tracker not configured"}
        footprint_tracker.load_session(session_id)
        s = footprint_tracker.get_footprint_summary(session_id)
        return {"session_id": session_id, "trail": s["movement_trail"],
                "segments": s["movement_segments"],
                "unique_locations": s["unique_locations"],
                "total_distance_km": s["total_distance_km"]}

    @router.get("/footprint/{session_id}/graph")
    async def get_session_graph(session_id: str):
        """Merged nodes + edges from all snapshots of a session."""
        if not footprint_tracker:
            return {"nodes": [], "edges": []}
        footprint_tracker.load_session(session_id)
        snaps = footprint_tracker._sessions.get(session_id, [])
        nodes = {}
        edges_seen = set()
        edges = []
        for snap in snaps:
            for e in snap.entities.values():
                if e.get("id") not in nodes:
                    nodes[e["id"]] = e
            for r in snap.relationships:
                key = (r.get("source"), r.get("target"), r.get("type"))
                if key in edges_seen:
                    continue
                edges_seen.add(key)
                edges.append(r)
        return {
            "session_id": session_id,
            "nodes": list(nodes.values()),
            "edges": edges,
            "node_count": len(nodes),
            "edge_count": len(edges),
        }

    @router.get("/footprint/{session_id}/snapshots/{snapshot_id}")
    async def get_snapshot(session_id: str, snapshot_id: str):
        if not footprint_tracker:
            return {"error": "footprint_tracker not configured"}
        return footprint_tracker.get_snapshot(session_id, snapshot_id) or {"error": "not found"}

    @router.get("/footprint/{session_id}/diff/{snapshot_a}/{snapshot_b}")
    async def diff_snapshots(session_id: str, snapshot_a: str, snapshot_b: str):
        if not footprint_tracker:
            return {"error": "footprint_tracker not configured"}
        return footprint_tracker.get_diff(session_id, snapshot_a, snapshot_b)

    # ─── GRAPH ───

    @router.get("/graph")
    async def get_full_graph():
        """Full graph export (nodes + edges)."""
        if not graph_manager.connected:
            return {"nodes": [], "edges": []}
        return graph_manager.full_export()

    @router.get("/graph/{entity_id}")
    async def get_graph(entity_id: str, depth: int = 3):
        if not graph_manager.connected:
            return {"error": "Graph not connected", "nodes": [], "edges": []}
        n = graph_manager.get_neighborhood(entity_id, depth)
        return {"entity_id": entity_id, "depth": depth,
                "nodes": n.get("nodes", []), "edges": n.get("edges", [])}

    @router.get("/entity/{entity_id}")
    async def get_entity(entity_id: str):
        if not graph_manager.connected:
            raise HTTPException(status_code=503, detail="Graph not connected")
        entity = graph_manager.get_entity(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail="Entité non trouvée")
        score = correlation_engine.calculate_entity_score(entity_id)
        return {"entity": entity, "relevance_score": round(score, 3)}

    @router.get("/graph/search")
    async def search_entities(q: str, limit: int = 20):
        if not graph_manager.connected:
            return {"results": []}
        entities = graph_manager.search_entities(q, limit)
        return {"query": q, "results": entities, "total": len(entities)}

    @router.get("/stats")
    async def get_stats():
        if not graph_manager.connected:
            return {"total_entities": 0, "total_relationships": 0}
        return graph_manager.get_graph_stats()

    @router.get("/modules")
    async def list_modules():
        from modules import list_all_modules
        return {"modules": list_all_modules()}

    @router.post("/export")
    async def export_graph(request: ExportRequest):
        from core.exporters import ReportExporter
        exporter = ReportExporter(graph_manager)
        footprint = None
        if request.include_footprint and request.session_id and footprint_tracker:
            footprint_tracker.load_session(request.session_id)
            footprint = footprint_tracker.get_footprint_summary(request.session_id)
        if request.format == "json":
            data = exporter.export_json(request.entity_id)
            if request.include_footprint and footprint:
                data["footprint"] = footprint
            return JSONResponse(content=data,
                                headers={"Content-Disposition": "attachment; filename=osin_chain_export.json"})
        elif request.format == "pdf":
            fp = exporter.export_pdf(request.entity_id)
            if not fp:
                raise HTTPException(status_code=500, detail="Export failed")
            media = "application/pdf" if fp.endswith(".pdf") else "text/html"
            return FileResponse(fp, media_type=media,
                                filename="osin_chain_report.pdf" if fp.endswith(".pdf") else "osin_chain_report.html")
        raise HTTPException(status_code=400, detail="Format non supporté")

    @router.get("/activity/stream")
    async def activity_stream(request: Request):
        """Server-Sent Events stream of live activity across all sessions."""
        from fastapi.responses import StreamingResponse
        import asyncio, json
        from datetime import datetime, timezone

        async def event_gen():
            while True:
                if await request.is_disconnected():
                    break
                stats = {}
                if graph_manager and graph_manager.connected:
                    stats = graph_manager.get_graph_stats()
                payload = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "stats": stats,
                    "footprint_sessions": len(footprint_tracker._sessions) if footprint_tracker else 0,
                }
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(2.0)

        return StreamingResponse(event_gen(), media_type="text/event-stream")

    @router.get("/sessions")
    async def list_sessions():
        """List all footprint sessions with metadata."""
        if not footprint_tracker:
            return {"sessions": []}
        from pathlib import Path
        base = Path(footprint_tracker.persist_dir)
        out = []
        for d in sorted(base.iterdir(), reverse=True):
            if not d.is_dir():
                continue
            files = list(d.glob("fp_*.json"))
            if not files:
                continue
            footprint_tracker.load_session(d.name)
            summary = footprint_tracker.get_footprint_summary(d.name)
            out.append({
                "session_id": d.name,
                "snapshots": len(files),
                "first_seen": summary.get("first_seen"),
                "last_seen": summary.get("last_seen"),
                "duration_seconds": summary.get("duration_seconds"),
                "unique_entities": summary.get("unique_entities_seen"),
                "total_relationships": summary.get("total_relationships"),
                "geo_points": summary.get("geo_points_count"),
                "total_distance_km": summary.get("total_distance_km"),
                "unique_locations": summary.get("unique_locations_count"),
            })
        return {"sessions": out, "count": len(out)}

    @router.delete("/session/{session_id}")
    async def clear_session(session_id: str):
        cleared = 0
        if graph_manager.connected:
            cleared = graph_manager.clear_session_data(session_id)
        if footprint_tracker:
            footprint_tracker.cleanup_session(session_id)
        return {"status": "cleared", "session_id": session_id, "entities_removed": cleared}

    @router.post("/face/search")
    async def face_search(file: UploadFile = File(..., alias="file"),
                          top_k: int = 10,
                          threshold: float = 0.50,
                          session_id: Optional[str] = None):
        """Search _FACE_INDEX by uploading a photo. Returns all matches per detected face."""
        if not rate_limiter.check("face_search"):
            raise HTTPException(status_code=429, detail="Rate limit")
        from core.face_service import search_by_photo
        try:
            data = await file.read()
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Could not read file: {e}")
        result = search_by_photo(data, top_k=top_k, threshold=threshold)
        result["session_id"] = session_id or uuid.uuid4().hex[:12]
        return result

    @router.post("/face/search/base64")
    async def face_search_base64(request: Request, top_k: int = 10, threshold: float = 0.50):
        """Search _FACE_INDEX by base64 data URL."""
        if not rate_limiter.check("face_search_b64"):
            raise HTTPException(status_code=429, detail="Rate limit")
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="JSON requis")
        data_url = body.get("image", "")
        if not data_url.startswith("data:image"):
            raise HTTPException(status_code=400, detail="data:image/...;base64,...")
        try:
            _, b64 = data_url.split(",", 1)
            data = base64.b64decode(b64)
        except Exception:
            raise HTTPException(status_code=400, detail="base64 invalide")
        from core.face_service import search_by_photo
        return search_by_photo(data, top_k=top_k, threshold=threshold)

    @router.get("/face/index")
    async def face_index(limit: int = 50, offset: int = 0):
        """List all indexed faces."""
        from core.face_service import get_index
        return get_index(limit=limit, offset=offset)

    @router.get("/face/clusters")
    async def face_clusters():
        """Get all person clusters (DBSCAN)."""
        from core.face_service import get_clusters
        return {"clusters": get_clusters(), "count": len(get_clusters())}

    @router.get("/face/person/{cluster_id}")
    async def face_person(cluster_id: int):
        """Get person profile (all faces in a cluster)."""
        from core.face_service import get_person_profile
        prof = get_person_profile(cluster_id)
        if not prof:
            raise HTTPException(status_code=404, detail="Cluster not found")
        return prof

    @router.get("/face/compare")
    async def face_compare(a: str, b: str):
        """Compare 2 faces by their face_ids."""
        from core.face_service import compare_faces
        return compare_faces(a, b)

    @router.get("/face/stats")
    async def face_stats():
        """Demographics & index stats."""
        from core.face_service import get_stats
        return get_stats()

    @router.get("/face/timeline/{face_id}")
    async def face_timeline(face_id: str):
        """Get sighting timeline for a specific face."""
        from core.face_service import get_timeline
        return {"face_id": face_id, "sightings": get_timeline(face_id), "count": len(get_timeline(face_id))}

    @router.get("/face/density")
    async def face_density(cell_size: float = 1.0):
        """Get 2D density grid of face sightings (for heatmap)."""
        from core.face_service import get_density_grid
        return get_density_grid(cell_size=cell_size)

    @router.post("/face/cluster/{cluster_id}/name")
    async def face_cluster_name(cluster_id: int, request: Request):
        """Persist human name for a Person cluster."""
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="JSON required")
        name = (body.get("name") or "").strip()[:80]
        if not name:
            raise HTTPException(status_code=400, detail="name required")
        from core.face_service import set_person_name
        set_person_name(cluster_id, name)
        return {"cluster_id": cluster_id, "name": name, "saved": True}

    @router.get("/face/person-names")
    async def face_person_names():
        """List all person names."""
        from core.face_service import get_all_person_names
        names = get_all_person_names()
        return {"names": names, "count": len(names)}

    @router.post("/face/match-avatar")
    async def face_match_avatar(file: UploadFile = File(..., alias="file"),
                                top_k: int = 5, threshold: float = 0.40):
        """Match an avatar/social photo against face index."""
        from core.face_service import search_by_photo
        try:
            data = await file.read()
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))
        result = search_by_photo(data, top_k=top_k, threshold=threshold)
        result["mode"] = "avatar_match"
        return result

    @router.get("/face/by-session/{session_id}")
    async def face_by_session(session_id: str):
        """List all face sightings in a specific session."""
        from core.face_service import _FACE_TIMELINE
        out = []
        for fid, sights in _FACE_TIMELINE.items():
            ses = [s for s in sights if s.get("session") == session_id]
            if ses:
                out.append({"face_id": fid, "session": session_id, "count": len(ses),
                           "sightings": ses})
        return {"session_id": session_id, "faces": out, "count": len(out)}

    @router.delete("/face/{face_id}")
    async def face_delete(face_id: str):
        """Remove a face from index (RGPD)."""
        from core.face_service import delete_face
        return delete_face(face_id)

    @router.delete("/face/index/clear")
    async def face_clear():
        """Clear entire face index (RGPD)."""
        from core.face_service import clear_index
        return clear_index()

    @router.post("/image/batch")
    async def image_batch(files: list = File(..., alias="files"),
                          session_id: Optional[str] = None):
        """Batch upload multiple photos. Each photo processed through FaceMatch."""
        if not rate_limiter.check("image_batch"):
            raise HTTPException(status_code=429, detail="Rate limit")
        if not files:
            raise HTTPException(status_code=400, detail="No files provided")
        if len(files) > 20:
            raise HTTPException(status_code=400, detail="Max 20 files per batch")
        from modules import get_module_instance
        fm = get_module_instance(14, rate_limiter=rate_limiter)
        sid = session_id or uuid.uuid4().hex[:12]
        os.makedirs("data/uploads", exist_ok=True)
        results = []
        for f in files:
            ext = os.path.splitext(f.filename or "img.jpg")[1].lower() or ".jpg"
            if ext not in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"):
                results.append({"filename": f.filename, "error": f"Format non supporté: {ext}"})
                continue
            dest = f"data/uploads/{sid}_{int(uuid.uuid4().int >> 96)}{ext}"
            with open(dest, "wb") as out:
                shutil.copyfileobj(f.file, out)
            ent = {"id": f"img_{uuid.uuid4().hex[:10]}", "type": "image",
                   "value": os.path.abspath(dest),
                   "metadata": {"source_url": os.path.abspath(dest),
                                "session": sid, "uploaded_filename": f.filename}}
            try:
                r = fm.execute(ent)
                results.append({
                    "filename": f.filename,
                    "status": r.status,
                    "backend": r.sources_hit[0] if r.sources_hit else "opencv_haar",
                    "entities": len(r.entities_found),
                    "warnings": r.warnings,
                    "execution_time_ms": round(r.execution_time_ms, 1),
                })
            except Exception as e:
                results.append({"filename": f.filename, "error": str(e)})
        return {"session_id": sid, "count": len(results), "results": results}

    @router.post("/image/upload")
    async def image_upload(file: UploadFile = File(..., alias="file"),
                           session_id: Optional[str] = None):
        client_ip = "image_upload"
        if not rate_limiter.check(client_ip):
            raise HTTPException(status_code=429, detail="Rate limit")
        sid = session_id or uuid.uuid4().hex[:12]
        os.makedirs("data/uploads", exist_ok=True)
        ext = os.path.splitext(file.filename or "img.jpg")[1].lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"):
            raise HTTPException(status_code=400, detail=f"Format non support\u00e9: {ext}")
        dest = f"data/uploads/{sid}_{int(uuid.uuid4().int >> 96)}{ext}"
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        try:
            file.file.close()
        except Exception:
            pass

        from modules import get_module_instance
        fm = get_module_instance(14, rate_limiter=rate_limiter)
        ent = {"id": f"img_{uuid.uuid4().hex[:10]}", "type": "image",
               "value": os.path.abspath(dest),
               "metadata": {"source_url": os.path.abspath(dest),
                            "session": sid, "uploaded_filename": file.filename}}
        r = fm.execute(ent)

        entities_added = []
        rels_added = []
        if graph_manager.connected:
            from core.dispatcher import InputDispatcher
            disp = dispatcher if isinstance(dispatcher, InputDispatcher) else InputDispatcher()
            try:
                if not any(e.get("id") == ent["id"] for e in r.entities_found):
                    graph_manager.create_entity(
                        entity_id=ent["id"], entity_type="image",
                        value=ent["value"], source="user_upload",
                        confidence=1.0,
                        metadata={"session": sid, "filename": file.filename,
                                  "local_path": dest})
            except Exception as ex:
                logger = None
            for e in r.entities_found:
                try:
                    graph_manager.create_entity(
                        entity_id=e["id"], entity_type=e["type"],
                        value=e["value"], source=e.get("source", "facematch"),
                        confidence=e.get("confidence", 0.8),
                        metadata={**e.get("metadata", {}), "session": sid})
                    entities_added.append({"id": e["id"], "type": e["type"],
                                           "value": e["value"],
                                           "confidence": e.get("confidence", 0.8),
                                           "metadata": e.get("metadata", {})})
                except Exception:
                    pass
            for rel in (r.relationships or []):
                try:
                    graph_manager.create_relationship(
                        source_id=rel["source"], target_id=rel["target"],
                        rel_type=rel["type"], weight=rel.get("weight", 0.8),
                        evidence=rel.get("evidence", ""))
                    rels_added.append({"source": rel["source"], "target": rel["target"],
                                        "type": rel["type"],
                                        "weight": rel.get("weight", 0.8),
                                        "evidence": rel.get("evidence", "")})
                except Exception:
                    pass

        return {
            "status": r.status,
            "session_id": sid,
            "local_path": dest,
            "backend": r.sources_hit[0] if r.sources_hit else "opencv_haar",
            "entities": entities_added,
            "relationships": rels_added,
            "warnings": r.warnings,
            "execution_time_ms": round(r.execution_time_ms, 1),
        }

    @router.post("/image/base64")
    async def image_base64(request: Request):
        try:
            body = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="JSON requis")
        if not rate_limiter.check("image_b64"):
            raise HTTPException(status_code=429, detail="Rate limit")
        sid = body.get("session_id") or uuid.uuid4().hex[:12]
        data_url = body.get("image", "")
        if not data_url.startswith("data:image"):
            raise HTTPException(
                status_code=400,
                detail="image doit etre data:image/...;base64,...")
        os.makedirs("data/uploads", exist_ok=True)
        try:
            header, b64 = data_url.split(",", 1)
            img_bytes = base64.b64decode(b64)
        except Exception:
            raise HTTPException(status_code=400, detail="base64 invalide")
        ext = ".png"
        if "jpeg" in header or "jpg" in header:
            ext = ".jpg"
        elif "webp" in header:
            ext = ".webp"
        dest = f"data/uploads/{sid}_b64{ext}"
        with open(dest, "wb") as f:
            f.write(img_bytes)

        from modules import get_module_instance
        fm = get_module_instance(14, rate_limiter=rate_limiter)
        ent = {"id": f"img_{uuid.uuid4().hex[:10]}", "type": "image",
               "value": os.path.abspath(dest),
               "metadata": {"source_url": os.path.abspath(dest),
                            "session": sid, "from": "base64"}}
        r = fm.execute(ent)
        entities_added = []
        rels_added = []
        if graph_manager.connected:
            for e in r.entities_found:
                try:
                    graph_manager.create_entity(
                        entity_id=e["id"], entity_type=e["type"],
                        value=e["value"], source=e.get("source", "facematch"),
                        confidence=e.get("confidence", 0.8),
                        metadata={**e.get("metadata", {}), "session": sid})
                    entities_added.append({"id": e["id"], "type": e["type"],
                                           "value": e["value"]})
                except Exception:
                    pass
            for rel in (r.relationships or []):
                try:
                    graph_manager.create_relationship(
                        source_id=rel["source"], target_id=rel["target"],
                        rel_type=rel["type"], weight=rel.get("weight", 0.8),
                        evidence=rel.get("evidence", ""))
                    rels_added.append({"source": rel["source"],
                                        "target": rel["target"],
                                        "type": rel["type"]})
                except Exception:
                    pass

        return _sanitize({
            "status": r.status, "session_id": sid, "local_path": dest,
            "backend": r.sources_hit[0] if r.sources_hit else "opencv_haar",
            "entities": entities_added, "relationships": rels_added,
            "warnings": r.warnings,
            "execution_time_ms": round(r.execution_time_ms, 1),
        })


    @router.get("/face/density-grid")
    async def face_density_grid(cell_size: float = 1.0):
        """Build a density grid of faces with GPS coordinates (heatmap)."""
        from core.face_service import get_density_grid
        return get_density_grid(cell_size=cell_size)

    @router.get("/face/sessions")
    async def face_sessions():
        """List all sessions with face counts (cross-session search)."""
        from core.face_service import list_sessions
        return list_sessions()

    @router.get("/face/webcam-token")
    async def face_webcam_token():
        """Generate one-time token for webcam capture."""
        import secrets
        return {"token": secrets.token_urlsafe(16), "expires_in": 3600}

    @router.get("/face/cluster/names")
    async def face_cluster_names():
        """Get all named person clusters."""
        from core.face_service import get_cluster_names
        return get_cluster_names()

    app.include_router(router)


async def _run_chain(pipeline, root_entity, session_id, max_depth,
                     graph_manager, correlation_engine, rate_limiter,
                     ws_manager=None, footprint_tracker=None, geo_manager=None,
                     snapshot_pacing_seconds=0.0):
    from core.chain_engine import ChainEngine

    engine = ChainEngine(
        max_depth=max_depth,
        max_entities=800,
        max_modules_per_type=8,
        ws_broadcast=ws_manager.send if ws_manager else None,
        graph_manager=graph_manager,
        rate_limiter=rate_limiter,
        footprint_tracker=footprint_tracker,
        geo_manager=geo_manager,
        snapshot_pacing_seconds=snapshot_pacing_seconds,
    )

    root_dict = {
        "id": root_entity.id,
        "type": root_entity.type.value,
        "value": root_entity.value,
        "metadata": root_entity.metadata,
    }

    await engine.run(root_entity=root_dict, initial_modules=pipeline,
                     session_id=session_id)
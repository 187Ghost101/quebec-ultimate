"""OSIN CHAIN QUEBEC ULTIMATE — Footprint Tracker
Ghost1o1 — Capture l'empreinte numérique du sujet à travers le temps

Permet de voir:
- L'évolution du graphe (entités ajoutées, relations créées)
- Le mouvement géographique (GPS, IP, adresse, carrier)
- Les nouveaux comptes / plateformes découverts
- Les corrélations temporelles (X a été vu avant Y)
"""
import json
import time
import uuid
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Set, Tuple
from collections import defaultdict
from threading import Lock


class FootprintSnapshot:
    def __init__(self, session_id: str, trigger: str = ""):
        self.snapshot_id = f"fp_{uuid.uuid4().hex[:12]}"
        self.session_id = session_id
        self.trigger = trigger
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.timestamp_unix = time.time()
        self.entities: Dict[str, Dict] = {}
        self.relationships: List[Dict] = []
        self.modules_run: List[Dict] = []
        self.geo_points: List[Dict] = []

    def to_dict(self):
        return {
            "snapshot_id": self.snapshot_id,
            "session_id": self.session_id,
            "trigger": self.trigger,
            "timestamp": self.timestamp,
            "timestamp_unix": self.timestamp_unix,
            "entities": list(self.entities.values()),
            "relationships": self.relationships,
            "modules_run": self.modules_run,
            "geo_points": self.geo_points,
            "entity_count": len(self.entities),
            "relationship_count": len(self.relationships),
            "geo_count": len(self.geo_points),
        }


class FootprintTracker:
    def __init__(self, persist_dir: Optional[Path] = None):
        self.persist_dir = Path(persist_dir) if persist_dir else Path(__file__).parent.parent / "data" / "footprints"
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self._sessions: Dict[str, List[FootprintSnapshot]] = defaultdict(list)
        self._lock = Lock()

    def new_snapshot(self, session_id: str, trigger: str = "") -> FootprintSnapshot:
        return FootprintSnapshot(session_id, trigger)

    def _extract_geo_points(self, snap: FootprintSnapshot):
        """Extract geo points from snapshot entities (idempotent + None-safe)."""
        for eid, ent in snap.entities.items():
            meta = ent.get("metadata") or {}
            lat = meta.get("lat")
            lon = meta.get("lon")
            if lat is None or lon is None:
                continue
            try:
                lat_f = float(lat)
                lon_f = float(lon)
            except (ValueError, TypeError):
                continue
            if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
                continue
            if any(gp.get("entity_id") == eid for gp in snap.geo_points):
                continue
            snap.geo_points.append({
                "entity_id": eid,
                "type": ent.get("type"),
                "value": ent.get("value"),
                "lat": lat_f,
                "lon": lon_f,
                "source": meta.get("geo_source", "unknown"),
                "confidence": float(meta.get("geo_confidence", 0.5)),
                "timestamp": snap.timestamp_unix,
            })

    def record(self, snapshot: FootprintSnapshot) -> str:
        self._extract_geo_points(snapshot)
        with self._lock:
            self._sessions[snapshot.session_id].append(snapshot)
            self._save_snapshot(snapshot)
        return snapshot.snapshot_id

    def record_change(self, session_id: str, graph_manager,
                      trigger: str = "chain_step",
                      extra_metadata: Optional[Dict] = None,
                      geo_manager=None) -> str:
        snap = self.new_snapshot(session_id, trigger)
        if extra_metadata:
            snap.modules_run.append({"trigger": trigger, "metadata": extra_metadata, "ts": snap.timestamp})
        try:
            snap.entities = {e["id"]: dict(e) for e in graph_manager.entities.values()}
        except Exception:
            pass
        try:
            for u, v, d in graph_manager.graph.edges(data=True):
                snap.relationships.append({
                    "source": u, "target": v,
                    "type": d.get("type", ""),
                    "weight": d.get("weight", 1.0),
                    "evidence": d.get("evidence", ""),
                })
        except Exception:
            try:
                snap.relationships = list(graph_manager.full_export().get("edges", []))
            except Exception:
                pass
        return self.record(snap)

    def get_timeline(self, session_id: str) -> List[Dict]:
        with self._lock:
            snaps = self._sessions.get(session_id, [])
            return [s.to_dict() for s in snaps]

    def get_snapshot(self, session_id: str, snapshot_id: str) -> Optional[Dict]:
        with self._lock:
            for s in self._sessions.get(session_id, []):
                if s.snapshot_id == snapshot_id:
                    return s.to_dict()
        return None

    def get_diff(self, session_id: str, snapshot_a_id: str, snapshot_b_id: str) -> Dict:
        with self._lock:
            snaps = {s.snapshot_id: s for s in self._sessions.get(session_id, [])}
            a = snaps.get(snapshot_a_id)
            b = snaps.get(snapshot_b_id)
            if not a or not b:
                return {"error": "snapshot not found"}
        ids_a = set(a.entities.keys())
        ids_b = set(b.entities.keys())
        added = ids_b - ids_a
        removed = ids_a - ids_b
        common = ids_a & ids_b
        changed = []
        for eid in common:
            va = a.entities[eid].get("value", "")
            vb = b.entities[eid].get("value", "")
            if va != vb:
                changed.append({"id": eid, "type": b.entities[eid].get("type"),
                                "before": va, "after": vb})
        return {
            "from_snapshot": snapshot_a_id, "to_snapshot": snapshot_b_id,
            "from_timestamp": a.timestamp, "to_timestamp": b.timestamp,
            "duration_seconds": b.timestamp_unix - a.timestamp_unix,
            "entities_added": list(added), "entities_removed": list(removed),
            "entities_changed": changed,
            "summary": {"added_count": len(added), "removed_count": len(removed), "changed_count": len(changed)},
        }

    def get_movement_trail(self, session_id: str) -> List[Dict]:
        with self._lock:
            snaps = sorted(self._sessions.get(session_id, []), key=lambda s: s.timestamp_unix)
        trail = []
        for i, snap in enumerate(snaps):
            for gp in snap.geo_points:
                trail.append({
                    "step": i, "snapshot_id": snap.snapshot_id,
                    "timestamp": snap.timestamp,
                    "timestamp_unix": snap.timestamp_unix,
                    "trigger": snap.trigger, **gp,
                })
        return trail

    def get_movement_segments(self, session_id: str) -> List[Dict]:
        trail = self.get_movement_trail(session_id)
        if len(trail) < 2:
            return []
        from core.geo import GeoManager, GeoPoint
        gm = GeoManager()
        segments = []
        for i in range(1, len(trail)):
            p1_dict = trail[i - 1]
            p2_dict = trail[i]
            p1 = GeoPoint(p1_dict["lat"], p1_dict["lon"], p1_dict["source"])
            p1.timestamp = p1_dict.get("timestamp_unix")
            p2 = GeoPoint(p2_dict["lat"], p2_dict["lon"], p2_dict["source"])
            p2.timestamp = p2_dict.get("timestamp_unix")
            dist_km = gm.haversine_km(p1, p2)
            bearing = gm.bearing_deg(p1, p2)
            dt = (p2.timestamp - p1.timestamp) if (p1.timestamp and p2.timestamp) else None
            speed_kmh = gm.speed_kmh(p1, p2)
            segments.append({
                "from": p1_dict, "to": p2_dict,
                "distance_km": round(dist_km, 2),
                "bearing_deg": round(bearing, 1),
                "bearing_compass": gm.bearing_to_compass(bearing),
                "duration_seconds": round(dt, 2) if dt else None,
                "speed_kmh": round(speed_kmh, 1) if speed_kmh else None,
                "speed_category": (
                    "impossible" if speed_kmh and speed_kmh > 1000
                    else "air_travel" if speed_kmh and speed_kmh > 200
                    else "highway" if speed_kmh and speed_kmh > 80
                    else "city_drive" if speed_kmh and speed_kmh > 20
                    else "walking" if speed_kmh and speed_kmh > 2
                    else "stationary"
                ),
            })
        return segments

    def get_footprint_summary(self, session_id: str) -> Dict:
        with self._lock:
            snaps = self._sessions.get(session_id, [])
        if not snaps:
            return {"session_id": session_id, "snapshots": 0}
        all_entities: Set[str] = set()
        all_rels: List[Dict] = []
        type_count: Dict[str, int] = defaultdict(int)
        for snap in snaps:
            for eid, entity in snap.entities.items():
                all_entities.add(eid)
                type_count[entity.get("type", "unknown")] += 1
            all_rels.extend(snap.relationships)
        trail = self.get_movement_trail(session_id)
        segments = self.get_movement_segments(session_id)
        total_distance_km = sum(s.get("distance_km", 0) or 0 for s in segments)
        unique_locations = []
        seen_locs: Set[Tuple[float, float]] = set()
        for p in trail:
            key = (round(p["lat"], 2), round(p["lon"], 2))
            if key not in seen_locs:
                seen_locs.add(key)
                unique_locations.append({
                    "lat": p["lat"], "lon": p["lon"],
                    "label": p.get("value"), "type": p.get("type"),
                    "source": p.get("source"),
                })
        return {
            "session_id": session_id,
            "snapshots_count": len(snaps),
            "first_seen": snaps[0].timestamp,
            "last_seen": snaps[-1].timestamp,
            "duration_seconds": snaps[-1].timestamp_unix - snaps[0].timestamp_unix,
            "unique_entities_seen": len(all_entities),
            "total_relationships": len(all_rels),
            "entities_by_type": dict(type_count),
            "geo_points_count": len(trail),
            "unique_locations_count": len(unique_locations),
            "total_distance_km": round(total_distance_km, 2),
            "movement_trail": trail,
            "movement_segments": segments,
            "unique_locations": unique_locations,
        }

    def _save_snapshot(self, snap: FootprintSnapshot):
        try:
            session_dir = self.persist_dir / snap.session_id
            session_dir.mkdir(parents=True, exist_ok=True)
            fp = session_dir / f"{snap.snapshot_id}.json"
            with open(fp, "w", encoding="utf-8") as f:
                json.dump(snap.to_dict(), f, indent=2, ensure_ascii=False, default=str)
        except Exception:
            pass

    def load_session(self, session_id: str) -> int:
        session_dir = self.persist_dir / session_id
        if not session_dir.exists():
            return 0
        loaded = 0
        with self._lock:
            self._sessions.pop(session_id, None)
            for fp in sorted(session_dir.glob("fp_*.json")):
                try:
                    with open(fp) as f:
                        d = json.load(f)
                    snap = FootprintSnapshot(d["session_id"], d.get("trigger", ""))
                    snap.snapshot_id = d["snapshot_id"]
                    snap.timestamp = d["timestamp"]
                    snap.timestamp_unix = d["timestamp_unix"]
                    snap.entities = {e["id"]: e for e in d.get("entities", [])}
                    snap.relationships = d.get("relationships", [])
                    snap.modules_run = d.get("modules_run", [])
                    snap.geo_points = d.get("geo_points", [])
                    self._sessions[session_id].append(snap)
                    loaded += 1
                except Exception:
                    continue
        return loaded

    def cleanup_session(self, session_id: str):
        with self._lock:
            self._sessions.pop(session_id, None)
        session_dir = self.persist_dir / session_id
        if session_dir.exists():
            shutil.rmtree(session_dir)
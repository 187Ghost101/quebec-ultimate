"""OSIN CHAIN QUEBEC ULTIMATE — Face Service
Ghost1o1 — Centralized face indexing, search, clustering, comparison.

Cross-session, cross-module, cross-photo face recognition.
- Search by photo upload
- Cosine similarity matching
- DBSCAN clustering into "person" profiles
- Perceptual hash fallback (dHash)
- Demographics stats
- Compare any 2 faces directly
"""
import io
import time
import base64
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict

import numpy as np
from PIL import Image

# Reuse _FACE_INDEX and helpers from face_match module
from modules.face_match import (
    _FACE_INDEX, _phash_int, _hamming, _cosine,
    INSIGHTFACE, FACE_REC, OPENCV_OK, SKLEARN_OK,
)


# ════════════════════════════════════════════════════════════
# FACE SEARCH
# ════════════════════════════════════════════════════════════

def search_faces(emb: np.ndarray = None, phash: int = None,
                 top_k: int = 10, threshold: float = 0.50) -> List[Dict]:
    """
    Search _FACE_INDEX for similar faces.

    Args:
        emb: 512-d ArcFace embedding to match against
        phash: dHash 64-bit of face crop (fallback)
        top_k: max results
        threshold: min cosine similarity (0.0-1.0)

    Returns:
        list of {face_id, similarity, type, value, metadata, source}
    """
    if not _FACE_INDEX:
        return []

    results = []
    for fid, fdata in _FACE_INDEX.items():
        sim = 0.0
        if emb is not None and fdata.get("embedding") is not None:
            try:
                sim = _cosine(emb, fdata["embedding"])
            except Exception:
                sim = 0.0
        elif phash is not None and fdata.get("phash") is not None:
            try:
                ham = _hamming(int(phash), int(fdata["phash"]))
                sim = max(0.0, 1.0 - (ham / 64.0))
            except Exception:
                sim = 0.0
        if sim >= threshold:
            results.append({
                "face_id": fid,
                "similarity": round(float(sim), 4),
                "type": fdata.get("type", "face"),
                "value": fdata.get("value", ""),
                "metadata": fdata.get("metadata", {}),
                "source": fdata.get("source", ""),
                "created_at": fdata.get("created_at", 0),
            })
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]


def search_by_photo(photo_bytes: bytes, top_k: int = 10,
                    threshold: float = 0.50) -> Dict:
    """
    Upload a photo, extract all faces, search _FACE_INDEX for each.

    Returns:
        {
          "query_faces": [...],  # detected faces in query
          "matches": [...]       # matches per query face
        }
    """
    try:
        pil = Image.open(io.BytesIO(photo_bytes)).convert("RGB")
    except Exception as e:
        return {"error": f"Could not open image: {e}", "query_faces": [], "matches": []}

    arr = np.array(pil)
    detected = []

    # Try InsightFace first
    if INSIGHTFACE:
        try:
            from modules.face_match import _get_analyzer
            analyzer = _get_analyzer()
            faces = analyzer.get(arr)
            for f in faces:
                emb = f.normed_embedding.astype(np.float32)
                detected.append({
                    "embedding": emb,
                    "phash_int": _phash_int(pil.crop((int(f.bbox[0]), int(f.bbox[1]),
                                                    int(f.bbox[2]), int(f.bbox[3])))),
                    "bbox": [float(x) for x in f.bbox],
                    "age": int(getattr(f, "age", 0)) if getattr(f, "age", None) else None,
                    "gender": "M" if getattr(f, "gender", None) == 1 else "F" if getattr(f, "gender", None) == 0 else None,
                    "backend": "insightface",
                })
        except Exception:
            pass

    # Fallback: face_recognition
    if not detected and FACE_REC:
        try:
            import face_recognition
            locations = face_recognition.face_locations(arr, model="hog")
            encodings = face_recognition.face_encodings(arr, locations)
            for loc, enc in zip(locations, encodings):
                top, right, bottom, left = loc
                detected.append({
                    "embedding": np.array(enc, dtype=np.float32),
                    "phash_int": _phash_int(pil.crop((left, top, right, bottom))),
                    "bbox": [float(left), float(top), float(right), float(bottom)],
                    "age": None,
                    "gender": None,
                    "backend": "face_recognition",
                })
        except Exception:
            pass

    # Fallback: OpenCV Haar (no embedding, phash only)
    if not detected and OPENCV_OK:
        try:
            import cv2
            arr_bgr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
            cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            rects = cascade.detectMultiScale(arr_bgr, 1.1, 5, minSize=(30, 30))
            for (x, y, w, h) in rects:
                detected.append({
                    "embedding": None,
                    "phash_int": _phash_int(pil.crop((x, y, x + w, y + h))),
                    "bbox": [float(x), float(y), float(x + w), float(y + h)],
                    "age": None,
                    "gender": None,
                    "backend": "opencv_haar",
                })
        except Exception:
            pass

    # For each detected face, search _FACE_INDEX
    matches_per_face = []
    for i, qface in enumerate(detected):
        matches = search_faces(
            emb=qface.get("embedding"),
            phash=qface.get("phash_int"),
            top_k=top_k,
            threshold=threshold,
        )
        matches_per_face.append({
            "query_index": i,
            "bbox": qface["bbox"],
            "backend": qface["backend"],
            "age": qface.get("age"),
            "gender": qface.get("gender"),
            "match_count": len(matches),
            "matches": matches,
        })

    return {
        "query_faces": [{
            "index": i, "bbox": q["bbox"],
            "backend": q["backend"],
            "age": q.get("age"), "gender": q.get("gender"),
        } for i, q in enumerate(detected)],
        "matches": matches_per_face,
        "total_indexed": len(_FACE_INDEX),
    }


# ════════════════════════════════════════════════════════════
# CLUSTERING (Person Profiles)
# ════════════════════════════════════════════════════════════

def get_clusters(eps: float = 0.45, min_samples: int = 2) -> List[Dict]:
    """
    Run DBSCAN on _FACE_INDEX to group faces into "person" profiles.
    Returns list of clusters with their faces.
    """
    if not _FACE_INDEX or not SKLEARN_OK or len(_FACE_INDEX) < 2:
        return []

    try:
        from sklearn.cluster import DBSCAN
        ids = list(_FACE_INDEX.keys())
        # Build distance matrix
        n = len(ids)
        dist = np.zeros((n, n), dtype=np.float32)
        for i in range(n):
            for j in range(i + 1, n):
                ei = _FACE_INDEX[ids[i]].get("embedding")
                ej = _FACE_INDEX[ids[j]].get("embedding")
                if ei is not None and ej is not None:
                    d = 1.0 - _cosine(ei, ej)
                    dist[i, j] = d
                    dist[j, i] = d
                else:
                    pi = _FACE_INDEX[ids[i]].get("phash", 0)
                    pj = _FACE_INDEX[ids[j]].get("phash", 0)
                    d = _hamming(int(pi), int(pj)) / 64.0
                    dist[i, j] = d
                    dist[j, i] = d
        clustering = DBSCAN(eps=eps, min_samples=min_samples,
                           metric="precomputed").fit(dist)

        clusters = defaultdict(list)
        for fid, cid in zip(ids, clustering.labels_):
            clusters[int(cid)].append(fid)

        result = []
        for cid, face_ids in clusters.items():
            if cid < 0:  # noise
                continue
            faces = [_FACE_INDEX[fid] for fid in face_ids]
            # Aggregate demographics
            ages = [f.get("age", 0) for f in faces if f.get("age")]
            genders = [f.get("gender") for f in faces if f.get("gender")]
            avg_age = sum(ages) / len(ages) if ages else None
            dominant_gender = max(set(genders), key=genders.count) if genders else None
            name = get_person_name(int(cid))
            result.append({
                "cluster_id": int(cid),
                "name": name,
                "face_count": len(face_ids),
                "face_ids": face_ids[:20],
                "avg_age": round(avg_age) if avg_age else None,
                "dominant_gender": dominant_gender,
                "first_seen": min(f.get("created_at", 0) for f in faces),
                "last_seen": max(f.get("created_at", 0) for f in faces),
                "sources": list(set(f.get("source", "") for f in faces))[:10],
            })
        result.sort(key=lambda x: x["face_count"], reverse=True)
        return result
    except Exception as e:
        return [{"error": str(e)}]


def get_person_profile(cluster_id: int) -> Optional[Dict]:
    """Get all faces in a cluster (person) with their sightings."""
    clusters = get_clusters()
    for c in clusters:
        if c["cluster_id"] == cluster_id:
            faces = []
            for fid in c["face_ids"]:
                f = _FACE_INDEX.get(fid, {})
                faces.append({
                    "face_id": fid,
                    "value": f.get("value", ""),
                    "type": f.get("type", "face"),
                    "source": f.get("source", ""),
                    "created_at": f.get("created_at", 0),
                    "metadata": f.get("metadata", {}),
                })
            return {
                "cluster_id": cluster_id,
                "face_count": c["face_count"],
                "avg_age": c["avg_age"],
                "dominant_gender": c["dominant_gender"],
                "first_seen": c["first_seen"],
                "last_seen": c["last_seen"],
                "faces": faces,
            }
    return None


# ════════════════════════════════════════════════════════════
# COMPARE 2 FACES
# ════════════════════════════════════════════════════════════

def compare_faces(face_id_a: str, face_id_b: str) -> Dict:
    """Compute similarity between 2 indexed faces."""
    a = _FACE_INDEX.get(face_id_a)
    b = _FACE_INDEX.get(face_id_b)
    if not a or not b:
        return {"error": "Face not found in index", "face_id_a": face_id_a, "face_id_b": face_id_b}

    sim = 0.0
    method = "none"
    if a.get("embedding") is not None and b.get("embedding") is not None:
        sim = _cosine(a["embedding"], b["embedding"])
        method = "cosine_arcface_512d"
    elif a.get("phash") is not None and b.get("phash") is not None:
        ham = _hamming(int(a["phash"]), int(b["phash"]))
        sim = max(0.0, 1.0 - (ham / 64.0))
        method = "hamming_dhash"

    # Classification
    if sim >= 0.65:
        verdict = "same_person"
    elif sim >= 0.50:
        verdict = "probably_same_person"
    elif sim >= 0.35:
        verdict = "possibly_related"
    else:
        verdict = "different_person"

    return {
        "face_id_a": face_id_a,
        "face_id_b": face_id_b,
        "similarity": round(float(sim), 4),
        "method": method,
        "verdict": verdict,
        "face_a": {"value": a.get("value", ""), "source": a.get("source", ""),
                   "created_at": a.get("created_at", 0)},
        "face_b": {"value": b.get("value", ""), "source": b.get("source", ""),
                   "created_at": b.get("created_at", 0)},
    }


# ════════════════════════════════════════════════════════════
# INDEX OPERATIONS
# ════════════════════════════════════════════════════════════

def get_index(limit: int = 100, offset: int = 0) -> Dict:
    """List all indexed faces (paginated)."""
    items = []
    for fid, fdata in list(_FACE_INDEX.items())[offset:offset + limit]:
        items.append({
            "face_id": fid,
            "type": fdata.get("type", "face"),
            "value": fdata.get("value", ""),
            "source": fdata.get("source", ""),
            "created_at": fdata.get("created_at", 0),
            "has_embedding": fdata.get("embedding") is not None,
            "phash": fdata.get("phash_int", 0),
            "metadata": fdata.get("metadata", {}),
        })
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return {
        "items": items,
        "total": len(_FACE_INDEX),
        "offset": offset,
        "limit": limit,
    }


def record_sighting(face_id: str, source: str, lat: float = None, lon: float = None,
                    session: str = None, backend: str = None):
    """Record a sighting for a face (timeline tracking)."""
    if face_id not in _FACE_TIMELINE:
        _FACE_TIMELINE[face_id] = []
    _FACE_TIMELINE[face_id].append({
        "timestamp": time.time(),
        "source": source[:200] if source else "",
        "lat": lat, "lon": lon,
        "session": session,
        "backend": backend,
    })
    if len(_FACE_TIMELINE[face_id]) > 100:
        _FACE_TIMELINE[face_id] = _FACE_TIMELINE[face_id][-100:]


def get_timeline(face_id: str) -> List[Dict]:
    """Get sighting timeline for a face."""
    return _FACE_TIMELINE.get(face_id, [])


def get_density_grid(cell_size: float = 1.0) -> Dict:
    """
    Compute 2D density grid of face sightings with GPS.
    Returns {"cells": [{"lat", "lon", "count"}], "total": N, "cell_size": cell_size}.
    """
    cells = {}
    for sightings in _FACE_TIMELINE.values():
        for s in sightings:
            if s.get("lat") is None or s.get("lon") is None:
                continue
            lat = round(float(s["lat"]) / cell_size) * cell_size
            lon = round(float(s["lon"]) / cell_size) * cell_size
            key = f"{lat:.2f},{lon:.2f}"
            cells[key] = cells.get(key, {"lat": lat, "lon": lon, "count": 0})
            cells[key]["count"] += 1
    grid = sorted(cells.values(), key=lambda c: -c["count"])
    return {"cells": grid, "total": sum(c["count"] for c in grid), "cell_size": cell_size}


def set_person_name(cluster_id: int, name: str):
    """Persist human name for a cluster (Person profile)."""
    _PERSON_NAMES[int(cluster_id)] = name[:80]


def get_person_name(cluster_id: int) -> Optional[str]:
    return _PERSON_NAMES.get(int(cluster_id))


def get_all_person_names() -> Dict[int, str]:
    return dict(_PERSON_NAMES)


def get_stats() -> Dict:
    """Get statistics about the face index."""
    if not _FACE_INDEX:
        return {
            "total_faces": 0,
            "total_persons": 0,
            "backends": {},
            "demographics": {"avg_age": None, "genders": {}},
        }

    backends = defaultdict(int)
    ages = []
    genders = defaultdict(int)
    sources = defaultdict(int)
    with_embedding = 0

    for f in _FACE_INDEX.values():
        meta = f.get("metadata", {})
        # FIX: backend can be at root OR in metadata, age/gender too
        backend = f.get("backend") or meta.get("backend", "unknown")
        if backend == "unknown":
            # Try to infer from embedding shape
            emb = f.get("embedding")
            if hasattr(emb, "__len__"):
                if len(emb) == 512: backend = "ArcFace-512d"
                elif len(emb) == 128: backend = "dlib-128d"
                else: backend = "OpenCV-Haar"
        backends[backend] += 1
        sources[f.get("source", "unknown")] += 1
        if f.get("embedding") is not None:
            with_embedding += 1
        age = f.get("age") or meta.get("age")
        if age:
            ages.append(age)
        gender = f.get("gender") or meta.get("gender")
        if gender:
            genders[gender] += 1

    clusters = get_clusters()

    return {
        "total_faces": len(_FACE_INDEX),
        "total_persons": len(clusters),
        "with_embedding": with_embedding,
        "backends": dict(backends),
        "sources": dict(sources),
        "demographics": {
            "avg_age": round(sum(ages) / len(ages), 1) if ages else None,
            "age_min": min(ages) if ages else None,
            "age_max": max(ages) if ages else None,
            "genders": dict(genders),
        },
        "first_face": min((f.get("created_at", 0) for f in _FACE_INDEX.values()), default=0),
        "last_face": max((f.get("created_at", 0) for f in _FACE_INDEX.values()), default=0),
    }


def delete_face(face_id: str) -> Dict:
    """Remove a face from the index."""
    if face_id in _FACE_INDEX:
        del _FACE_INDEX[face_id]
        return {"deleted": True, "face_id": face_id, "remaining": len(_FACE_INDEX)}
    return {"deleted": False, "face_id": face_id, "error": "not found"}


def clear_index() -> Dict:
    """Clear all indexed faces (RGPD right to be forgotten)."""
    n = len(_FACE_INDEX)
    _FACE_INDEX.clear()
    _FACE_TIMELINE.clear()
    _FACE_SESSIONS.clear()
    return {"cleared": n, "remaining": 0}


# ════════════════════════════════════════════════════════════
# PHASE 2 — TIMELINE / DENSITY / NAMING / AVATAR / SESSIONS
# ════════════════════════════════════════════════════════════

def get_timeline(face_id: str) -> Optional[Dict]:
    """Get all sightings for a face across time."""
    from modules.face_match import _FACE_TIMELINE
    sightings = _FACE_TIMELINE.get(face_id, [])
    if not sightings:
        return None
    return {
        "face_id": face_id,
        "sighting_count": len(sightings),
        "first_seen": sightings[0]["timestamp"] if sightings else 0,
        "last_seen": sightings[-1]["timestamp"] if sightings else 0,
        "sessions": list(set(s.get("session", "?") for s in sightings)),
        "sources": list(set(s.get("source", "?") for s in sightings))[:20],
        "sightings": sightings,
    }


def get_density_grid(cell_size: float = 1.0) -> Dict:
    """Build a density grid of faces across lat/lon (from EXIF GPS).

    Returns list of cells with count + center lat/lon.
    cell_size in degrees (default 1°).
    """
    from modules.face_match import _FACE_INDEX, _FACE_TIMELINE
    cells = {}
    for fid, fdata in _FACE_INDEX.items():
        # Try to extract GPS from metadata or timeline sightings
        meta = fdata.get("metadata", {})
        lat = meta.get("lat")
        lon = meta.get("lon")
        if lat is None or lon is None:
            # Search timeline
            for s in _FACE_TIMELINE.get(fid, []):
                src = s.get("source", "")
                if "exif" in s.get("backend", "") and meta.get("lat") is None:
                    pass
        if lat is not None and lon is not None:
            cell = (round(lat / cell_size), round(lon / cell_size))
            if cell not in cells:
                cells[cell] = {"count": 0, "lat_sum": 0, "lon_sum": 0, "face_ids": []}
            cells[cell]["count"] += 1
            cells[cell]["lat_sum"] += lat
            cells[cell]["lon_sum"] += lon
            cells[cell]["face_ids"].append(fid)
    grid = []
    for (clat, clon), c in cells.items():
        grid.append({
            "lat": c["lat_sum"] / c["count"],
            "lon": c["lon_sum"] / c["count"],
            "count": c["count"],
            "face_count": c["count"],
            "cell": [clat, clon],
            "face_ids": c["face_ids"][:10],
        })
    grid.sort(key=lambda x: -x["count"])
    return {
        "total_cells": len(grid),
        "total_faces_with_gps": sum(g["count"] for g in grid),
        "cell_size_degrees": cell_size,
        "grid": grid,
    }


def name_cluster(cluster_id: int, name: str) -> Dict:
    """Persist a human-readable name for a person cluster."""
    from modules.face_match import _PERSON_NAMES
    _PERSON_NAMES[int(cluster_id)] = name.strip()
    return {"cluster_id": int(cluster_id), "name": name.strip(),
            "named_clusters": len(_PERSON_NAMES)}


def get_cluster_names() -> Dict:
    """Get all named clusters."""
    from modules.face_match import _PERSON_NAMES
    return {"names": _PERSON_NAMES, "count": len(_PERSON_NAMES)}


def match_avatar(avatar_bytes: bytes, top_k: int = 10,
                 threshold: float = 0.40) -> Dict:
    """Upload a small avatar image, find matching indexed faces.

    Use case: social profile avatar → match to all faces seen across sessions.
    """
    return search_by_photo(avatar_bytes, top_k=top_k, threshold=threshold)


def get_faces_by_session(session_id: str) -> Dict:
    """Get all faces detected in a specific session (cross-session search)."""
    from modules.face_match import _FACE_INDEX, _FACE_SESSIONS
    face_ids = _FACE_SESSIONS.get(session_id, set())
    faces = []
    for fid in face_ids:
        f = _FACE_INDEX.get(fid, {})
        faces.append({
            "face_id": fid,
            "value": f.get("value", ""),
            "backend": f.get("backend", "?"),
            "created_at": f.get("created_at", 0),
            "source": f.get("source", ""),
            "metadata": f.get("metadata", {}),
        })
    return {
        "session_id": session_id,
        "face_count": len(faces),
        "faces": sorted(faces, key=lambda x: x["created_at"], reverse=True),
    }


def list_sessions() -> Dict:
    """List all sessions that have faces indexed."""
    from modules.face_match import _FACE_SESSIONS
    sessions = []
    for sid, fids in _FACE_SESSIONS.items():
        sessions.append({
            "session_id": sid,
            "face_count": len(fids),
            "first_face_ts": min((_FACE_INDEX[fid].get("created_at", 0) for fid in fids), default=0),
        })
    sessions.sort(key=lambda x: x.get("first_face_ts", 0), reverse=True)
    return {"sessions": sessions, "total": len(sessions)}

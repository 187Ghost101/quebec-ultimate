"""FaceMatch V1 - REAL face recognition via ArcFace + EXIF GPS - Ghost1o1
State-of-the-art local face recognition. No external API.

Pipeline:
1. Download image (URL or data URL or local path)
2. Extract EXIF (GPS, camera, timestamp) - geolocation from photo metadata
3. Detect faces (RetinaFace via InsightFace → dlib → OpenCV fallback)
4. Compute 512-d ArcFace embedding per face
5. Compute dHash perceptual hash of face crop
6. Match against in-memory face index (cross-session, cross-platform)
7. DBSCAN cluster similar faces into "same person" groups

REAL correlations produced:
- same_face_as       : ArcFace cosine >= 0.65 (same person)
- similar_to         : ArcFace cosine >= 0.50 (probably same person)
- geo_tagged_at      : EXIF GPS coordinates
- taken_with         : camera make/model
- captured_at        : EXIF datetime
- face_cluster       : DBSCAN cluster ID for grouping
"""
import os
import io
import json
import time
import re
import math
import hashlib
import logging
import numpy as np
from PIL import Image, ExifTags
from typing import Dict, List, Any, Optional
from .base import OSINTModule, ModuleResult, STATUS_VERIFIED, STATUS_INFERRED, STATUS_FAILED

logger = logging.getLogger("osin_chain")

INSIGHTFACE = False
FACE_REC = False
OPENCV_OK = False
SKLEARN_OK = False

try:
    import insightface
    from insightface.app import FaceAnalysis
    INSIGHTFACE = True
except Exception:
    pass

try:
    import face_recognition
    FACE_REC = True
except Exception:
    pass

try:
    import cv2
    OPENCV_OK = True
except Exception:
    pass

try:
    from sklearn.cluster import DBSCAN
    SKLEARN_OK = True
except Exception:
    pass


_FACE_INDEX: Dict[str, Dict] = {}
_FACE_INDEX_LOCK = False
_FACE_TIMELINE: Dict[str, List[Dict]] = {}  # face_id -> list of sightings
_PERSON_NAMES: Dict[int, str] = {}  # cluster_id -> human name
_FACE_SESSIONS: Dict[str, set] = {}  # session_id -> set of face_ids

# Persistence paths
_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
_FACE_INDEX_PATH = os.path.join(_DATA_DIR, "face_index.json")
_PERSON_NAMES_PATH = os.path.join(_DATA_DIR, "persons.json")
_FACE_TIMELINE_PATH = os.path.join(_DATA_DIR, "face_timeline.json")
_FACE_SESSIONS_PATH = os.path.join(_DATA_DIR, "face_sessions.json")


def _save_face_index() -> bool:
    """Persist face index to disk (JSON, numpy arrays as base64)."""
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        import base64
        out = {}
        for fid, f in _FACE_INDEX.items():
            entry = {k: v for k, v in f.items() if k != "embedding"}
            if f.get("embedding") is not None:
                arr = f["embedding"]
                if hasattr(arr, "tobytes"):
                    entry["_emb_b64"] = base64.b64encode(arr.tobytes()).decode()
                    entry["_emb_dtype"] = str(arr.dtype)
                    entry["_emb_shape"] = list(arr.shape)
            out[fid] = entry
        with open(_FACE_INDEX_PATH, "w") as fh:
            json.dump(out, fh, ensure_ascii=False, default=str)
        return True
    except Exception as e:
        logger.warning(f"face_index save failed: {e}")
        return False


def _load_face_index() -> int:
    """Load face index from disk. Returns count loaded."""
    if not os.path.exists(_FACE_INDEX_PATH):
        return 0
    try:
        import base64
        with open(_FACE_INDEX_PATH) as fh:
            data = json.load(fh)
        loaded = 0
        for fid, entry in data.items():
            if "_emb_b64" in entry:
                arr = np.frombuffer(
                    base64.b64decode(entry["_emb_b64"]),
                    dtype=entry.get("_emb_dtype", "float32"),
                ).reshape(entry.get("_emb_shape", [-1]))
                entry["embedding"] = arr
                del entry["_emb_b64"], entry["_emb_dtype"], entry["_emb_shape"]
            _FACE_INDEX[fid] = entry
            loaded += 1
        if loaded:
            logger.info(f"[FaceMatch] Loaded {loaded} faces from disk")
        return loaded
    except Exception as e:
        logger.warning(f"face_index load failed: {e}")
        return 0


def _save_persons() -> bool:
    """Persist named persons map to disk."""
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(_PERSON_NAMES_PATH, "w") as fh:
            json.dump({str(k): v for k, v in _PERSON_NAMES.items()}, fh, ensure_ascii=False)
        return True
    except Exception as e:
        logger.warning(f"persons save failed: {e}")
        return False


def _load_persons() -> int:
    """Load persons map from disk. Returns count."""
    if not os.path.exists(_PERSON_NAMES_PATH):
        return 0
    try:
        with open(_PERSON_NAMES_PATH) as fh:
            data = json.load(fh)
        loaded = 0
        for k, v in data.items():
            _PERSON_NAMES[int(k)] = v
            loaded += 1
        return loaded
    except Exception as e:
        logger.warning(f"persons load failed: {e}")
        return 0


def _save_timeline() -> bool:
    """Persist face sighting timeline (capped to 200 last per face)."""
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        out = {fid: sights[-200:] for fid, sights in _FACE_TIMELINE.items()}
        with open(_FACE_TIMELINE_PATH, "w") as fh:
            json.dump(out, fh, ensure_ascii=False, default=str)
        return True
    except Exception as e:
        logger.warning(f"timeline save failed: {e}")
        return False


def _load_timeline() -> int:
    if not os.path.exists(_FACE_TIMELINE_PATH):
        return 0
    try:
        with open(_FACE_TIMELINE_PATH) as fh:
            data = json.load(fh)
        loaded = 0
        for fid, sights in data.items():
            _FACE_TIMELINE[fid] = sights
            loaded += 1
        return loaded
    except Exception:
        return 0


def _save_sessions() -> bool:
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        out = {sid: sorted(list(fids)) for sid, fids in _FACE_SESSIONS.items()}
        with open(_FACE_SESSIONS_PATH, "w") as fh:
            json.dump(out, fh, ensure_ascii=False)
        return True
    except Exception:
        return False


def _load_sessions() -> int:
    if not os.path.exists(_FACE_SESSIONS_PATH):
        return 0
    try:
        with open(_FACE_SESSIONS_PATH) as fh:
            data = json.load(fh)
        loaded = 0
        for sid, fids in data.items():
            _FACE_SESSIONS[sid] = set(fids)
            loaded += 1
        return loaded
    except Exception:
        return 0


def _persist_all() -> None:
    """Save all face-related state to disk (called after each detection)."""
    _save_face_index()
    _save_timeline()
    _save_sessions()
    # Persons saved only on name assignment (avoid disk thrash)


# Auto-load on import
_load_face_index()
_load_persons()
_load_timeline()
_load_sessions()


def _init_logger():
    """Emit backend availability at module import."""
    try:
        backends = []
        if INSIGHTFACE: backends.append("ArcFace-512d")
        if FACE_REC: backends.append("dlib-128d")
        if OPENCV_OK: backends.append("OpenCV-Haar")
        if SKLEARN_OK: backends.append("DBSCAN")
        logger.info(
            f"Module 14 FaceMatch ready — backends: {', '.join(backends) if backends else 'NONE'}"
        )
    except Exception:
        pass


_init_logger()


def _get_exif_gps(pil_img: Image.Image) -> Dict:
    """Extract GPS coords from EXIF (decimal lat/lon)."""
    meta = {}
    try:
        exif = pil_img._getexif()
        if not exif:
            return meta
        gps_info = {}
        for tag_id, val in exif.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            if tag == "GPSInfo":
                for gps_tag_id, gps_val in val.items():
                    gps_tag = ExifTags.GPSTAGS.get(gps_tag_id, gps_tag_id)
                    gps_info[gps_tag] = gps_val
        if not gps_info:
            return meta

        def _to_deg(v):
            d, m, s = float(v[0]), float(v[1]), float(v[2])
            return d + m / 60 + s / 3600

        if "GPSLatitude" in gps_info and "GPSLongitude" in gps_info:
            lat = _to_deg(gps_info["GPSLatitude"])
            lon = _to_deg(gps_info["GPSLongitude"])
            if gps_info.get("GPSLatitudeRef") == "S":
                lat = -lat
            if gps_info.get("GPSLongitudeRef") == "W":
                lon = -lon
            meta["lat"] = lat
            meta["lon"] = lon
    except Exception:
        pass
    return meta


def _get_exif_meta(pil_img: Image.Image) -> Dict:
    """Extract camera/timestamp metadata from EXIF."""
    meta = {}
    try:
        exif = pil_img._getexif()
        if not exif:
            return meta
        wanted = {"Make", "Model", "DateTime", "DateTimeOriginal",
                  "Software", "LensModel", "ISOSpeedRatings", "FNumber",
                  "ExposureTime", "FocalLength", "Artist", "Copyright"}
        for tag_id, val in exif.items():
            tag = ExifTags.TAGS.get(tag_id, tag_id)
            if tag in wanted:
                if isinstance(val, str):
                    meta[tag.lower()] = val.strip()
                elif isinstance(val, bytes):
                    try:
                        meta[tag.lower()] = val.decode("utf-8", "ignore").strip()
                    except Exception:
                        pass
                elif isinstance(val, (int, float)):
                    meta[tag.lower()] = val
                elif isinstance(val, tuple) and len(val) == 2:
                    meta[tag.lower()] = f"{val[0]}/{val[1]}"
    except Exception:
        pass
    return meta


def _phash_int(image: Image.Image, hash_size: int = 8) -> int:
    """Difference hash (dHash) - 64 bits, fast, robust to scaling."""
    image = image.convert("L").resize((hash_size + 1, hash_size), Image.LANCZOS)
    pixels = list(image.getdata())
    diff = []
    for row in range(hash_size):
        offset = row * (hash_size + 1)
        for col in range(hash_size):
            diff.append(pixels[offset + col] > pixels[offset + col + 1])
    h = 0
    for v in diff:
        h = (h << 1) | int(v)
    return h


def _hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


class FaceMatch(OSINTModule):
    module_name = "FaceMatch"
    module_icon = "🧬👤"
    module_description = "Reconnaissance faciale ArcFace 512-d + EXIF GPS + clustering DBSCAN"
    input_type = "image"
    output_types = ["face", "gps", "exif", "camera", "avatar", "face_cluster"]
    api_requirements = []
    needs_internet = False

    _analyzer = None
    _analyzer_init_failed = False

    @classmethod
    def _get_analyzer(cls):
        if cls._analyzer is not None:
            return cls._analyzer
        if cls._analyzer_init_failed or not INSIGHTFACE:
            return None
        try:
            a = FaceAnalysis(name="buffalo_l",
                             providers=["CPUExecutionProvider"])
            a.prepare(ctx_id=0, det_size=(640, 640))
            cls._analyzer = a
            return a
        except Exception:
            cls._analyzer_init_failed = True
            return None

    def execute(self, entity: Dict) -> ModuleResult:
        t0 = time.time()
        r = ModuleResult()
        val = (entity.get("value") or "").strip()
        meta = entity.get("metadata") or {}
        etype = entity.get("type", "")
        source_url = meta.get("source_url") or val

        img_bytes = self._fetch_image(val, meta)
        if not img_bytes:
            r.errors.append("Could not fetch image")
            r.status = STATUS_FAILED
            r.execution_time_ms = (time.time() - t0) * 1000
            return r

        try:
            pil = Image.open(io.BytesIO(img_bytes))
            pil.load()
            if pil.mode != "RGB":
                pil = pil.convert("RGB")
        except Exception as e:
            r.errors.append(f"Image decode failed: {e}")
            r.status = STATUS_FAILED
            r.execution_time_ms = (time.time() - t0) * 1000
            return r

        # 1) EXIF: GPS + camera + datetime
        gps = _get_exif_gps(pil)
        exif_m = _get_exif_meta(pil)

        if gps.get("lat") is not None:
            r.entities_found.append(self._new_entity(
                "gps", f"{gps['lat']:.6f},{gps['lon']:.6f}",
                source="facematch/exif_gps",
                confidence=0.97, status=STATUS_VERIFIED,
                metadata={"lat": gps["lat"], "lon": gps["lon"],
                          "source_image": source_url,
                          "precision": "exif_native"},
                source_url=source_url))
            r.sources_hit.append("exif_gps")

        cam_make = (exif_m.get("make") or "").strip()
        cam_model = (exif_m.get("model") or "").strip()
        cam_str = " ".join(filter(None, [cam_make, cam_model]))
        if cam_str:
            r.entities_found.append(self._new_entity(
                "camera", cam_str,
                source="facematch/exif_camera",
                confidence=0.95, status=STATUS_VERIFIED,
                metadata={"make": cam_make, "model": cam_model,
                          "from_image": source_url, **exif_m},
                source_url=source_url))
            r.sources_hit.append("exif_camera")

        dt = (exif_m.get("datetimeoriginal") or exif_m.get("datetime") or "").strip()
        if dt and dt != "0000:00:00 00:00:00":
            r.entities_found.append(self._new_entity(
                "exif", dt,
                source="facematch/exif_datetime",
                confidence=0.9, status=STATUS_VERIFIED,
                metadata={"datetime": dt, "from_image": source_url, **exif_m},
                source_url=source_url))

        # 2) Face detection + embeddings
        faces = self._detect_and_embed(img_bytes, pil, r)
        if not faces:
            r.warnings.append("No face detected")
            r.execution_time_ms = (time.time() - t0) * 1000
            return r

        r.sources_hit.append(f"face_detection/{len(faces)}_faces")
        r.status = STATUS_VERIFIED

        # 3) Generate face entities + cross-match
        for fdata in faces:
            emb = fdata["embedding"]
            emb_hex = emb.tobytes().hex()
            face_id = f"face_{hashlib.md5(emb_hex.encode()).hexdigest()[:16]}"
            ph = fdata["phash"]
            ph_hex = f"{ph:016x}"
            bbox = fdata["bbox"]

            r.entities_found.append(self._new_entity(
                "face", f"embedding:{face_id}",
                source="facematch/arcface" if fdata["backend"] == "insightface"
                else f"facematch/{fdata['backend']}",
                confidence=0.95 if fdata["backend"] == "insightface" else 0.7,
                status=STATUS_VERIFIED,
                metadata={
                    "embedding_hex": emb_hex,
                    "embedding_dim": len(emb),
                    "phash": ph_hex,
                    "bbox": bbox,
                    "from_image": source_url,
                    "backend": fdata["backend"],
                },
                source_url=source_url))

            # Crop avatar entity (for cross-match with ContentMiner avatars)
            r.entities_found.append(self._new_entity(
                "avatar", f"phash:{ph_hex}",
                source="facematch/face_crop",
                confidence=0.85, status=STATUS_VERIFIED,
                metadata={"phash": ph_hex, "face_id": face_id,
                          "from_image": source_url},
                source_url=source_url))

            # Match against existing face index
            for other_id, other in list(_FACE_INDEX.items()):
                if other_id == face_id:
                    continue
                # Cosine on ArcFace embeddings
                sim = _cosine(emb, other["embedding"])
                # Hamming on pHash (robust)
                ham = _hamming(ph, other["phash"])
                # Combine: if either matches strongly
                if sim >= 0.62 or ham <= 8:
                    weight = max(sim, 1.0 - ham / 64.0)
                    rel_type = "same_face_as" if (sim >= 0.65 or ham <= 5) else "similar_to"
                    r.entities_found.append(self._new_rel(
                        face_id, other_id, rel_type,
                        evidence=f"ArcFace sim={sim:.3f}, pHash ham={ham}",
                        weight=round(weight, 3)))
                    r.sources_hit.append(f"face_match/{other_id[:12]}/{rel_type}")

            _FACE_INDEX[face_id] = {
                "embedding": emb,
                "phash": ph,
                "source": source_url,
                "first_seen": time.time(),
            }
            # Phase 2: timeline + session tracking
            try:
                meta = entity.get("metadata") or {} if isinstance(entity, dict) else {}
                self._record_timeline(face_id, source_url, meta, fdata)
                ses = meta.get("session")
                if ses:
                    _FACE_SESSIONS.setdefault(ses, set()).add(face_id)
            except Exception:
                pass

        # 4) DBSCAN clustering on all known faces (every N runs)
        self._maybe_cluster(r)

        # 5) WebSocket push: face_detected event (real-time UI update)
        try:
            from api.websocket import ws_manager
            for ent in r.entities_found:
                if ent.get("type") == "face":
                    import asyncio
                    payload = {
                        "event": "face_detected",
                        "face_id": ent.get("id"),
                        "source": source_url,
                        "session": meta.get("session", "default"),
                        "confidence": ent.get("confidence", 0.0),
                        "backend": ent.get("metadata", {}).get("backend", "unknown"),
                        "bbox": ent.get("metadata", {}).get("bbox"),
                        "phash": ent.get("metadata", {}).get("phash"),
                        "gps": {"lat": gps.get("lat"), "lon": gps.get("lon")} if gps.get("lat") is not None else None,
                        "timestamp": time.time(),
                    }
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(ws_manager.broadcast_all(payload))
                    except Exception:
                        pass
        except Exception:
            pass

        # 6) Persist state to disk (face_index, timeline, sessions)
        try:
            _persist_all()
        except Exception:
            pass

        r.execution_time_ms = (time.time() - t0) * 1000
        return r

    def _fetch_image(self, val: str, meta: Dict) -> Optional[bytes]:
        if not val:
            return None
        if val.startswith("http://") or val.startswith("https://"):
            r = self.http_get(val, timeout=12)
            if r and r.status_code == 200 and len(r.content) >= 100:
                return r.content
            return None
        if val.startswith("data:image"):
            try:
                import base64
                _, b64 = val.split(",", 1)
                return base64.b64decode(b64)
            except Exception:
                return None
        if os.path.isfile(val):
            try:
                with open(val, "rb") as f:
                    return f.read()
            except Exception:
                return None
        # Try metadata image_url
        for k in ("image_url", "source_url"):
            u = meta.get(k)
            if u and u != val:
                r = self.http_get(u, timeout=12)
                if r and r.status_code == 200 and len(r.content) >= 100:
                    return r.content
        return None

    def _detect_and_embed(self, img_bytes: bytes, pil: Image.Image,
                          r: ModuleResult) -> List[Dict]:
        """Detect faces + compute embeddings. Tries backends in priority order."""

        # Backend 1: InsightFace (best - ArcFace 512-d + RetinaFace)
        analyzer = self._get_analyzer()
        if analyzer and INSIGHTFACE:
            try:
                arr = np.array(pil)
                if OPENCV_OK:
                    arr = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                faces = analyzer.get(arr)
                results = []
                for f in faces:
                    emb = f.normed_embedding.astype(np.float32)
                    bbox = [float(v) for v in f.bbox]
                    x1, y1, x2, y2 = [int(max(0, v)) for v in bbox]
                    x2 = min(x2, pil.width)
                    y2 = min(y2, pil.height)
                    crop = pil.crop((x1, y1, x2, y2)) if x2 > x1 and y2 > y1 else pil
                    ph = _phash_int(crop)
                    results.append({"embedding": emb, "phash": ph,
                                    "bbox": bbox, "backend": "insightface"})
                if results:
                    return results
            except Exception as e:
                r.warnings.append(f"insightface error: {e}")

        # Backend 2: face_recognition (dlib 128-d)
        if FACE_REC:
            try:
                arr = np.array(pil)
                locations = face_recognition.face_locations(arr, model="hog")
                encodings = face_recognition.face_encodings(arr, locations)
                results = []
                for (top, right, bottom, left), enc in zip(locations, encodings):
                    crop = pil.crop((left, top, right, bottom))
                    ph = _phash_int(crop)
                    results.append({
                        "embedding": np.array(enc, dtype=np.float32),
                        "phash": ph,
                        "bbox": [left, top, right, bottom],
                        "backend": "face_recognition",
                    })
                if results:
                    return results
            except Exception as e:
                r.warnings.append(f"face_recognition error: {e}")

        # Backend 3: OpenCV Haar (detection only - no real embedding)
        if OPENCV_OK:
            try:
                arr = np.array(pil.convert("L"))
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                cascade = cv2.CascadeClassifier(cascade_path)
                rects = cascade.detectMultiScale(arr, 1.1, 5, minSize=(30, 30))
                results = []
                for (x, y, w, h) in rects:
                    crop = pil.crop((x, y, x + w, y + h))
                    ph = _phash_int(crop)
                    # Encode pHash as 64-dim vector for cross-match
                    emb = np.array([(ph >> i) & 1 for i in range(64)],
                                   dtype=np.float32)
                    emb = np.concatenate([emb, np.zeros(448, dtype=np.float32)])
                    results.append({"embedding": emb, "phash": ph,
                                    "bbox": [x, y, x + w, y + h],
                                    "backend": "opencv_haar"})
                return results
            except Exception as e:
                r.warnings.append(f"opencv error: {e}")

        return []

    def _record_timeline(self, face_id: str, source_url: str,
                         meta: Dict, fdata: Dict):
        """Record a sighting in the face timeline (in-memory history)."""
        if face_id not in _FACE_TIMELINE:
            _FACE_TIMELINE[face_id] = []
        _FACE_TIMELINE[face_id].append({
            "timestamp": time.time(),
            "source": source_url,
            "session": meta.get("session", "unknown"),
            "backend": fdata.get("backend", "unknown"),
            "bbox": fdata.get("bbox"),
            "age": fdata.get("age"),
            "gender": fdata.get("gender"),
        })
        # Cap history per face
        if len(_FACE_TIMELINE[face_id]) > 100:
            _FACE_TIMELINE[face_id] = _FACE_TIMELINE[face_id][-100:]

    def _maybe_cluster(self, r: ModuleResult):
        """DBSCAN cluster on the in-memory face index periodically."""
        if not SKLEARN_OK:
            return
        if len(_FACE_INDEX) < 4 or len(_FACE_INDEX) % 5 != 0:
            return
        try:
            ids = list(_FACE_INDEX.keys())
            X = np.stack([_FACE_INDEX[i]["embedding"] for i in ids])
            norms = np.linalg.norm(X, axis=1, keepdims=True)
            Xn = X / np.maximum(norms, 1e-9)
            sim = Xn @ Xn.T
            dist = np.clip(1.0 - sim, 0.0, 2.0)
            clustering = DBSCAN(eps=0.45, min_samples=2, metric="precomputed").fit(dist)
            for fid, cid in zip(ids, clustering.labels_):
                if cid < 0:
                    continue
                r.entities_found.append(self._new_entity(
                    "face_cluster", f"cluster_{cid}",
                    source="facematch/dbscan",
                    confidence=0.85, status=STATUS_INFERRED,
                    metadata={"cluster_id": int(cid),
                              "face_id": fid,
                              "cluster_size": int((clustering.labels_ == cid).sum())},
                    source_url=_FACE_INDEX[fid].get("source", "")))
        except Exception:
            pass
"""ImageDeepScan V3 - Image deep analysis - Ghost1o1
Sources: PIL EXIF, perceptual hash, file metadata.
Honest: Reverse image search (TinEye/Yandex/PimEyes) requires API key.
"""
import re, time, hashlib, base64, io
from .base import OSINTModule, ModuleResult, STATUS_VERIFIED, STATUS_FAILED, STATUS_API_REQUIRED
from typing import Dict, List, Any, Optional


class ImageDeepScan(OSINTModule):
    module_name = "ImageDeepScan"
    module_icon = "🖼️"
    module_description = "EXIF + perceptual hash + dimensions (reverse search = API requise)"
    input_type = "image"
    output_types = ["hash", "perceptual_hash", "image_dimensions", "gps", "exif_field"]
    api_requirements = [
        "TINEYE_API_KEY (optionnel)",
        "YANDEX_OAUTH_TOKEN (optionnel)",
        "PIMEYES_API_KEY (optionnel, reconnaissance faciale)",
    ]
    needs_internet = True

    def execute(self, entity: Dict) -> ModuleResult:
        t0 = time.time()
        r = ModuleResult()
        val = entity.get("value", "").strip()
        if not val:
            r.errors.append("Empty")
            r.status = STATUS_FAILED
            r.execution_time_ms = (time.time() - t0) * 1000
            return r

        data = None
        if val.startswith("http"):
            resp = self.http_get(val, timeout=20)
            if resp and resp.status_code == 200:
                data = resp.content
                r.sources_hit.append(f"http_fetch({val[:50]})")
            else:
                r.errors.append(f"Fetch failed: HTTP {resp.status_code if resp else 'no resp'}")
        elif val.startswith("data:") or len(val) > 500:
            try:
                b64 = val.split(",", 1)[1] if val.startswith("data:") else val
                data = base64.b64decode(b64)
            except Exception as e:
                r.errors.append(f"Base64 decode failed: {e}")
        elif val.startswith(("/", "./", "~")):
            try:
                import os
                with open(os.path.expanduser(val), "rb") as f:
                    data = f.read()
            except Exception as e:
                r.errors.append(f"File open failed: {e}")

        if not data:
            r.status = STATUS_FAILED
            r.execution_time_ms = (time.time() - t0) * 1000
            return r

        sha256 = hashlib.sha256(data).hexdigest()
        phash = self._perceptual_hash(data)
        r.entities_found.append(self._new_entity(
            "hash_sha256", sha256, source="crypto",
            confidence=1.0, status=STATUS_VERIFIED,
            metadata={"size_bytes": len(data)}))
        r.entities_found.append(self._new_entity(
            "perceptual_hash", phash, source="perceptual_hash",
            confidence=1.0, status=STATUS_VERIFIED,
            metadata={"algorithm": "avg-luminance-32x32"}))

        try:
            from PIL import Image
            from PIL.ExifTags import TAGS, GPSTAGS
            img = Image.open(io.BytesIO(data))
            r.entities_found.append(self._new_entity(
                "image_dimensions", f"{img.width}x{img.height}",
                source="pil_metadata", confidence=1.0, status=STATUS_VERIFIED,
                metadata={"width": img.width, "height": img.height,
                          "format": img.format, "mode": img.mode}))

            exif = img._getexif() if hasattr(img, "_getexif") else None
            if exif:
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == "GPSInfo" and isinstance(value, dict):
                        gps = {}
                        for k, v in value.items():
                            gps[GPSTAGS.get(k, k)] = v
                        lat = self._dms_to_dd(gps.get("GPSLatitude"))
                        lon = self._dms_to_dd(gps.get("GPSLongitude"))
                        if lat is not None and lon is not None:
                            r.entities_found.append(self._new_entity(
                                "gps", f"{lat},{lon}", source="exif_gps",
                                confidence=1.0, status=STATUS_VERIFIED,
                                metadata={"lat": lat, "lon": lon}))
                    elif isinstance(value, str) and len(value) < 200:
                        if tag in ("Make", "Model", "Software"):
                            r.entities_found.append(self._new_entity(
                                tag.lower(), value, source="exif",
                                confidence=1.0, status=STATUS_VERIFIED))
                        elif tag in ("Artist", "Copyright", "CameraOwnerName", "OwnerName"):
                            r.entities_found.append(self._new_entity(
                                "name", value, source="exif",
                                confidence=0.9, status=STATUS_VERIFIED,
                                metadata={"exif_tag": tag}))
            r.sources_hit.append("PIL + EXIF extraction")
        except ImportError:
            r.warnings.append("pip install Pillow pour EXIF complet")
        except Exception:
            pass

        r.warnings.append(
            "Reverse image search (TinEye/Yandex/PimEyes) REQUIRES API keys. "
            "Pour reconnaissance faciale (PimEyes), compte Pro + clé."
        )
        r.entities_found.append(self._new_entity(
            "reverse_search_status",
            "non_effectue — API key requise",
            source="honest_disclosure",
            confidence=0.0, status=STATUS_API_REQUIRED,
            metadata={"would_call": ["TinEye API", "Yandex Images", "PimEyes API"],
                      "instructions": "Set TINEYE_API_KEY or PIMEYES_API_KEY in env"}))

        r.execution_time_ms = (time.time() - t0) * 1000
        r.raw_data = {"size_bytes": len(data), "phash": phash, "sha256": sha256}
        return r

    def _perceptual_hash(self, data: bytes) -> str:
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(data)).convert("L").resize((32, 32), Image.LANCZOS)
            pixels = list(img.getdata())
            avg = sum(pixels) / len(pixels)
            return "".join("1" if p > avg else "0" for p in pixels)[:64]
        except Exception:
            return "unavailable"

    def _dms_to_dd(self, dms):
        try:
            if not dms:
                return None
            d, m, s = [float(x) for x in dms[:3]]
            return round(d + m / 60 + s / 3600, 6)
        except Exception:
            return None
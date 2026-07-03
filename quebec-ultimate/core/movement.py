"""OSIN CHAIN QUEBEC ULTIMATE — Movement Detector
Ghost1o1 — Détecte les déplacements du sujet dans le temps

Analyse les snapshots footprint pour détecter:
- Changement de localisation (IP, GPS, ville, pays)
- Changement de carrier / opérateur
- Changement d'adresse
- Apparition/disparition de comptes
- Anomalies temporelles (gros changement en peu de temps)
"""
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict


class MovementDetector:
    GEO_TYPES = {"city", "country", "ip", "gps", "address", "asn", "isp", "carrier",
                 "timezone", "region", "postal_code", "area_code"}
    IDENTITY_TYPES = {"email", "username", "name", "phone"}
    PLATFORM_TYPES = {"social_profile", "platform_link", "url"}

    def __init__(self):
        self.anomalies: List[Dict] = []

    def analyze(self, snapshots: List[Dict]) -> Dict:
        if not snapshots:
            return {"error": "no snapshots"}

        sorted_snaps = sorted(snapshots, key=lambda s: s.get("timestamp_unix", 0))

        report = {
            "session_id": sorted_snaps[0].get("session_id"),
            "period": {
                "start": sorted_snaps[0].get("timestamp"),
                "end": sorted_snaps[-1].get("timestamp"),
                "duration_seconds": sorted_snaps[-1].get("timestamp_unix", 0) - sorted_snaps[0].get("timestamp_unix", 0),
                "snapshots_count": len(sorted_snaps),
            },
            "geo_trajectory": [],
            "identity_evolution": [],
            "platform_discoveries": [],
            "anomalies": [],
            "speed_anomaly": None,
            "heatmap": [],
        }

        prev_geo: Dict[str, str] = {}
        prev_id: Dict[str, str] = {}
        seen_platforms: set = set()
        prev_coords: Optional[tuple] = None
        prev_ts: Optional[float] = None

        for i, snap in enumerate(sorted_snaps):
            current_geo = {}
            current_id = {}
            current_platforms = []

            for entity in snap.get("entities", []):
                etype = entity.get("type", "")
                value = entity.get("value", "")
                meta = entity.get("metadata") or {}

                if etype in self.GEO_TYPES:
                    current_geo[etype] = value
                elif etype in self.IDENTITY_TYPES:
                    current_id[etype] = value
                elif etype in self.PLATFORM_TYPES:
                    if value not in seen_platforms:
                        current_platforms.append({
                            "url": value, "type": etype,
                            "source": entity.get("source", ""),
                        })
                        seen_platforms.add(value)

                # Heatmap: any entity with coords (None-safe)
                lat = meta.get("lat")
                lon = meta.get("lon")
                if lat is not None and lon is not None:
                    try:
                        lat_f, lon_f = float(lat), float(lon)
                        if -90 <= lat_f <= 90 and -180 <= lon_f <= 180:
                            report["heatmap"].append({
                                "lat": lat_f,
                                "lon": lon_f,
                                "weight": entity.get("confidence", 0.5),
                                "type": etype,
                                "value": value,
                            })
                    except (ValueError, TypeError):
                        pass

            if i > 0:
                geo_changes = {k: {"from": prev_geo.get(k), "to": v}
                               for k, v in current_geo.items()
                               if prev_geo.get(k) and prev_geo[k] != v}
                id_changes = {k: {"from": prev_id.get(k), "to": v}
                              for k, v in current_id.items()
                              if prev_id.get(k) and prev_id[k] != v}

                if geo_changes:
                    report["geo_trajectory"].append({
                        "step": i,
                        "snapshot_id": snap.get("snapshot_id"),
                        "timestamp": snap.get("timestamp"),
                        "trigger": snap.get("trigger"),
                        "changes": geo_changes,
                        "moved": True,
                    })

                if id_changes:
                    report["identity_evolution"].append({
                        "step": i,
                        "snapshot_id": snap.get("snapshot_id"),
                        "timestamp": snap.get("timestamp"),
                        "trigger": snap.get("trigger"),
                        "changes": id_changes,
                    })

            if current_platforms:
                report["platform_discoveries"].append({
                    "step": i, "snapshot_id": snap.get("snapshot_id"),
                    "timestamp": snap.get("timestamp"),
                    "new_platforms": current_platforms,
                })

            prev_geo = current_geo
            prev_id = current_id

        report["anomalies"] = self._detect_anomalies(report, sorted_snaps)
        report["summary"] = {
            "total_movements": len(report["geo_trajectory"]),
            "total_identity_changes": len(report["identity_evolution"]),
            "total_new_platforms": sum(len(p["new_platforms"]) for p in report["platform_discoveries"]),
            "anomalies_detected": len(report["anomalies"]),
            "unique_locations": len(set(
                (round(h["lat"], 2), round(h["lon"], 2))
                for h in report["heatmap"]
            )),
            "geo_events": len(report["heatmap"]),
        }
        return report

    def _detect_anomalies(self, report, snapshots):
        anomalies = []

        if report["period"]["duration_seconds"] > 0:
            movements = report["geo_trajectory"]
            if len(movements) > 1:
                intervals = []
                for i in range(1, len(movements)):
                    t1 = movements[i - 1].get("timestamp")
                    t2 = movements[i].get("timestamp")
                    if t1 and t2:
                        try:
                            d1 = datetime.fromisoformat(t1.replace("Z", "+00:00"))
                            d2 = datetime.fromisoformat(t2.replace("Z", "+00:00"))
                            intervals.append((d2 - d1).total_seconds())
                        except Exception:
                            continue

                if intervals:
                    avg_interval = sum(intervals) / len(intervals)
                    if avg_interval < 60:
                        anomalies.append({
                            "type": "rapid_location_change",
                            "severity": "high",
                            "description": f"{len(movements)} changements de localisation en {avg_interval:.0f}s en moyenne",
                            "implication": "Possible utilisation de VPN, proxy, ou scraping multi-géo",
                        })

        if len(set(m.get("trigger") for m in report["geo_trajectory"])) == 1 and len(report["geo_trajectory"]) > 3:
            anomalies.append({
                "type": "single_source_geo_data",
                "severity": "medium",
                "description": "Toutes les données géo proviennent du même module/pattern",
                "implication": "Risque de données déduites/non-vérifiées",
            })

        ip_changes = sum(1 for m in report["geo_trajectory"] if "ip" in m.get("changes", {}))
        if ip_changes > 2:
            anomalies.append({
                "type": "multiple_ip_changes",
                "severity": "medium",
                "description": f"{ip_changes} changements d'IP détectés",
                "implication": "Sujet mobile ou multi-points d'accès",
            })

        return anomalies
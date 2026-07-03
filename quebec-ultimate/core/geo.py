"""OSIN CHAIN QUEBEC ULTIMATE — Geo Manager
Ghost1o1 — Enrichissement géographique pour footprint + movement

Transforme les entités en coordonnées exploitables:
- IP         → (lat, lon) via ip-api.com
- Ville      → (lat, lon) via table offline
- Pays       → capitale via table offline
- GPS string → parse direct
- Phone area code → centre géographique NANP
"""
import re
import math
import time
from typing import Dict, Optional, Any
from dataclasses import dataclass
from threading import Lock


@dataclass
class GeoPoint:
    lat: float
    lon: float
    source: str
    confidence: float = 0.9
    label: Optional[str] = None
    entity_id: Optional[str] = None
    timestamp: Optional[float] = None

    def to_dict(self):
        return {
            "lat": self.lat, "lon": self.lon, "source": self.source,
            "confidence": self.confidence, "label": self.label,
            "entity_id": self.entity_id, "timestamp": self.timestamp,
        }


CITY_COORDS = {
    "montreal": (45.5017, -73.5673), "montréal": (45.5017, -73.5673),
    "quebec": (46.8139, -71.2080), "québec": (46.8139, -71.2080),
    "toronto": (43.6532, -79.3832), "vancouver": (49.2827, -123.1207),
    "calgary": (51.0447, -114.0719), "edmonton": (53.5461, -113.4938),
    "ottawa": (45.4215, -75.6972), "winnipeg": (49.8951, -97.1384),
    "halifax": (44.6488, -63.5752), "victoria": (48.4284, -123.3656),
    "saskatoon": (52.1332, -106.6700), "regina": (50.4452, -104.6189),
    "laval": (45.6066, -73.7124), "gatineau": (45.4765, -75.7013),
    "longueuil": (45.5312, -73.5183), "sherbrooke": (45.4040, -71.8929),
    "new york": (40.7128, -74.0060), "los angeles": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298), "houston": (29.7604, -95.3698),
    "phoenix": (33.4484, -112.0740), "philadelphia": (39.9526, -75.1652),
    "san antonio": (29.4241, -98.4936), "san diego": (32.7157, -117.1611),
    "dallas": (32.7767, -96.7970), "austin": (30.2672, -97.7431),
    "miami": (25.7617, -80.1918), "atlanta": (33.7490, -84.3880),
    "boston": (42.3601, -71.0589), "seattle": (47.6062, -122.3321),
    "denver": (39.7392, -104.9903), "washington": (38.9072, -77.0369),
    "ashburn": (39.0438, -77.4874), "mountain view": (37.3861, -122.0839),
    "san francisco": (37.7749, -122.4194),
    "london": (51.5074, -0.1278), "paris": (48.8566, 2.3522),
    "berlin": (52.5200, 13.4050), "madrid": (40.4168, -3.7038),
    "rome": (41.9028, 12.4964), "amsterdam": (52.3676, 4.9041),
    "brussels": (50.8503, 4.3517), "zurich": (47.3769, 8.5417),
    "vienna": (48.2082, 16.3738), "tokyo": (35.6762, 139.6503),
    "beijing": (39.9042, 116.4074), "shanghai": (31.2304, 121.4737),
    "hong kong": (22.3193, 114.1694), "singapore": (1.3521, 103.8198),
    "seoul": (37.5665, 126.9780), "dubai": (25.2048, 55.2708),
    "sydney": (-33.8688, 151.2093), "mexico city": (19.4326, -99.1332),
    "sao paulo": (-23.5505, -46.6333), "cairo": (30.0444, 31.2357),
}

COUNTRY_CAPITALS = {
    "canada": (45.4215, -75.6972, "Ottawa"),
    "united states": (38.9072, -77.0369, "Washington"),
    "france": (48.8566, 2.3522, "Paris"),
    "united kingdom": (51.5074, -0.1278, "London"),
    "germany": (52.5200, 13.4050, "Berlin"),
    "spain": (40.4168, -3.7038, "Madrid"),
    "italy": (41.9028, 12.4964, "Rome"),
    "netherlands": (52.3676, 4.9041, "Amsterdam"),
    "belgium": (50.8503, 4.3517, "Brussels"),
    "switzerland": (46.9481, 7.4474, "Bern"),
    "austria": (48.2082, 16.3738, "Vienna"),
    "japan": (35.6762, 139.6503, "Tokyo"),
    "china": (39.9042, 116.4074, "Beijing"),
    "south korea": (37.5665, 126.9780, "Seoul"),
    "australia": (-35.2809, 149.1300, "Canberra"),
    "brazil": (-15.8267, -47.9218, "Brasilia"),
    "mexico": (19.4326, -99.1332, "Mexico City"),
    "israel": (31.7683, 35.2137, "Jerusalem"),
}

NANP_AREA_COORDS = {
    "514": (45.5017, -73.5673, "Montreal QC"),
    "438": (45.5017, -73.5673, "Montreal QC"),
    "450": (45.5312, -73.5183, "Banlieue MTL"),
    "579": (45.5017, -73.5673, "Montérégie QC"),
    "418": (46.8139, -71.2080, "Québec QC"),
    "581": (46.8139, -71.2080, "Québec QC"),
    "819": (45.4765, -75.7013, "Outaouais QC"),
    "873": (46.8139, -71.2080, "Québec QC"),
    "416": (43.6532, -79.3832, "Toronto ON"),
    "647": (43.6532, -79.3832, "Toronto ON"),
    "437": (43.6532, -79.3832, "Toronto ON"),
    "905": (43.6532, -79.3832, "GTA ON"),
    "613": (45.4215, -75.6972, "Ottawa ON"),
    "604": (49.2827, -123.1207, "Vancouver BC"),
    "778": (49.2827, -123.1207, "Vancouver BC"),
    "403": (51.0447, -114.0719, "Calgary AB"),
    "780": (53.5461, -113.4938, "Edmonton AB"),
    "204": (49.8951, -97.1384, "Winnipeg MB"),
    "902": (44.6488, -63.5752, "Halifax NS"),
    "212": (40.7831, -73.9712, "Manhattan NY"),
    "646": (40.7831, -73.9712, "Manhattan NY"),
    "718": (40.6782, -73.9442, "Brooklyn NY"),
    "213": (34.0522, -118.2437, "Los Angeles CA"),
    "415": (37.7749, -122.4194, "San Francisco CA"),
    "312": (41.8781, -87.6298, "Chicago IL"),
    "305": (25.7617, -80.1918, "Miami FL"),
    "617": (42.3601, -71.0589, "Boston MA"),
}


class GeoManager:
    EARTH_RADIUS_KM = 6371.0

    def __init__(self):
        self._ip_cache: Dict[str, Optional[GeoPoint]] = {}
        self._lock = Lock()
        self._last_request_ts = 0.0
        self._min_request_interval = 0.3

    def _throttle(self):
        elapsed = time.time() - self._last_request_ts
        if elapsed < self._min_request_interval:
            time.sleep(self._min_request_interval - elapsed)
        self._last_request_ts = time.time()

    def city_to_point(self, city):
        c = (city or "").strip().lower()
        if not c:
            return None
        if c in CITY_COORDS:
            lat, lon = CITY_COORDS[c]
            return GeoPoint(lat=lat, lon=lon, source="city_table", confidence=0.92, label=city)
        for k, (lat, lon) in CITY_COORDS.items():
            if k in c or c in k:
                return GeoPoint(lat=lat, lon=lon, source="city_table_partial", confidence=0.7, label=city)
        return None

    def country_to_point(self, country):
        c = (country or "").strip().lower()
        if c in COUNTRY_CAPITALS:
            lat, lon, name = COUNTRY_CAPITALS[c]
            return GeoPoint(lat=lat, lon=lon, source="country_capital", confidence=0.75, label=f"{name} ({country})")
        return None

    def area_code_to_point(self, area):
        a = (area or "").strip()
        if a in NANP_AREA_COORDS:
            lat, lon, label = NANP_AREA_COORDS[a]
            return GeoPoint(lat=lat, lon=lon, source="nanp_area_code", confidence=0.8, label=f"Area {a} ({label})")
        return None

    def gps_string_to_point(self, gps):
        if not gps or "," not in gps:
            return None
        try:
            parts = [p.strip() for p in gps.split(",", 1)]
            lat = float(parts[0])
            lon = float(parts[1])
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return GeoPoint(lat=lat, lon=lon, source="gps_parsed", confidence=1.0, label=gps)
        except (ValueError, IndexError):
            pass
        return None

    def ip_to_point(self, ip, force_refresh=False):
        with self._lock:
            if not force_refresh and ip in self._ip_cache:
                return self._ip_cache[ip]

        self._throttle()
        try:
            import requests
            r = requests.get(
                f"http://ip-api.com/json/{ip}",
                params={"fields": "status,country,regionName,city,lat,lon,timezone,isp,org,as,query"},
                timeout=8,
            )
            if r.status_code == 200:
                d = r.json()
                if d.get("status") == "success":
                    p = GeoPoint(
                        lat=float(d.get("lat", 0)),
                        lon=float(d.get("lon", 0)),
                        source="ip-api.com",
                        confidence=0.95,
                        label=f"{d.get('city', '')}, {d.get('regionName', '')}, {d.get('country', '')}",
                    )
                    with self._lock:
                        self._ip_cache[ip] = p
                    return p
        except Exception:
            pass

        with self._lock:
            self._ip_cache[ip] = None
        return None

    def enrich_entity(self, entity):
        etype = (entity.get("type") or "").lower()
        value = (entity.get("value") or "").strip()
        if not value:
            return None

        point = None
        if etype == "ip":
            point = self.ip_to_point(value)
        elif etype == "city":
            point = self.city_to_point(value)
        elif etype == "country":
            point = self.country_to_point(value)
        elif etype == "gps":
            point = self.gps_string_to_point(value)
        elif etype == "area_code":
            point = self.area_code_to_point(value)
        elif etype in ("asn", "isp"):
            meta = entity.get("metadata") or {}
            if meta.get("lat") and meta.get("lon"):
                point = GeoPoint(
                    lat=float(meta["lat"]), lon=float(meta["lon"]),
                    source="asn_metadata", confidence=0.7, label=value,
                )
            else:
                city = meta.get("city") or meta.get("country")
                if city:
                    point = self.city_to_point(city) or self.country_to_point(city)
        elif etype == "phone":
            digits = re.sub(r"\D", "", value)
            if digits.startswith("1") and len(digits) >= 11:
                point = self.area_code_to_point(digits[1:4])
            elif len(digits) >= 10:
                point = self.area_code_to_point(digits[:3])

        if point:
            point.entity_id = entity.get("id")
            point.timestamp = time.time()
            meta = entity.get("metadata") or {}
            meta["lat"] = point.lat
            meta["lon"] = point.lon
            meta["geo_source"] = point.source
            meta["geo_confidence"] = point.confidence
            entity["metadata"] = meta

        return point

    @staticmethod
    def haversine_km(p1, p2):
        lat1, lon1 = math.radians(p1.lat), math.radians(p1.lon)
        lat2, lon2 = math.radians(p2.lat), math.radians(p2.lon)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return GeoManager.EARTH_RADIUS_KM * c

    @staticmethod
    def bearing_deg(p1, p2):
        lat1, lon1 = math.radians(p1.lat), math.radians(p1.lon)
        lat2, lon2 = math.radians(p2.lat), math.radians(p2.lon)
        dlon = lon2 - lon1
        x = math.sin(dlon) * math.cos(lat2)
        y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
        b = math.degrees(math.atan2(x, y))
        return (b + 360) % 360

    @staticmethod
    def bearing_to_compass(bearing):
        dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        idx = int((bearing + 22.5) / 45) % 8
        return dirs[idx]

    def speed_kmh(self, p1, p2):
        if not p1.timestamp or not p2.timestamp:
            return None
        dt = abs(p2.timestamp - p1.timestamp)
        if dt < 1:
            return None
        d = self.haversine_km(p1, p2)
        return d / (dt / 3600.0)
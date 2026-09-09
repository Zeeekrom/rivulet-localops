import json
import math
from pathlib import Path

from .models import AssetMatch, Coordinates


SOURCE_NAME = "City of Hobart ASSET Litter Bins public ArcGIS layer"


def _haversine_metres(a: Coordinates, latitude: float, longitude: float) -> float:
    radius = 6_371_000.0
    lat1 = math.radians(a.latitude)
    lat2 = math.radians(latitude)
    delta_lat = lat2 - lat1
    delta_lon = math.radians(longitude - a.longitude)
    hav = math.sin(delta_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(delta_lon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(hav), math.sqrt(1 - hav))


class AssetRepository:
    def __init__(self, path: Path):
        self.path = path
        self.features: list[dict] = []
        if path.exists():
            payload = json.loads(path.read_text(encoding="utf-8"))
            self.features = payload.get("features", [])

    @property
    def count(self) -> int:
        return len(self.features)

    def nearest_litter_bin(self, coordinates: Coordinates, max_distance_metres: float = 500) -> AssetMatch | None:
        nearest: tuple[float, dict] | None = None
        for feature in self.features:
            geometry = feature.get("geometry") or {}
            point = geometry.get("coordinates")
            if geometry.get("type") != "Point" or not point or len(point) < 2:
                continue
            longitude, latitude = float(point[0]), float(point[1])
            distance = _haversine_metres(coordinates, latitude, longitude)
            if nearest is None or distance < nearest[0]:
                nearest = (distance, feature)

        if nearest is None or nearest[0] > max_distance_metres:
            return None

        distance, feature = nearest
        longitude, latitude = feature["geometry"]["coordinates"][:2]
        properties = feature.get("properties") or {}
        source_id = properties.get("GlobalID") or properties.get("OBJECTID") or feature.get("id")
        return AssetMatch(
            asset_type="litter_bin",
            source_id=str(source_id),
            description=properties.get("Description"),
            latitude=float(latitude),
            longitude=float(longitude),
            distance_metres=round(distance, 1),
            source=SOURCE_NAME,
        )

"""Pure-Python geodesy helpers (no pyproj needed).

WGS84 -> UTM forward projection with the Krueger series (Karney 2011),
accurate to well under 1 mm inside a UTM zone.
"""
import math

from .config import CHIP_SIZE, PIXEL_SIZE

_A = 6378137.0
_F = 1 / 298.257223563
_N = _F / (2 - _F)
_AA = _A / (1 + _N) * (1 + _N**2 / 4 + _N**4 / 64)
_ALPHA = (
    _N / 2 - 2 / 3 * _N**2 + 5 / 16 * _N**3,
    13 / 48 * _N**2 - 3 / 5 * _N**3,
    61 / 240 * _N**3,
)
_K0 = 0.9996


def utm_zone(lon):
    return int((lon + 180) // 6) % 60 + 1


def utm_epsg(lat, lon):
    return (32600 if lat >= 0 else 32700) + utm_zone(lon)


def latlon_to_utm(lat, lon, zone=None):
    """Return (easting, northing, epsg) for a WGS84 point."""
    zone = zone or utm_zone(lon)
    lon0 = math.radians(zone * 6 - 183)
    phi, lam = math.radians(lat), math.radians(lon) - lon0
    c = 2 * math.sqrt(_N) / (1 + _N)
    t = math.sinh(math.atanh(math.sin(phi)) - c * math.atanh(c * math.sin(phi)))
    xi = math.atan2(t, math.cos(lam))
    eta = math.atanh(math.sin(lam) / math.sqrt(1 + t * t))
    e = eta + sum(a * math.cos(2 * j * xi) * math.sinh(2 * j * eta) for j, a in enumerate(_ALPHA, 1))
    n = xi + sum(a * math.sin(2 * j * xi) * math.cosh(2 * j * eta) for j, a in enumerate(_ALPHA, 1))
    easting = 500000.0 + _K0 * _AA * e
    northing = _K0 * _AA * n + (0.0 if lat >= 0 else 10000000.0)
    epsg = (32600 if lat >= 0 else 32700) + zone
    return easting, northing, epsg


def make_grid(lat, lon, size=CHIP_SIZE, scale=PIXEL_SIZE):
    """Pixel grid (UTM, north-up) centred on lat/lon, snapped to the 10 m lattice.

    Returns a dict usable as `grid` in ee.data.computePixels, plus the
    lon/lat bounding box for filterBounds.
    """
    x, y, epsg = latlon_to_utm(lat, lon)
    half = size * scale / 2
    x0 = round((x - half) / scale) * scale
    y0 = round((y + half) / scale) * scale
    grid = {
        "dimensions": {"width": size, "height": size},
        "affineTransform": {
            "scaleX": scale, "shearX": 0, "translateX": x0,
            "shearY": 0, "scaleY": -scale, "translateY": y0,
        },
        "crsCode": f"EPSG:{epsg}",
    }
    # generous lon/lat box (chip + ~1 km margin) for collection filtering
    dlat = (half + 1000) / 111_320
    dlon = dlat / max(math.cos(math.radians(lat)), 0.05)
    bbox = [lon - dlon, lat - dlat, lon + dlon, lat + dlat]
    return grid, bbox

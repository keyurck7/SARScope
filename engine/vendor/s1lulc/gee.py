"""Earth Engine side: Sentinel-1 monthly composites and Dynamic World monthly labels.

The SAME functions are used to build the training set and to run the prototype,
so preprocessing at training time and at inference time is identical.

Sentinel-1 chain (per scene, then per month):
  1. COPERNICUS/S1_GRD_FLOAT: calibrated sigma0 (linear), thermal noise removed,
     orbit-corrected and terrain-corrected (geometric) by Google with SNAP.
  2. Swath-edge mask (incidence angle 31-45 deg) against border noise.
  3. Radiometric terrain flattening, volume model (Vollrath et al. 2020),
     sigma0 -> gamma0_flat, with layover/shadow masked.
  4. Monthly mean in LINEAR power (multi-temporal speckle reduction).
  Spatial Lee filtering and dB conversion happen locally (preprocess.py).
"""
import math
import time
import datetime as dt

import ee
import numpy as np

from .config import (
    S1_COLLECTION, DW_COLLECTION, DEM_COLLECTION, WORLDCOVER, CLASSES,
    ANGLE_MIN, ANGLE_MAX, NODATA, N_MONTHS, HIGH_VOLUME_URL,
)

_DEG = math.pi / 180


def init(project, high_volume=True):
    """Initialise Earth Engine. Run ee.Authenticate() once per machine before this."""
    if high_volume:
        ee.Initialize(project=project, opt_url=HIGH_VOLUME_URL)
    else:
        ee.Initialize(project=project)


def month_windows(start_year, start_month, n=N_MONTHS):
    """[(start, end, 'YYYY-MM'), ...] for n consecutive calendar months."""
    out = []
    y, m = start_year, start_month
    for _ in range(n):
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        out.append((f"{y:04d}-{m:02d}-01", f"{ny:04d}-{nm:02d}-01", f"{y:04d}-{m:02d}"))
        y, m = ny, nm
    return out


def dem():
    col = ee.ImageCollection(DEM_COLLECTION).select("DEM")
    return col.mosaic().setDefaultProjection(col.first().projection())


# --------------------------------------------------------------------------- S1
def _edge_mask(img):
    angle = img.select("angle")
    return img.updateMask(angle.gt(ANGLE_MIN).And(angle.lt(ANGLE_MAX)))


def _terrain_flatten(img, elevation, heading_region):
    """Angular-based radiometric slope correction, volume model (Vollrath et al. 2020)."""
    theta_i = img.select("angle").multiply(_DEG)
    # Look direction from the incidence-angle gradient, averaged over the WHOLE scene
    # footprint (as in Vollrath et al.). A small local region can fall on the masked
    # scene border and return null, which failed 90 of 1,300 chips in the first run.
    heading = (ee.Terrain.aspect(img.select("angle"))
               .reduceRegion(ee.Reducer.mean(), img.geometry(), 1000, maxPixels=1e9, bestEffort=True)
               .get("aspect"))
    phi_i = ee.Image.constant(ee.Number(ee.Algorithms.If(heading, heading, 0))).multiply(_DEG)
    valid_heading = ee.Number(ee.Algorithms.If(heading, 1, 0))

    alpha_s = ee.Terrain.slope(elevation).multiply(_DEG)
    phi_s = ee.Terrain.aspect(elevation).multiply(_DEG)
    phi_r = phi_i.subtract(phi_s)
    alpha_r = alpha_s.tan().multiply(phi_r.cos()).atan()      # range-direction slope
    ninety = ee.Image.constant(90 * _DEG)

    gamma0 = img.select(["VV", "VH"]).divide(theta_i.cos())
    scf = (ninety.subtract(theta_i).add(alpha_r).tan()
           .divide(ninety.subtract(theta_i).tan()))
    flat = gamma0.divide(scf)

    not_layover = alpha_r.lt(theta_i)
    not_shadow = alpha_r.gt(ninety.subtract(theta_i).multiply(-1))
    # if no heading could be computed at all, drop the scene rather than mis-correct it
    keep = not_layover.And(not_shadow).And(ee.Image.constant(valid_heading))
    out = flat.updateMask(keep).addBands(img.select("angle"))
    return ee.Image(out.copyProperties(img, ["system:time_start"]))


def s1_collection(bbox_geom, start, end):
    return (ee.ImageCollection(S1_COLLECTION)
            .filterBounds(bbox_geom)
            .filterDate(start, end)
            .filter(ee.Filter.eq("instrumentMode", "IW"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VV"))
            .filter(ee.Filter.listContains("transmitterReceiverPolarisation", "VH")))


def s1_month(bbox_geom, heading_region, start, end, elevation, flatten=True):
    """One monthly composite: bands VV, VH (linear gamma0 / sigma0), n (scene count)."""
    col = s1_collection(bbox_geom, start, end)
    if flatten:  # flatten first (heading needs the full, unmasked angle band), then mask edges
        col = col.map(lambda im: _terrain_flatten(im, elevation, heading_region))
    col = col.map(_edge_mask).select(["VV", "VH"])
    # an all-masked dummy keeps empty months valid (output = NODATA, n = 0)
    dummy = ee.ImageCollection([ee.Image.constant([0, 0]).rename(["VV", "VH"]).toFloat().updateMask(0)])
    col = col.merge(dummy)
    mean = col.mean().unmask(NODATA)
    n = col.select("VV").count().rename("n").unmask(0)
    return mean.addBands(n).toFloat()


def s1_stack(bbox, start_year, start_month, flatten=True, n_months=N_MONTHS):
    """12-month stack as ONE image: VV_00, VH_00, n_00, ..., VV_11, VH_11, n_11."""
    geom = ee.Geometry.Rectangle(bbox)
    heading_region = geom.centroid().buffer(20000)
    elevation = dem()
    imgs = []
    for i, (s, e, _) in enumerate(month_windows(start_year, start_month, n_months)):
        imgs.append(s1_month(geom, heading_region, s, e, elevation, flatten)
                    .rename([f"VV_{i:02d}", f"VH_{i:02d}", f"n_{i:02d}"]))
    return ee.Image.cat(imgs)


# --------------------------------------------------------------- Dynamic World
def dw_month(bbox_geom, start, end):
    """Monthly label = argmax of the MEAN class probability over all clear S2 looks.

    Bands: label (0-8, 255 = no observation), conf (max mean prob x 100), n (looks).
    """
    col = ee.ImageCollection(DW_COLLECTION).filterBounds(bbox_geom).filterDate(start, end).select(CLASSES)
    dummy = ee.ImageCollection([ee.Image.constant([0] * len(CLASSES)).rename(CLASSES).toFloat().updateMask(0)])
    col = col.merge(dummy)
    probs = col.mean()
    label = probs.toArray().arrayArgmax().arrayGet([0]).rename("label").unmask(255)
    conf = probs.reduce(ee.Reducer.max()).multiply(100).rename("conf").unmask(0)
    n = col.select("water").count().rename("n").unmask(0)
    return ee.Image.cat([label, conf, n]).toUint8()


def dw_stack(bbox, start_year, start_month, n_months=N_MONTHS):
    geom = ee.Geometry.Rectangle(bbox)
    imgs = [dw_month(geom, s, e).rename([f"label_{i:02d}", f"conf_{i:02d}", f"n_{i:02d}"])
            for i, (s, e, _) in enumerate(month_windows(start_year, start_month, n_months))]
    return ee.Image.cat(imgs)


def worldcover():
    """ESA WorldCover 2021 (independent reference for the case study only)."""
    return ee.ImageCollection(WORLDCOVER).first().select("Map").toUint8()


# ------------------------------------------------------------------ download
def fetch(image, grid, retries=6):
    """Download an ee.Image on a pixel grid -> (bands, H, W) array, band names."""
    delay = 4
    for attempt in range(retries):
        try:
            arr = ee.data.computePixels({
                "expression": image,
                "fileFormat": "NUMPY_NDARRAY",
                "grid": grid,
            })
            names = list(arr.dtype.names)
            return np.stack([arr[n] for n in names], 0), names
        except Exception as e:  # quota / transient errors: back off and retry
            msg = str(e)
            if attempt == retries - 1 or "not found" in msg.lower() or "invalid" in msg.lower():
                raise
            time.sleep(delay)
            delay = min(delay * 2, 120)

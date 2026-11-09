"""Project-wide constants: classes, colours, data sources, chip geometry."""

# --- Data sources (Google Earth Engine) -------------------------------------
S1_COLLECTION = "COPERNICUS/S1_GRD_FLOAT"   # linear power, calibrated, thermal-noise removed, GTC
DW_COLLECTION = "GOOGLE/DYNAMICWORLD/V1"    # monthly training labels (Sentinel-2 derived)
WORLDCOVER = "ESA/WorldCover/v200"          # 2021 map: INDEPENDENT check only, never used in training
DEM_COLLECTION = "COPERNICUS/DEM/GLO30_2024_1"  # global 30 m DEM (2024 release) for terrain flattening

HIGH_VOLUME_URL = "https://earthengine-highvolume.googleapis.com"

# --- Classes: Dynamic World's 9 classes, no merging -------------------------
CLASSES = [
    "water", "trees", "grass", "flooded_vegetation", "crops",
    "shrub_and_scrub", "built", "bare", "snow_and_ice",
]
NUM_CLASSES = len(CLASSES)
IGNORE_INDEX = 255

# Official Dynamic World palette
CLASS_COLORS = [
    "#419BDF", "#397D49", "#88B053", "#7A87C6", "#E49635",
    "#DFC35A", "#C4281B", "#A59B8F", "#B39FE1",
]

# --- Chip geometry -----------------------------------------------------------
CHIP_SIZE = 256        # pixels
PIXEL_SIZE = 10        # metres -> a chip is 2.56 km x 2.56 km
N_MONTHS = 12

# --- SAR preprocessing -------------------------------------------------------
ANGLE_MIN, ANGLE_MAX = 31.0, 45.0   # mask swath edges (border noise)
NODATA = -9999.0
GRD_ENL = 4.4                       # equivalent number of looks, IW GRD high-res

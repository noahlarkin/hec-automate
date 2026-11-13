import os
# ==========================================================================
# Configuration files
# ==========================================================================
#
# BASE_DIR is intentionally hardcoded. This program must always be
# installed at this exact path -- installation instructions require it.
# Both app.exe and run_pipeline.exe are built against this same fixed
# path, so they always agree on where the shared data/models/archive
# folders live, regardless of where app.exe itself is run from.

BASE_DIR = r"C:\hec-automate"

DATA_DIR     = os.path.join(BASE_DIR, "data")
TEMPLATE_DIR = os.path.join(DATA_DIR, "templates")
INPUT_DIR    = os.path.join(DATA_DIR, "input")

MODEL_PATH_CSV  = os.path.join(INPUT_DIR, "CreekLocations_LowerSilver.csv")
BATCH_SPECS_CSV = os.path.join(INPUT_DIR, "HECSPECS_LowerSilver.csv")

HECSPECS_TEMPLATE_CSV       = os.path.join(TEMPLATE_DIR, "HECSPECS_TEMPLATE.csv")

NVAR_LIST = [1, 2, 4, 5, 9, 10, 14, 29, 32, 47, 62, 150, 151, 152, 153,
             196, 199, 200, 201, 202, 205, 206, 207, 226]

MAX_RUNS = None
RAS_COM_PROGID = "RAS60.HECRASController"
RIVER_ID = 1
REACH_ID = 1  # confirmed single-reach for every model tested so far; revisit if a multi-reach model is added
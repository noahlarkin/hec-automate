import os
# ==========================================================================
# EXAMPLE CONFIG FILES
# ==========================================================================

BASE_DIR = r"C:\EXAMPLE_DIRECTORY"


MODEL_DIR = os.path.join(BASE_DIR, "models")
DATA_DIR      = os.path.join(BASE_DIR, "data")
TEMPLATE_DIR  = os.path.join(DATA_DIR, "templates")
INPUT_DIR     = os.path.join(DATA_DIR, "input")
ARCHIVE_DIR   = os.path.join(DATA_DIR, "archive")

HECSPECS_TEMPLATE_CSV       = os.path.join(TEMPLATE_DIR, "HECSPECS_TEMPLATE.csv")
CREEKLOCATIONS_TEMPLATE_CSV = os.path.join(TEMPLATE_DIR, "CreekLocations_TEMPLATE.csv")
HECSPECS_INPUT_CSV          = os.path.join(INPUT_DIR, "HECSPECS_input.csv")
CREEKLOCATIONS_INPUT_CSV    = os.path.join(INPUT_DIR, "CreekLocations_input.csv")

NVAR_LIST = []

MAX_RUNS = None
RAS_COM_PROG = "RAS60.HECRASController"
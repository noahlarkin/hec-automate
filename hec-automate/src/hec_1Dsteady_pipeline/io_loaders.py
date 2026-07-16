import csv

# ============================================================
# Read project locations CSV
# Columns: CREEK_NAME, PRJ_PATH, BASE_GEOM_PATH, BASE_FLOW_PATH, BASE_PLAN_PATH
# ============================================================
creek_locations = {}
with open(CREEKLOCACTIONS_INPUT_CSV) as file:
    reader = csv.DictReader(file)
    for row in reader:
        creek_name = row['CREEK_NAME'].strip()
        creek_locations[creek_name] = {
            'prj_path': row['PRJ_PATH'].strip(),
            'base_geom_path': row['BASE_GEOM_PATH'].strip(),
            'base_flow_path': row['BASE_FLOW_PATH'].strip(),
            'base_plan_path': row['BASE_PLAN_PATH'].strip()
        }
return creek_locations

# ============================================================
# Load all reach specs from engineer input CSV
# ============================================================
reach_specs = []
with open(HECSPECS_INPUT_CSV) as specs:
    reader = csv.DictReader(specs)
    for row in reader:
        reach_specs.append({
            'creek_name': row['CREEK_NAME'].strip(),
            'mg_reach_name': row['CREEK_REACH'].strip(),
            'ds_station': float(row['DS_STATION']),
            'us_station': float(row['US_STATION']),
            'rep_xs_station': row['REP_XS_STATION'].strip(),
            'los_profile_index': int(row['LOS_PROFILE_INDEX']),
            'top_of_bank': float(row['TOP_OF_BANK']),
            'n_values': [
                float(row['N_LOW']),
                float(row['N_MID1']),
                float(row['N_MID2']),
                float(row['N_HIGH'])
            ],
            'sed_depths': [
                float(row['SED_0']),
                float(row['SED_1']),
                float(row['SED_2']),
                float(row['SED_3'])
            ]
        })
return reach_specs

print(f"Loaded {len(reach_specs)} reaches from HECSPECS.")
import csv

SEDIMENT_COLUMNS = ['SED_0', 'SED_1', 'SED_2', 'SED_3', 'SED_4', 'SED_5']
ROUGHNESS_COLUMNS = ['N_0', 'N_1', 'N_2', 'N_3', 'N_4', 'N_5']


def load_creek_locations(csv_path):
    creek_locations = {}
    with open(csv_path) as file:
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


def load_reach_specs(csv_path):
    reach_specs = []
    with open(csv_path) as specs:
        reader = csv.DictReader(specs)
        for row in reader:
            sed_depths = []
            for col in SEDIMENT_COLUMNS:
                val = row.get(col, '').strip()
                if val:
                    sed_depths.append(float(val))

            if not sed_depths:
                raise ValueError(
                    f"Reach '{row.get('CREEK_REACH', '?')}': no sediment depth values "
                    f"filled in ({', '.join(SEDIMENT_COLUMNS)}). At least one is required."
                )

            n_values = []
            for col in ROUGHNESS_COLUMNS:
                val = row.get(col, '').strip()
                if val:
                    n_values.append(float(val))

            if not n_values:
                raise ValueError(
                    f"Reach '{row.get('CREEK_REACH', '?')}': no roughness values "
                    f"filled in ({', '.join(ROUGHNESS_COLUMNS)}). At least one is required."
                )

            reach_specs.append({
                'creek_name': row['CREEK_NAME'].strip(),
                'mg_reach_name': row['CREEK_REACH'].strip(),
                'ds_station': float(row['DS_STATION']),
                'us_station': float(row['US_STATION']),
                'rep_xs_station': row['REP_XS_STATION'].strip(),
                'top_of_bank': float(row['TOP_OF_BANK']),
                'n_values': n_values,
                'sed_depths': sed_depths
            })
    return reach_specs
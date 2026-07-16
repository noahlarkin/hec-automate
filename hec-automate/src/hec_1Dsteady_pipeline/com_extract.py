import csv
import os


def extract_and_write_scenario_table(RC, river_id, plan_title, batch_dir,
                                      profile_index, nvar_list, var_names):
    """
    Uses Output_ReachOutput to get all cross section values for each
    variable in one call per variable per reach. Writes one CSV per
    scenario with River_Sta as rows and variable name columns.
    """
    def col_name(nvar):
        try:
            return var_names[nvar - 1].strip()
        except (IndexError, TypeError):
            return f'nVar_{nvar}'

    result = RC.Output_GetReaches(river_id, 0, None)
    if not isinstance(result, tuple) or len(result) < 3:
        print(f"      WARNING: Unexpected Output_GetReaches result, skipping export.")
        return

    n_reaches = result[1]

    station_data = {}
    station_order = []

    for reach_id in range(1, n_reaches + 1):
        first_result = RC.Output_ReachOutput(
            river_id, reach_id, profile_index, nvar_list[0], 0, None, None, None
        )
        if not isinstance(first_result, tuple) or len(first_result) < 8:
            print(f"      WARNING: Unexpected Output_ReachOutput result for reach {reach_id}.")
            continue

        n_xs = first_result[4]
        rs_strings = first_result[5]
        values_first = first_result[7]

        for i in range(n_xs):
            rs_label = rs_strings[i].strip().split()[-1].strip()
            if rs_label not in station_data:
                station_data[rs_label] = {}
                station_order.append(rs_label)
            station_data[rs_label][col_name(nvar_list[0])] = values_first[i]

        for nvar in nvar_list[1:]:
            var_result = RC.Output_ReachOutput(
                river_id, reach_id, profile_index, nvar, 0, None, None, None
            )
            if not isinstance(var_result, tuple) or len(var_result) < 8:
                continue
            values = var_result[7]
            for i in range(n_xs):
                rs_label = rs_strings[i].strip().split()[-1].strip()
                station_data[rs_label][col_name(nvar)] = values[i]

    if not station_data:
        print(f"      WARNING: No data collected for {plan_title}, skipping CSV write.")
        return

    fieldnames = ['River_Sta'] + [col_name(nvar) for nvar in nvar_list]
    csv_path = os.path.join(batch_dir, f"{plan_title}.csv")

    with open(csv_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rs_label in station_order:
            row = {'River_Sta': rs_label}
            row.update(station_data[rs_label])
            writer.writerow(row)

    print(f"      Table written to: {csv_path}")
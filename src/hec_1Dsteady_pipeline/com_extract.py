import csv
import os
from hec_1Dsteady_pipeline.flow_parser import sanitize_for_filename

# Every original NVAR_LIST code, resolved to its real HEC-RAS variable
# name (confirmed via Output_Variables). Output_NodeOutput takes the raw
# code directly, so all 24 columns are available this way.
NVAR_MAP = {
    "Profile":         1,   # not queried -- filled with profile_name directly
    "W.S. Elev":       2,
    "Max Chl Dpth":    4,
    "Min Ch El":       5,
    "Q Total":         9,
    "Flow Area":       10,
    "W.P. Total":      14,
    "Top Wdth Act":    29,
    "Area":            32,
    "Mann Comp":       47,
    "Top Width":       62,
    "Shear Total":     150,
    "Shear LOB":       151,
    "Shear Chan":      152,
    "Shear ROB":       153,
    "Invert Slope":    196,
    "L. Freeboard":    199,
    "R. Freeboard":    200,
    "Levee El Left":   201,
    "Levee El Right":  202,
    "L. Levee Frbrd":  205,
    "R. Levee Frbrd":  206,
    "Mann Wtd Total":  207,
    "Top W Act Chan":  226,
}

FIELDNAMES = ["River_Sta"] + list(NVAR_MAP.keys())


def extract_and_write_scenario_table(RC, river_id, reach_id, plan_title, batch_dir,
                                      profile_index, profile_name):
    """
    Reads output via Output_NodeOutput, looping over every node from
    Geometry_GetNodes and pulling each nVar code individually per node,
    for one specific profile (profile_index/profile_name).

    Must be called immediately after Compute_CurrentPlan for this exact
    plan, in the same fresh-Project_Open-per-plan pattern already in use
    in run_pipeline.py. Compute itself already runs every profile in the
    flow file in one call -- this only controls which profile's output
    gets read back out, so it's safe to call once per profile without
    recomputing.

    Skips structure nodes (BR, Culv, etc.) -- XS only, matching the
    original CSV convention. Reaches every true cross-section in the
    model, including the ones confirmed missing from the bulk
    Output_ReachOutput array / HDF Cross Section Attributes dataset
    (capped at 127 by physical file position, structures included).

    Output filename is prefixed with the sanitized profile name, e.g.
    "100yr_LIONS_CREEK_REACH1_sed0.0ft_n0.035.csv".
    """
    node_result = RC.Geometry_GetNodes(river_id, reach_id, None, None, None)
    node_ids = node_result[3]
    node_types = node_result[4]

    rows = []
    for i, (node_id, node_type) in enumerate(zip(node_ids, node_types)):
        node_code = i + 1  # node codes are 1-based

        if str(node_type).strip() != "":
            continue  # not a plain cross-section -- skip structures

        station = str(node_id).strip()
        row = {"River_Sta": station}

        for col_name, nvar in NVAR_MAP.items():
            if col_name == "Profile":
                row[col_name] = profile_name
                continue
            try:
                value_result = RC.Output_NodeOutput(river_id, reach_id, node_code, 0, profile_index, nvar)
                value = value_result[0] if isinstance(value_result, tuple) else value_result
            except Exception as e:
                print(f"      WARNING: Output_NodeOutput failed for station {station}, "
                      f"'{col_name}' (nvar={nvar}): {e}")
                value = ""
            row[col_name] = value

        rows.append(row)

    if not rows:
        print(f"      WARNING: No data collected for {plan_title} / {profile_name}, skipping CSV write.")
        return []

    filename = f"{sanitize_for_filename(profile_name)}_{plan_title}.csv"
    csv_path = os.path.join(batch_dir, filename)
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"      Table written to: {csv_path} ({len(rows)} cross-sections)")
    return rows
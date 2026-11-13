import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))
print(f"DEBUG: sys.argv = {sys.argv}")
import csv
import itertools
import win32com.client
import config
from hec_1Dsteady_pipeline.io_loaders import load_creek_locations, load_reach_specs
from hec_1Dsteady_pipeline.flow_parser import parse_flow_profiles, sanitize_for_filename
from hec_1Dsteady_pipeline.batching import calc_available_slots, make_batches
from hec_1Dsteady_pipeline.folder_setup import setup_batch_folder
from hec_1Dsteady_pipeline.geometry_editor import modify_geometry_scenario, set_geom_title
from hec_1Dsteady_pipeline.prj_editor import (
    register_geometry_in_prj, register_plan_in_prj,
    set_current_plan_in_prj
)
from hec_1Dsteady_pipeline.plan_editor import (
    create_plan_file, get_scenario_plans,
    filter_scenario_plans, get_existing_scenario_titles,
    find_unexpected_scenario_titles
)
from hec_1Dsteady_pipeline.com_extract import extract_and_write_scenario_table
from hec_1Dsteady_pipeline.archiving import prompt_run_name, confirm


def main(run_name=None, skip_confirm=False, destination=None):
    if run_name is None:
        run_name = prompt_run_name()

    if not os.path.exists(config.MODEL_PATH_CSV) or not os.path.exists(config.BATCH_SPECS_CSV):
        print("\nERROR: Input CSVs not found in data/input/.")
        if not skip_confirm:
            input("\nPress Enter to close this window.")
        return

    creek_locations = load_creek_locations(config.MODEL_PATH_CSV)
    reach_specs = load_reach_specs(config.BATCH_SPECS_CSV)

    print(f"\n  CreekLocations_input.csv: {len(creek_locations)} project(s) found")
    print(f"  HECSPECS_input.csv      : {len(reach_specs)} reaches found")

    if not reach_specs or not creek_locations:
        print("\nERROR: One or both input CSVs are empty. Please fill them out and try again.")
        if not skip_confirm:
            input("\nPress Enter to close this window.")
        return

    if not skip_confirm:
        if not confirm("\nProceed with this run?"):
            print("Cancelled. Your input files were left untouched.")
            input("\nPress Enter to close this window.")
            return

    first_creek = list(creek_locations.values())[0]
    available_slots, base_geom_number = calc_available_slots(first_creek['base_geom_path'])
    batches = make_batches(reach_specs, available_slots)

    print(f"\nBase geometry number: {base_geom_number}")
    print(f"Available geometry/plan slots per batch: {available_slots}")
    print(f"Total batches: {len(batches)}")
    for i, batch in enumerate(batches):
        reach_names = [r['mg_reach_name'] for r in batch]
        batch_scenario_count = sum(len(r['sed_depths']) * len(r['n_values']) for r in batch)
        print(f"  Batch {i+1}: {reach_names} ({batch_scenario_count} scenarios)")

    reach_order = {r['mg_reach_name']: idx for idx, r in enumerate(reach_specs)}
    scenario_metadata = {}

    prj_path = first_creek['prj_path']
    base_geom_path = first_creek['base_geom_path']
    base_flow_path = first_creek['base_flow_path']
    base_plan_path = first_creek['base_plan_path']
    project_dir = os.path.dirname(prj_path)

    output_dir = destination if destination else project_dir
    os.makedirs(output_dir, exist_ok=True)
    print(f"\nOutput directory: {output_dir}")

    profiles = parse_flow_profiles(base_flow_path)
    print(f"\nFlow profiles found in {base_flow_path}:")
    for profile_index, profile_name in profiles:
        print(f"  {profile_index}: {profile_name}")

    # ========================================================
    # PHASE 1: build all batch folders, scenario geometries, plan files
    # ========================================================
    total_created = 0
    total_skipped = 0

    for batch_idx, batch in enumerate(batches):
        batch_name = f"Batch{batch_idx + 1}"
        batch_dir = os.path.join(output_dir, batch_name)

        print(f"\n{'='*60}")
        print(f"Setting up {batch_name} with {len(batch)} reaches.")

        dest_prj, dest_geom, dest_flow, dest_plan = setup_batch_folder(
            batch_dir, prj_path, base_geom_path, base_flow_path, base_plan_path
        )

        prj_base = os.path.splitext(os.path.basename(dest_prj))[0]
        geom_ext = os.path.splitext(dest_geom)[1]

        def _read_geom_title(geom_path):
            try:
                with open(geom_path, 'r', newline='') as f:
                    for line in f:
                        if line.startswith('Geom Title='):
                            return line.strip().split('=', 1)[1].strip()
            except Exception:
                pass
            return None

        # Compute the full set of scenario titles THIS batch's HECSPECS
        # should produce, using the exact same construction as the
        # creation loop below -- before creating anything, so we can
        # check for unexpected leftover geometry files first.
        expected_titles = set()
        base_geom_title = _read_geom_title(dest_geom)
        if base_geom_title:
            expected_titles.add(base_geom_title)
        for reach in batch:
            for sed_depth, n_value in itertools.product(reach['sed_depths'], reach['n_values']):
                title = f"{reach['creek_name']}_{reach['mg_reach_name']}_sed{sed_depth}ft_n{n_value}"
                expected_titles.add(title.replace(' ', '_'))

        unexpected_titles = find_unexpected_scenario_titles(batch_dir, prj_base, expected_titles)
        if unexpected_titles:
            print(f"\nERROR: {batch_name} contains {len(unexpected_titles)} geometry file(s) "
                  f"that don't match any scenario the current HECSPECS would produce -- "
                  f"likely leftover from a different or earlier run reusing this folder:")
            for title in unexpected_titles:
                print(f"    - {title}")
            raise ValueError(
                f"{batch_name}: unexpected leftover geometry files found. Clear out "
                f"{batch_dir} (or move it aside) before running this HECSPECS file, "
                f"or these unrelated scenarios will keep consuming geometry/plan file "
                f"numbers in every future run against this folder."
            )

        existing_titles = get_existing_scenario_titles(batch_dir, prj_base)
        print(f"  Found {len(existing_titles)} existing scenario geometry files.")

        for reach in batch:
            creek_name = reach['creek_name']
            mg_reach_name = reach['mg_reach_name']
            ds_station = reach['ds_station']
            us_station = reach['us_station']
            n_values = reach['n_values']
            sed_depths = reach['sed_depths']

            print(f"\n  Processing reach: {mg_reach_name}")
            print(f"    DS station: {ds_station}  US station: {us_station}")

            reach_created = 0
            reach_skipped = 0

            for sed_depth, n_value in itertools.product(sed_depths, n_values):
                scenario_title = f"{creek_name}_{mg_reach_name}_sed{sed_depth}ft_n{n_value}"
                scenario_title = scenario_title.replace(' ', '_')
                scenario_metadata[scenario_title] = {
                    'reach_order': reach_order[mg_reach_name],
                    'reach': mg_reach_name,
                    'sed_depth': sed_depth,
                    'n_value': n_value,
                    'top_of_bank': reach['top_of_bank'],
                    'rep_xs_station': reach['rep_xs_station'],
                }

                if scenario_title in existing_titles:
                    print(f"    SKIP (already exists): {scenario_title}")
                    reach_skipped += 1
                    continue

                print(f"    Creating: {scenario_title}")

                new_geom_ext = register_geometry_in_prj(dest_prj, geom_ext)
                scenario_geom_path = os.path.join(batch_dir, f"{prj_base}.{new_geom_ext}")
                modify_geometry_scenario(
                    base_geom_path=dest_geom,
                    out_path=scenario_geom_path,
                    ds_station=ds_station,
                    us_station=us_station,
                    sed_depth=sed_depth,
                    n_value=n_value
                )
                set_geom_title(scenario_geom_path, scenario_title)

                new_plan_ext = register_plan_in_prj(dest_prj)
                scenario_plan_path = os.path.join(batch_dir, f"{prj_base}.{new_plan_ext}")
                create_plan_file(
                    base_plan_path=dest_plan,
                    out_plan_path=scenario_plan_path,
                    plan_title=scenario_title,
                    geom_ext=new_geom_ext
                )

                reach_created += 1
                existing_titles.add(scenario_title)

            print(f"    Reach complete: {reach_created} created, {reach_skipped} skipped.")
            total_created += reach_created
            total_skipped += reach_skipped

    print(f"\nAll batches complete.")
    print(f"Total scenarios created: {total_created}")
    print(f"Total scenarios skipped: {total_skipped}")

    # ========================================================
    # PHASE 2: compute + extract, minimal COM surface
    #
    # Plan_SetCurrent, PlanOutput_SetCurrent, Geometry_GetNodes, and
    # Output_NodeOutput have all been removed. The only COM calls left
    # are Project_Open and Compute_CurrentPlan.
    #
    # Which plan gets computed is controlled entirely by our own
    # set_current_plan_in_prj() (a plain text-file edit, no COM) writing
    # the Current Plan= line, followed by a FRESH Project_Open every
    # single plan -- not once per batch. This forces HEC-RAS to actually
    # re-read the .prj from disk before each compute, rather than
    # relying on Plan_SetCurrent to update in-memory state that may not
    # actually be taking effect.
    # ========================================================
    RC = win32com.client.Dispatch(config.RAS_COM_PROGID)
    print("\nCOM object created. Beginning run phase.")

    runs_completed = 0
    all_results_by_profile = {profile_name: [] for _, profile_name in profiles}
    failed_extractions = []

    try:
        for batch_idx, batch in enumerate(batches):
            batch_name = f"Batch{batch_idx + 1}"
            batch_dir = os.path.join(output_dir, batch_name)
            dest_prj = os.path.join(batch_dir, os.path.basename(prj_path))
            prj_base = os.path.splitext(os.path.basename(dest_prj))[0]

            scenario_plans = get_scenario_plans(batch_dir, prj_base)
            print(f"\n{'='*60}")
            print(f"Batch {batch_idx + 1}: {dest_prj}")
            print(f"  Found {len(scenario_plans)} scenario plans.")

            filtered_plans = filter_scenario_plans(scenario_plans, batch)
            print(f"  {len(filtered_plans)} scenario plans to run.")

            print(f"\n  -- Computing and extracting each plan (minimal COM surface) --")

            for plan_ext, plan_title, matched_reach in filtered_plans:
                if config.MAX_RUNS is not None and runs_completed >= config.MAX_RUNS:
                    print(f"\nMAX_RUNS limit of {config.MAX_RUNS} reached. Stopping.")
                    raise StopIteration

                print(f"    Computing: {plan_title} ({plan_ext})")

                # Write Current Plan= directly to the .prj -- no COM call.
                set_current_plan_in_prj(dest_prj, plan_ext)

                # Fresh reload, every single plan. This is the actual
                # test: does forcing HEC-RAS to re-read the .prj from
                # disk (instead of relying on Plan_SetCurrent, now
                # removed) make it pick up the plan we just wrote?
                RC.Project_Open(dest_prj)

                RC.Compute_HideComputationWindow()
                compute_result = RC.Compute_CurrentPlan(0, None, True)
                print(f"      Compute result: {compute_result}")
                runs_completed += 1

                print(f"    Extracting: {plan_title} ({plan_ext})")
                for profile_index, profile_name in profiles:
                    try:
                        rows = extract_and_write_scenario_table(
                            RC, config.RIVER_ID, config.REACH_ID, plan_title, batch_dir,
                            profile_index, profile_name
                        )

                        meta = scenario_metadata.get(plan_title, {})
                        for row in rows:
                            row['REACH'] = meta.get('reach', matched_reach)
                            row['SED_DEPTH'] = meta.get('sed_depth')
                            row['N_VALUE'] = meta.get('n_value')
                            row['TOP_OF_BANK'] = meta.get('top_of_bank')
                            row['REP_XS_STATION'] = meta.get('rep_xs_station')
                            row['_reach_order'] = meta.get('reach_order', 0)
                            all_results_by_profile[profile_name].append(row)

                    except Exception as e:
                        print(f"      EXTRACTION FAILED for {plan_title} ({plan_ext}), "
                              f"profile '{profile_name}': {e}")
                        print(f"      Skipping this plan/profile, continuing with the rest of the run.")
                        failed_extractions.append(f"{plan_title} [{profile_name}]")
                        continue

    except StopIteration:
        print(f"\nMAX_RUNS limit reached after {runs_completed} runs.")
    except Exception as e:
        print(f"\nERROR: {e}")
    finally:
        RC.QuitRAS()
        print("\nHEC-RAS closed.")

    print(f"\nAll done. Total plans computed: {runs_completed}")
    if failed_extractions:
        print(f"WARNING: {len(failed_extractions)} plan(s) failed extraction and are missing from results:")
        for title in failed_extractions:
            print(f"    - {title}")

    for profile_index, profile_name in profiles:
        results = all_results_by_profile[profile_name]
        if not results:
            continue

        results.sort(key=lambda r: (r['_reach_order'], r['SED_DEPTH'], r['N_VALUE']))

        id_cols = ['REACH', 'SED_DEPTH', 'N_VALUE', 'TOP_OF_BANK', 'REP_XS_STATION']
        other_cols = [k for k in results[0].keys() if k not in id_cols and k != '_reach_order']
        combined_fieldnames = id_cols + other_cols

        combined_filename = f"{sanitize_for_filename(profile_name)}_{run_name}_ALL_RESULTS.csv"
        combined_path = os.path.join(output_dir, combined_filename)
        with open(combined_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=combined_fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(results)

        print(f"Combined results for '{profile_name}' written to: {combined_path}")

    # Archiving removed for now (1.0 cleanup item -- input CSVs are left
    # in place as-is after a run, not moved or reset to a blank template).
    print(f"\nRun complete. Input files left as-is (archiving disabled).")

    if not skip_confirm:
        input("\nPress Enter to close this window.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_name_arg = sys.argv[1]
        destination_arg = sys.argv[2] if len(sys.argv) > 2 and sys.argv[2] else None
        main(run_name=run_name_arg, skip_confirm=True, destination=destination_arg)
    else:
        main()
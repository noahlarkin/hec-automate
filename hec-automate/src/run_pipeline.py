import os
import itertools
import win32com.client
import config
from hec_1Dsteady_pipeline.io_loaders import load_creek_locations, load_reach_specs
from hec_1Dsteady_pipeline.batching import calc_max_reaches_per_batch, make_batches
from hec_1Dsteady_pipeline.folder_setup import setup_batch_folder
from hec_1Dsteady_pipeline.geometry_editor import modify_geometry_scenario, set_geom_title
from hec_1Dsteady_pipeline.prj_editor import (
    register_geometry_in_prj, register_plan_in_prj,
    get_next_plan_ext, set_current_plan_in_prj
)
from hec_1Dsteady_pipeline.plan_editor import (
    create_plan_file, get_scenario_plans,
    filter_scenario_plans, get_existing_scenario_titles
)
from hec_1Dsteady_pipeline.com_extract import extract_and_write_scenario_table
from hec_1Dsteady_pipeline.archiving import prompt_run_name, confirm, archive_and_reset_inputs


def main():
    run_name = prompt_run_name()

    if not os.path.exists(config.MODEL_PATH_CSV) or not os.path.exists(config.BATCH_SPECS_CSV):
        print("\nERROR: Input CSVs not found in data/input/.")
        input("\nPress Enter to close this window.")
        return

    creek_locations = load_creek_locations(config.MODEL_PATH_CSV)
    reach_specs = load_reach_specs(config.BATCH_SPECS_CSV)

    print(f"\n  CreekLocations_input.csv: {len(creek_locations)} project(s) found")
    print(f"  HECSPECS_input.csv      : {len(reach_specs)} reaches found")

    if not reach_specs or not creek_locations:
        print("\nERROR: One or both input CSVs are empty. Please fill them out and try again.")
        input("\nPress Enter to close this window.")
        return

    if not confirm("\nProceed with this run?"):
        print("Cancelled. Your input files were left untouched.")
        input("\nPress Enter to close this window.")
        return

    first_creek = list(creek_locations.values())[0]
    max_reaches_per_batch, base_geom_number = calc_max_reaches_per_batch(first_creek['base_geom_path'])
    batches = make_batches(reach_specs, max_reaches_per_batch)

    print(f"\nBase geometry number: {base_geom_number}")
    print(f"Max reaches per batch: {max_reaches_per_batch}")
    print(f"Total batches: {len(batches)}")
    for i, batch in enumerate(batches):
        reach_names = [r['mg_reach_name'] for r in batch]
        print(f"  Batch {i+1}: {reach_names}")

    prj_path = first_creek['prj_path']
    base_geom_path = first_creek['base_geom_path']
    base_flow_path = first_creek['base_flow_path']
    base_plan_path = first_creek['base_plan_path']
    project_dir = os.path.dirname(prj_path)

    # ========================================================
    # PHASE 1 (same script, same run): build all batch folders,
    # scenario geometries, and plan files
    # ========================================================
    total_created = 0
    total_skipped = 0

    for batch_idx, batch in enumerate(batches):
        batch_name = f"Batch{batch_idx + 1}"
        batch_dir = os.path.join(project_dir, batch_name)

        print(f"\n{'='*60}")
        print(f"Setting up {batch_name} with {len(batch)} reaches.")

        dest_prj, dest_geom, dest_flow, dest_plan = setup_batch_folder(
            batch_dir, prj_path, base_geom_path, base_flow_path, base_plan_path
        )

        prj_base = os.path.splitext(os.path.basename(dest_prj))[0]
        geom_ext = os.path.splitext(dest_geom)[1]

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
                scenario_title = f"{creek_name}_{mg_reach_name}_n{n_value}_sed{sed_depth}ft"
                scenario_title = scenario_title.replace(' ', '_')

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

                new_plan_ext = get_next_plan_ext(dest_prj)
                scenario_plan_path = os.path.join(batch_dir, f"{prj_base}.{new_plan_ext}")
                create_plan_file(
                    base_plan_path=dest_plan,
                    out_plan_path=scenario_plan_path,
                    plan_title=scenario_title,
                    geom_ext=new_geom_ext
                )
                register_plan_in_prj(dest_prj, new_plan_ext)

                reach_created += 1
                existing_titles.add(scenario_title)

            print(f"    Reach complete: {reach_created} created, {reach_skipped} skipped.")
            total_created += reach_created
            total_skipped += reach_skipped

    print(f"\nAll batches complete.")
    print(f"Total scenarios created: {total_created}")
    print(f"Total scenarios skipped: {total_skipped}")

    # ========================================================
    # PHASE 2 (same script, same run): open HEC-RAS via COM,
    # compute every plan, extract output tables
    # `batches` is still in memory here - no re-reading needed
    # ========================================================
    RC = win32com.client.Dispatch(config.RAS_COM_PROGID)
    print("\nCOM object created. Beginning run phase.")

    runs_completed = 0

    try:
        for batch_idx, batch in enumerate(batches):
            batch_name = f"Batch{batch_idx + 1}"
            batch_dir = os.path.join(project_dir, batch_name)
            dest_prj = os.path.join(batch_dir, os.path.basename(prj_path))
            prj_base = os.path.splitext(os.path.basename(dest_prj))[0]

            print(f"\n{'='*60}")
            print(f"Opening {batch_name}: {dest_prj}")
            RC.Project_Open(dest_prj)

            scenario_plans = get_scenario_plans(batch_dir, prj_base)
            print(f"  Found {len(scenario_plans)} scenario plans.")

            filtered_plans = filter_scenario_plans(scenario_plans, batch)
            print(f"  {len(filtered_plans)} scenario plans to run.")

            print(f"\n  -- Phase 1: Computing all plans --")
            for plan_ext, plan_title, matched_reach in filtered_plans:
                if config.MAX_RUNS is not None and runs_completed >= config.MAX_RUNS:
                    print(f"\nMAX_RUNS limit of {config.MAX_RUNS} reached. Stopping.")
                    raise StopIteration

                print(f"    Computing: {plan_title} ({plan_ext})")

                set_current_plan_in_prj(dest_prj, plan_ext)

                success = RC.Plan_SetCurrent(plan_title)
                if not success:
                    print(f"      WARNING: Plan_SetCurrent returned False for {plan_title}")

                RC.Compute_HideComputationWindow()
                RC.Compute_CurrentPlan(0, None, True)

                print(f"      Computed.")
                runs_completed += 1

            print(f"\n  -- Phase 2: Extracting output tables --")

            RC.Project_Open(dest_prj)

            var_result = RC.Output_Variables(0, None, None)
            var_names = var_result[1]

            for plan_ext, plan_title, matched_reach in filtered_plans:
                print(f"    Extracting: {plan_title} ({plan_ext})")

                set_current_plan_in_prj(dest_prj, plan_ext)
                RC.Plan_SetCurrent(plan_title)

                current_reach_spec = next(
                    r for r in batch if r['mg_reach_name'] == matched_reach
                )
                profile_index = current_reach_spec['los_profile_index']

                extract_and_write_scenario_table(
                    RC, config.RIVER_ID, plan_title, batch_dir,
                    profile_index, config.NVAR_LIST, var_names
                )

    except StopIteration:
        print(f"\nMAX_RUNS limit reached after {runs_completed} runs.")
    except Exception as e:
        print(f"\nERROR: {e}")
    finally:
        RC.QuitRAS()
        print("\nHEC-RAS closed.")

    print(f"\nAll done. Total plans computed: {runs_completed}")

    # Archive/reset only after the full run (build + compute + extract) succeeds
    archive_and_reset_inputs(
        run_name,
        config.ARCHIVE_DIR,
        config.BATCH_SPECS_CSV,
        config.MODEL_PATH_CSV,
        config.HECSPECS_TEMPLATE_CSV,
        config.CREEKLOCATIONS_TEMPLATE_CSV
    )

    input("\nPress Enter to close this window.")


if __name__ == "__main__":
    main()
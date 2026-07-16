import os
import shutil
import datetime


def prompt_run_name():
    print("=" * 60)
    print("  HEC-RAS Batch Pipeline")
    print("=" * 60)
    name = input("Please enter a name for this run (e.g. the creek/watershed name): ").strip()
    while not name:
        name = input("Run name cannot be blank. Please enter a name: ").strip()
    return name


def confirm(prompt):
    resp = input(f"{prompt} (y/n): ").strip().lower()
    return resp == "y"


def archive_and_reset_inputs(run_name, archive_dir, hecspecs_input_csv, creeklocations_input_csv,
                              hecspecs_template_csv, creeklocations_template_csv):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    run_archive_dir = os.path.join(archive_dir, f"{run_name}_{timestamp}")
    os.makedirs(run_archive_dir, exist_ok=True)

    shutil.copy2(hecspecs_input_csv, os.path.join(run_archive_dir, "HECSPECS.csv"))
    shutil.copy2(creeklocations_input_csv, os.path.join(run_archive_dir, "CreekLocations.csv"))
    print(f"Archived this run's inputs to: {run_archive_dir}")

    shutil.copy2(hecspecs_template_csv, hecspecs_input_csv)
    shutil.copy2(creeklocations_template_csv, creeklocations_input_csv)
    print("Input files have been reset - ready for your next run.")
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
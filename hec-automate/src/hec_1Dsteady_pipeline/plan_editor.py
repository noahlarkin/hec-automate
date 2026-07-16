import os


def create_plan_file(base_plan_path, out_plan_path, plan_title, geom_ext):
    short_id = plan_title[-16:].strip() if len(plan_title) > 16 else plan_title

    with open(base_plan_path, 'r') as f:
        lines = f.readlines()

    with open(out_plan_path, 'w') as f:
        for line in lines:
            if line.startswith('Plan Title='):
                f.write(f'Plan Title={plan_title}\r\n')
            elif line.startswith('Short Identifier='):
                f.write(f'Short Identifier={short_id}\r\n')
            elif line.startswith('Program Version='):
                f.write(f'Program Version=6.00\r\n')
            elif line.startswith('Geom File='):
                f.write(f'Geom File={geom_ext}\r\n')
            else:
                f.write(line)

    print(f"    Plan file written to: {out_plan_path}")


def get_scenario_plans(batch_dir, prj_base):
    scenario_plans = []
    for filename in os.listdir(batch_dir):
        if filename.startswith(prj_base + '.p') and not filename.endswith('.hdf'):
            plan_path = os.path.join(batch_dir, filename)
            plan_ext = os.path.splitext(filename)[1].lstrip('.')
            try:
                with open(plan_path, 'r') as f:
                    for line in f:
                        if line.startswith('Plan Title='):
                            title = line.strip().split('=')[1].strip()
                            scenario_plans.append((plan_ext, title))
                            break
            except Exception:
                pass

    scenario_plans.sort(key=lambda x: int(x[0][1:]))
    return scenario_plans


def filter_scenario_plans(scenario_plans, batch):
    """
    Returns only plans that match a known HECSPECS reach,
    skipping base plans or any unrecognized titles.
    """
    filtered = []
    for plan_ext, plan_title in scenario_plans:
        matched_reach = None
        for reach in batch:
            reach_tag = reach['mg_reach_name'].replace(' ', '_')
            if f"_{reach_tag}_n" in plan_title:
                matched_reach = reach['mg_reach_name']
                break
        if matched_reach is None:
            print(f"  Skipping non-scenario plan: {plan_title} ({plan_ext})")
            continue
        filtered.append((plan_ext, plan_title, matched_reach))
    return filtered


def get_existing_scenario_titles(batch_dir, prj_base):
    existing_titles = set()
    for filename in os.listdir(batch_dir):
        if filename.startswith(prj_base + '.g') and not filename.endswith('.hdf'):
            geom_path = os.path.join(batch_dir, filename)
            try:
                with open(geom_path, 'r') as f:
                    for line in f:
                        if line.startswith('Geom Title='):
                            title = line.strip().split('=')[1].strip()
                            existing_titles.add(title)
                            break
            except Exception:
                pass
    return existing_titles
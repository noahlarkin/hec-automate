import os


def create_plan_file(base_plan_path, out_plan_path, plan_title, geom_ext):
    short_id = plan_title[-16:].strip() if len(plan_title) > 16 else plan_title

    with open(base_plan_path, 'r', newline='') as f:
        lines = f.readlines()

    with open(out_plan_path, 'w', newline='') as f:
        for line in lines:
            if line.startswith('Plan Title='):
                f.write(f'Plan Title={plan_title}\r\n')
            elif line.startswith('Short Identifier='):
                f.write(f'Short Identifier={short_id}\r\n')
            elif line.startswith('Program Version='):
                f.write(f'Program Version=6.00\r\n')
            elif line.startswith('Geom File='):
                f.write(f'Geom File={geom_ext}\r\n')
            elif line.startswith('Run HTab='):
                # Force hydraulic table rebuild from the current geometry on
                # every compute. Without this, HEC-RAS can compute against
                # cached hydraulic property tables carried over from the
                # base geometry, silently ignoring edited roughness/sediment
                # values even though the geometry file itself is correct.
                f.write('Run HTab= 1 \r\n')
            elif line.startswith('HDF Fixed Rows='):
                # Confirmed cause of missing downstream cross-sections in
                # output: with this enabled, HEC-RAS pre-allocates the
                # results array at a fixed size rather than sizing it to
                # the current geometry, silently truncating any XS's added
                # after that size was originally locked in. Force dynamic
                # sizing instead.
                f.write('HDF Fixed Rows= 0 \r\n')
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
                with open(plan_path, 'r', newline='') as f:
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
            if f"_{reach_tag}_sed" in plan_title:
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
                with open(geom_path, 'r', newline='') as f:
                    for line in f:
                        if line.startswith('Geom Title='):
                            title = line.strip().split('=')[1].strip()
                            existing_titles.add(title)
                            break
            except Exception:
                pass
    return existing_titles


def find_unexpected_scenario_titles(batch_dir, prj_base, expected_titles):
    """
    Compares scenario titles found in existing .g## files in batch_dir
    against expected_titles -- the set of titles the CURRENT HECSPECS
    should produce for this batch. Returns a sorted list of any titles
    present on disk that aren't in that expected set -- geometry files
    likely left over from a different/earlier run reusing this same
    folder, not from this run's own prior progress.
    """
    existing_titles = get_existing_scenario_titles(batch_dir, prj_base)
    unexpected = existing_titles - set(expected_titles)
    return sorted(unexpected)
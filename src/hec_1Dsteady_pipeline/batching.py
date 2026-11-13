import os


def calc_available_slots(base_geom_path):
    """
    Returns (available_slots, base_geom_number). available_slots is how
    many more geometry/plan file numbers are free in a batch before
    hitting HEC-RAS's 99-file cap, given the base geometry's own number.
    """
    base_geom_ext = os.path.splitext(base_geom_path)[1]
    base_geom_number = int(base_geom_ext.lstrip('.g'))
    available_slots = 99 - base_geom_number
    return available_slots, base_geom_number


def make_batches(reach_specs, available_slots):
    """
    Packs reaches into batches so each batch's TOTAL scenario count
    (sed_depths x n_values, summed across every reach in that batch)
    stays within available_slots -- each scenario needs its own
    geometry/plan file number, capped at 99 per project.

    Scenario count now varies per reach (sediment depth count is 1-6,
    no longer a fixed constant), so batches are packed by actual
    scenario count rather than a fixed number of reaches per batch.
    """
    batches = []
    current_batch = []
    current_count = 0

    for reach in reach_specs:
        scenario_count = len(reach['sed_depths']) * len(reach['n_values'])

        if scenario_count > available_slots:
            raise ValueError(
                f"Reach '{reach['mg_reach_name']}' needs {scenario_count} scenarios "
                f"({len(reach['sed_depths'])} sediment x {len(reach['n_values'])} roughness), "
                f"which exceeds the {available_slots} available geometry/plan slots in a "
                f"single batch. Reduce the number of sediment or roughness values for "
                f"this reach."
            )

        if current_count + scenario_count > available_slots:
            batches.append(current_batch)
            current_batch = []
            current_count = 0

        current_batch.append(reach)
        current_count += scenario_count

    if current_batch:
        batches.append(current_batch)

    return batches
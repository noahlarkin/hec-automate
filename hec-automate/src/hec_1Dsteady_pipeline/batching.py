import os
import math


def calc_max_reaches_per_batch(base_geom_path):
    """
    Determines how many reaches (x16 scenarios each) fit in one batch
    without exceeding HEC-RAS's .g99 file numbering limit.
    """
    base_geom_ext = os.path.splitext(base_geom_path)[1]
    base_geom_number = int(base_geom_ext.lstrip('.g'))
    max_reaches_per_batch = math.floor((99 - base_geom_number) / 16)
    return max_reaches_per_batch, base_geom_number


def make_batches(reach_specs, max_reaches_per_batch):
    """Splits the full reach_specs list into batch-sized chunks."""
    return [
        reach_specs[i:i + max_reaches_per_batch]
        for i in range(0, len(reach_specs), max_reaches_per_batch)
    ]
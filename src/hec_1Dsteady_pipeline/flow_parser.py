def parse_flow_profiles(flow_path):
    """
    Reads a HEC-RAS steady flow file (.fXX) and returns a list of
    (profile_index, profile_name) tuples, 1-indexed, matching the order
    HEC-RAS uses internally for profile numbering (Output_ReachOutput's
    profile argument).

    Expects:
        Number of Profiles= N
        Profile Names=Name1,Name2,...,NameN
    on their own lines, matching the confirmed HEC-RAS steady flow file
    format. Validates the count matches the number of names found.
    """
    with open(flow_path, 'r', newline='') as f:
        lines = f.readlines()

    num_profiles = None
    profile_names = None

    for line in lines:
        if line.startswith('Number of Profiles='):
            num_profiles = int(line.strip().split('=')[1].strip())
        elif line.startswith('Profile Names='):
            names_str = line.strip().split('=', 1)[1]
            profile_names = [n.strip() for n in names_str.split(',')]

    if num_profiles is None or profile_names is None:
        raise ValueError(
            f"Could not find 'Number of Profiles=' and/or 'Profile Names=' in {flow_path}"
        )

    if len(profile_names) != num_profiles:
        raise ValueError(
            f"Profile count mismatch in {flow_path}: 'Number of Profiles=' says "
            f"{num_profiles}, but 'Profile Names=' lists {len(profile_names)} names."
        )

    return [(i + 1, name) for i, name in enumerate(profile_names)]


def sanitize_for_filename(name):
    return name.strip().replace(' ', '_')
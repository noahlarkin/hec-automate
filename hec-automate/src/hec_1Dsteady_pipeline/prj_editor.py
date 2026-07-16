import os


def register_geometry_in_prj(prj_path, geom_ext):
    with open(prj_path, 'r') as f:
        lines = f.readlines()

    project_dir = os.path.dirname(prj_path)
    prj_base = os.path.splitext(os.path.basename(prj_path))[0]

    geom_numbers = []
    clean_lines = []

    for line in lines:
        if line.startswith('Geom File='):
            ext = line.strip().split('=')[1].strip()
            geom_file_path = os.path.join(project_dir, f"{prj_base}.{ext}")
            if os.path.exists(geom_file_path):
                try:
                    geom_numbers.append(int(ext[1:]))
                except ValueError:
                    pass
                clean_lines.append(line)
            else:
                print(f"    Removing missing geometry reference: {ext}")
        else:
            clean_lines.append(line)

    next_num = max(geom_numbers) + 1 if geom_numbers else 1
    new_ext = f'g{next_num:02d}'

    insert_idx = 0
    for idx, line in enumerate(clean_lines):
        if line.startswith('Geom File='):
            insert_idx = idx

    clean_lines.insert(insert_idx + 1, f'Geom File={new_ext}\r\n')

    with open(prj_path, 'w') as f:
        f.writelines(clean_lines)

    print(f"    Registered new geometry file: {new_ext}")
    return new_ext


def register_plan_in_prj(prj_path, plan_ext):
    with open(prj_path, 'a') as f:
        f.write(f'Plan File={plan_ext}\r\n')
    print(f"    Registered new plan file: {plan_ext}")


def get_next_plan_ext(prj_path):
    with open(prj_path, 'r') as f:
        lines = f.readlines()

    plan_numbers = []
    project_dir = os.path.dirname(prj_path)
    prj_base = os.path.splitext(os.path.basename(prj_path))[0]

    for line in lines:
        if line.startswith('Plan File='):
            ext = line.strip().split('=')[1].strip()
            plan_file_path = os.path.join(project_dir, f"{prj_base}.{ext}")
            if os.path.exists(plan_file_path):
                try:
                    plan_numbers.append(int(ext[1:]))
                except ValueError:
                    pass

    next_num = max(plan_numbers) + 1 if plan_numbers else 1
    return f'p{next_num:02d}'


def set_current_plan_in_prj(prj_path, plan_ext):
    with open(prj_path, 'r') as f:
        lines = f.readlines()

    found = False
    for idx, line in enumerate(lines):
        if line.startswith('Current Plan='):
            lines[idx] = f'Current Plan={plan_ext}\r\n'
            found = True
            break

    if not found:
        lines.insert(1, f'Current Plan={plan_ext}\r\n')

    with open(prj_path, 'w') as f:
        f.writelines(lines)
import os
import shutil


def setup_batch_folder(batch_dir, prj_path, base_geom_path, base_flow_path, base_plan_path):
    os.makedirs(batch_dir, exist_ok=True)

    prj_filename = os.path.basename(prj_path)
    geom_filename = os.path.basename(base_geom_path)
    flow_filename = os.path.basename(base_flow_path)
    plan_filename = os.path.basename(base_plan_path)

    dest_prj = os.path.join(batch_dir, prj_filename)
    dest_geom = os.path.join(batch_dir, geom_filename)
    dest_flow = os.path.join(batch_dir, flow_filename)
    dest_plan = os.path.join(batch_dir, plan_filename)

    if not os.path.exists(dest_prj):
        shutil.copy2(prj_path, dest_prj)
        print(f"    Copied prj to: {dest_prj}")
    else:
        print(f"    PRJ already exists, skipping copy.")

    if not os.path.exists(dest_geom):
        shutil.copy2(base_geom_path, dest_geom)
        print(f"    Copied as-built geometry to {dest_geom}")
    else:
        print(f"    geometry already exists, skipping copy.")

    if not os.path.exists(dest_flow):
        shutil.copy2(base_flow_path, dest_flow)
        print(f"    Copied flow file to: {dest_flow}")
    else:
        print(f"    Flow file already exists, skipping copy.")

    if not os.path.exists(dest_plan):
        shutil.copy2(base_plan_path, dest_plan)
        print(f"    Copied base plan to: {dest_plan}")
    else:
        print(f"    Base plan already exists, skipping copy.")

    return dest_prj, dest_geom, dest_flow, dest_plan
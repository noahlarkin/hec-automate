import os
import sys
import csv
import re
import glob
import shutil
import tempfile
import threading
import queue
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

import config

log_queue = queue.Queue()
proc_handle = {"proc": None}

HOW_TO_USE_TEXT = """\
HEC-AUTOMATE — How to Use

OVERVIEW
This tool batch-generates HEC-RAS geometry and plan files across
sediment/roughness scenarios, computes them, and extracts results
into a single combined CSV.

REQUIREMENTS -- READ BEFORE USING
This tool currently assumes your HEC-RAS project contains
ONE creek and ONE reach. Before running a model through this tool,
open it in HEC-RAS and confirm this in the river/reach schematic --
if more than one river or more than one reach is present, extraction
will silently target only the first one (River ID 1, Reach ID 1) and
results for anything else will be missing, with no error shown.
Additionally, it is recommended NOT to use HEC-RAS while using this app. 
For best practice, run while using lightweight applications on your
computer (ie: *not* Civil 3D or ArcMap (ArcGIS Online is okay)). 
Alternatively, leave running overnight, at lunch, or while in the field. 

STEPS

1. Input Run name
   A short label for this run. Used to name the final results file
   (e.g. "LSC_Test_ALL_RESULTS.csv").

2. Select Project folder
   Browse to the folder containing your HEC-RAS project: the .prj
   file plus its base geometry (.g##), flow (.f##), and plan (.p##)
   files. The app auto-detects the lowest-numbered file of each type
   as the "base" files to build scenarios from. The program is equipped 
   to compute and extract results for multiple flow profiles within the 
   same .f## flow file, but will not ingest multiple flow files. 

   *** IMPORTANT: LOCAL VS. NETWORK DRIVE ***
   Run this from a folder on your local C: drive whenever possible,
   NOT a network drive (particularly when accessing network drive via VPN when teleworking),
   although it will work for whatever drive you put the model in.
   This program reads and rewrites many small files repeatedly 
   (once per scenario, per reach). On a network drive that overhead 
   is much slower than on local disk, and a run that takes a few minutes locally can take
   noticeably longer over the network drives. Copy the project locally
   before running if it currently lives on a shared drive for fastest performance.
   Once the program has ran, transfer to the network drive to save storage 
   space. 

3. Detected files
   Confirms exactly which .prj/.g##/.f##/.p## files were found.
   Double check this before running. If it's wrong, re-select the
   folder or check that the folder contains only one project.

4. HECSPECS CSV
   The spreadsheet of reaches/scenarios to process. In this spreadsheet, fill out the template with creek name and reach, 
   stationing bounds of each reach, representative cross section, top of bank, and the sediment and roughness levels you want run. 
   The program will then automatically compute all possible combinations of sediment and roughness scenarios, extract results, 
   and combine them in an Excel spreadsheet. 
   There are three ways to provide the CSV:
     - Browse: select an existing CSV you already have.
     - Fill In App...: build it directly in this program - add a
       row per reach, fill in the fields, and Save. This guarantees
       the column headers are correct, since the app writes them
       for you.
   A green "Headers OK" message confirms the file is ready to run.
   A red message tells you exactly which column(s) are missing.

5. Run
   Click Run to see a summary of what's about to happen. Confirm,
   and the pipeline runs in the background. Progress streams into
   the log window below. The window stays responsive while it runs.

WHEN IT'S DONE
   Results are written to a single combined CSV inside your project
   folder, named "<run name>_ALL_RESULTS.csv". This run's input
   files are also archived automatically.

Questions or something looks wrong? Check the log window text first - 
it mirrors exactly what the pipeline is doing, in order.
"""


# ==========================================================================
# Project folder auto-detection
# ==========================================================================

def _lowest_numbered_file(project_folder, prefix_letter):
    candidates = glob.glob(os.path.join(project_folder, f"*.{prefix_letter}*"))
    numbered = []
    for f in candidates:
        ext = os.path.splitext(f)[1][1:]  # e.g. "g01"
        if not ext.startswith(prefix_letter):
            continue
        try:
            num = int(ext[1:])
        except ValueError:
            continue
        numbered.append((num, f))
    if not numbered:
        return None
    numbered.sort(key=lambda pair: pair[0])
    return numbered[0][1]


def auto_detect_project_files(project_folder):
    prj_files = glob.glob(os.path.join(project_folder, "*.prj"))
    if len(prj_files) == 0:
        raise ValueError("No .prj file found in the selected folder.")
    if len(prj_files) > 1:
        raise ValueError(
            f"Found {len(prj_files)} .prj files in the selected folder. "
            "Please select a folder containing exactly one project."
        )
    prj_path = prj_files[0]

    geom_path = _lowest_numbered_file(project_folder, "g")
    flow_path = _lowest_numbered_file(project_folder, "f")
    plan_path = _lowest_numbered_file(project_folder, "p")

    missing = []
    if geom_path is None:
        missing.append("geometry (.g##)")
    if flow_path is None:
        missing.append("flow (.f##)")
    if plan_path is None:
        missing.append("plan (.p##)")
    if missing:
        raise ValueError(f"Could not find base {', '.join(missing)} file(s) in project folder.")

    return prj_path, geom_path, flow_path, plan_path


# ==========================================================================
# CSV generation / copying
# ==========================================================================

def read_creek_name_from_hecspecs(hecspecs_path):
    """
    Reads CREEK_NAME from the first data row of the selected HECSPECS
    CSV, spaces replaced with underscores. Used to populate
    CreekLocations.csv's CREEK_NAME field now that there's no separate
    GUI field for it -- keeps both CSVs sourced from one real value
    instead of a second, disconnected input.
    """
    with open(hecspecs_path, newline="") as f:
        reader = csv.DictReader(f)
        first_row = next(reader, None)
    if not first_row or not first_row.get("CREEK_NAME", "").strip():
        raise ValueError("Could not read CREEK_NAME from the first row of the HECSPECS CSV.")
    return first_row["CREEK_NAME"].strip().replace(" ", "_")


def write_creek_locations_csv(csv_path, creek_name, prj_path, geom_path, flow_path, plan_path):
    os.makedirs(os.path.dirname(csv_path), exist_ok=True)
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["CREEK_NAME", "PRJ_PATH", "BASE_GEOM_PATH", "BASE_FLOW_PATH", "BASE_PLAN_PATH"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "CREEK_NAME": creek_name,
                "PRJ_PATH": prj_path,
                "BASE_GEOM_PATH": geom_path,
                "BASE_FLOW_PATH": flow_path,
                "BASE_PLAN_PATH": plan_path,
            }
        )


def copy_hecspecs_csv(source_path, dest_path):
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    if os.path.exists(dest_path):
        os.remove(dest_path)
    shutil.copy2(source_path, dest_path)


# Must match load_reach_specs()'s expected columns in io_loaders.py exactly.
REQUIRED_HECSPECS_COLUMNS = [
    "CREEK_NAME", "CREEK_REACH", "DS_STATION", "US_STATION",
    "REP_XS_STATION", "TOP_OF_BANK",
    "N_0", "N_1", "N_2", "N_3", "N_4", "N_5",
    "SED_0", "SED_1", "SED_2", "SED_3", "SED_4", "SED_5",
]

# Roughness and sediment are each their own group: any subset may be
# filled per row, but each group independently needs AT LEAST ONE
# filled -- these are two separate checks, not one pooled check across
# all 12 columns (a row with 6 blank sediment cells and 1 filled
# roughness cell should still fail, not pass on a technicality).
SEDIMENT_COLUMNS = ["SED_0", "SED_1", "SED_2", "SED_3", "SED_4", "SED_5"]
ROUGHNESS_COLUMNS = ["N_0", "N_1", "N_2", "N_3", "N_4", "N_5"]
OPTIONAL_HECSPECS_COLUMNS = set(SEDIMENT_COLUMNS) | set(ROUGHNESS_COLUMNS)


_NUMERIC_COLUMNS = ["DS_STATION", "US_STATION", "TOP_OF_BANK"] + ROUGHNESS_COLUMNS + SEDIMENT_COLUMNS
_REQUIRED_NONOPTIONAL_COLUMNS = [c for c in REQUIRED_HECSPECS_COLUMNS if c not in OPTIONAL_HECSPECS_COLUMNS]
_WHITESPACE_RE = re.compile(r"\s+")


def validate_and_clean_hecspecs(source_path, dest_path):
    """
    Reads source_path row by row, checking every row before writing
    anything:
      - every required, non-optional column (everything except the
        sediment/roughness groups) must be non-blank
      - each of the sediment/roughness groups independently needs at
        least one filled value per row
      - every numeric column's value: whitespace ANYWHERE in the cell
        (not just leading/trailing) is stripped automatically -- e.g.
        "0.0 35" -> "0.035" -- since a stray space inside a number is
        never a meaningful value, only ever a typo. Anything that still
        doesn't parse as a number after that (letters, extra decimal
        points, symbols) is NOT guessed at or silently altered -- it's
        flagged and blocks the run, since silently stripping an
        arbitrary character risks turning a typo into a different,
        wrong-but-plausible number.

    Returns (is_valid, blank_columns, invalid_columns) -- each a dict
    of {column_name: number_of_rows_affected}. Only writes dest_path
    if is_valid is True; a blocked file is never copied/cleaned.
    """
    blank_columns = {}
    invalid_columns = {}
    cleaned_rows = []
    fieldnames = None

    with open(source_path, newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            cleaned_row = dict(row)

            for col in _REQUIRED_NONOPTIONAL_COLUMNS:
                raw = row.get(col, "")
                if raw is None or raw.strip() == "":
                    blank_columns[col] = blank_columns.get(col, 0) + 1

            if not any(row.get(c, "").strip() for c in SEDIMENT_COLUMNS):
                key = "SED_0..SED_5 (at least one required per row)"
                blank_columns[key] = blank_columns.get(key, 0) + 1

            if not any(row.get(c, "").strip() for c in ROUGHNESS_COLUMNS):
                key = "N_0..N_5 (at least one required per row)"
                blank_columns[key] = blank_columns.get(key, 0) + 1

            for col in _NUMERIC_COLUMNS:
                raw = row.get(col, "")
                if raw is None:
                    continue
                no_whitespace = _WHITESPACE_RE.sub("", raw)
                if no_whitespace == "":
                    continue  # blank -- handled by the required/optional checks above
                try:
                    float(no_whitespace)
                    cleaned_row[col] = no_whitespace  # write back the cleaned value
                except ValueError:
                    invalid_columns[col] = invalid_columns.get(col, 0) + 1

            cleaned_rows.append(cleaned_row)

    is_valid = not blank_columns and not invalid_columns

    if is_valid:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        if os.path.exists(dest_path):
            os.remove(dest_path)
        with open(dest_path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(cleaned_rows)

    return is_valid, blank_columns, invalid_columns


def validate_hecspecs_headers(csv_path):
    """
    Returns (is_valid, missing_columns, extra_columns).
    Reads only the header row -- doesn't touch the actual data rows,
    so this is cheap to call on every file selection. Header names must
    all be present even for optional columns (SED_0-5) -- it's only the
    per-row VALUES in those columns that are allowed to be blank.
    """
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        try:
            headers = next(reader)
        except StopIteration:
            return False, REQUIRED_HECSPECS_COLUMNS, []

    headers = [h.strip() for h in headers]
    required_set = set(REQUIRED_HECSPECS_COLUMNS)
    header_set = set(headers)

    missing = [c for c in REQUIRED_HECSPECS_COLUMNS if c not in header_set]
    extra = [h for h in headers if h not in required_set]

    return (len(missing) == 0), missing, extra


# Expected value type per column, matching load_reach_specs()'s float()/int() calls.
# CREEK_NAME/CREEK_REACH/REP_XS_STATION are free text; everything else is numeric.
HECSPECS_COLUMN_TYPES = {
    "CREEK_NAME": str, "CREEK_REACH": str, "DS_STATION": float, "US_STATION": float,
    "REP_XS_STATION": str, "TOP_OF_BANK": float,
    "N_0": float, "N_1": float, "N_2": float, "N_3": float, "N_4": float, "N_5": float,
    "SED_0": float, "SED_1": float, "SED_2": float, "SED_3": float,
    "SED_4": float, "SED_5": float,
}


def cleanup_temp_csvs():
    for path in (config.MODEL_PATH_CSV, config.BATCH_SPECS_CSV):
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError as e:
            log_queue.put(f"WARNING: could not remove {path}: {e}\n")


# ==========================================================================
# GUI
# ==========================================================================

class HecAutomateGUI:
    def __init__(self, root):
        self.root = root
        root.title("HEC-AUTOMATE")

        self.run_name_var = tk.StringVar()
        self.project_folder_var = tk.StringVar()
        self.hecspecs_path_var = tk.StringVar()
        self.destination_var = tk.StringVar()

        frame_help = tk.Frame(root)
        frame_help.pack(fill="x", padx=10, pady=(10, 0))
        tk.Button(frame_help, text="How to Use", command=self._show_instructions).pack(side="right")

        frame_name = tk.Frame(root)
        frame_name.pack(fill="x", padx=10, pady=(10, 2))
        tk.Label(frame_name, text="Run name", width=15, anchor="w").pack(side="left")
        tk.Entry(frame_name, textvariable=self.run_name_var, width=50).pack(side="left", padx=5)

        frame_folder = tk.Frame(root)
        frame_folder.pack(fill="x", padx=10, pady=2)
        tk.Label(frame_folder, text="Project folder", width=15, anchor="w").pack(side="left")
        tk.Entry(frame_folder, textvariable=self.project_folder_var, width=50).pack(side="left", padx=5)
        tk.Button(frame_folder, text="Browse", command=self._browse_project_folder).pack(side="left")

        frame_preview = tk.Frame(root)
        frame_preview.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(frame_preview, text="Detected files", width=15, anchor="nw").pack(side="left")
        self.preview_text = tk.Text(
            frame_preview, height=5, width=65, state="disabled",
            bg=self.root.cget("bg"), relief="flat", wrap="none"
        )
        self.preview_text.pack(side="left", padx=5)

        frame_dest = tk.Frame(root)
        frame_dest.pack(fill="x", padx=10, pady=2)
        tk.Label(frame_dest, text="Output folder", width=15, anchor="w").pack(side="left")
        tk.Entry(frame_dest, textvariable=self.destination_var, width=50).pack(side="left", padx=5)
        tk.Button(frame_dest, text="Browse", command=self._browse_destination).pack(side="left")
        tk.Label(
            root,
            text="(auto-fills to match the project folder above -- change it if you want "
                 "generated files written somewhere else)",
            anchor="w", fg="gray30"
        ).pack(fill="x", padx=10, pady=(0, 4))

        frame_hecspecs = tk.Frame(root)
        frame_hecspecs.pack(fill="x", padx=10, pady=2)
        tk.Label(frame_hecspecs, text="HECSPECS CSV", width=15, anchor="w").pack(side="left")
        tk.Entry(frame_hecspecs, textvariable=self.hecspecs_path_var, width=50).pack(side="left", padx=5)
        tk.Button(frame_hecspecs, text="Browse", command=self._browse_hecspecs).pack(side="left")
        tk.Button(frame_hecspecs, text="Fill In App...", command=self._open_hecspecs_editor).pack(side="left", padx=(5, 0))

        frame_hecspecs_status = tk.Frame(root)
        frame_hecspecs_status.pack(fill="x", padx=10, pady=(0, 4))
        tk.Label(frame_hecspecs_status, text="", width=15).pack(side="left")
        self.hecspecs_status_label = tk.Label(
            frame_hecspecs_status, text="", anchor="w", justify="left", fg="black"
        )
        self.hecspecs_status_label.pack(side="left", padx=5)

        frame_buttons = tk.Frame(root)
        frame_buttons.pack(pady=10)
        self.run_button = tk.Button(frame_buttons, text="Run", command=self.on_run_clicked)
        self.run_button.pack(side="left", padx=5)
        tk.Button(frame_buttons, text="Clear", command=self._clear_form).pack(side="left", padx=5)

        self.log_text = tk.Text(root, height=25, width=90, state="disabled")
        self.log_text.pack(padx=10, pady=(0, 10))

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(100, self._poll_log_queue)
        self.root.after(200, self._show_instructions)

    def _show_instructions(self):
        win = tk.Toplevel(self.root)
        win.title("How to Use HEC-AUTOMATE")
        win.geometry("620x560")
        text = ScrolledText(win, wrap="word")
        text.pack(fill="both", expand=True, padx=10, pady=10)
        text.insert("1.0", HOW_TO_USE_TEXT)
        text.config(state="disabled")
        tk.Button(win, text="Close", command=win.destroy).pack(pady=(0, 10))
        win.transient(self.root)

    def _browse_project_folder(self):
        path = filedialog.askdirectory(title="Select project folder")
        if path:
            self.project_folder_var.set(path)
            self._update_file_preview(path)
            if not self.destination_var.get().strip():
                self.destination_var.set(path)

    def _update_file_preview(self, project_folder):
        self.preview_text.config(state="normal")
        self.preview_text.delete("1.0", "end")
        try:
            prj_path, geom_path, flow_path, plan_path = auto_detect_project_files(project_folder)
            preview = (
                f"PRJ:  {os.path.basename(prj_path)}\n"
                f"Geom: {os.path.basename(geom_path)}\n"
                f"Flow: {os.path.basename(flow_path)}\n"
                f"Plan: {os.path.basename(plan_path)}"
            )
        except ValueError as e:
            preview = f"(!) {e}"
        self.preview_text.insert("1.0", preview)
        self.preview_text.config(state="disabled")

    def _browse_hecspecs(self):
        path = filedialog.askopenfilename(
            title="Select HECSPECS CSV", filetypes=[("CSV files", "*.csv")]
        )
        if path:
            self.hecspecs_path_var.set(path)
            self._update_hecspecs_status(path)

    def _browse_destination(self):
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            self.destination_var.set(path)

    def _update_hecspecs_status(self, csv_path):
        try:
            is_valid, missing, extra = validate_hecspecs_headers(csv_path)
        except OSError as e:
            self.hecspecs_status_label.config(text=f"(!) Could not read file: {e}", fg="red")
            return

        if not is_valid:
            msg = f"(!) Missing required column(s): {', '.join(missing)}"
            self.hecspecs_status_label.config(text=msg, fg="red")
            return

        # Headers are fine -- now check row content too, using a throwaway
        # temp destination so this live preview doesn't prematurely write
        # into the real working CSV before Run is actually clicked.
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".csv")
        os.close(tmp_fd)
        try:
            rows_valid, blank_columns, invalid_columns = validate_and_clean_hecspecs(csv_path, tmp_path)
        except OSError as e:
            self.hecspecs_status_label.config(text=f"(!) Could not read file: {e}", fg="red")
            return
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        if rows_valid:
            msg = "Headers and values OK"
            if extra:
                msg += f"  (unused extra columns: {', '.join(extra)})"
            self.hecspecs_status_label.config(text=msg, fg="green")
        else:
            problem_cols = list(blank_columns.keys()) + list(invalid_columns.keys())
            msg = f"(!) Needs review -- see these column(s): {', '.join(problem_cols)}"
            self.hecspecs_status_label.config(text=msg, fg="red")

    def _save_hecspecs_template(self):
        dest = filedialog.asksaveasfilename(
            title="Save HECSPECS template as...",
            defaultextension=".csv",
            initialfile="HECSPECS_TEMPLATE.csv",
            filetypes=[("CSV files", "*.csv")],
        )
        if not dest:
            return
        try:
            with open(dest, "w", newline="") as f:
                f.write(",".join(REQUIRED_HECSPECS_COLUMNS) + "\n")
            messagebox.showinfo("Template saved", f"Template saved to:\n{dest}")
        except OSError as e:
            messagebox.showerror("Could not save template", str(e))

    def _open_hecspecs_editor(self):
        editor = tk.Toplevel(self.root)
        editor.title("HECSPECS Editor")

        # scrollable area, since REQUIRED_HECSPECS_COLUMNS is wide and rows can grow
        canvas = tk.Canvas(editor, height=350)
        scroll_y = tk.Scrollbar(editor, orient="vertical", command=canvas.yview)
        scroll_x = tk.Scrollbar(editor, orient="horizontal", command=canvas.xview)
        grid_frame = tk.Frame(canvas)

        grid_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=grid_frame, anchor="nw")
        canvas.configure(yscrollcommand=scroll_y.set, xscrollcommand=scroll_x.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        scroll_y.grid(row=0, column=1, sticky="ns")
        scroll_x.grid(row=1, column=0, sticky="ew")
        editor.grid_rowconfigure(0, weight=1)
        editor.grid_columnconfigure(0, weight=1)

        # header row
        for col_idx, col_name in enumerate(REQUIRED_HECSPECS_COLUMNS):
            tk.Label(
                grid_frame, text=col_name, width=14, relief="ridge", bg="#e0e0e0"
            ).grid(row=0, column=col_idx, sticky="nsew")

        row_widgets = []  # list of {col_name: tk.Entry}

        def add_row():
            row_idx = len(row_widgets) + 1
            row_entries = {}
            for col_idx, col_name in enumerate(REQUIRED_HECSPECS_COLUMNS):
                entry = tk.Entry(grid_frame, width=14)
                entry.grid(row=row_idx, column=col_idx, sticky="nsew")
                row_entries[col_name] = entry
            row_widgets.append(row_entries)

        def remove_last_row():
            if not row_widgets:
                return
            row_entries = row_widgets.pop()
            for entry in row_entries.values():
                entry.destroy()

        def save_and_close():
            if not row_widgets:
                messagebox.showerror("No rows", "Add at least one reach row before saving.", parent=editor)
                return

            rows_out = []
            for row_idx, row_entries in enumerate(row_widgets, start=1):
                row_values = {}
                for col_name, entry in row_entries.items():
                    raw = entry.get().strip()
                    expected_type = HECSPECS_COLUMN_TYPES[col_name]

                    if not raw and col_name in OPTIONAL_HECSPECS_COLUMNS:
                        row_values[col_name] = ""
                        continue

                    if expected_type is str:
                        if not raw:
                            messagebox.showerror(
                                "Missing value",
                                f"Row {row_idx}: '{col_name}' cannot be blank.",
                                parent=editor
                            )
                            return
                        row_values[col_name] = raw
                    else:
                        try:
                            expected_type(raw)
                        except ValueError:
                            messagebox.showerror(
                                "Invalid value",
                                f"Row {row_idx}: '{col_name}' must be a "
                                f"{'whole number' if expected_type is int else 'number'} "
                                f"(got: {raw!r}).",
                                parent=editor
                            )
                            return
                        row_values[col_name] = raw

                if not any(row_values.get(c, "") for c in SEDIMENT_COLUMNS):
                    messagebox.showerror(
                        "Missing sediment depth",
                        f"Row {row_idx}: fill in at least one sediment depth "
                        f"(SED_0 through SED_5).",
                        parent=editor
                    )
                    return

                if not any(row_values.get(c, "") for c in ROUGHNESS_COLUMNS):
                    messagebox.showerror(
                        "Missing roughness value",
                        f"Row {row_idx}: fill in at least one roughness value "
                        f"(N_0 through N_5).",
                        parent=editor
                    )
                    return

                rows_out.append(row_values)

            dest = filedialog.asksaveasfilename(
                title="Save HECSPECS as...",
                defaultextension=".csv",
                initialfile="HECSPECS.csv",
                filetypes=[("CSV files", "*.csv")],
                parent=editor,
            )
            if not dest:
                return

            try:
                with open(dest, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=REQUIRED_HECSPECS_COLUMNS)
                    writer.writeheader()
                    writer.writerows(rows_out)
            except OSError as e:
                messagebox.showerror("Could not save file", str(e), parent=editor)
                return

            self.hecspecs_path_var.set(dest)
            self._update_hecspecs_status(dest)
            editor.destroy()

        button_bar = tk.Frame(editor)
        button_bar.grid(row=2, column=0, columnspan=2, pady=8)
        tk.Button(button_bar, text="Add Row", command=add_row).pack(side="left", padx=5)
        tk.Button(button_bar, text="Remove Last Row", command=remove_last_row).pack(side="left", padx=5)
        tk.Button(button_bar, text="Save", command=save_and_close).pack(side="left", padx=15)

        add_row()  # start with one blank row

    def _validate_inputs(self):
        if not self.run_name_var.get().strip():
            messagebox.showerror("Missing run name", "Please enter a run name.")
            return False

        project_folder = self.project_folder_var.get().strip()
        if not project_folder or not os.path.isdir(project_folder):
            messagebox.showerror("Missing project folder", "Please select a valid project folder.")
            return False

        hecspecs_path = self.hecspecs_path_var.get().strip()
        if not hecspecs_path or not os.path.exists(hecspecs_path):
            messagebox.showerror("Missing HECSPECS file", "Please select a valid HECSPECS CSV.")
            return False

        destination = self.destination_var.get().strip()
        if destination and not os.path.isdir(destination):
            messagebox.showerror(
                "Invalid output folder",
                "The selected output folder doesn't exist. Leave it blank to use the "
                "project folder instead, or choose a valid folder."
            )
            return False

        try:
            is_valid, missing, extra = validate_hecspecs_headers(hecspecs_path)
        except OSError as e:
            messagebox.showerror("HECSPECS file error", f"Could not read HECSPECS CSV:\n{e}")
            return False
        if not is_valid:
            messagebox.showerror(
                "HECSPECS header mismatch",
                "The selected CSV is missing required column(s):\n\n"
                f"{', '.join(missing)}\n\n"
                "Use 'Fill In App...' to build a correctly-headed file."
            )
            return False

        return True

    def on_run_clicked(self):
        if not self._validate_inputs():
            return

        project_folder = self.project_folder_var.get().strip()

        try:
            prj_path, geom_path, flow_path, plan_path = auto_detect_project_files(project_folder)
        except ValueError as e:
            messagebox.showerror("Project folder error", str(e))
            return

        try:
            creek_name = read_creek_name_from_hecspecs(self.hecspecs_path_var.get().strip())
        except (ValueError, OSError) as e:
            messagebox.showerror("HECSPECS file error", str(e))
            return

        try:
            write_creek_locations_csv(
                config.MODEL_PATH_CSV,
                creek_name,
                prj_path, geom_path, flow_path, plan_path
            )
        except OSError as e:
            messagebox.showerror("File error", f"Could not prepare input CSVs:\n{e}")
            return

        try:
            is_valid, blank_columns, invalid_columns = validate_and_clean_hecspecs(
                self.hecspecs_path_var.get().strip(), config.BATCH_SPECS_CSV
            )
        except OSError as e:
            messagebox.showerror("HECSPECS file error", f"Could not read HECSPECS CSV:\n{e}")
            return

        if not is_valid:
            lines = []
            if blank_columns:
                lines.append("Blank/missing values in these columns:")
                for col, count in blank_columns.items():
                    lines.append(f"    {col}  ({count} row(s))")
            if invalid_columns:
                if lines:
                    lines.append("")
                lines.append("Values that aren't valid numbers in these columns:")
                for col, count in invalid_columns.items():
                    lines.append(f"    {col}  ({count} row(s))")
            messagebox.showerror(
                "HECSPECS needs review before running",
                "The HECSPECS file has issues that need fixing before this run "
                "can proceed:\n\n" + "\n".join(lines)
            )
            return

        self.run_button.config(state="disabled")
        self._clear_log()

        run_name = self.run_name_var.get().strip()
        destination = self.destination_var.get().strip()  # empty = default to project folder
        threading.Thread(
            target=self._run_pipeline_subprocess, args=(run_name, destination), daemon=True
        ).start()

    def _resolve_pipeline_command(self, run_name, destination):
        """
        Returns (pipeline_path, command_list).

        destination: output folder for all generated files, or "" to
        default to the project folder. Passed through as a third CLI
        argument; run_pipeline.py treats an empty string the same as
        "not provided".

        Pipeline location is always derived from config.BASE_DIR (the
        fixed install path), never from app.exe's own runtime location --
        this is what allows app.exe to be moved without breaking the
        lookup, as long as the project is still installed at BASE_DIR.

        Dev mode (running app.py directly with a real Python interpreter):
        launch run_pipeline.py via that same interpreter.

        Frozen mode (app.py packaged into app.exe via PyInstaller):
        sys.executable points at app.exe itself -- there is no general
        Python interpreter to hand a .py script to. Instead, this expects
        run_pipeline.py to have been separately packaged into its own
        run_pipeline.exe, at BASE_DIR\\run_pipeline\\run_pipeline.exe.
        No Python installation is required on the machine running the
        packaged app.
        """
        if getattr(sys, "frozen", False):
            pipeline_path = os.path.join(config.BASE_DIR, "run_pipeline", "run_pipeline.exe")
            command = [pipeline_path, run_name, destination]
        else:
            pipeline_path = os.path.join(config.BASE_DIR, "run_pipeline.py")
            command = [sys.executable, "-u", pipeline_path, run_name, destination]
        return pipeline_path, command

    def _run_pipeline_subprocess(self, run_name, destination):
        pipeline_path, command = self._resolve_pipeline_command(run_name, destination)

        # --- diagnostics: confirm exactly what's about to be launched ---
        log_queue.put(f"DEBUG: sys.executable = {sys.executable!r}\n")
        log_queue.put(f"DEBUG: run_name = {run_name!r}\n")
        log_queue.put(f"DEBUG: pipeline_path exists = {os.path.exists(pipeline_path)} ({pipeline_path})\n")
        log_queue.put(f"DEBUG: command = {command!r}\n")
        # ------------------------------------------------------------

        try:
            proc = subprocess.Popen(
                command,
                cwd=config.BASE_DIR,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            proc_handle["proc"] = proc
            log_queue.put(f"DEBUG: subprocess PID = {proc.pid}\n")

            for line in proc.stdout:
                log_queue.put(line)

            proc.wait()
            log_queue.put(f"\n[Process exited with code {proc.returncode}]\n")

        except Exception as e:
            log_queue.put(f"ERROR launching pipeline: {e}\n")
        finally:
            proc_handle["proc"] = None
            cleanup_temp_csvs()
            log_queue.put("__DONE__")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

    def _clear_form(self):
        self.run_name_var.set("")
        self.project_folder_var.set("")
        self.hecspecs_path_var.set("")
        self.destination_var.set("")

        self.preview_text.config(state="normal")
        self.preview_text.delete("1.0", "end")
        self.preview_text.config(state="disabled")

        self.hecspecs_status_label.config(text="", fg="black")

        self._clear_log()

    def _poll_log_queue(self):
        try:
            while True:
                line = log_queue.get_nowait()
                if line == "__DONE__":
                    self.run_button.config(state="normal")
                else:
                    self.log_text.config(state="normal")
                    self.log_text.insert("end", line)
                    self.log_text.see("end")
                    self.log_text.config(state="disabled")
        except queue.Empty:
            pass
        self.root.after(100, self._poll_log_queue)

    def _on_close(self):
        proc = proc_handle.get("proc")
        if proc is not None and proc.poll() is None:
            if not messagebox.askyesno(
                "Pipeline running",
                "A pipeline run is still in progress. Close anyway? "
                "(HEC-RAS may be left in an inconsistent state.)",
            ):
                return
            try:
                proc.terminate()
            except OSError:
                pass
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()

    pipeline_exe_path = os.path.join(config.BASE_DIR, "run_pipeline", "run_pipeline.exe")
    if getattr(sys, "frozen", False) and not os.path.exists(pipeline_exe_path):
        root.withdraw()
        messagebox.showerror(
            "Missing pipeline executable",
            "This app (app.exe) can be run from anywhere -- but it needs "
            "the pipeline component installed at a fixed location, which "
            "was not found:\n\n"
            f"    {pipeline_exe_path}\n\n"
            "Please make sure run_pipeline.exe is installed there before "
            "running this app."
        )
        sys.exit(1)

    app = HecAutomateGUI(root)
    root.mainloop()
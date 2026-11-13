# hec-automate

# HEC-RAS Batch Sediment and Roughness Scenario Automation

###Overview

This program automates the creation, execution, and output extraction of HEC-RAS 1D steady-state models across a matrix of sediment accumulation and Manning's roughness scenarios for creek maintenance analysis. It is designed to process multiple maintenance reaches within a single creek model. Each reach can have up to 6 sediment depths and up to 6 roughness values, and every combination is run as its own scenario (up to 36 scenarios per reach).

There are two ways to run it:

- `app.py` -- a GUI so people without Python experience can set up and run the tool: pick the project folder, load or fill in HECSPECS, choose an output folder, and click Run.
- `run_pipeline.py` -- the backend. The GUI calls it, or it can be run directly.

The pipeline is organized into two sequential phases that run end to end without human intervention after startup:

**PHASE ONE: Geometry and Plan File Creation** - Pure text file manipulation, no HEC-RAS connection required. Creates all scenario geometry files and associated plan files, organized into batch folders to avoid hitting the g99 geometry file ceiling.

**PHASE TWO: Run and Extract** - Computes every scenario plan through the HEC-RAS COM API and extracts output at every cross section, for every flow profile in the flow file.

The original project files are never modified.

---------------

## Requirements

- Windows
- HEC-RAS 6.0 installed and licensed, with the COM interface registered
- HEC-RAS project must contain exactly one river and one reach (see Open Items)
- Python 3.11 or 3.12 (3.13 is not compatible with pywin32)
- pywin32

It is recommended not to use HEC-RAS or heavy programs like Civil 3D or ArcMap while a run is going. Run from a project copy on the local C: drive when possible. The tool reads and rewrites many small files, which is much slower on a network drive, especially over VPN.

---------------

## Using the App

The How to Use window opens when the app starts and can be reopened with the How to Use button in the top-right corner.

1. **Run name** -- a short label used to name the results files.
2. **Project folder** -- folder containing the HEC-RAS project. Must contain exactly one .prj. The app uses the lowest-numbered geometry (.g##), flow (.f##), and plan (.p##) files as the base files to build scenarios from. Only one flow file is used, but every profile in it is computed and extracted.
3. **Detected files** -- shows which .prj/.g##/.f##/.p## files were found. Check these before running.
4. **Output folder** -- where batch folders and results are written. Auto-fills to the project folder.
5. **HECSPECS CSV** -- the reaches and scenarios to run. Either:
   - **Browse** to an existing CSV, or
   - **Fill In App...** to build it in a table in the app (Add Row, Remove Last Row, Save). This guarantees the headers are correct.

   A green "Headers and values OK" message means the file is ready. A red message lists the columns that need fixing.
6. **Run** -- starts the pipeline in the background. Progress streams into the log window and the window stays responsive.

**Clear** resets the form. Closing the app during a run asks for confirmation first, since stopping mid-run can leave HEC-RAS in an inconsistent state.

### What the App Does When Run Is Clicked

1. Checks the run name, project folder, output folder, and HECSPECS file
2. Re-detects the base project files
3. Reads `CREEK_NAME` from the first row of HECSPECS (spaces replaced with underscores)
4. Writes a temporary CreekLocations CSV with the creek name and the paths to the .prj, base geometry, flow, and plan files
5. Validates and cleans HECSPECS and writes a temporary copy for the pipeline
6. Starts `run_pipeline.py` with the run name and output folder
7. Deletes both temporary CSVs when the run finishes

### Base Plan File

The base plan must be a plan saved by HEC-RAS 6.0. Each scenario plan is a copy of it with these lines changed:

- `Plan Title=` -- scenario title
- `Short Identifier=` -- last 16 characters of the scenario title
- `Program Version=6.00`
- `Geom File=` -- the scenario's geometry file
- `Run HTab= 1` -- forces HEC-RAS to rebuild hydraulic property tables from the edited geometry. Without this, HEC-RAS can compute against cached tables from the base geometry and every scenario returns the same results.
- `HDF Fixed Rows= 0` -- sizes the results array to the actual geometry. With fixed rows, cross sections beyond the original array size were silently missing from output.

All other computation settings are preserved exactly as they appear in the base plan.

---------------

## Input Files

### HECSPECS.csv

One row per maintenance reach. All columns must be present in the header, even if some sediment/roughness values are left blank.

Columns:

- `CREEK_NAME` -- name of the creek. Read from the first row and used in scenario titles.
- `CREEK_REACH` -- name of the maintenance reach (e.g. REACH 1A). Used in scenario titles and results. Must be unique.
- `DS_STATION` -- downstream station limit of the maintenance reach in feet. Only cross sections at or between DS_STATION and US_STATION receive sediment and roughness edits.
- `US_STATION` -- upstream station limit of the maintenance reach in feet.
- `REP_XS_STATION` -- representative cross section for the reach, entered by the user. Passed through to the results for use in the nomograph spreadsheet.
- `TOP_OF_BANK` -- top of bank elevation for the reach, entered by the user. Passed through to the results.
- `N_0` through `N_5` -- up to six Manning's n values. Blank cells are skipped. At least one is required per row. Applied to every Manning's n value at every in-reach cross section.
- `SED_0` through `SED_5` -- up to six sediment depths in feet. Blank cells are skipped. At least one is required per row. Applied as absolute elevation (thalweg + sed_depth) at every in-reach cross section.

Scenarios per reach = (number of n values) x (number of sediment depths).

Example:

|CREEK_NAME|CREEK_REACH|DS_STATION|US_STATION|REP_XS_STATION|TOP_OF_BANK|N_0|N_1|N_2|N_3|N_4|N_5|SED_0|SED_1|SED_2|SED_3|SED_4|SED_5|
|----------|-----------|----------|----------|--------------|-----------|---|---|---|---|---|---|-----|-----|-----|-----|-----|-----|
|LowerSilver|REACH 1|0|6000|3200|138.5|0.035|0.05|0.07|0.1|||0|2|4|6|||
|LowerSilver|REACH 2|6000|12000|8100|141.2|0.035|0.05|0.07|0.1|||0|2|4|6|||

### HECSPECS Validation

Before a run, the app checks HECSPECS:

- Every column except the N and SED columns must be filled in on every row
- Each row needs at least one N value and at least one SED value
- Numeric columns (stations, top of bank, N, SED) have any spaces inside the value removed automatically, e.g. `0.0 35` becomes `0.035`
- Anything that still isn't a valid number blocks the run and is reported by column. It is not guessed at or changed.

### CreekLocations.csv

Generated automatically by the app from the selected project folder and HECSPECS. Only needs to be made by hand when running `run_pipeline.py` without the app.

Columns:

- `CREEK_NAME` -- name of the creek
- `PRJ_PATH` -- full path to the base HEC-RAS project file (.prj)
- `BASE_GEOM_PATH` -- full path to the base geometry file (.g##). Never modified. All scenario geometries are derived from this file.
- `BASE_FLOW_PATH` -- full path to the steady flow file (.f##). Copied unchanged into every batch folder. Flow conditions never change between scenarios.
- `BASE_PLAN_PATH` -- full path to the base plan file (.p##) used as the template for all scenario plans.

---------------

## Output Structure

All output goes to the output folder (the project folder by default).

### Batch Folders

Reaches are packed into numbered batch folders (`Batch1`, `Batch2`, etc.). Each batch can hold `99 - base_geom_number` scenarios. Reaches are added to a batch until the next reach's scenarios won't fit, then a new batch starts. If a single reach needs more scenarios than fit in one batch, the run stops with an error telling you to reduce its sediment or roughness values.

Each batch folder contains:

- A copy of the base prj, geometry, flow, and plan files
- One geometry file and one plan file per scenario, registered in the batch prj
- One results CSV per scenario per flow profile

### Scenario File Naming

Scenario geometry and plan files are named by their extension number (e.g. `LowerSilver.g05`, `LowerSilver.p05`). The title inside each file identifies the scenario:

{CREEK_NAME}_{CREEK_REACH}_sed{sed_depth}ft_n{n_value}

Spaces are replaced with underscores. Example: `LowerSilver_REACH_1A_sed2.0ft_n0.04`

### Per-Scenario Results

One CSV per scenario per flow profile, written to the batch folder:

{profile}_{scenario_title}.csv

One row per cross section in the model. Structures (bridges, culverts, etc.) are skipped.

### Combined Results

One combined CSV per flow profile, written to the output folder:

{profile}_{run_name}_ALL_RESULTS.csv

Contains every scenario for every reach, sorted by reach (HECSPECS order), then sediment depth, then n value. Spaces in profile names are replaced with underscores.

Columns:

- `REACH`, `SED_DEPTH`, `N_VALUE` -- the scenario
- `TOP_OF_BANK`, `REP_XS_STATION` -- from HECSPECS for that reach
- `River_Sta` -- cross section station
- `Profile` -- flow profile name
- HEC-RAS output variables (nVar code): W.S. Elev (2), Max Chl Dpth (4), Min Ch El (5), Q Total (9), Flow Area (10), W.P. Total (14), Top Wdth Act (29), Area (32), Mann Comp (47), Top Width (62), Shear Total (150), Shear LOB (151), Shear Chan (152), Shear ROB (153), Invert Slope (196), L. Freeboard (199), R. Freeboard (200), Levee El Left (201), Levee El Right (202), L. Levee Frbrd (205), R. Levee Frbrd (206), Mann Wtd Total (207), Top W Act Chan (226)

---

## How It Works

### Phase 1 -- Geometry and Plan Creation

1. Reads CreekLocations.csv and HECSPECS.csv
2. Reads flow profiles from the flow file's `Number of Profiles=` and `Profile Names=` lines and checks the count matches the number of names
3. Packs reaches into batches
4. For each batch:
   - Creates the batch folder and copies in the base files (files already there are not overwritten)
   - Checks for leftover geometry files (see Skip Logic and Pre-Run Checks)
   - For each reach, loops through every sediment and roughness combination using `itertools.product(sed_depths, n_values)` with sediment as the outer loop
   - For each scenario: registers the next geometry number in the prj, writes the scenario geometry, sets `Geom Title=`, registers the next plan number, and writes the scenario plan

### Geometry Editing

The geometry editor splits the file on the `Type RM Length L Ch R =` delimiter to process each node block independently. Only node type 1 (regular cross sections) within the reach station bounds are edited. All other node types (culverts, bridges, multiple openings, inline structures, lateral structures) and all out-of-range cross sections are copied through unchanged.

For each in-reach cross section the editor:
- Reads `#Sta/Elev=` data in 8-character fixed-width fields to collect all elevation values
- Calculates thalweg as the global minimum elevation (see Open Items)
- Inserts or replaces `Sediment Elevation=` after `Bank Sta=` with the value thalweg + sed_depth
- Reads `#Mann=` header to get the triplet count, reads exactly `n_count * 3 * 8` characters of Manning's data, replaces the n value in each triplet with the scenario n value, and writes back preserving original line structure

### Skip Logic and Pre-Run Checks

Before creating anything in a batch, the pipeline builds the full list of scenario titles the current HECSPECS should produce and compares it against the geometry titles already in the batch folder:

- **Leftover files** -- if the folder has geometry files that don't match any expected scenario (e.g. from an earlier run with a different HECSPECS), the run stops with an error listing them. Clear or move that batch folder before running again.
- **Existing scenarios** -- any scenario whose title already exists is skipped, so an interrupted run can be restarted without duplicating work.

When registering files in the prj, references to geometry or plan files that no longer exist on disk are removed.

### Phase 2 -- Run and Extract

HEC-RAS is opened once via `win32com.client.Dispatch`. For every scenario plan in every batch:

1. Writes `Current Plan=` for that plan directly into the batch prj (text edit, no COM call)
2. Opens the project fresh with `RC.Project_Open`
3. Calls `RC.Compute_HideComputationWindow()` and `RC.Compute_CurrentPlan(0, None, True)`
4. For each flow profile, gets all nodes with `Geometry_GetNodes` and pulls each output variable at each cross section with `Output_NodeOutput`

One compute runs all profiles, so extraction just reads each profile's output from the same compute.

If extraction fails for a plan or profile, it is logged and skipped and the run continues. Failures are listed at the end of the run. `RC.QuitRAS()` is called when the run finishes, even if there was an error.

**Sticky COM API** -- HEC-RAS's COM functions hold on to state within a session. Switching plans with `Plan_SetCurrent` and reading output with `Output_ReachOutput` returned results from a previous plan instead of the current one. The pipeline gets around this by writing `Current Plan=` to the prj and reopening the project before every plan, so HEC-RAS re-reads the prj from disk each time. `Plan_SetCurrent` is no longer used. Do not change this back to a single-session loop.

**Why Output_NodeOutput** -- the bulk outputs (`Output_ReachOutput` and the HDF Cross Section Attributes) capped at 127 entries including structures, so some cross sections were missing. Pulling node by node reaches every cross section.

### Running Without the App

python run_pipeline.py

With no arguments, prompts for a run name and a y/n confirmation, and reads the input CSVs from the paths in `config.py`.

python run_pipeline.py <run_name> <output_folder>

With arguments, skips the prompts. A blank output folder uses the project folder. This is how the app calls it.

---

## Configuration

Set in `config.py`:

- `BASE_DIR` -- install location of the tool
- `MODEL_PATH_CSV` -- path to CreekLocations.csv
- `BATCH_SPECS_CSV` -- path to the HECSPECS CSV the pipeline reads
- `RAS_COM_PROGID` -- HEC-RAS COM class (HEC-RAS 6.0)
- `RIVER_ID`, `REACH_ID` -- river and reach extracted (1 and 1 for a single river/reach model)
- `MAX_RUNS` -- stops after this many computes. Set to a small number like 2 for testing. Set to `None` to run everything with no limit.

---

## Project Structure

- `app.py` -- GUI
- `run_pipeline.py` -- pipeline entry point
- `config.py` -- paths and settings
- `src/hec_1Dsteady_pipeline/`
  - `archiving.py` -- run name and y/n prompts when running without the app
  - `batching.py` -- available file slots and packing reaches into batches
  - `com_extract.py` -- output variable list and per-cross-section extraction
  - `flow_parser.py` -- reads flow profiles from the flow file
  - `folder_setup.py` -- creates batch folders and copies base files
  - `geometry_editor.py` -- sediment elevation and Manning's n edits
  - `io_loaders.py` -- loads CreekLocations and HECSPECS
  - `plan_editor.py` -- creates scenario plans, finds and filters plans, checks existing titles
  - `prj_editor.py` -- registers geometry/plan files and sets Current Plan in the prj

---

## Known Issues

- Roughness and sediment input edge cases:
  - Decimals without a 0 in front
  - Special characters and spaces within values
  - Non-consecutive columns filled (e.g. N_0 and N_2 filled, not N_1)
- Typing a project folder path works, but the files don't show up in Detected files (only updates through Browse)
- Duplicate iterations of as-built geometry, plan, and flow files
- No values output when 2 scenarios were run

---

## Open Items and Known Limitations

The following items are pending engineer input or future development:

- Only one river and one reach per HEC-RAS project is supported. Extraction uses `RIVER_ID` and `REACH_ID` from `config.py`, so in a model with more than one, everything except the first river/reach is silently missing from results.
- Culvert sediment fill via `Culvert Depth Blocked=` is not yet implemented. Currently only cross sections receive sediment elevation edits. Whether this is sufficient for freeboard analysis at culverts is an open engineer question.
- Structures beyond culverts (bridges, multiple openings, inline structures, lateral structures) have not been confirmed regarding whether sediment fill or roughness changes are needed beyond what bounding cross section edits already provide.
- Thalweg is currently calculated as the global minimum elevation across all station-elevation points in a cross section. This assumes overbank elevations are always higher than channel elevations, which is pending engineer confirmation for SCVWD models.
- The up/down index argument in `Output_NodeOutput` is hardcoded to 0. Structures are skipped, so this only matters if structure output is added later.
- `REP_XS_STATION` and `TOP_OF_BANK` come from HECSPECS as entered and are not checked against the model.
- The compute result is printed to the log but not checked. A failed compute still goes on to extraction.

---

## Key Source References

- Breaking the HEC-RAS Code by Goodell
- HEC-RAS 6.0 Users Manual

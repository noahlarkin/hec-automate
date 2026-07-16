# hec-automate

# HEC-RAS Batch Sediment and Roughness Scenario Automation

###Overview

This script automates the creation, execution, and output extraction of HEC-RAS 1D steady-state models across a matrix of sediment accumulation and Manning's roughness scenarios for creek maintenance analysis. It is designed to process multiple maintenance reaches within a single creek model, generating 16 scenarios per reach (4 roughness values x 4 sediment depths) and producing a freeboard results table per reach.

The script is organized into two sequential phases that run end to end without human intervention after startup:

**PHASE ONE: Geometry and Plan File Creation** - Pure text file manipulation, no HEC-RAS connection required. Creates all scenario geometry files and associated plan files, organized into batch folders to avoid hitting the g99 geometry file ceiling.

**PHASE TWO: Run and Extract** - Opens HEC-RAS once via the COM API, runs every scenario plan sequentially, extracts output variables at the representative cross section for each reach, and writes a results CSV per reach.

---------------

## Requirements

- Python 3.11-3.13
- pywin32
- HEC-RAS 6.0 installed with COM interface registered
- No other third-party libraries required

---------------

## Input Files

### CreekLocations.csv

One row per creek. Defines the source project files that the script copies from. Since only one creek is processed per run, this file will have one data row.

Columns:

- `CREEK_NAME` -- name of the creek, must match exactly what appears in HECSPECS.csv
- `PRJ_PATH` -- full path to the base HEC-RAS project file (.prj)
- `BASE_GEOM_PATH` -- full path to the base geometry file (.g##). This file is never modified by the script. All scenario geometries are derived from this file.
- `BASE_FLOW_PATH` -- full path to the steady flow file (.f##). This file is copied unchanged into every batch folder. Flow conditions never change between scenarios.
- `BASE_PLAN_PATH` -- full path to a valid HEC-RAS 6.0 plan file (.p##) to use as the template for all scenario plans. This must be a plan file that was saved by HEC-RAS 6.0 (Program Version=6.00), not an older version. The script overwrites Plan Title=, Short Identifier=, Program Version=, and Geom File= in each copy. All other computation settings are preserved exactly as they appear in this template.

Example:

|       CREEK_NAME       |        PRJ_PATH        |     BASE_GEOM_PATH     |     BASE_FLOW_PATH     |     BASE_PLAN_PATH     |
|------------------------|------------------------|------------------------|------------------------|------------------------|
|       Cold Creek       |   c:\path\creek.prj    |   c:\path\creek.g01    |   c:\path\creek.f01    |   c:\path\creek.p01    |


### HECSPECS.csv

One row per maintenance reach. Each row defines one reach's station boundaries, roughness values, sediment depths, and profile index. Multiple rows can belong to the same creek.

Columns:

- `CREEK_NAME` -- must match exactly what appears in CreekLocations.csv
- `CREEK_REACH` -- name of the maintenance reach (e.g. REACH 1A). Used as the scenario title component and results CSV filename. Must be unique within the creek.
- `DS_STATION` -- downstream station limit of the maintenance reach in feet. Only cross sections at or between DS_STATION and US_STATION receive sediment and roughness edits.
- `US_STATION` -- upstream station limit of the maintenance reach in feet.
- `REP_XS_STATION` -- currently loaded but not used for output extraction. The representative cross section is determined automatically by finding the cross section with the lowest bank elevation within the reach station limits.
- `TOP_OF_BANK` -- currently loaded but not used for freeboard calculation. Top of bank is determined automatically from output variables LOB Elev (nVar=197) and ROB Elev (nVar=198).
- `N_LOW`, `N_MID1`, `N_MID2`, `N_HIGH` -- four Manning's n values defining the roughness scenario matrix. Applied uniformly to all Manning's n triplets at every in-reach cross section.
- `SED_0`, `SED_1`, `SED_2`, `SED_3` -- four sediment depth values in feet defining the sediment scenario matrix. Applied as absolute elevation (thalweg + sed_depth) at every in-reach cross section.
- `LOS_PROFILE_INDEX` -- zero-based index of the Level of Service flow profile within the steady flow file. Used to select the correct profile when extracting output variables.

Example:

|CREEK_NAME|CREEK_REACH|DS_STATION|US_STATION|REP_XS_STATION|TOP_OF_BANK|N_LOW|N_MID1|N_MID2|N_HIGH|SED_0|SED_1|SED_2|SED_3|LOS_PROFILE_INDEX|
|-----------|-----------|---------|----------|--------------|-----------|-----|------|-------|-----|-----|-----|-----|-----|-----------------|
|ColdCreek|REACH 1|0|6000|8000|10|0.035|0.05|0.07|0.1|0|2|4|6|1|
|ColdCreek|REACH 2|6000|12000|8000|10|0.035|0.05|0.07|0.1|0|2|4|6|1|
|ColdCreek|REACH 3|12000|15000|8000|10|0.035|0.05|0.07|0.1|0|2|4|6|1|
---

## Output Structure

### Batch Folders

The script creates numbered batch folders inside the base project directory (e.g. `Batch1`, `Batch2`). The number of reaches per batch is calculated automatically as `floor((99 - base_geom_number) / 16)` to avoid exceeding the g99 geometry file ceiling. Each batch folder contains:

- A copy of the base prj, geometry, flow, and plan files
- 16 scenario geometry files per reach (e.g. `LowerSilver.g05` through `LowerSilver.g20` for one reach starting from g04)
- 16 scenario plan files per reach with matching numbering
- One results CSV per reach (see below)

The original project folder is never modified.

### Scenario File Naming

Scenario geometry and plan files are named by their extension number (e.g. `LowerSilver.g05`, `LowerSilver.p05`). The title inside each file identifies the scenario:

{CREEK_NAME}_{CREEK_REACH}_n{n_value}_sed{sed_depth}ft

Example: `LowerSilver_REACH 1A_n0.04_sed2.0ft`

The plan file's `Short Identifier=` field uses the last 16 characters of the scenario title.

### Results CSV

One CSV per reach, named `{CREEK_NAME}_{CREEK_REACH}_results.csv`, written to the batch folder containing that reach's scenarios.

Columns:

- `River_Sta` -- river station of the representative cross section, determined automatically as the cross section with the lowest bank elevation within the reach station limits
- `Roughness` -- Manning's n value for this scenario
- `Sediment` -- sediment depth in feet for this scenario
- `Min_Ch_El` -- minimum channel elevation at the representative cross section (nVar=5)
- `WS_Elev` -- computed water surface elevation at the representative cross section (nVar=2)
- `Top_of_Bank` -- lowest bank elevation found within the reach station limits, from LOB Elev (nVar=197) and ROB Elev (nVar=198), constant across all 16 scenarios for a given reach
- `Freeboard` -- Top_of_Bank minus WS_Elev in feet, negative values indicate overtopping

---

## How It Works

### Phase 1 -- Geometry and Plan Creation

1. Reads CreekLocations.csv and HECSPECS.csv
2. Calculates batch size from the base geometry file number
3. Groups all reaches into batches
4. For each batch:
   - Creates the batch folder
   - Copies base prj, geometry, flow, and plan files into it
   - For each reach in the batch, loops through all 16 combinations of roughness and sediment depth using `itertools.product(sed_depths, n_values)` with sediment as the outer loop
   - For each scenario, creates a geometry file by editing the base geometry in plain text (no HEC-RAS connection), then creates a plan file by copying the base plan and updating identifying fields
   - Registers each geometry and plan file in the batch prj

### Geometry Editing

The geometry editor splits the file on the `Type RM Length L Ch R =` delimiter to process each node block independently. Only node type 1 (regular cross sections) within the reach station bounds are edited. All other node types (culverts, bridges, multiple openings, inline structures, lateral structures) and all out-of-range cross sections are copied through unchanged.

For each in-reach cross section the editor:
- Reads `#Sta/Elev=` data in 8-character fixed-width fields to collect all elevation values
- Calculates thalweg as the global minimum elevation (see open items below)
- Inserts or replaces `Sediment Elevation=` after `Bank Sta=` with the value thalweg + sed_depth
- Reads `#Mann=` header to get the triplet count, reads exactly `n_count * 3 * 8` characters of Manning's data, replaces n values at triplet positions 1, 4, 7... with the scenario n value, and writes back preserving original line structure

### Skip Logic

Before creating any scenario, the script scans existing geometry file titles in the batch folder. Any scenario whose title already exists is skipped. This means the script can be stopped and restarted at any point without duplicating work or corrupting existing files.

### Phase 2 -- Run and Extract

1. Opens HEC-RAS once via `win32com.client.Dispatch("RAS60.HECRASController")`
2. For each batch folder, opens the batch prj via `RC.Project_Open`
3. Scans all plan files in the batch folder, groups them by HECSPECS reach based on title substring matching, skipping the base plan which does not match any scenario title
4. For each reach group:
   - Runs each of the 16 scenario plans sequentially
   - Before each run, updates `Current Plan=` in the prj text directly and calls `RC.Plan_SetCurrent(plan_title)` via API
   - Calls `RC.Compute_HideComputationWindow()` and `RC.Compute_CurrentPlan(0, None, True)`
   - On the first completed run for each reach, calls `find_rep_xs_and_top_of_bank` which loops through every HEC-RAS reach in the river, filters nodes by DS_STATION/US_STATION, pulls LOB Elev and ROB Elev for each in-range node, and identifies the node with the lowest combined bank elevation as the representative cross section
   - For every run, extracts WS Elev and Min Ch El at the representative cross section node
   - Calculates freeboard as Top_of_Bank minus WS_Elev
   - After all 16 scenarios for a reach complete, writes the results CSV
5. Calls `RC.QuitRAS()` after all batches are complete

---

## Configuration

`MAX_RUNS` near the top of the run phase controls how many scenario plans are computed before the script stops. Set to a small number like 2 for testing. Set to `None` to run everything with no limit.

`river_id = 1` is set at the top of the run phase. Since only one creek is processed per run, this is always 1. If a model with multiple rivers is ever encountered this will need to be updated.

---

## Open Items and Known Limitations

The following items are pending engineer input or future development:

- Culvert sediment fill via `Culvert Depth Blocked=` is not yet implemented. Currently only bounding cross sections receive sediment elevation edits. Whether this is sufficient for RCDP freeboard analysis at culverts is an open engineer question.
- Thalweg is currently calculated as the global minimum elevation across all station-elevation points in a cross section. Filtering to elevations between bank stations only has been implemented but is tabled pending engineer confirmation that overbank elevations are always higher than channel elevations in SCVWD models.
- The up/down index argument in `Output_NodeOutput` is hardcoded to 0 for all nodes including bridges. The correct value for bridge upstream and downstream faces is pending engineer clarification.
- `REP_XS_STATION` and `TOP_OF_BANK` columns in HECSPECS.csv are loaded but not currently used. The script determines these automatically from output variables. Whether to cross-check against engineer-provided values is a future decision.
- Structures beyond culverts (bridges, multiple openings, inline structures, lateral structures) have not been confirmed regarding whether sediment fill or roughness changes are needed beyond what bounding cross section edits already provide.
- The profile selection is currently hardcoded via `LOS_PROFILE_INDEX` as a zero-based index into the flow file profiles. A flow file profile name picker with engineer confirmation prompt is planned but not yet implemented.
- Results export currently contains only River_Sta, Roughness, Sediment, Min_Ch_El, WS_Elev, Top_of_Bank, and Freeboard. Additional output columns from the HEC-RAS output variable list will be added once the engineer specifies which variables are needed.
- Multiple river support within a single geometry is partially handled -- `find_rep_xs_and_top_of_bank` loops through all HEC-RAS reaches automatically, but `river_id` is hardcoded to 1. A river selection prompt is planned.
- PyInstaller packaging into a standalone .exe has not yet been implemented.

---

## Key Source References

- Breaking the HEC-RAS Code by Goodell -- Appendix A (HECRASController API functions and arguments), Appendix E (output variable nVar index numbers)
- HEC-RAS 6.0 Users Manual -- Chapter 5 (geometry file structure, fixed sediment elevations, culvert Depth Blocked field, bounding cross section behavior for bridges and culverts)
- HEC-RAS 6.0 geometry file format confirmed from real LowerPenitencia geometry file

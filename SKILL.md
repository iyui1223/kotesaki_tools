---
name: scientific-project-structure
description: Standardize directory trees, naming conventions, and numbered shell-script pipelines for scientific computing projects (e.g. HPC, Slurm-based). Use this skill whenever organizing, refactoring, or starting a new scientific project so that all steps, scripts, logs, data, and figures follow a consistent, discoverable structure with centralized constants.
---

# Scientific Project Structure & Pipeline Skill

Use this skill to design and maintain **clear, numbered, reproducible pipelines** for scientific projects.
It enforces:
- A predictable **directory tree**
- Intuitive, numbered **step naming** (`F00_...`, `F01_...`, …)
- **Shell-governed jobs** whose scripts make the pipeline readable
- Centralized **constants / environment variables** under `Const/`

Always follow these rules when you:
- Create a new project
- Add a new step (e.g. new analysis stage)
- Suggest file names / Slurm scripts
- Refactor an existing messy project into a clean layout

---

## 1. Core Principles

When using this skill, keep these principles in mind:

1. **Numbered steps**  
   - Each major processing step gets an ID: `F00`, `F01`, `F02`, …  
   - Combine the ID with a **short, descriptive name**:
     - Good: `F00_preprocess`, `F01_regression`, `F02_visualize_timeseries`
     - Avoid vague names like `F01_step1`, `F02_misc`

2. **Directory tree mirrors the pipeline**  
   - Top-level directories indicate content *type*:
     - `Sh/`     — Shell & Slurm job scripts
     - `Python/` — Python codes
     - `Data/`   — Input/output data
     - `Figs/`   — Figures/plots
     - `Log/`    — Logs (stdout/stderr, summaries)
     - `Work/`   — Ephemeral working directories per step
     - `Const/`  — Constants, configuration, env settings
   - Within each of these, use the same `Fxx_name` pattern to indicate which step produced/uses the content.

3. **Shell scripts are the “mother” controllers**  
   - Each step is governed by a **single main shell script**:
     - e.g. `Sh/F00_preprocess_slurm.sh`
   - That script:
     - Sets up the working directory
     - Symlinks/copies inputs and code
     - Submits or runs the main Python job(s)
     - Moves final outputs to the proper `Data/`, `Figs/`, and `Log/` locations

4. **Centralize constants in `Const/`**  
   - Do **not** hardcode permanent parameters (paths, domain settings, experiment names, etc.) in every script.  
   - Instead, store them in:
     - Shell config: `Const/env_settings.sh`
     - Optional YAML/TOML: e.g. `Const/params_global.yaml`
   - Scripts **source or load** these constants.

---

## 2. Standard Directory Layout

When asked to design or refactor a project, propose a tree like:

```text
project_root/
  Sh/
    F00_preprocess_slurm.sh
    F01_data_analysis_slurm.sh
    F02_visualize_results_slurm.sh
  Python/
    preprocess.py
    data_analysis.py
    visualize_results.py
    utils_io.py
    utils_plot.py
  Const/
    env_settings.sh
    params_global.yaml
  Data/
    F00_preprocess/
    F01_data_analysis/
    F02_visualize_results/
  Figs/
    F01_data_analysis/
    F02_visualize_results/
  Log/
    F00_preprocess/
    F01_data_analysis/
    F02_visualize_results/
  Work/
    (created dynamically by shell scripts)
````

### Naming conventions
* **General rule for easier typing**:
   * Only use the FXX_ header for top-level, user-invoked shell scripts.
   
   Why:
   * If many files share the same starting character, tab-completion must disambiguate more characters, increasing typing. 
   * When scanning a directory, the FXX_ entries quickly show which files are steps vs helpers — making the call tree obvious.
   Tolerances & exceptions:
   * Two duplicates of the same step are tolerable (for example, for the user ivocative script and its slurm wrapper):
       * F01_preprocess_slurm.sh
       * F01_preprocess.sh
   
* **Steps**: `FXX_shortname`

  * `XX` = two-digit integer (`00`, `01`, `02`, …)
  * `shortname` describes the purpose (e.g. `preprocess`, `downscale`, `train_model`, `eval`, `visualize`)

* **Shell scripts** (`Sh/`):

  * For Slurm / batch jobs:

    * `Sh/F00_preprocess_slurm.sh`
    * `Sh/F01_train_model_slurm.sh`
  * For local or driver scripts (no Slurm):

    * `Sh/F00_preprocess.sh`

* **Python scripts** (`Python/`):

  * Mirror semantic meaning, not necessarily the `FXX` prefix:

    * `Python/preprocess.py`
    * `Python/train_model.py`
    * `Python/evaluate_metrics.py`
    * `Python/plot_spatial_maps.py`

* **Data/Figs/Log subdirectories**:

  * Use `FXX_shortname/` to indicate “products of this step”:

    * `Data/F00_preprocess/`
    * `Data/F01_train_model/`
    * `Figs/F02_visualize/`
    * `Log/F01_train_model/`

* **Work directories**:

  * For each step, main script creates:

    * `Work/FXX_shortname/`
    * `Work/FXX_shortname/out/`


---

## 3. Shell Script Responsibilities (Per Step)

When creating or editing `Sh/FXX_name*.sh`, follow this pattern:

1. **Load constants and environment**

   * At the top of the script:

     ```bash
     #!/bin/bash
     #SBATCH --job-name=F00_preprocess
     #SBATCH --output=Log/F00_preprocess/slurm_%j.out
     #SBATCH --error=Log/F00_preprocess/slurm_%j.err
     # ... other SBATCH options ...

     set -euo pipefail

     # Load shared environment and constants
     source Const/env_settings.sh
     ```

   * `env_settings.sh` might set:

     * `PROJECT_ROOT`
     * `PYTHON=/path/to/python`
     * `DATA_ROOT`, `RAW_DATA_DIR`, etc.
     * Global seeds, domain configs, etc.

2. **Create working directory**

   ```bash
   STEP_ID="F00_preprocess"
   WORK_DIR="Work/${STEP_ID}"
   OUT_DIR="${WORK_DIR}/out"

   mkdir -p "${WORK_DIR}" "${OUT_DIR}" "Log/${STEP_ID}" "Data/${STEP_ID}"
   ```

3. **Symlink or copy code & inputs**

   ```bash
   # Example: symlink Python scripts and required input data
   ln -sf "${PROJECT_ROOT}/Python/preprocess.py" "${WORK_DIR}/preprocess.py"
   ln -sf "${RAW_DATA_DIR}/input_data.nc" "${WORK_DIR}/input_data.nc"
   ```

4. **Run the Python program(s) in WORK/out**

   ```bash
   cd "${WORK_DIR}"

   "${PYTHON}" preprocess.py \
       --input input_data.nc \
       --output "${OUT_DIR}/preprocessed.nc" \
       --config "${PROJECT_ROOT}/Const/params_global.yaml" \
       2>&1 | tee "${PROJECT_ROOT}/Log/${STEP_ID}/preprocess_run.log"
   ```

5. **Move / sync outputs to canonical locations**

   ```bash
   # Move or copy final outputs to Data/ and Figs/
   mv "${OUT_DIR}/preprocessed.nc" "${PROJECT_ROOT}/Data/${STEP_ID}/"

   # If figures are produced:
   # mv "${OUT_DIR}"/*.png "${PROJECT_ROOT}/Figs/${STEP_ID}/"
   ```

6. **Avoid step-internal hardcoding**

   * Inputs, outputs, and parameter values should be driven by:

     * Environment variables from `Const/env_settings.sh`
     * Config files from `Const/` (YAML/TOML/etc.)
   * The shell script should read like a **pipeline storyboard**:

     * “Prepare working dir → link inputs → run python → move outputs”

---

## 4. Constants and Configuration (`Const/`)

Always prefer **centralized configuration** over scattered hardcoding.

### `Const/env_settings.sh`

* This is the main entry for shell-level constants:

  ```bash
  # Const/env_settings.sh

  # Project root
  export PROJECT_ROOT="$(pwd)"

  # Python executable
  export PYTHON="python"

  # Data roots
  export RAW_DATA_DIR="${PROJECT_ROOT}/Data/raw"
  export PROCESSED_DATA_DIR="${PROJECT_ROOT}/Data"

  # Misc
  export GLOBAL_SEED=42
  ```

* Every main step script should **source** this file:

  ```bash
  source Const/env_settings.sh
  ```

### Additional config (optional)

* `Const/params_global.yaml` for domain or experiment-level settings:

  * geographic domain
  * variable names
  * default resolutions
  * model hyperparameters
* Python scripts then load this YAML (e.g. `ruamel.yaml`, `PyYAML`).

---

## 5. Example: 3-Step Pipeline

For a project with 3 steps:

0. **Preprocess data**
1. **Data analysis**
2. **Visualization**

Propose:

```text
Sh/
  F00_preprocess_slurm.sh
  F01_data_analysis_slurm.sh
  F02_visualize_results_slurm.sh

Python/
  preprocess.py
  data_analysis.py
  visualize_results.py

Data/
  F00_preprocess/
  F01_data_analysis/
  F02_visualize_results/

Figs/
  F01_data_analysis/
  F02_visualize_results/

Log/
  F00_preprocess/
  F01_data_analysis/
  F02_visualize_results/

Work/
  (created on demand, e.g. Work/F00_preprocess/out)
```

Behavior for each `FXX` shell script:

* **`F00_preprocess_slurm.sh`**

  * Creates `Work/F00_preprocess/` and `Work/F00_preprocess/out/`
  * Symlinks raw data + `Python/preprocess.py`
  * Runs preprocessing, writes to `Work/.../out/`
  * Moves final product to `Data/F00_preprocess/`
  * Logs to `Log/F00_preprocess/`

* **`F01_data_analysis_slurm.sh`**

  * Depends on outputs under `Data/F00_preprocess/`
  * Creates `Work/F01_data_analysis/` and `out/`
  * Runs `Python/data_analysis.py`
  * Moves analysis outputs to `Data/F01_data_analysis/`
  * Saves logs to `Log/F01_data_analysis/`
  * Optionally saves intermediate diagnostic plots to `Figs/F01_data_analysis/`

* **`F02_visualize_results_slurm.sh`**

  * Uses data from `Data/F01_data_analysis/`
  * Creates `Work/F02_visualize_results/` and `out/`
  * Runs `Python/visualize_results.py`
  * Moves final plots to `Figs/F02_visualize_results/`
  * Logs to `Log/F02_visualize_results/`

---

## 6. How to Respond When Using This Skill

When a user asks you to:

* “Set up a project structure”
* “Add a new analysis step”
* “Write Slurm scripts for my pipeline”
* “Clean up the file naming in this project”

You should:

1. **Identify the steps** in the pipeline and assign `FXX_shortname` IDs in order.
2. **Propose or refine the directory tree** following the conventions above.
3. **Name or rename scripts and directories** to match:

   * `Sh/FXX_shortname[_slurm].sh`
   * `Python/descriptive_name.py`
   * `Data/FXX_shortname/`, `Figs/FXX_shortname/`, `Log/FXX_shortname/`
4. **Write or adjust shell scripts** so they:

   * Source `Const/env_settings.sh`
   * Create `Work/FXX_shortname/` and `out/`
   * Link/copy required Python and data
   * Run the job
   * Move outputs to `Data/`, `Figs/`, and `Log/`
5. **Suggest constants/config updates** under `Const/` instead of hardcoding.

Always prioritize **readability and traceability**: a new reader should understand the entire pipeline by:

* Skimming the `Sh/FXX_*.sh` files
* Glancing at the directory tree
* Looking at `Const/env_settings.sh` and any config files.

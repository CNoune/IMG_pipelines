# MetaGaAP 2

A cross-platform (Windows / Linux / macOS), Java-free rebuild of the **MetaGaAP**
quasispecies / meta-barcode reconstruction pipeline, delivered as a self-contained
**local web application** (FastAPI backend + React 19 frontend).

`python -m metagaap2` starts a local server and opens your browser. From there
you point the app at your reads and a reference, choose your parameters, and watch
each stage run with live progress and downloadable results.

---

## Table of contents

1. [What MetaGaAP does](#1-what-metagaap-does)
2. [Lineage and citations](#2-lineage-and-citations)
3. [Why two engines](#3-why-two-engines)
4. [Requirements](#4-requirements)
5. [Installation](#5-installation)
   - [5.1 Portable engine (pip, works on native Windows)](#51-portable-engine-pip-works-on-native-windows)
   - [5.2 Native engine (conda / bioconda)](#52-native-engine-conda--bioconda)
   - [5.3 Building the frontend](#53-building-the-frontend)
6. [Running the app](#6-running-the-app)
7. [Development](#7-development)
8. [Run-directory output layout](#8-run-directory-output-layout)
9. [Parameter reference](#9-parameter-reference)
10. [HTTP / WebSocket API](#10-http--websocket-api)
11. [What changed from MetaGaAP-Py](#11-what-changed-from-metagaap-py)
12. [Changelog](#12-changelog)
13. [Licence](#13-licence)

---

## 1. What MetaGaAP does

MetaGaAP is a **reference-guided quasispecies / meta-barcode reconstruction**
pipeline. The underlying science is unchanged from the original publications.
Given a reference sequence and a set of sequencing reads it:

1. **QC / trims** the reads.
2. **Maps** the reads to the reference.
3. **Calls variants** against the reference (quasispecies-sensitive, low-frequency
   alleles included).
4. **Builds a combinatorial haplotype database** — every allele combination within
   a sliding window the size of a read. This is the step the original pipeline
   delegated to `biostar175929.jar`; in MetaGaAP 2 it is reimplemented in pure
   Python (`metagaap2/haplotypes.py`).
5. **Re-maps** the reads to the haplotype database and keeps haplotypes that
   recruit more than a threshold number of reads — the **"confirmed sequences"**.
6. **Multi-sample**: with a single shared reference, merges the per-sample
   databases, de-duplicates them, then re-maps every sample against the merged
   database.

The result is a per-sample set of confirmed haplotype sequences with read counts
and statistics, suitable for estimating community composition and abundance from
non-model, ultra-deep "meta-barcode" sequence data.

---

## 2. Lineage and citations

MetaGaAP 2 is a modern rebuild of **MetaGaAP-Py** (C. Noune & C. Hauxwell, 2017),
itself the Python successor to the original bash MetaGaAP pipeline. It was first
developed within the Invertebrates & Microbiology Group at the Queensland
University of Technology to analyse baculovirus quasispecies, and keeps the exact
method while replacing the Java and unmaintained dependencies.

If you use MetaGaAP 2, **please cite the original MetaGaAP publication and the
bioRxiv pre-print**:

> Noune, C.; Hauxwell, C. *MetaGaAP: A Novel Pipeline to Estimate Community
> Composition and Abundance from Non-Model Sequence Data.* **Biology 2017, 6, 14.**

> Noune, C.; Hauxwell, C. *Enhanced Pipeline 'MetaGaAP-Py' for the Analysis of
> Quasispecies and Non-Model Microbial Populations using Ultra-Deep 'Meta-barcode'
> Sequencing.* **bioRxiv, 2017.**

And, for the pipeline collection as a whole:

> Noune, C. *The Invertebrates & Microbiology Group Pipelines*, GitHub,
> Queensland University of Technology: <https://github.com/CNoune/IMG_pipelines>, 2016.

Please also cite the underlying tools you actually used in a given run (for
example cutadapt, minimap2, samtools, bcftools, lofreq, fastp).

---

## 3. Why two engines

MetaGaAP 2 abstracts its compute core behind an `Engine` interface
(`metagaap2/engines/base.py`) with two interchangeable implementations. The
science-bearing steps — combinatorial haplotype generation, de-duplication,
confirmed-sequence extraction, merging and the run-directory layout — are
**engine-independent pure Python**; only the three platform-sensitive operations
(`trim`, `align_and_call`, `map_and_count`) differ between engines.

The reason there are two engines is a hard packaging fact: **the fast native
bioinformatics binaries have no pip wheels for native Windows.** There is no
htslib-based `pysam`, no `minimap2`, no `mappy`, and no `edlib` wheel that installs
cleanly on a stock Windows Python. Forcing those dependencies would lock Windows
users out of a `pip`-only install. So:

### Portable engine — `key = "portable"` (default)

Pure-Python, built only on packages that publish wheels for **all three** operating
systems including native Windows. This is the default and the cross-platform
guarantee.

| Stage         | Implementation                                                       |
|---------------|---------------------------------------------------------------------|
| Trim          | `cutadapt` (invoked as `python -m cutadapt`, a pip-installed module) |
| FASTQ/FASTA IO| `dnaio` + `xopen`; `pyfastx` for indexed random access; `biopython`  |
| Align         | k-mer / minimiser seed index (`numpy`) + `parasail` SIMD extension  |
| Variant call  | built-in frequency pileup caller (`caller = "builtin"`)             |
| Haplotype DB  | shared pure-Python combinatorial generator (`haplotypes.py`)         |
| Confirm/count | k-mer pseudo-assignment of reads to haplotypes                       |

### Native engine — `key = "native"` (optional, auto-detected)

Wraps fast external binaries **when they are present on `PATH`** (conda/bioconda
on Linux/macOS; WSL or conda on Windows). It is auto-detected and never required —
if the binaries are not found, the engine simply reports itself unavailable and
the app falls back to portable.

| Stage         | Implementation                                                          |
|---------------|------------------------------------------------------------------------|
| Trim          | `fastp`                                                                 |
| Align         | `minimap2` (default) or `bwa-mem2`, piped to `samtools sort`            |
| Variant call  | `bcftools mpileup \| call` (`caller="bcftools"`) or `lofreq` (`caller="lofreq"`) |
| Haplotype DB  | shared pure-Python combinatorial generator (`haplotypes.py`)            |
| Confirm/count | `minimap2` / `bwa-mem2` map → `samtools idxstats`                       |

**Engine selection.** On start-up the server probes both engines
(`GET /api/engines`) and reports their availability and capabilities to the UI.
The UI offers only the aligners and callers the chosen engine supports. The
default engine is **native if its binaries are detected, otherwise portable**;
you can always override the choice in the UI.

> All external commands are executed through `metagaap2.runner` with list
> arguments. **`shell=True` is never used anywhere in the codebase.**

---

## 4. Requirements

- **Python ≥ 3.10** (3.12 recommended).
- **Node.js ≥ 20** with `npm` — only needed to build the frontend (a one-off step,
  or whenever the UI source changes).
- For the optional native engine: a **conda / mamba** installation (Miniforge,
  Miniconda or Anaconda) with the **bioconda** channel, or the binaries otherwise
  on your `PATH`.

Recommended hardware (carried over from the original pipeline): at least 8 GB RAM,
a 4-core CPU, and roughly 20 GB of free storage per dataset analysed.

---

## 5. Installation

### 5.1 Portable engine (pip, works on native Windows)

This is the zero-conda path. Every runtime dependency ships Windows, Linux and
macOS wheels, so a plain `pip install` gives you a fully working pipeline on the
portable engine — including on **native Windows** with no WSL.

```bash
# from the MetaGaAP-2/ project root
python -m venv .venv

# activate the virtual environment:
#   Linux / macOS:   source .venv/bin/activate
#   Windows (PowerShell):  .venv\Scripts\Activate.ps1
#   Windows (cmd):         .venv\Scripts\activate.bat

python -m pip install --upgrade pip
pip install -e .
```

This installs the `metagaap2` package and its runtime dependencies: `fastapi`,
`uvicorn[standard]`, `pydantic>=2`, `python-multipart`, `cutadapt`, `dnaio`,
`xopen`, `pyfastx`, `parasail`, `numpy` and `biopython`.

> The portable engine calls cutadapt as a subprocess via
> `python -m cutadapt`, so it works identically across all three operating systems
> with no separate binary to install.

To also install the test tooling:

```bash
pip install -e ".[dev]"
```

### 5.2 Native engine (conda / bioconda)

The native engine adds the fast external aligners and callers. These are provided
through conda/bioconda. The supplied `environment.yml` creates an environment with
Python, the portable-engine Python dependencies **and** the native binaries.

```bash
conda env create -f environment.yml
conda activate metagaap2
pip install -e .            # install the metagaap2 package itself
```

The environment pulls these binaries from bioconda (auto-detected on `PATH`):
`minimap2`, `bwa-mem2`, `samtools`, `bcftools`, `lofreq`, `fastp`.

**Operating-system notes**

- **Linux / macOS** — the native binaries are first-class on bioconda; the above
  is all you need.
- **Windows** — bioconda does not publish these binaries for native Windows.
  Either stay on the portable engine (which needs no conda at all), or run the
  conda environment **under WSL** (Windows Subsystem for Linux) to get the native
  engine.

Once active, the app auto-detects whatever native tools are present; you do not
have to configure paths. The `Engine status` panel in the UI shows exactly which
tools were found and their versions.

### 5.3 Building the frontend

The React UI must be built once so the backend can serve it. Vite emits the
production build straight into the backend package
(`backend/metagaap2/webui/`), which is where `python -m metagaap2` looks for it.

```bash
cd frontend
npm install
npm run build
```

After this, `backend/metagaap2/webui/index.html` and its assets exist, and the
single command `python -m metagaap2` will serve both the API and the UI. Re-run
`npm run build` whenever you change the frontend source.

---

## 6. Running the app

From any activated environment that has `metagaap2` installed and the frontend
built:

```bash
python -m metagaap2
```

This launches the FastAPI backend under uvicorn on `http://127.0.0.1:8000/` and,
after a moment, opens your default web browser at that address. The server binds
to the **loopback interface only** by default, so it is not exposed to your
network.

Command-line options:

| Option         | Default     | Description                                                    |
|----------------|-------------|----------------------------------------------------------------|
| `--host`       | `127.0.0.1` | Interface to bind to. Use `0.0.0.0` only to expose on the LAN. |
| `--port`       | `8000`      | Port to listen on.                                             |
| `--no-browser` |             | Start the server without opening a browser.                    |
| `--version`    |             | Print the MetaGaAP 2 version and exit.                         |

Examples:

```bash
python -m metagaap2 --port 9001
python -m metagaap2 --no-browser            # e.g. on a headless box
```

If you installed with `pip install -e .`, the console script `metagaap2` is also
on your `PATH`, so you can simply run `metagaap2` instead of `python -m metagaap2`.

Using the app:

1. Open the **Engine status** panel to confirm which engines and native tools were
   detected on this machine.
2. Fill in the **run configuration** — run name, working directory, engine,
   threads, reference mode and the shared reference (single mode).
3. Add your **samples** (R1 / optional R2 reads, optional per-sample reference and
   read-group metadata).
4. Adjust **QC / variant / haplotype / confirm** parameters as needed
   (see [§9](#9-parameter-reference)).
5. Start the run and watch live per-stage progress and logs over the WebSocket.
6. Download confirmed sequences, counts and statistics from the results view.

---

## 7. Development

For UI work you usually want Vite's hot-reloading dev server in front of a live
backend, rather than rebuilding into the package each time.

Run the backend (terminal 1):

```bash
# from the project root, with the package installed
python -m metagaap2 --no-browser          # serves the API on 127.0.0.1:8000
```

Run the Vite dev server (terminal 2):

```bash
cd frontend
npm run dev                                # serves the UI on 127.0.0.1:5173
```

Then open <http://127.0.0.1:5173/>. The dev server **proxies** `/api` requests and
the `/ws` WebSocket through to the uvicorn backend on `127.0.0.1:8000`
(configured in `frontend/vite.config.ts`), so the running app talks to the real
backend with full hot-reload on the React side. To point the proxy at a different
backend, set `METAGAAP_BACKEND`:

```bash
METAGAAP_BACKEND=http://127.0.0.1:9001 npm run dev
```

Other useful commands:

```bash
# Frontend type-check only
cd frontend && npm run typecheck

# Backend tests (pytest)
pip install -e ".[dev]"
pytest

# Backend Python syntax check after edits
python -m py_compile backend/metagaap2/*.py backend/metagaap2/engines/*.py
```

The backend also enables permissive CORS for loopback origins on any port, so the
separately-served dev frontend can call the API directly during development.

---

## 8. Run-directory output layout

Each run creates a directory `<work_dir>/<run_name>/` populated by
`metagaap2/pipeline.py`:

```
<work_dir>/<run_name>/
  run_config.json          # the exact RunConfig used (fully reproducible)
  manifest.json            # Job snapshot (stages, outputs, timings)
  logs/<sample>.<stage>.log
  trimmed/<sample>_R1.fastq.gz ...
  alignments/<sample>.bam | .paf
  variants/<sample>.vcf
  haplotypes/<sample>_db.fasta | merged_db.fasta
  results/<sample>_stats.csv, <sample>_confirmed.fasta, <sample>_counts.csv
```

Key outputs per sample:

- **`results/<sample>_confirmed.fasta`** — the confirmed haplotype sequences (those
  recruiting at least `min_mapped_reads` reads).
- **`results/<sample>_counts.csv`** — reads recruited per haplotype.
- **`results/<sample>_stats.csv`** — per-sample summary statistics.

In single-reference multi-sample runs, `haplotypes/merged_db.fasta` is the
de-duplicated merge of every per-sample database, and the confirm step re-maps each
sample against it. Result files can be downloaded through the UI; downloads are
sandboxed to the job's own run directory.

---

## 9. Parameter reference

These are the configurable parameters posted as a `RunConfig` to `POST /api/jobs`.
The authoritative definitions live in `backend/metagaap2/models.py`.

### Run configuration (`RunConfig`)

| Parameter                | Type / values                                  | Default      | Meaning                                                                 |
|--------------------------|------------------------------------------------|--------------|-------------------------------------------------------------------------|
| `run_name`               | string                                         | *(required)* | Run label; names the output directory.                                  |
| `work_dir`               | path                                           | *(required)* | Parent directory for run outputs.                                       |
| `engine`                 | `portable` \| `native`                         | `portable`   | Which compute engine runs the per-sample stages.                        |
| `aligner`                | `builtin` \| `minimap2` \| `bwa_mem2`          | `builtin`    | Aligner; must be supported by the chosen engine.                        |
| `threads`                | integer ≥ 1                                     | `4`          | Thread count for engines that support multi-threading.                  |
| `reference_mode`         | `single` \| `multiple`                         | `single`     | `single` = one shared reference (merge across samples); `multiple` = per-sample references. |
| `reference`              | path                                           | `null`       | Shared reference FASTA (required when `reference_mode=single`).         |
| `merge_single_reference` | boolean                                        | `true`       | In single-reference multi-sample runs, merge per-sample databases.      |
| `samples`                | list of `Sample` (≥ 1)                         | *(required)* | The samples to process.                                                 |

### Sample (`Sample`) and read group (`ReadGroup`)

| Parameter            | Type / values | Default            | Meaning                                                          |
|----------------------|---------------|--------------------|------------------------------------------------------------------|
| `name`               | string        | *(required)*       | Unique sample identifier.                                        |
| `r1`                 | path          | *(required)*       | Forward / single-end FASTQ.                                      |
| `r2`                 | path          | `null`             | Reverse FASTQ (paired-end). Omit for single-end.                |
| `reference`          | path          | `null`             | Per-sample reference (required when `reference_mode=multiple`).  |
| `read_group.sample`  | string        | *(required if set)*| RGSM — sample name.                                              |
| `read_group.library` | string        | `lib1`             | RGLB — library name.                                            |
| `read_group.platform`| string        | `ILLUMINA`         | RGPL — e.g. `ILLUMINA`, `IONTORRENT`.                           |
| `read_group.unit`    | string        | `unit1`            | RGPU — sequencing unit.                                         |
| `read_group.id`      | string        | `sample.unit`      | RGID — defaults to `<sample>.<unit>`.                           |

### QC / trimming (`QCParams`)

| Parameter         | Type / values     | Default | Meaning                                              |
|-------------------|-------------------|---------|------------------------------------------------------|
| `enabled`         | boolean           | `true`  | If false, reads are passed through untrimmed.        |
| `min_quality`     | integer 0–60      | `20`    | Quality trim threshold (Q).                          |
| `min_length`      | integer ≥ 1       | `30`    | Discard reads shorter than this after trimming.      |
| `trim_front`      | integer ≥ 0       | `0`     | Fixed bases to cut from the 5′ end.                  |
| `trim_tail`       | integer ≥ 0       | `0`     | Fixed bases to cut from the 3′ end.                  |
| `adapter_fwd`     | string            | `null`  | Optional 3′ adapter for R1.                          |
| `adapter_rev`     | string            | `null`  | Optional 3′ adapter for R2.                          |
| `detect_adapters` | boolean           | `true`  | Auto-detect adapters where supported.               |

### Variant calling (`VariantParams`)

| Parameter             | Type / values                      | Default   | Meaning                                                      |
|-----------------------|------------------------------------|-----------|--------------------------------------------------------------|
| `caller`              | `builtin` \| `bcftools` \| `lofreq`| `builtin` | Variant caller; must be supported by the chosen engine.      |
| `min_base_quality`    | integer 0–60                       | `20`      | Minimum base quality.                                        |
| `min_mapping_quality` | integer 0–60                       | `20`      | Minimum mapping quality.                                     |
| `min_depth`           | integer ≥ 1                        | `10`      | Minimum site depth to consider a variant.                    |
| `min_alt_fraction`    | float 0.0–1.0                      | `0.02`    | Minimum ALT allele fraction (quasispecies-sensitive).        |
| `ploidy`              | integer ≥ 1                        | `2`       | Ploidy for `bcftools call` (ignored by the frequency caller).|

### Haplotype database (`HaplotypeParams`)

| Parameter                    | Type / values | Default              | Meaning                                                                   |
|------------------------------|---------------|----------------------|---------------------------------------------------------------------------|
| `window`                     | integer ≥ 1   | `null` → modal read length | Sliding-window size in bp.                                            |
| `step`                       | integer ≥ 1   | `null` → window      | Window step in bp (`null` = non-overlapping).                             |
| `max_haplotypes_per_window`  | integer ≥ 1   | `1024`               | Safety cap on combinations emitted per window.                            |
| `max_variants_per_window`    | integer ≥ 1   | `12`                 | Skip windows with more variant sites than this (combinatorial-blow-up guard). |

### Confirmation (`ConfirmParams`)

| Parameter          | Type / values | Default | Meaning                                                          |
|--------------------|---------------|---------|------------------------------------------------------------------|
| `min_mapped_reads` | integer ≥ 1   | `2`     | Keep haplotypes recruiting at least this many reads (original used > 1). |
| `min_identity`     | float 0.0–1.0 | `0.90`  | Minimum read-to-haplotype identity for portable assignment.      |

---

## 10. HTTP / WebSocket API

The frontend talks to the backend through this API (see
`backend/metagaap2/server.py` and `frontend/src/api.ts`):

| Method | Path                              | Purpose                                                       |
|--------|-----------------------------------|---------------------------------------------------------------|
| `GET`  | `/api/health`                     | Liveness probe → `{status, version}`.                         |
| `GET`  | `/api/engines`                    | `ServerInfo` — detected engines, tools, platform, defaults.   |
| `GET`  | `/api/fs?path=`                   | Directory listing for the in-app file picker.                 |
| `POST` | `/api/jobs`                       | Create a job from a `RunConfig`; starts in the background.    |
| `GET`  | `/api/jobs`                       | List all jobs.                                                |
| `GET`  | `/api/jobs/{id}`                  | Fetch a single job.                                           |
| `POST` | `/api/jobs/{id}/cancel`           | Co-operatively cancel a running job.                          |
| `GET`  | `/api/jobs/{id}/download?path=`   | Stream a result file (sandboxed to the run directory).        |
| `WS`   | `/ws/jobs/{id}`                   | Live stream of `state` / `stage` / `log` / `done` events.     |

---

## 11. What changed from MetaGaAP-Py

MetaGaAP 2 keeps the original science but modernises everything around it:

- **No Java.** **GATK and `biostar175929.jar` are no longer required.** Variant
  calling uses the built-in frequency caller (portable) or `bcftools` / `lofreq`
  (native), and the combinatorial haplotype generation that was `biostar175929.jar`
  is reimplemented in pure Python (`haplotypes.py`).
- **No unmaintained tools.** The FASTX-toolkit and picard steps are gone; read-group
  handling that picard's `AddOrReplaceReadGroups` performed is now data on the
  sample (`ReadGroup`), and QC/trimming uses cutadapt (portable) or fastp (native).
- **Cross-platform, including native Windows.** The default portable engine relies
  only on pip wheels available for Windows, Linux and macOS — no conda required.
- **No `shell=True`.** Every external command runs through `metagaap2.runner` with
  list arguments and checked return codes, fixing the original shell-injection and
  spaces-in-paths problems.
- **Non-interactive and reproducible.** A run is fully described by a `RunConfig`
  written to `run_config.json`; no GUI file-picker prompts for GATK or the
  IMG_pipelines directory.
- **Local web app.** A FastAPI backend with a React 19 frontend replaces the old
  Tkinter interface, with live per-stage progress and result downloads.

---

## 12. Changelog

All notable changes to MetaGaAP 2. Newest first; dates DD/MM/YYYY.

### v2.0.0 — 24/06/2026

Initial release of the MetaGaAP 2 rebuild.

- Complete **Java-free, cross-platform** rewrite of MetaGaAP-Py as a local web app
  (FastAPI backend + React 19 / Vite 8 / Tailwind 4 frontend).
- **Two interchangeable compute engines** — portable pure-Python (default) and
  native external-tools (auto-detected) — see [§3](#3-why-two-engines).
- Pure-Python **combinatorial haplotype generator** replacing `biostar175929.jar`,
  and a built-in **frequency variant caller** replacing GATK.
- Safe command execution: every external command runs through `metagaap2.runner`
  with list arguments and checked return codes — **`shell=True` is never used**.
  `run_pipe` drains each stage's stderr on its own thread to avoid pipe-buffer
  deadlocks with verbose native tools.
- **Verified end-to-end on native Windows** (Python 3.13): the full backend test
  suite passes, a complete pipeline run (trim → align/call → haplotypes → confirm)
  calls a known SNP and produces confirmed haplotypes, and the browser UI drives a
  run to completion with live progress and working result downloads.
- **Fix (UI):** the live progress view now re-fetches the authoritative job
  snapshot when a run finishes, so the Results view always shows the per-sample
  haplotype / confirmed counts and download links. (WebSocket events carry
  per-stage updates only, not the final per-sample summary, so the previously
  reconstructed snapshot could under-report as `0`.)

---

## 13. Licence

MIT. See the `license` field in `pyproject.toml`.

---

*MetaGaAP 2 — C. Noune & C. Hauxwell. Last updated 24/06/2026.*

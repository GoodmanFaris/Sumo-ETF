# Video-to-SUMO Traffic Demand Pipeline

This repository contains an offline pipeline that converts an intersection video into structured traffic demand and generates a SUMO-compatible `flows.xml` file.

**Pipeline flow:**

`Video → Frame Extraction → YOLO Detection → Pseudo-Tracking → Traffic Metrics → SUMO Demand File`

---

## Table of Contents

- [System Requirements](#system-requirements)
- [Project Structure](#project-structure)
- [Step-by-Step Workflow](#step-by-step-workflow)
- [Output Files](#output-files)
- [What You Get](#what-you-get)
- [Important Notes](#important-notes)

## System Requirements

- Python 3.10+
- Windows or Linux
- SUMO (optional, for simulation)
- Label Studio (for manual labeling)

Install dependencies:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Project Structure

Relevant folders:

```text
raw/videos/
raw/images/

dataset/images/
dataset/incoming/
dataset/processed/

models/

inference/detections/
inference/pseudo_tracks/

metrics/per_frame/
metrics/aggregated/

sumo/zones/
sumo/mapping/
sumo/demand/
sumo/net/
```

## Step-by-Step Workflow

### 1) Add video

Place your source video here:

`raw/videos/cam01.mp4`

Recommended conditions:

- Fixed camera (no movement)
- Entire intersection visible
- Resolution of at least 1080p

### 2) Extract snapshots

Run:

```bash
python src/pipeline/extract_frames.py
```

This extracts frames every 3 seconds and saves them to `raw/images/`.

### 3) Select 200 random images for labeling

Run:

```bash
python src/utils/select_random_images.py
```

This copies a random subset to `dataset/images/`.

### 4) Label images in Label Studio

Install and start Label Studio:

```bash
pip install label-studio
label-studio start
```

Inside Label Studio:

1. Create a new Bounding Boxes project.
2. Define classes (`car`, `bus`, `truck`).
3. Import images from `dataset/images/`.
4. Label all images.
5. Export in YOLO format.

Save exported ZIP as:

`dataset/incoming/data.zip`

### 5) Train YOLO model

Run:

```bash
python src/train/train_from_zip.py
```

This step:

- Unzips the labeled dataset
- Creates train/validation split (90% / 10%)
- Generates `data.yaml`
- Trains from `yolov8n.pt`
- Saves best weights to `models/cam01_yolo/weights/best.pt`

### 6) Configure zones

Create and edit:

`sumo/zones/zones.json`

Define:

- `entry_zones`
- `exit_zones`
- `queue_zones`
- `count_lines`

Validate structure with:

`sumo/zones/zones.schema.json`

All coordinates must be in pixel space for the same camera viewpoint.

### 7) Configure SUMO mapping

Edit:

`sumo/mapping/mapping.json`

Define:

- `count_line_to_approach`
- `approaches` (`from_edge`)
- `exit_zone_to_movement` (`L`/`T`/`R`)
- `turns` (`to_edge`)

> Edge IDs in mapping must exactly match IDs in your SUMO network file.

### 8) Run complete pipeline

Run:

```bash
python src/run_pipeline.py
```

This executes:

- Frame extraction
- YOLO inference using trained `best.pt`
- Pseudo-tracking
- Traffic metric extraction
- SUMO `flows.xml` generation

## Output Files

After running the pipeline, you get:

### Detections

- `inference/detections/*.json` — bounding boxes and classes per snapshot.

### Pseudo tracks

- `inference/pseudo_tracks/pseudo_tracks.json` — reconstructed vehicle IDs across snapshots.

### Traffic metrics

- `metrics/per_frame/observations_per_frame.csv`
- `metrics/aggregated/metrics_aggregated.csv`
- `metrics/aggregated/turning_counts_long.csv`

These include flow by approach, turning counts (`L`/`T`/`R`), and queue estimation.

### SUMO demand file

- `sumo/demand/flows.xml`

Contains vehicle flows per interval with from/to edge mappings, ready for use in a SUMO `.sumocfg` setup.

## What You Get

Final outputs include:

- Measured traffic flow
- Turning movement distribution
- Queue estimation
- SUMO-compatible demand definition

## Important Notes

- Camera viewpoint must remain fixed.
- Zones are defined manually.
- Mapping must match SUMO edge IDs exactly.
- Model quality improves significantly with better manual labels.

## Workflow Summary

`Add Video → Extract Frames → Select Images → Label Data → Train YOLO → Run Pipeline → Generate flows.xml`
# EVERYFISH-COCO Annotation Editor

The EVERYFISH-COCO Annotation Editor is a local browser tool for reviewing
polygon annotations one image at a time. It is a portable Python package and
does not include the source dataset or image files.

## Requirements

- Python 3
- Pillow, installed from `requirements.txt`
- A dataset directory containing matching source images and annotations

## Installation

From the repository root, create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell, activate it with:

```powershell
.venv\Scripts\Activate.ps1
```

Install the project dependency:

```bash
python -m pip install -r requirements.txt
```

## Dataset layout

Pass the editor a dataset directory containing `images/` and `annotations/`:

```text
dataset-root/
  images/
    example.png
  annotations/
    example.json
```

Image and annotation files must have matching stems. The editor creates these
reviewed output directories beside the source folders when needed:

```text
dataset-root/
  reviewed_annotations/
  reviewed_render/
```

The source `images/` and `annotations/` directories are read-only inputs. The
editor writes reviewed annotation copies and rendered previews to the reviewed
output directories instead.

## Run the editor

From the repository root, activate the virtual environment and run:

```bash
source .venv/bin/activate
python -m everyfish_coco_annotation_editor --dataset-root /path/to/dataset
```

Open the printed address in a browser. The default address is:

```text
http://127.0.0.1:8765/
```

The command accepts optional listener settings:

```bash
python -m everyfish_coco_annotation_editor \
  --dataset-root /path/to/dataset \
  --host 127.0.0.1 \
  --port 8765
```

Keep the terminal running while reviewing annotations. Press `Ctrl+C` to stop
the editor.

## Manual

See the [Annotation Editor Manual](ANNOTATION_EDITOR_MANUAL.md) for the full
workflow and control reference. It covers:

- Image navigation, quick jumping, filename search, zoom, and panning.
- Selecting annotations from the canvas or annotation sidebar.
- Showing and hiding annotations, including single-annotation previews.
- Highlighting any class with red masks and bounding boxes.
- Drawing polygon instances and deleting reviewed instances.
- Maskless annotations and how they are preserved until explicitly deleted.
- Automatic saving before navigation and behavior when a save fails.
- The reviewed annotation and rendered preview output folders.

For a first review, start the editor, open the first image, inspect the
polygons, make only the required changes, and use the reviewed output folders
for the resulting dataset. The original source folders remain unchanged.

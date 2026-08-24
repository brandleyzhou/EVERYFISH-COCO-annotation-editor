# EVERYFISH-COCO Annotation Editor

This folder is a portable Python package for reviewing EVERYFISH-COCO
annotations. It does not include the source dataset or image files.

## Dataset layout

Pass a directory containing:

```text
dataset-root/
  images/
  annotations/
```

The editor creates and maintains `reviewed_annotations/` and
`reviewed_render/` beside those source directories. Source annotations and
images are never modified.

## Run

Install the dependency once:

```bash
python3 -m pip install -r requirements.txt
```

Run from the directory containing this package:

```bash
python3 -m everyfish_coco_annotation_editor --dataset-root /path/to/dataset
```

The browser editor listens on `http://127.0.0.1:8765/` by default. Use
`--host` and `--port` to change the listener.


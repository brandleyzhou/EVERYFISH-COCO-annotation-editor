# EVERYFISH-COCO Annotation Editor Manual

This manual is for first-time users of the local EVERYFISH-COCO Annotation Editor.

## What the editor does

The editor lets you review image annotations one instance at a time. You can select an instance, delete it from the reviewed copy, and move through the image set. The original annotation files are kept unchanged.

## Before you start

Make sure the repository contains:

- `images/` — source PNG images.
- `annotations/` — source EVERYFISH-COCO JSON annotations.
- `everyfish_coco_annotation_editor/` — the editor package.

For portable use, use this project folder and run it against a
dataset root containing `images/` and `annotations/`. Install Pillow from
`requirements.txt`, then run:

```bash
python3 -m everyfish_coco_annotation_editor --dataset-root /path/to/dataset
```

The editor uses Pillow to create reviewed renderings. The recommended Python interpreter on this machine is `/usr/local/bin/python`.

## Start the editor

From the repository root, run:

```bash
python3 -m everyfish_coco_annotation_editor --dataset-root /path/to/dataset
```

Open this address in a browser:

```text
http://127.0.0.1:8765/
```

Keep the terminal running while using the editor. Press `Ctrl+C` in the terminal to stop it.

## Main controls

Click **Help** in the top bar, or press `?`, to open the in-app help page. It
summarizes the editor controls, keyboard shortcuts, drawing workflow, class
highlighting, and save behavior.

### Image navigation

You can change images in any of these ways:

- Click **Previous** or **Next**.
- Press the **Left Arrow** or **Right Arrow** key.
- Enter a 1-based image number in **Jump to image** and press `Enter`.
- Choose an image from the image selector.
- Click an image in the image list.

The current reviewed annotation is saved automatically before navigation. If the save fails, navigation is stopped so the current review remains visible.

The quick-jump field uses the visible image number: enter `1` for the first image, `2` for the second image, and so on. Values outside the available image range are rejected.

Click **Hide image list** to collapse the left sidebar and give the canvas more
horizontal space. Click **Show image list** to restore it. Collapsing the sidebar
does not change the current image or selected annotation.

### Search by filename

Use **Search filename** in the sidebar to filter the image list while typing.
Search is case-insensitive and matches partial filenames. Press `Enter` to open
the first matching image. If there are no matches, the current image remains
open and a status message is shown. Clear the field to restore the full image
list.

### Zoom

Use **Zoom In**, **Zoom Out**, and **Reset Zoom** in the top bar. On a Mac
trackpad, you can also pinch over the canvas to zoom:

- Pinch outward to zoom in.
- Pinch inward to zoom out.
- Zoom is centered on the pointer position, keeping a small object near the
  cursor.
- The zoom range is 100% to 800%.
- Resetting or opening another image returns the view to 100%.

When zoomed in, use two fingers to scroll the canvas area and inspect parts of
the image outside the viewport. Normal two-finger scrolling does not change
the zoom level. Clicking and hovering continue to use the original image
coordinates, so small objects can be selected accurately.

You can also press and drag the zoomed image with the touchpad to pan around
the image. A short click still selects an instance; moving the pointer while
holding the click pans the image instead of selecting an instance.

## Understanding the canvas

Each annotation instance is displayed over its source image:

- Ordinary classes use blue polygon overlays.
- Classes `40` and `41` use red polygon overlays and red bounding boxes.
- The selected instance is highlighted in yellow.
- The status line shows the current image and instance count.

Click **Hide annotations** or press `Space` to hide annotation overlays. Click
**Show annotations** or press `Space` again to make them visible. This only
changes the on-screen view; it does not change the reviewed annotation JSON.
Annotations are shown again when you move to another image.

While annotations are hidden, selecting an annotation from the right sidebar
toggles that individual annotation on the canvas. Click the same annotation
again to hide it. Clicking a different annotation hides the previous one and
shows the newly selected annotation instead.

Enter a numeric value in `Highlight class ID` and apply it to highlight every
instance of that class with a red mask and bounding box. Matching rows in the
annotation sidebar are highlighted red as well. The selected class remains
active while navigating through the remaining images; use `Clear highlight` to
restore the default class colors.

### Hover behavior

When the mouse is over an instance, its polygon fill, outline, and label are hidden. For class `40` and class `41`, only the bounding box remains visible. Move the mouse away from the instance to restore the normal overlay.

For ordinary classes, no hover bounding box is shown, so the complete overlay is hidden while the pointer is over the instance.

The instance ID is also a hover and selection target. Hovering over an ID
triggers the same hover behavior as hovering over its polygon. Clicking an ID
selects that instance.

## Select an instance

1. Move the pointer over a polygon or instance ID if you need to inspect it.
2. Click inside the polygon or click its ID.
3. Confirm the selected instance in the status text, which shows its instance index and class ID.

For overlapping polygons or IDs, the topmost matching instance is selected.
ID selection remains accurate while zoomed or after touchpad panning.

The right sidebar also lists every annotation for the current image by ID and
class. Click an annotation row to select that instance on the canvas. The active
row follows canvas selection, and the list updates after an instance is deleted.
Use the up and down arrow buttons above the list, or the keyboard **Up Arrow**
and **Down Arrow** keys, to move through the annotation rows. The list scrolls
to keep the active row visible.

## Draw a polygon

1. Enter a numeric class in **Category ID**.
2. Click **Draw polygon**.
3. Click the image to place polygon vertices.
4. Double-click or press `Enter` to finish and save.

Press `Escape` or click **Cancel drawing** to discard the draft polygon before
it is saved. A polygon needs at least three points before it can be saved.

When a polygon is saved, it becomes a new annotation instance with one
segmentation region. If the save fails, the draft polygon remains visible so you
can retry finishing it or cancel it. The category field uses the typed value; if
it is empty, drawing uses the selected annotation class when available, then the
last class used for drawing.

## Delete an instance

1. Click inside the instance polygon.
2. Confirm that the correct instance is selected.
3. Click **Delete selected instance**.
4. Confirm the deletion dialog.

You can also press the `Backspace` key after selecting an instance. The keyboard
shortcut deletes immediately without confirmation; the button always asks for
confirmation.

The instance is removed from the reviewed copy and the reviewed rendering is updated only after the save succeeds. Other instances and the remaining annotation fields are preserved.

If the save fails, the selected instance remains visible and the reviewed JSON is left unchanged. Deletion cannot be undone through the editor after it is saved. To start over, restore the relevant file in `reviewed_annotations/` from `annotations/` before reviewing it again.

## Maskless instances

Opening an image is read-only. The editor does not remove reviewed instances just because they do not contain a usable polygon mask.

An instance is maskless if none of its segmentation regions contains at least three points. Delete these instances explicitly if they should be removed from the reviewed copy. The original file in `annotations/` is not modified.

## Saved files

The editor uses two output folders:

### `reviewed_annotations/`

Contains copies of the annotation JSON files. Deleted instances are applied here after a successful save.

### `reviewed_render/`

Contains rendered PNGs only for images whose annotations have changed through the editor. Opening or browsing an image does not create or update a rendered PNG. These renderings show the current reviewed annotations, including class-40 and class-41 bounding boxes.

The source folders remain separate:

- `annotations/` is never modified by the editor.
- `images/` is read-only input for the editor.

## Recommended review workflow

1. Start the editor from the repository root.
2. Open the first image and wait for it to finish loading.
3. Inspect the polygons and use hover to see the underlying image.
4. Click and delete only incorrect instances.
5. Use the arrow keys to move to the next image; the current image saves automatically first.
6. If a save error appears, remain on the current image and retry after checking the terminal or filesystem.
7. Use the files in `reviewed_annotations/` and `reviewed_render/` as the reviewed dataset outputs.

## Troubleshooting

### The browser cannot connect

Confirm that the terminal process is still running and that you opened the exact address printed by the editor. The default port is `8765`.

### Pillow is missing

The editor requires Pillow for rendering. Run it with an interpreter that has Pillow installed, such as:

```bash
python3 -m everyfish_coco_annotation_editor --dataset-root /path/to/dataset
```

### Images or annotations are missing

The editor expects matching files with the same stem:

```text
images/example.png
annotations/example.json
```

Restore missing source images or annotation JSONs before reviewing that pair.

### An instance has a label but no visible mask

That annotation does not have a usable polygon. It is preserved until you explicitly delete it.

### A save fails

Navigation is intentionally blocked after a failed save. Keep the editor open, check that the reviewed output folders are writable, and retry the action.

## Completion checklist

- All intended images were reviewed.
- Unwanted instances were deleted.
- Navigation completed without unresolved save errors.
- `reviewed_annotations/` contains the reviewed JSON files.
- `reviewed_render/` contains the reviewed PNGs needed for inspection.
- The original `annotations/` folder remains unchanged.

"""Render EVERYFISH-COCO polygon annotations onto their source images.

Annotation instances are drawn in blue. Rendered images are written to a
`render/` directory.

Usage:
    python -m everyfish_coco_annotation_editor.renderer [--count N]
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

def distinct_colors(n):
    """Generate n visually distinct RGB colors."""
    colors = []
    for i in range(n):
        # Use golden-ratio hue spacing on the HSV wheel for good separation.
        hue = (i * 0.618033988749895) % 1.0
        sat = 0.75
        val = 0.95
        h_i = int(hue * 6)
        f = hue * 6 - h_i
        p = val * (1 - sat)
        q = val * (1 - f * sat)
        t = val * (1 - (1 - f) * sat)
        if h_i == 0:
            r, g, b = val, t, p
        elif h_i == 1:
            r, g, b = q, val, p
        elif h_i == 2:
            r, g, b = p, val, t
        elif h_i == 3:
            r, g, b = p, q, val
        elif h_i == 4:
            r, g, b = t, p, val
        else:
            r, g, b = val, p, q
        colors.append((int(r * 255), int(g * 255), int(b * 255)))
    return colors


_FONT_CANDIDATES = [
    "DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/Library/Fonts/Arial.ttf",
]


def _load_font(img_width, divisor):
    """Load a bold TrueType font sized as img_width/divisor, else PIL default."""
    font_size = max(14, int(img_width / divisor))
    for name in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(name, font_size)
        except OSError:
            continue
    return ImageFont.load_default()


def _polygon_centroid(poly):
    """Return (cx, cy) of a polygon via the shoelace formula.

    Degenerate (near-zero-area) polygons fall back to the arithmetic mean of
    their points so the result always stays within the data's range.
    """
    pts = [(p["x"], p["y"]) for p in poly]
    n = len(pts)
    if n == 0:
        return None

    def mean():
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return sum(xs) / n, sum(ys) / n

    area = 0.0
    cx = cy = 0.0
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    if abs(area) < 1e-6:
        return mean()
    area *= 0.5
    cx /= 6 * area
    cy /= 6 * area
    # Guard against numerical blow-up on pathological polygons.
    if not all(abs(v) < 1e7 for v in (cx, cy)):
        return mean()
    return cx, cy


def _draw_total_box(draw, img, count, font):
    """Draw a textbox in the top-right corner showing the total instance count."""
    text = f"Total: {count}"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = 8
    x0 = img.width - tw - pad * 2
    y0 = pad
    x1 = img.width - pad
    y1 = pad + th + pad
    draw.rectangle([x0, y0, x1, y1], fill=(0, 0, 0, 180))
    draw.text((x0 + pad, y0 + pad), text, fill=(255, 255, 255, 255), font=font)


def render_one(img_path, ann_path, out_path):
    """Draw all polygon instances of an annotation onto the image.

    Each instance gets a blue outline/fill and a numbered id label
    placed on the centroid of every region belonging to that instance
    (multi-region instances share the same id on each part). A textbox in the
    top-right corner reports the total number of instances including
    non-fish instances in the image.
    """
    with open(ann_path, "r") as f:
        data = json.load(f)

    annotations = data.get("annotation", [])
    img = Image.open(img_path).convert("RGB")
    draw = ImageDraw.Draw(img, "RGBA")
    # Fonts for instance/class ids and the total-count textbox.
    id_font = _load_font(img.width, 40)  # smaller id font
    total_font = _load_font(img.width, 20)

    for idx, ann in enumerate(annotations):
        class_id = ann.get("category_id")
        color = (0, 0, 255)
        # Semi-transparent fill for the body + opaque outline for the edge.
        fill = color + (70,)
        outline = color + (255,)
        label = f"{idx}" if class_id is None else f"{idx}.{class_id}"

        for poly in ann.get("segmentation") or []:
            pts = [(p["x"], p["y"]) for p in poly]
            if len(pts) >= 3:
                draw.polygon(pts, fill=fill, outline=outline)
            elif len(pts) == 2:
                draw.line(pts, fill=outline, width=2)

            # Place the same instance id (+ class id) on each region.
            centroid = _polygon_centroid(poly)
            if centroid is not None:
                cx, cy = centroid
                # Skip if the centroid falls outside the image (bad polygon data).
                if not (0 <= cx <= img.width and 0 <= cy <= img.height):
                    continue
                bbox = draw.textbbox((0, 0), label, font=id_font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                tx = int(round(cx - tw / 2))
                ty = int(round(cy - th / 2))
                # Dark backing box for readability, then the id.class text.
                draw.rectangle(
                    [tx - 2, ty - 2, tx + tw + 2, ty + th + 2],
                    fill=(0, 0, 0, 160),
                )
                draw.text((tx, ty), label, fill=(255, 255, 255, 255), font=id_font)

    # Top-right textbox with the total number of instances (fish) in the image.
    _draw_total_box(draw, img, len(annotations), total_font)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path)
    return len(annotations)


def main():
    parser = argparse.ArgumentParser(description="Render annotations onto images")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path.cwd(),
        help="Dataset directory containing images/ and annotations/. Default: current directory.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=10,
        help="Number of images to render (in sorted filename order). Default: 10.",
    )
    parser.add_argument(
        "--start",
        type=int,
        default=0,
        help="Skip this many images before rendering (useful for pagination).",
    )
    args = parser.parse_args()
    root = args.dataset_root.expanduser().resolve()
    img_dir = root / "images"
    ann_dir = root / "annotations"
    out_dir = root / "render"

    img_files = sorted(img_dir.glob("*.png"))
    if args.start >= len(img_files):
        print(f"--start ({args.start}) is out of range (only {len(img_files)} images).")
        return
    selected = img_files[args.start : args.start + args.count]

    out_dir.mkdir(parents=True, exist_ok=True)

    for i, img_path in enumerate(selected):
        ann_path = ann_dir / (img_path.stem + ".json")
        if not ann_path.exists():
            print(f"[WARN] No annotation for {img_path.name}; skipping.")
            continue
        out_path = out_dir / img_path.name
        n = render_one(img_path, ann_path, out_path)
        print(f"[{i}] {img_path.name}: {n} instances -> {out_path}")

    print(f"Done. Rendered {len(selected)} images into {out_dir}.")


if __name__ == "__main__":
    main()

"""Local browser-based editor for EVERYFISH-COCO instance annotations."""

from __future__ import annotations

import argparse
import json
import mimetypes
import shutil
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .renderer import render_one


@dataclass(frozen=True)
class EditorPaths:
    """Filesystem locations used by one editor server instance."""

    root: Path
    images: Path
    annotations: Path
    reviewed_annotations: Path
    reviewed_render: Path

    @classmethod
    def from_root(cls, root: Path) -> "EditorPaths":
        root = root.expanduser().resolve()
        return cls(
            root=root,
            images=root / "images",
            annotations=root / "annotations",
            reviewed_annotations=root / "reviewed_annotations",
            reviewed_render=root / "reviewed_render",
        )


HTML = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EVERYFISH-COCO Annotation Editor</title>
  <style>
    :root { color-scheme: dark; font-family: system-ui, sans-serif; }
    body { margin: 0; background: #111827; color: #e5e7eb; }
    header { display: flex; gap: 14px; align-items: center; padding: 12px 18px; background: #1f2937; }
    h1 { margin: 0; font-size: 18px; white-space: nowrap; }
    button, select, input { border: 1px solid #4b5563; border-radius: 5px; background: #374151; color: inherit; padding: 7px 10px; }
    button:hover { background: #4b5563; cursor: pointer; }
    button:disabled { opacity: .45; cursor: not-allowed; }
    #layout { display: grid; grid-template-columns: minmax(220px, 310px) minmax(0, 1fr) minmax(210px, 280px); height: calc(100vh - 59px); }
    #imageSidebar, #annotationSidebar { overflow: auto; padding: 12px; }
    #imageSidebar { border-right: 1px solid #374151; }
    #annotationSidebar { border-left: 1px solid #374151; }
    body.left-collapsed #layout { grid-template-columns: 0 minmax(0, 1fr) minmax(210px, 280px); }
    body.left-collapsed #imageSidebar { overflow: hidden; padding: 0; border-right: 0; }
    body.left-collapsed #imageSidebar > * { display: none; }
    #imageList, #annotationList { display: grid; gap: 4px; margin-top: 10px; }
    .image-item { overflow: hidden; text-align: left; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
    .image-item.active { background: #2563eb; }
    .panel-title { color: #9ca3af; font-size: 12px; font-weight: 700; text-transform: uppercase; }
    #annotationNav { display: flex; gap: 4px; margin-top: 8px; }
    #annotationNav button { flex: 1; font-size: 18px; line-height: 1; padding: 5px 8px; }
    .annotation-item { display: grid; gap: 2px; text-align: left; font-size: 12px; }
    .annotation-item.active { background: #2563eb; }
    .annotation-item.visible { border-color: #22d3ee; box-shadow: inset 3px 0 0 #22d3ee; }
    .annotation-item.class-40 { border-color: #991b1b; background: #451a1a; color: #fecaca; }
    .annotation-item.class-40 .ann-meta { color: #fca5a5; }
    .annotation-item.class-40.active { border-color: #facc15; background: #991b1b; color: #fff; }
    .annotation-item.class-40.active .ann-meta { color: #fee2e2; }
    .annotation-item.class-40.visible { border-color: #f87171; box-shadow: inset 3px 0 0 #f87171; }
    .annotation-item.class-highlighted { border-color: #dc2626; background: #7f1d1d; color: #fee2e2; }
    .annotation-item.class-highlighted .ann-meta { color: #fecaca; }
    .annotation-item.class-highlighted.active { border-color: #facc15; background: #991b1b; color: #fff; }
    .annotation-item.class-highlighted.active .ann-meta { color: #fee2e2; }
    .annotation-item.class-highlighted.visible { border-color: #f87171; box-shadow: inset 3px 0 0 #f87171; }
    .annotation-item .ann-title { font-weight: 700; }
    .annotation-item .ann-meta { color: #cbd5e1; }
    .empty-list { color: #9ca3af; font-size: 13px; }
    main { display: flex; min-width: 0; flex-direction: column; padding: 12px; gap: 8px; }
    #toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
    #status { color: #9ca3af; font-size: 13px; }
    #canvasWrap { display: flex; min-height: 0; flex: 1; align-items: flex-start; justify-content: flex-start; overflow: auto; background: #030712; }
    canvas { display: block; }
    canvas.pan-ready { cursor: grab; }
    canvas.pan-active { cursor: grabbing; }
    canvas.draw-mode { cursor: crosshair; }
    #details { min-height: 24px; color: #fbbf24; font-size: 13px; }
    dialog { width: min(760px, calc(100vw - 32px)); max-height: calc(100vh - 48px); overflow: auto; border: 1px solid #4b5563; border-radius: 8px; background: #1f2937; color: #e5e7eb; padding: 0; }
    dialog::backdrop { background: rgba(3, 7, 18, .72); }
    .help-header { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 18px; border-bottom: 1px solid #374151; }
    .help-header h2 { margin: 0; font-size: 18px; }
    .help-content { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px 24px; padding: 18px; }
    .help-content section { min-width: 0; }
    .help-content h3 { margin: 0 0 7px; font-size: 14px; color: #fbbf24; }
    .help-content p { margin: 0; color: #d1d5db; font-size: 13px; line-height: 1.45; }
    .help-content ul { margin: 0; padding-left: 19px; color: #d1d5db; font-size: 13px; line-height: 1.55; }
    .help-content kbd { border: 1px solid #6b7280; border-radius: 4px; background: #111827; padding: 1px 5px; color: #f9fafb; font-family: inherit; font-size: 12px; }
    @media (max-width: 640px) { .help-content { grid-template-columns: 1fr; } }
    @media (max-width: 900px) { #layout, body.left-collapsed #layout { grid-template-columns: 1fr; grid-template-rows: 180px 1fr 180px; height: auto; } #imageSidebar, #annotationSidebar { border-right: 0; border-left: 0; border-bottom: 1px solid #374151; } body.left-collapsed #layout { grid-template-rows: 0 1fr 180px; } }
  </style>
</head>
<body>
  <header>
    <h1>EVERYFISH-COCO Annotation Editor</h1>
    <button id="toggleSidebar">Hide image list</button>
    <button id="prev">Previous</button>
    <button id="next">Next</button>
    <label>Jump to image <input id="jumpInput" type="number" min="1" step="1" placeholder="1" style="width: 72px"></label>
    <button id="zoomOut" disabled>Zoom Out</button>
    <button id="zoomIn" disabled>Zoom In</button>
    <button id="zoomReset" disabled>Reset Zoom</button>
    <span id="zoomLabel">100%</span>
    <button id="toggleAnnotations" disabled>Hide annotations</button>
    <label>Category ID <input id="categoryInput" type="number" step="1" style="width: 72px"></label>
    <button id="drawPolygon" disabled>Draw polygon</button>
    <button id="cancelDrawing" hidden disabled>Cancel drawing</button>
    <label>Highlight class ID <input id="highlightInput" type="number" step="1" style="width: 72px"></label>
    <button id="setHighlight" disabled>Highlight class</button>
    <button id="clearHighlight" disabled>Clear highlight</button>
    <button id="delete" disabled>Delete selected instance</button>
    <button id="helpButton" title="Open help ( ? )" aria-label="Open help">Help</button>
    <span id="status">Loading…</span>
  </header>
  <div id="layout">
    <aside id="imageSidebar">
      <label>Search filename <input id="searchInput" type="search" placeholder="Filter filenames"></label>
      <label>Image <select id="imageSelect"></select></label>
      <div id="imageList"></div>
    </aside>
    <main>
      <div id="details">Click a polygon to select an instance.</div>
      <div id="canvasWrap"><canvas id="canvas"></canvas></div>
    </main>
    <aside id="annotationSidebar">
      <div class="panel-title">Annotations</div>
      <div id="annotationNav">
        <button id="annotationUp" title="Previous annotation" aria-label="Previous annotation" disabled>↑</button>
        <button id="annotationDown" title="Next annotation" aria-label="Next annotation" disabled>↓</button>
      </div>
      <div id="annotationList"></div>
    </aside>
  </div>
  <dialog id="helpDialog" aria-labelledby="helpTitle">
    <div class="help-header">
      <h2 id="helpTitle">EVERYFISH-COCO Annotation Editor help</h2>
      <button id="closeHelpButton" type="button" title="Close help" aria-label="Close help">×</button>
    </div>
    <div class="help-content">
      <section>
        <h3>Navigate images</h3>
        <ul>
          <li><kbd>←</kbd> / <kbd>→</kbd> or Previous / Next: change image</li>
          <li>Jump to image: enter an image number and press <kbd>Enter</kbd></li>
          <li>Search filename: filter the left image list</li>
          <li>Hide image list: collapse the left sidebar</li>
        </ul>
      </section>
      <section>
        <h3>Navigate annotations</h3>
        <ul>
          <li><kbd>↑</kbd> / <kbd>↓</kbd> or the sidebar arrows: select an annotation</li>
          <li>Click a polygon, ID, or row: select an annotation</li>
          <li>In hidden mode, selecting a row shows only that annotation</li>
        </ul>
      </section>
      <section>
        <h3>Canvas view</h3>
        <ul>
          <li><kbd>Space</kbd>: hide or show all annotations</li>
          <li>Zoom buttons or trackpad pinch: zoom from 100% to 800%</li>
          <li>When zoomed, drag or scroll the canvas to pan</li>
        </ul>
      </section>
      <section>
        <h3>Draw and edit</h3>
        <ul>
          <li>Enter a Category ID, then choose Draw polygon</li>
          <li>Click vertices; double-click or press <kbd>Enter</kbd> to save</li>
          <li><kbd>Esc</kbd>: cancel the draft polygon</li>
          <li><kbd>Backspace</kbd>: delete the selected instance immediately</li>
        </ul>
      </section>
      <section>
        <h3>Highlight a class</h3>
        <p>Enter a numeric class ID and choose Highlight class. Matching instances and list rows use red masks and bounding boxes. The choice stays active while moving through images. Choose Clear highlight to restore default colors.</p>
      </section>
      <section>
        <h3>Saving</h3>
        <p>Changes are saved to the reviewed copy before navigation. Original files stay unchanged. Reviewed PNGs are generated only when annotation data actually changes.</p>
      </section>
    </div>
  </dialog>
<script>
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const toggleSidebarButton = document.getElementById('toggleSidebar');
const prevButton = document.getElementById('prev');
const nextButton = document.getElementById('next');
const imageSelect = document.getElementById('imageSelect');
const imageList = document.getElementById('imageList');
const annotationList = document.getElementById('annotationList');
const annotationUpButton = document.getElementById('annotationUp');
const annotationDownButton = document.getElementById('annotationDown');
const searchInput = document.getElementById('searchInput');
const statusEl = document.getElementById('status');
const details = document.getElementById('details');
const deleteButton = document.getElementById('delete');
const jumpInput = document.getElementById('jumpInput');
const canvasWrap = document.getElementById('canvasWrap');
const zoomOutButton = document.getElementById('zoomOut');
const zoomInButton = document.getElementById('zoomIn');
const zoomResetButton = document.getElementById('zoomReset');
const zoomLabel = document.getElementById('zoomLabel');
const toggleAnnotationsButton = document.getElementById('toggleAnnotations');
const categoryInput = document.getElementById('categoryInput');
const drawPolygonButton = document.getElementById('drawPolygon');
const cancelDrawingButton = document.getElementById('cancelDrawing');
const highlightInput = document.getElementById('highlightInput');
const setHighlightButton = document.getElementById('setHighlight');
const clearHighlightButton = document.getElementById('clearHighlight');
const helpButton = document.getElementById('helpButton');
const helpDialog = document.getElementById('helpDialog');
const closeHelpButton = document.getElementById('closeHelpButton');
const MIN_ZOOM = 1;
const MAX_ZOOM = 8;
let images = [], current = -1, annotations = [], selected = -1, hovered = -1, sourceImage = null, zoom = MIN_ZOOM, annotationsVisible = true;
let loadedImageName = null, loadRequestId = 0, savePromise = null, loading = false;
let leftSidebarCollapsed = false;
let visibleAnnotationIndexes = new Set();
let drawing = false, draftPoints = [], lastCategoryId = null, highlightCategoryId = null;
let dragging = false, dragMoved = false, suppressClick = false, dragStartX = 0, dragStartY = 0, dragScrollLeft = 0, dragScrollTop = 0;

function setStatus(text) { statusEl.textContent = text; }
function points(poly) { return poly.map(p => [p.x, p.y]); }
function isBusy() { return Boolean(savePromise) || loading; }
function cloneAnnotations(value) { return JSON.parse(JSON.stringify(value)); }
function updateSidebar() {
  document.body.classList.toggle('left-collapsed', leftSidebarCollapsed);
  toggleSidebarButton.textContent = leftSidebarCollapsed ? 'Show image list' : 'Hide image list';
}
function updateControls() {
  const busy = isBusy();
  const blocked = busy || drawing;
  prevButton.disabled = blocked;
  nextButton.disabled = blocked;
  imageSelect.disabled = blocked;
  searchInput.disabled = blocked;
  jumpInput.disabled = blocked;
  document.querySelectorAll('.image-item').forEach(button => { button.disabled = blocked; });
  document.querySelectorAll('.annotation-item').forEach(button => { button.disabled = blocked; });
  annotationUpButton.disabled = blocked || !annotations.length || (selected >= 0 && selected <= 0);
  annotationDownButton.disabled = blocked || !annotations.length || (selected >= 0 && selected >= annotations.length - 1);
  categoryInput.disabled = busy;
  drawPolygonButton.disabled = busy || drawing || !loadedImageName || !sourceImage;
  cancelDrawingButton.hidden = !drawing;
  cancelDrawingButton.disabled = busy || !drawing;
  highlightInput.disabled = busy;
  setHighlightButton.disabled = busy || !sourceImage;
  clearHighlightButton.disabled = busy || highlightCategoryId === null;
  deleteButton.disabled = blocked || selected < 0 || !loadedImageName || !sourceImage;
  toggleAnnotationsButton.textContent = annotationsVisible ? 'Hide annotations' : 'Show annotations';
  toggleAnnotationsButton.disabled = busy || !sourceImage;
}
function toggleAnnotationVisibility() {
  if (!sourceImage || isBusy()) return;
  annotationsVisible = !annotationsVisible;
  if (!annotationsVisible) visibleAnnotationIndexes = new Set();
  updateControls();
  renderAnnotationList();
  draw();
}
function parseCategoryId() {
  const value = Number(categoryInput.value);
  return Number.isInteger(value) ? value : null;
}
function parseHighlightCategoryId() {
  const value = Number(highlightInput.value);
  return Number.isInteger(value) ? value : null;
}
function setHighlightCategory() {
  const categoryId = parseHighlightCategoryId();
  if (categoryId === null) {
    setStatus('Enter a numeric class ID to highlight.');
    highlightInput.focus();
    return;
  }
  highlightCategoryId = categoryId;
  highlightInput.value = String(categoryId);
  renderAnnotationList();
  draw();
  setStatus(`Highlighting class ${categoryId} across images.`);
}
function clearHighlightCategory() {
  highlightCategoryId = null;
  highlightInput.value = '';
  renderAnnotationList();
  draw();
  setStatus('Class highlighting cleared.');
}
function selectedCategoryId() {
  if (selected < 0 || selected >= annotations.length) return null;
  const value = Number(annotations[selected].category_id);
  return Number.isInteger(value) ? value : null;
}
function activeCategoryId() {
  return parseCategoryId() ?? selectedCategoryId() ?? lastCategoryId;
}
function pointInPolygon(x, y, poly) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const xi = poly[i].x, yi = poly[i].y, xj = poly[j].x, yj = poly[j].y;
    const hit = ((yi > y) !== (yj > y)) && x < (xj - xi) * (y - yi) / (yj - yi) + xi;
    if (hit) inside = !inside;
  }
  return inside;
}
function drawDraftPolygon() {
  if (!drawing || !draftPoints.length) return;
  ctx.save();
  ctx.strokeStyle = '#22d3ee';
  ctx.fillStyle = 'rgba(34,211,238,.18)';
  ctx.lineWidth = 3;
  ctx.setLineDash([8, 5]);
  if (draftPoints.length >= 2) {
    ctx.beginPath();
    ctx.moveTo(draftPoints[0].x, draftPoints[0].y);
    draftPoints.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
    if (draftPoints.length >= 3) { ctx.closePath(); ctx.fill(); }
    ctx.stroke();
  }
  ctx.setLineDash([]);
  for (const point of draftPoints) {
    ctx.beginPath();
    ctx.arc(point.x, point.y, 4, 0, Math.PI * 2);
    ctx.fillStyle = '#facc15';
    ctx.strokeStyle = '#111827';
    ctx.lineWidth = 2;
    ctx.fill();
    ctx.stroke();
  }
  ctx.restore();
}
function drawAnnotation(ann, index, forceVisible = false) {
  const categoryId = Number(ann.category_id);
  const red = highlightCategoryId !== null ? categoryId === highlightCategoryId : [40, 41].includes(categoryId);
  const isHovered = !forceVisible && index === hovered;
  if (!isHovered) {
    ctx.fillStyle = red ? 'rgba(255,0,0,.28)' : 'rgba(0,0,255,.28)';
    ctx.strokeStyle = index === selected ? '#facc15' : (red ? '#ff2020' : '#2020ff');
    ctx.lineWidth = index === selected ? 5 : 3;
    for (const poly of (ann.segmentation || [])) {
      if (poly.length < 2) continue;
      ctx.beginPath(); ctx.moveTo(poly[0].x, poly[0].y);
      poly.slice(1).forEach(p => ctx.lineTo(p.x, p.y));
      if (poly.length >= 3) { ctx.closePath(); ctx.fill(); }
      ctx.stroke();
    }
  }
  const all = (ann.segmentation || []).flat();
  if (all.length) {
    if (red) {
      const xs = all.map(p => p.x), ys = all.map(p => p.y);
      ctx.strokeStyle = index === selected ? '#facc15' : '#ff2020';
      ctx.lineWidth = index === selected ? 5 : 3;
      ctx.strokeRect(Math.min(...xs), Math.min(...ys), Math.max(...xs) - Math.min(...xs), Math.max(...ys) - Math.min(...ys));
    }
    if (!isHovered) {
      const x = all.reduce((sum, p) => sum + p.x, 0) / all.length;
      const y = all.reduce((sum, p) => sum + p.y, 0) / all.length;
      ctx.fillStyle = '#fff'; ctx.strokeStyle = '#000'; ctx.lineWidth = 3;
      ctx.font = 'bold 18px sans-serif'; ctx.strokeText(`${index}.${ann.category_id ?? ''}`, x, y); ctx.fillText(`${index}.${ann.category_id ?? ''}`, x, y);
    }
  }
}
function draw() {
  if (!sourceImage) return;
  canvas.width = Math.round(sourceImage.naturalWidth * zoom); canvas.height = Math.round(sourceImage.naturalHeight * zoom);
  canvas.style.width = `${canvas.width}px`; canvas.style.height = `${canvas.height}px`;
  canvas.classList.toggle('pan-ready', zoom > MIN_ZOOM && !dragging && !drawing);
  canvas.classList.toggle('pan-active', dragging && !drawing);
  canvas.classList.toggle('draw-mode', drawing);
  ctx.setTransform(zoom, 0, 0, zoom, 0, 0);
  ctx.drawImage(sourceImage, 0, 0);
  if (!annotationsVisible) {
    for (const index of [...visibleAnnotationIndexes].sort((a, b) => a - b)) {
      if (index >= 0 && index < annotations.length) drawAnnotation(annotations[index], index, true);
    }
    drawDraftPolygon();
    zoomLabel.textContent = `${Math.round(zoom * 100)}%`;
    zoomOutButton.disabled = zoom <= MIN_ZOOM || !sourceImage;
    zoomInButton.disabled = zoom >= MAX_ZOOM || !sourceImage;
    zoomResetButton.disabled = zoom === MIN_ZOOM || !sourceImage;
    updateControls();
    return;
  }
  annotations.forEach(drawAnnotation);
  drawDraftPolygon();
  zoomLabel.textContent = `${Math.round(zoom * 100)}%`;
  zoomOutButton.disabled = zoom <= MIN_ZOOM || !sourceImage;
  zoomInButton.disabled = zoom >= MAX_ZOOM || !sourceImage;
  zoomResetButton.disabled = zoom === MIN_ZOOM || !sourceImage;
  updateControls();
}
function updateSelection() {
  if (selected >= annotations.length) selected = -1;
  updateControls();
  details.textContent = selected < 0 ? 'Click a polygon to select an instance.' : `Selected instance ${selected} — class ID ${annotations[selected].category_id}`;
  renderAnnotationList();
  draw();
}
function annotationSummary(ann) {
  const regions = Array.isArray(ann.segmentation) ? ann.segmentation : [];
  const validRegions = regions.filter(poly => Array.isArray(poly) && poly.length >= 3).length;
  if (!regions.length || !validRegions) return 'maskless';
  return validRegions === regions.length ? `${validRegions} regions` : `${validRegions}/${regions.length} regions`;
}
function renderAnnotationList() {
  annotationList.replaceChildren();
  if (!annotations.length) {
    const empty = document.createElement('div');
    empty.className = 'empty-list';
    empty.textContent = 'No annotations';
    annotationList.appendChild(empty);
    updateControls();
    return;
  }
  annotations.forEach((ann, index) => {
    const button = document.createElement('button');
    const class40 = Number(ann.category_id) === 40;
    const classHighlighted = highlightCategoryId !== null && Number(ann.category_id) === highlightCategoryId;
    const visible = !annotationsVisible && visibleAnnotationIndexes.has(index);
    button.className = `annotation-item${class40 ? ' class-40' : ''}${classHighlighted ? ' class-highlighted' : ''}${visible ? ' visible' : ''}${index === selected ? ' active' : ''}`;
    button.disabled = isBusy();
    const title = document.createElement('span');
    title.className = 'ann-title';
    title.textContent = `ID ${index}`;
    const meta = document.createElement('span');
    meta.className = 'ann-meta';
    meta.textContent = `Class ${ann.category_id ?? 'unknown'} · ${annotationSummary(ann)}`;
    button.append(title, meta);
    button.onclick = () => selectAnnotation(index);
    annotationList.appendChild(button);
  });
  updateControls();
}
function selectAnnotation(index) {
  if (isBusy() || index < 0 || index >= annotations.length) return;
  if (!annotationsVisible) {
    if (visibleAnnotationIndexes.has(index)) {
      visibleAnnotationIndexes.clear();
      selected = -1;
    } else {
      visibleAnnotationIndexes.clear();
      visibleAnnotationIndexes.add(index);
      selected = index;
    }
    hovered = -1;
    updateSelection();
    return;
  }
  selected = index; hovered = -1;
  updateSelection();
}
function navigateAnnotationSelection(delta) {
  if (isBusy() || drawing || !annotations.length) return;
  const next = selected < 0 ? (delta > 0 ? 0 : annotations.length - 1) : selected + delta;
  if (next < 0 || next >= annotations.length || next === selected) return;
  selectAnnotation(next);
  document.querySelectorAll('.annotation-item')[next]?.scrollIntoView({block: 'nearest'});
}
function startDrawing() {
  if (!sourceImage || !loadedImageName || isBusy() || drawing) return;
  const categoryId = activeCategoryId();
  if (categoryId === null) {
    setStatus('Enter a numeric category ID before drawing.');
    categoryInput.focus();
    return;
  }
  categoryInput.value = String(categoryId);
  lastCategoryId = categoryId;
  drawing = true; draftPoints = []; selected = -1; hovered = -1; dragging = false; suppressClick = false;
  details.textContent = 'Drawing polygon: click vertices, double-click or press Enter to finish, Escape to cancel.';
  setStatus('Drawing polygon — add at least 3 points.');
  updateControls();
  draw();
}
function cancelDrawing() {
  if (!drawing || isBusy()) return;
  drawing = false; draftPoints = [];
  updateSelection();
  setStatus('Drawing canceled.');
}
function addDraftPoint(point) {
  if (!drawing || !sourceImage || isBusy()) return;
  draftPoints.push({
    x: Math.max(0, Math.min(sourceImage.naturalWidth, point.x)),
    y: Math.max(0, Math.min(sourceImage.naturalHeight, point.y))
  });
  setStatus(`Drawing polygon — ${draftPoints.length} point${draftPoints.length === 1 ? '' : 's'}.`);
  draw();
}
async function finishDraftPolygon() {
  if (!drawing || isBusy()) return;
  const categoryId = activeCategoryId();
  if (categoryId === null) {
    setStatus('Enter a numeric category ID before saving the polygon.');
    categoryInput.focus();
    return;
  }
  if (draftPoints.length < 3) {
    setStatus('Add at least 3 points before saving the polygon.');
    return;
  }
  const imageName = loadedImageName;
  const newAnnotation = {
    category_id: categoryId,
    segmentation: [draftPoints.map(point => ({x: point.x, y: point.y}))]
  };
  const nextAnnotations = [...annotations, newAnnotation];
  if (!(await saveAnnotationState(imageName, nextAnnotations))) return;
  if (loadedImageName !== imageName) return;
  annotations = nextAnnotations;
  selected = annotations.length - 1; hovered = -1; drawing = false; draftPoints = []; lastCategoryId = categoryId;
  categoryInput.value = String(categoryId);
  updateSelection();
  setStatus(`${current + 1} of ${images.length} — saved; ${annotations.length} instances`);
}
function canvasPoint(event) {
  const rect = canvasWrap.getBoundingClientRect();
  return {
    x: (event.clientX - rect.left + canvasWrap.scrollLeft) / zoom,
    y: (event.clientY - rect.top + canvasWrap.scrollTop) / zoom
  };
}
function labelBounds(index, ann) {
  const all = (ann.segmentation || []).flat();
  if (!all.length) return null;
  const x = all.reduce((sum, p) => sum + p.x, 0) / all.length;
  const y = all.reduce((sum, p) => sum + p.y, 0) / all.length;
  ctx.save();
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.font = 'bold 18px sans-serif';
  const width = ctx.measureText(`${index}.${ann.category_id ?? ''}`).width;
  ctx.restore();
  return {x, y: y - 18, width, height: 22};
}
function instanceAtPoint(x, y) {
  for (let i = annotations.length - 1; i >= 0; i--) {
    const inPolygon = (annotations[i].segmentation || []).some(poly => poly.length >= 3 && pointInPolygon(x, y, poly));
    const label = labelBounds(i, annotations[i]);
    const inLabel = label && x >= label.x && x <= label.x + label.width && y >= label.y && y <= label.y + label.height;
    if (inPolygon || inLabel) return i;
  }
  return -1;
}
async function saveAnnotationState(imageName, nextAnnotations) {
  if (!imageName) return true;
  while (savePromise) {
    if (!(await savePromise)) return false;
  }
  const saveName = imageName;
  const payloadAnnotations = cloneAnnotations(nextAnnotations);
  const payload = JSON.stringify({image_name: saveName, annotation: payloadAnnotations});
  const saveIndex = images.indexOf(saveName);
  const savePosition = saveIndex >= 0 ? saveIndex + 1 : current + 1;
  setStatus(`Saving ${savePosition} of ${images.length}…`);
  savePromise = (async () => {
    try {
      const response = await fetch(`/api/annotation/${encodeURIComponent(saveName)}`, {
        method: 'PUT',
        headers: {'Content-Type': 'application/json'},
        body: payload
      });
      if (!response.ok) throw new Error(await response.text());
      return true;
    } catch (error) {
      setStatus(`Save failed: ${error.message}`);
      return false;
    } finally {
      savePromise = null;
      updateControls();
    }
  })();
  updateControls();
  return savePromise;
}
async function saveCurrent() {
  if (!loadedImageName || !sourceImage) return true;
  return saveAnnotationState(loadedImageName, annotations);
}
async function navigateTo(index) {
  if (!images.length || isBusy() || drawing) return;
  const target = Math.max(0, Math.min(index, images.length - 1));
  if (target === current) return;
  if (!(await saveCurrent())) return;
  await load(target);
}
async function load(index) {
  if (loading) return;
  const requestId = ++loadRequestId;
  const target = Math.max(0, Math.min(index, images.length - 1));
  const targetName = images[target];
  loading = true;
  updateControls();
  setStatus(`Loading ${target + 1} of ${images.length}…`);
  try {
    const response = await fetch(`/api/annotation/${encodeURIComponent(targetName)}`); if (!response.ok) throw new Error(await response.text());
    const data = await response.json();
    if (requestId !== loadRequestId) return;
    current = target; loadedImageName = targetName; annotations = data.annotation || [];
    selected = -1; hovered = -1; zoom = MIN_ZOOM; annotationsVisible = true; visibleAnnotationIndexes = new Set(); drawing = false; draftPoints = []; dragging = false; suppressClick = false;
    imageSelect.value = String(current); jumpInput.value = String(current + 1); document.querySelectorAll('.image-item').forEach((e, i) => e.classList.toggle('active', i === current));
    sourceImage = new Image();
    sourceImage.onload = () => {
      if (requestId !== loadRequestId || loadedImageName !== targetName) return;
      loading = false;
      draw(); setStatus(`${target + 1} of ${images.length} — ${annotations.length} instances`);
      updateControls();
    };
    sourceImage.onerror = () => {
      if (requestId !== loadRequestId || loadedImageName !== targetName) return;
      loading = false; sourceImage = null;
      setStatus('Could not load source image.');
      updateControls();
    };
    sourceImage.src = `/images/${encodeURIComponent(targetName)}`;
    updateSelection();
  } catch (error) {
    if (requestId === loadRequestId) {
      loading = false;
      setStatus(`Error: ${error.message}`);
      updateControls();
    }
  }
}
function setZoom(nextZoom, event = null) {
  if (!sourceImage) return;
  const next = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, nextZoom));
  if (next === zoom) return;
  let imageX, imageY, localX, localY;
  if (event) {
    const rect = canvasWrap.getBoundingClientRect();
    localX = event.clientX - rect.left;
    localY = event.clientY - rect.top;
    imageX = (localX + canvasWrap.scrollLeft) / zoom;
    imageY = (localY + canvasWrap.scrollTop) / zoom;
  }
  zoom = next;
  draw();
  if (event) {
    canvasWrap.scrollLeft = Math.max(0, imageX * zoom - localX);
    canvasWrap.scrollTop = Math.max(0, imageY * zoom - localY);
  }
}
function matchingImages() {
  const query = searchInput.value.trim().toLowerCase();
  return images.map((name, index) => ({name, index})).filter(item => !query || item.name.toLowerCase().includes(query));
}
function renderImageList() {
  imageList.replaceChildren();
  for (const item of matchingImages()) {
    const button = document.createElement('button');
    button.className = `image-item${item.index === current ? ' active' : ''}`;
    button.title = item.name;
    button.textContent = `${item.index + 1}: ${item.name}`;
    button.onclick = () => navigateTo(item.index);
    imageList.appendChild(button);
  }
  updateControls();
}
toggleSidebarButton.addEventListener('click', () => {
  leftSidebarCollapsed = !leftSidebarCollapsed;
  updateSidebar();
});
imageSelect.addEventListener('change', () => navigateTo(Number(imageSelect.value)));
prevButton.addEventListener('click', () => navigateTo(current - 1));
nextButton.addEventListener('click', () => navigateTo(current + 1));
searchInput.addEventListener('input', renderImageList);
searchInput.addEventListener('keydown', event => {
  if (event.key !== 'Enter') return;
  event.preventDefault();
  if (isBusy()) return;
  const matches = matchingImages();
  if (!matches.length) {
    setStatus(`No filenames match “${searchInput.value}”.`);
    return;
  }
  navigateTo(matches[0].index);
});
zoomInButton.addEventListener('click', () => setZoom(zoom * 1.25));
zoomOutButton.addEventListener('click', () => setZoom(zoom / 1.25));
zoomResetButton.addEventListener('click', () => setZoom(MIN_ZOOM));
toggleAnnotationsButton.addEventListener('click', toggleAnnotationVisibility);
annotationUpButton.addEventListener('click', () => navigateAnnotationSelection(-1));
annotationDownButton.addEventListener('click', () => navigateAnnotationSelection(1));
drawPolygonButton.addEventListener('click', startDrawing);
cancelDrawingButton.addEventListener('click', cancelDrawing);
setHighlightButton.addEventListener('click', setHighlightCategory);
clearHighlightButton.addEventListener('click', clearHighlightCategory);
helpButton.addEventListener('click', () => {
  if (helpDialog.open) helpDialog.close(); else helpDialog.showModal();
});
closeHelpButton.addEventListener('click', () => helpDialog.close());
helpDialog.addEventListener('click', event => {
  if (event.target === helpDialog) helpDialog.close();
});
categoryInput.addEventListener('change', () => {
  const categoryId = parseCategoryId();
  if (categoryId !== null) lastCategoryId = categoryId;
});
highlightInput.addEventListener('keydown', event => {
  if (event.key !== 'Enter') return;
  event.preventDefault();
  setHighlightCategory();
});
jumpInput.addEventListener('wheel', event => event.stopPropagation());
jumpInput.addEventListener('keydown', event => {
  if (event.key !== 'Enter') return;
  event.preventDefault();
  if (isBusy()) return;
  const imageNumber = Number(jumpInput.value);
  if (!Number.isInteger(imageNumber) || imageNumber < 1 || imageNumber > images.length) {
    setStatus(`Enter an image number from 1 to ${images.length}.`);
    jumpInput.value = String(current + 1);
    return;
  }
  navigateTo(imageNumber - 1);
});
document.addEventListener('keydown', event => {
  if (helpDialog.open) return;
  if (drawing && event.key === 'Enter') {
    event.preventDefault();
    finishDraftPolygon();
    return;
  }
  if (drawing && event.key === 'Escape') {
    event.preventDefault();
    cancelDrawing();
    return;
  }
  const target = event.target;
  const editing = target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement || target.isContentEditable;
  if (editing || !images.length) return;
  const shortcut = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Backspace'].includes(event.key) || event.code === 'Space' || event.key === '?';
  if ((isBusy() || drawing) && shortcut) {
    event.preventDefault();
    return;
  }
  if (event.key === 'ArrowLeft') {
    event.preventDefault();
    navigateTo(current - 1);
  } else if (event.key === 'ArrowRight') {
    event.preventDefault();
    navigateTo(current + 1);
  } else if (event.key === 'ArrowUp') {
    event.preventDefault();
    navigateAnnotationSelection(-1);
  } else if (event.key === 'ArrowDown') {
    event.preventDefault();
    navigateAnnotationSelection(1);
  } else if (event.key === 'Backspace') {
    event.preventDefault();
    deleteSelectedInstance(true);
  } else if (event.code === 'Space') {
    event.preventDefault();
    toggleAnnotationVisibility();
  } else if (event.key === '?') {
    event.preventDefault();
    helpDialog.showModal();
  }
});
async function deleteSelectedInstance(skipConfirmation = false) {
  if (selected < 0 || isBusy() || drawing) return;
  const deletedIndex = selected;
  const imageName = loadedImageName;
  if (!skipConfirmation && !confirm(`Delete instance ${deletedIndex} from this reviewed copy?`)) return;
  const nextAnnotations = annotations.filter((_, index) => index !== deletedIndex);
  if (!(await saveAnnotationState(imageName, nextAnnotations))) return;
  if (loadedImageName !== imageName) return;
  visibleAnnotationIndexes = new Set([...visibleAnnotationIndexes].flatMap(index => {
    if (index === deletedIndex) return [];
    return [index > deletedIndex ? index - 1 : index];
  }));
  annotations = nextAnnotations; selected = -1; hovered = -1;
  updateSelection(); setStatus(`${current + 1} of ${images.length} — saved; ${annotations.length} instances`);
}
deleteButton.addEventListener('click', () => deleteSelectedInstance(false));
canvas.addEventListener('pointerdown', event => {
  if (drawing || !sourceImage || zoom <= MIN_ZOOM || event.button !== 0) return;
  dragging = true; dragMoved = false;
  dragStartX = event.clientX; dragStartY = event.clientY;
  dragScrollLeft = canvasWrap.scrollLeft; dragScrollTop = canvasWrap.scrollTop;
  canvas.setPointerCapture(event.pointerId);
  draw();
});
canvas.addEventListener('pointermove', event => {
  if (!dragging) return;
  const dx = event.clientX - dragStartX;
  const dy = event.clientY - dragStartY;
  if (Math.abs(dx) > 4 || Math.abs(dy) > 4) dragMoved = true;
  canvasWrap.scrollLeft = dragScrollLeft - dx;
  canvasWrap.scrollTop = dragScrollTop - dy;
  const point = canvasPoint(event);
  hovered = instanceAtPoint(point.x, point.y);
});
function finishDrag(event) {
  if (!dragging) return;
  dragging = false;
  suppressClick = dragMoved;
  if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
  draw();
}
canvas.addEventListener('pointerup', finishDrag);
canvas.addEventListener('pointercancel', finishDrag);
canvas.addEventListener('click', event => {
  if (!sourceImage) return;
  if (drawing) {
    event.preventDefault();
    if (event.detail > 1) return;
    addDraftPoint(canvasPoint(event));
    return;
  }
  if (suppressClick) { suppressClick = false; return; }
  if (!annotationsVisible) return;
  const point = canvasPoint(event);
  selected = instanceAtPoint(point.x, point.y);
  updateSelection();
});
canvas.addEventListener('dblclick', event => {
  if (!drawing) return;
  event.preventDefault();
  finishDraftPolygon();
});
canvas.addEventListener('mousemove', event => {
  if (!sourceImage || drawing) return;
  const point = canvasPoint(event);
  const nextHovered = instanceAtPoint(point.x, point.y);
  if (nextHovered !== hovered) {
    hovered = nextHovered;
    draw();
  }
});
canvas.addEventListener('wheel', event => {
  if (!event.ctrlKey) return;
  event.preventDefault();
  setZoom(zoom * (event.deltaY < 0 ? 1.25 : 0.8), event);
}, {passive: false});
canvas.addEventListener('mouseleave', () => {
  if (hovered !== -1) {
    hovered = -1;
    draw();
  }
});
async function init() {
  const response = await fetch('/api/images'); images = await response.json();
  images.forEach((name, index) => { const option = new Option(`${index + 1}: ${name}`, index); imageSelect.add(option); });
  updateSidebar();
  renderImageList();
  renderAnnotationList();
  if (images.length) load(0); else setStatus('No images found.');
}
init().catch(error => setStatus(`Error: ${error.message}`));
</script>
</body>
</html>'''


def copy_all_annotations(paths: EditorPaths) -> None:
    paths.reviewed_annotations.mkdir(parents=True, exist_ok=True)
    for source in paths.annotations.glob("*.json"):
        target = paths.reviewed_annotations / source.name
        if not target.exists():
            shutil.copy2(source, target)
    paths.reviewed_render.mkdir(parents=True, exist_ok=True)


def safe_name(value: str, suffix: str) -> str:
    name = Path(unquote(value)).name
    if not name or Path(name).suffix.lower() != suffix:
        raise ValueError("invalid file name")
    return name


def render_review(paths: EditorPaths, name: str) -> None:
    image_path = paths.images / name
    annotation_path = paths.reviewed_annotations / f"{Path(name).stem}.json"
    if not image_path.exists() or not annotation_path.exists():
        raise FileNotFoundError(name)
    render_one(image_path, annotation_path, paths.reviewed_render / name)


class EditorHandler(BaseHTTPRequestHandler):
    paths: EditorPaths

    def send_bytes(self, payload: bytes, content_type: str, status=HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/":
                return self.send_bytes(HTML.encode(), "text/html; charset=utf-8")
            if parsed.path == "/api/images":
                names = sorted(path.name for path in self.paths.images.glob("*.png"))
                return self.send_bytes(json.dumps(names).encode(), "application/json")
            if parsed.path.startswith("/api/annotation/"):
                name = safe_name(parsed.path.rsplit("/", 1)[1], ".png")
                payload = (self.paths.reviewed_annotations / f"{Path(name).stem}.json").read_bytes()
                return self.send_bytes(payload, "application/json")
            if parsed.path.startswith("/images/"):
                name = safe_name(parsed.path.rsplit("/", 1)[1], ".png")
                payload = (self.paths.images / name).read_bytes()
                return self.send_bytes(payload, mimetypes.guess_type(name)[0] or "image/png")
            return self.send_bytes(b"Not found", "text/plain", HTTPStatus.NOT_FOUND)
        except (ValueError, FileNotFoundError):
            return self.send_bytes(b"Not found", "text/plain", HTTPStatus.NOT_FOUND)
        except Exception as error:
            return self.send_bytes(str(error).encode(), "text/plain", HTTPStatus.INTERNAL_SERVER_ERROR)

    def do_PUT(self):  # noqa: N802
        parsed = urlparse(self.path)
        if not parsed.path.startswith("/api/annotation/"):
            return self.send_bytes(b"Not found", "text/plain", HTTPStatus.NOT_FOUND)
        try:
            name = safe_name(parsed.path.rsplit("/", 1)[1], ".png")
            length = int(self.headers.get("Content-Length", "0"))
            data = json.loads(self.rfile.read(length))
            target = self.paths.reviewed_annotations / f"{Path(name).stem}.json"
            if not isinstance(data, dict) or not isinstance(data.get("annotation"), list):
                raise ValueError("annotation must be a list")
            if data.get("image_name") != name:
                raise ValueError("image_name must match request filename")
            current = json.loads(target.read_text())
            changed = current.get("annotation") != data["annotation"]
            if not changed:
                return self.send_bytes(b"{}", "application/json")
            current["annotation"] = data["annotation"]
            target.write_text(json.dumps(current, indent=1) + "\n")
            render_review(self.paths, name)
            return self.send_bytes(b"{}", "application/json")
        except (ValueError, FileNotFoundError, json.JSONDecodeError) as error:
            return self.send_bytes(str(error).encode(), "text/plain", HTTPStatus.BAD_REQUEST)
        except Exception as error:
            return self.send_bytes(str(error).encode(), "text/plain", HTTPStatus.INTERNAL_SERVER_ERROR)

    def log_message(self, format, *args):
        return


def make_handler(paths: EditorPaths):
    class ConfiguredEditorHandler(EditorHandler):
        pass

    ConfiguredEditorHandler.paths = paths
    return ConfiguredEditorHandler


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the EVERYFISH-COCO Annotation Editor")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=Path.cwd(),
        help="Dataset directory containing images/ and annotations/. Default: current directory.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    paths = EditorPaths.from_root(args.dataset_root)
    copy_all_annotations(paths)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(paths))
    print(f"Annotation editor: http://{args.host}:{args.port}")
    print(f"Dataset root: {paths.root}")
    print(f"Reviewed annotations: {paths.reviewed_annotations}")
    print(f"Reviewed renders: {paths.reviewed_render}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping editor.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

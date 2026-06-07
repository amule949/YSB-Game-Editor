
from __future__ import annotations

from typing import Any, Dict, List, Optional

from PyQt6.QtWidgets import QGraphicsPathItem, QGraphicsEllipseItem
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QPixmap, QPainterPath
from PyQt6.QtCore import Qt, QRectF, QPointF


class PageBrushEngine:
    """Runtime-only brush engine for the active page.

    This engine deliberately knows only the current viewer layer. It does not
    save project.json, does not encode PNG/NPY, and does not touch project-level
    state while the mouse is moving. A stroke creates one small patch-based
    history record on mouse release.
    """

    def __init__(self, viewer):
        self.viewer = viewer
        self.active = False
        self.target_item = None
        self.mode = None
        self.final_mode = False
        self.brush_size = 1
        self.color = QColor("#ffffff")
        self.last_pos = None
        self.preview_items: List[Any] = []
        self.preview_path: Optional[QPainterPath] = None
        self.preview_path_item: Optional[QGraphicsPathItem] = None
        self.paths: List[QPainterPath] = []
        self.dirty_scene_rect: Optional[QRectF] = None
        self.stroke_patches: List[Dict[str, Any]] = []
        # Backward compatibility name for older erase path code.
        self.erase_patches: List[Dict[str, Any]] = self.stroke_patches
        # Draw mode live-render buffer.  A stroke is recomposed from this base
        # pixmap on every mouse move so semi-transparent brushes do not create
        # bead-like overlaps at every segment endpoint.
        self.draw_base_pixmap: Optional[QPixmap] = None

    def clear_preview(self) -> None:
        scene = getattr(self.viewer, "scene", None)
        for item in list(self.preview_items):
            try:
                if item is not None and item.scene() is not None and scene is not None:
                    scene.removeItem(item)
            except Exception:
                pass
        self.preview_items = []

    def clear_runtime(self) -> None:
        self.clear_preview()
        self.active = False
        self.target_item = None
        self.mode = None
        self.final_mode = False
        self.last_pos = None
        self.preview_path = None
        self.preview_path_item = None
        self.paths = []
        self.dirty_scene_rect = None
        self.stroke_patches = []
        self.erase_patches = self.stroke_patches
        self.draw_base_pixmap = None

    def _view_update_scene_rect(self, rect: QRectF, *, force: bool = False) -> None:
        try:
            view_rect = self.viewer.mapFromScene(rect).boundingRect().adjusted(-6, -6, 6, 6)
            self.viewer.viewport().update(view_rect)
            if force:
                self.viewer.viewport().repaint(view_rect)
        except Exception:
            try:
                self.viewer.viewport().update()
                if force:
                    self.viewer.viewport().repaint()
            except Exception:
                pass

    def _add_dirty(self, rect: QRectF) -> None:
        if rect is None or rect.isNull():
            return
        self.dirty_scene_rect = QRectF(rect) if self.dirty_scene_rect is None else self.dirty_scene_rect.united(rect)

    def _segment_rect(self, a: QPointF, b: QPointF) -> QRectF:
        pad = max(2, int(self.brush_size or 1) + 6)
        return QRectF(a, b).normalized().adjusted(-pad, -pad, pad, pad)

    def _target_rect(self, scene_rect: QRectF):
        pix = self.target_item.pixmap() if self.target_item is not None else QPixmap()
        if pix.isNull():
            return pix, None
        try:
            local_rect = self.target_item.mapFromScene(scene_rect).boundingRect()
            qrect = local_rect.toAlignedRect().adjusted(-2, -2, 2, 2).intersected(pix.rect())
        except Exception:
            try:
                qrect = scene_rect.toAlignedRect().adjusted(-2, -2, 2, 2).intersected(pix.rect())
            except Exception:
                qrect = None
        if qrect is None or qrect.isEmpty():
            return pix, None
        return pix, qrect

    def _map_path_to_target(self, path: QPainterPath) -> QPainterPath:
        try:
            inv, ok = self.target_item.sceneTransform().inverted()
            if ok:
                return inv.map(path)
        except Exception:
            pass
        return path

    def _map_point_to_target(self, pt: QPointF) -> QPointF:
        try:
            return self.target_item.mapFromScene(pt)
        except Exception:
            return pt

    def _paint_segment_patch(self, a_scene: QPointF, b_scene: QPointF, *, erase: bool = False, force: bool = False) -> bool:
        """Apply one brush segment directly to the target pixmap using a dirty rect.

        Earlier draw mode used a temporary QGraphicsPath preview and only committed
        the real pixmap on mouse release. In practice that could show only the
        initial dot on some scenes/layers. This path mirrors the working eraser
        logic: draw the small dirty rect immediately, but store only that rect as
        a patch for Undo/Redo.
        """
        if self.target_item is None:
            return False
        a_scene = QPointF(a_scene)
        b_scene = QPointF(b_scene)
        # A zero-length drawLine is not reliably rendered by every backend, so
        # nudge the endpoint enough for the round cap to make a visible dot.
        if abs(a_scene.x() - b_scene.x()) < 0.001 and abs(a_scene.y() - b_scene.y()) < 0.001:
            b_scene = QPointF(a_scene.x() + 0.15, a_scene.y())
        scene_rect = self._segment_rect(a_scene, b_scene)
        pix, qrect = self._target_rect(scene_rect)
        if qrect is None:
            return False
        try:
            before = pix.copy(qrect)
            a_local = self._map_point_to_target(a_scene)
            b_local = self._map_point_to_target(b_scene)
            p = QPainter(pix)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            if erase:
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
                pen = QPen(Qt.GlobalColor.transparent, self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            else:
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
                pen = QPen(self.color, self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawLine(a_local, b_local)
            p.end()
            after = pix.copy(qrect)
            self.target_item.setPixmap(pix)
            self.target_item.update(QRectF(qrect))
            self.stroke_patches.append({"rect": qrect, "before": before, "after": after})
            self._add_dirty(scene_rect)
            self._view_update_scene_rect(scene_rect, force=force)
            return True
        except Exception:
            return False

    def _render_draw_live_to_target(self, *, force: bool = False) -> bool:
        """Render the current draw stroke directly onto the target pixmap.

        This is deliberately different from the old per-segment direct draw.
        We restore the dirty stroke area from the pixmap captured at stroke
        start, then draw the whole current path once.  That gives immediate
        feedback without semi-transparent endpoints accumulating into dotted
        beads.
        """
        if self.target_item is None or self.preview_path is None:
            return False
        base = self.draw_base_pixmap
        if base is None or base.isNull():
            return False
        pix = self.target_item.pixmap()
        if pix.isNull():
            return False
        dirty = self.dirty_scene_rect
        if dirty is None or dirty.isNull():
            dirty = self.preview_path.boundingRect().adjusted(-self.brush_size - 4, -self.brush_size - 4, self.brush_size + 4, self.brush_size + 4)
        pix_for_rect, qrect = self._target_rect(dirty)
        if qrect is None:
            return False
        try:
            p = QPainter(pix)
            # Rewind only the stroke's dirty rectangle to the pre-stroke base.
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            p.drawPixmap(qrect.topLeft(), base.copy(qrect))
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            p.setClipRect(qrect.adjusted(-2, -2, 2, 2))
            p.setPen(QPen(self.color, self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            p.drawPath(self._map_path_to_target(self.preview_path))
            p.end()
            self.target_item.setPixmap(pix)
            self.target_item.update(QRectF(qrect))
            try:
                scene_qrect = self.target_item.mapRectToScene(QRectF(qrect))
            except Exception:
                scene_qrect = QRectF(qrect)
            self._view_update_scene_rect(scene_qrect, force=force)
            return True
        except Exception:
            try:
                p.end()
            except Exception:
                pass
            return False

    def begin(self, target_item, start_pos, mode: str, color, brush_size: int, *, final_mode: bool = False) -> bool:
        self.clear_runtime()
        if target_item is None:
            return False
        self.target_item = target_item
        self.mode = str(mode or "draw")
        self.final_mode = bool(final_mode)
        self.brush_size = max(1, int(brush_size or 1))
        self.color = QColor(color) if not isinstance(color, QColor) else QColor(color)
        self.last_pos = QPointF(start_pos)
        self.active = True

        if self.mode == "draw":
            # Draw must be visible immediately, but direct per-segment painting
            # makes semi-transparent brushes look like a chain of dots. Capture
            # the pre-stroke layer once, then live-render the whole stroke from
            # that base on each move.
            try:
                self.draw_base_pixmap = target_item.pixmap().copy()
                self.preview_path = QPainterPath(self.last_pos)
                self.preview_path.lineTo(QPointF(self.last_pos.x() + 0.15, self.last_pos.y()))
                self.paths = [self.preview_path]
                r = self._segment_rect(self.last_pos, self.last_pos)
                self._add_dirty(r)
                self._render_draw_live_to_target(force=True)
            except Exception:
                pass
        elif self.mode == "erase":
            # Erase must affect the real layer immediately so removed pixels are
            # visible while dragging. Keep the working direct dirty-rect path.
            self._paint_segment_patch(self.last_pos, self.last_pos, erase=True, force=True)
        return True

    def extend(self, pos) -> bool:
        if not self.active or self.target_item is None:
            return False
        now = QPointF(pos)
        last = QPointF(self.last_pos or now)
        dx = now.x() - last.x()
        dy = now.y() - last.y()
        if (dx * dx + dy * dy) < 0.75:
            return True

        if self.mode == "draw":
            try:
                if self.preview_path is None:
                    self.preview_path = QPainterPath(last)
                self.preview_path.lineTo(now)
                r = self._segment_rect(last, now)
                self._add_dirty(r)
                self._render_draw_live_to_target(force=True)
            except Exception:
                pass
        else:
            self._paint_segment_patch(last, now, erase=True, force=False)
        self.last_pos = now
        return True

    def _kind(self) -> Optional[str]:
        try:
            if self.target_item is self.viewer.final_paint_item or self.target_item is self.viewer.final_paint_above_item:
                return "final_paint"
            if self.target_item is self.viewer.user_mask_item:
                return "mask"
        except Exception:
            pass
        return None

    def _sync_cached_images(self) -> None:
        try:
            pix = self.target_item.pixmap()
            if self.target_item is self.viewer.final_paint_above_item:
                self.viewer.final_paint_above_img = pix.toImage()
            elif self.target_item is self.viewer.final_paint_item:
                self.viewer.final_paint_img = pix.toImage()
            elif self.target_item is self.viewer.user_mask_item:
                self.viewer.user_mask_img = pix.toImage()
        except Exception:
            pass

    def commit(self) -> bool:
        if not self.active or self.target_item is None:
            self.clear_runtime()
            return False
        target = self.target_item
        mode = self.mode
        kind = self._kind()
        record = None
        try:
            if mode == "draw":
                pix = target.pixmap()
                if pix.isNull():
                    return False
                dirty = self.dirty_scene_rect
                if dirty is None:
                    dirty = self._segment_rect(QPointF(self.last_pos or QPointF(0, 0)), QPointF(self.last_pos or QPointF(0, 0)))
                pix, qrect = self._target_rect(dirty)
                if qrect is None:
                    return False
                base = self.draw_base_pixmap
                before = base.copy(qrect) if base is not None and not base.isNull() else pix.copy(qrect)
                # The live-render path has already drawn the final stroke onto
                # the target pixmap. Commit only records the patch; it does not
                # paint a second time.
                after = pix.copy(qrect)
                record = {"_brush_record": True, "target_item": target, "kind": kind, "patches": [{"rect": qrect, "before": before, "after": after}]}
                try:
                    scene_qrect = target.mapRectToScene(QRectF(qrect))
                except Exception:
                    scene_qrect = QRectF(qrect)
                self._view_update_scene_rect(scene_qrect, force=False)
            else:
                if self.stroke_patches:
                    record = {"_brush_record": True, "target_item": target, "kind": kind, "patches": list(self.stroke_patches)}
            if record is not None:
                reason = "최종 페인팅" if kind == "final_paint" else "마스크 브러시"
                try:
                    if hasattr(self.viewer.main, "undo_push_paint_record"):
                        self.viewer.main.undo_push_paint_record(self.viewer, record, kind=kind, reason=reason, max_history=80)
                    else:
                        self.viewer.history.append(record)
                        if len(self.viewer.history) > 80:
                            self.viewer.history.pop(0)
                        try:
                            self.viewer.redo_history.clear()
                        except Exception:
                            pass
                        if hasattr(self.viewer.main, "undo_push_page"):
                            self.viewer.main.undo_push_page({
                                "reason": reason,
                                "page_idx": int(getattr(self.viewer.main, "idx", 0) or 0),
                                "mode": int(self.viewer.main.cb_mode.currentIndex()) if hasattr(self.viewer.main, "cb_mode") else 0,
                                "paint_history": True,
                                "_undo_scope": "page",
                            }, page_idx=int(getattr(self.viewer.main, "idx", 0) or 0))
                except Exception:
                    pass
                self._sync_cached_images()
                return True
            return False
        finally:
            self.clear_runtime()

    def apply_record(self, record: Dict[str, Any], direction: str = "undo") -> Optional[str]:
        if not isinstance(record, dict) or not record.get("_brush_record"):
            return None
        target = record.get("target_item")
        patches = record.get("patches") or []
        if target is None or not patches:
            return None
        pix = target.pixmap()
        if pix.isNull():
            return None
        key = "before" if direction == "undo" else "after"
        ordered = list(reversed(patches)) if direction == "undo" else list(patches)
        try:
            p = QPainter(pix)
            p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
            dirty = None
            for patch in ordered:
                rect = patch.get("rect")
                img = patch.get(key)
                if rect is None or img is None:
                    continue
                p.drawPixmap(rect.topLeft(), img)
                rf = QRectF(rect)
                dirty = rf if dirty is None else dirty.united(rf)
            p.end()
            target.setPixmap(pix)
            if dirty is not None:
                target.update(dirty)
                try:
                    scene_dirty = target.mapRectToScene(dirty)
                except Exception:
                    scene_dirty = dirty
                self._view_update_scene_rect(scene_dirty, force=False)
            self.target_item = target
            self._sync_cached_images()
            return str(record.get("kind") or self._kind() or "paint")
        except Exception:
            return None

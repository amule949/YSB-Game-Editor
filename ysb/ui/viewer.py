import copy
import math
import numpy as np
import cv2
from PyQt6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsTextItem, QInputDialog, QGraphicsPathItem, QGraphicsItem, QApplication
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QImage, QPixmap, QFont, QPainterPath
from PyQt6.QtCore import Qt, QRect, QRectF, QTimer, QPointF

from ysb.engine.graphics_items import ToggleBoxItem, TypesettingItem
from ysb.core.brush_engine import PageBrushEngine


class MuleImageViewer(QGraphicsView):
    # 작업 화면 보조 UI 기준 해상도.
    # 현재 선/핸들 크기를 1086x1449 기준값으로 보고, 더 큰 이미지에서는 비례 확대한다.
    GUIDE_BASE_W = 1086.0
    GUIDE_BASE_H = 1449.0
    GUIDE_SCALE_MAX = 6.0

    def __init__(self, main_window):
        super().__init__()
        self.main = main_window
        self.scene = QGraphicsScene()
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        try:
            self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontSavePainterState, True)
            self.setOptimizationFlag(QGraphicsView.OptimizationFlag.DontAdjustForAntialiasing, True)
            # 텍스트/변형/Undo 복원은 정확한 전체 repaint가 우선이다.
            # MinimalViewportUpdate/CacheBackground는 일부 갱신 잔상을 만들 수 있어 정석 모드로 둔다.
            self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
            self.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)
        except Exception:
            pass
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setBackgroundBrush(QBrush(QColor("#0B0C0E")))

        self.draw_mode = None
        self.user_mask_item = None
        self.user_mask_img = None
        self.final_paint_item = None
        self.final_paint_above_item = None
        self.final_paint_img = None
        self.final_paint_above_img = None
        self.last_pt = None
        self.brush_size = 25
        self.mask_color = QColor(255, 0, 0, 100)
        self.history = []
        self.redo_history = []
        self.brush_engine = PageBrushEngine(self)
        try:
            if hasattr(self.main, "undo_bind_paint_viewer"):
                self.main.undo_bind_paint_viewer(self)
            elif hasattr(self.main, "get_undo_manager"):
                mgr = self.main.get_undo_manager()
                if mgr is not None:
                    mgr.bind_paint_viewer(self)
        except Exception:
            pass
        self._suppress_view_history = False
        self._scrollbar_view_undo_active = False
        # Scrollbar actions are page-local view operations.  They must be recorded
        # through the MainWindow/ViewEngine timeline, but never throw if the host
        # window is still booting or temporarily suppressing view history during
        # restore/Undo.
        try:
            self.horizontalScrollBar().actionTriggered.connect(lambda *_: self._begin_scroll_view_undo())
            self.verticalScrollBar().actionTriggered.connect(lambda *_: self._begin_scroll_view_undo())
            self.horizontalScrollBar().valueChanged.connect(lambda *_: self._schedule_scroll_view_undo_finish())
            self.verticalScrollBar().valueChanged.connect(lambda *_: self._schedule_scroll_view_undo_finish())
        except Exception:
            pass
        self.is_mask_painting = False
        self.magic_preview_items = []
        self.paste_preview_items = []
        self._active_transform_item = None
        # Small pixmap cache for same-page tab switching.  Source/final bases are
        # expensive to convert repeatedly on large pages, so keep the latest few
        # keyed base pixmaps and reuse them while the page/content key matches.
        self._layer_base_pixmap_cache = {}
        self._layer_base_pixmap_cache_order = []
        self._layer_base_pixmap_cache_order = []
        self._view_pan_undo_key = None
        self._view_pan_start_state = None
        self._paint_undo_key = None
        self._stroke_preview_item = None
        self._stroke_preview_items = []
        self._stroke_preview_path = None
        self._stroke_preview_paths = []
        self._stroke_preview_last_pos = None
        self._stroke_preview_segment_count = 0
        self._stroke_preview_target = None
        self._stroke_preview_final_mode = False
        self._stroke_preview_color = None
        self._stroke_preview_dirty_rect = None
        self.mask_wrap_shape = "rect"
        self.mask_wrap_start = None
        self.mask_wrap_points = []
        self.mask_wrap_preview_item = None
        self.is_mask_wrapping = False

        self.mask_cut_shape = "rect"
        self.mask_cut_start = None
        self.mask_cut_points = []
        self.mask_cut_preview_item = None
        self.is_mask_cutting = False

        self.ocr_region_shape = "rect"
        self.ocr_region_start = None
        self.ocr_region_points = []
        self.ocr_region_preview_item = None
        self.ocr_region_overlay_items = []
        self.is_ocr_region_drawing = False

        self.quick_ocr_start = None
        self.quick_ocr_preview_item = None
        self.is_quick_ocr_drawing = False
        self.quick_ocr_current_rect_norm = None
        self.quick_ocr_revision = 0
        self.quick_ocr_last_requested_revision = -1
        self.quick_ocr_hold_timer = QTimer(self)
        self.quick_ocr_hold_timer.setSingleShot(True)
        self.quick_ocr_hold_timer.timeout.connect(self._trigger_quick_ocr_if_still_holding)

        self.area_paint_shape = "rect"
        self.area_paint_start = None
        self.area_paint_points = []
        self.area_paint_preview_item = None
        self.is_area_painting = False
        self._area_paint_undo_key = None

        self.raster_erase_start = None
        self.raster_erase_preview_item = None
        self.is_raster_erasing = False
        self.is_raster_text_brush_erasing = False

        # 객체화 텍스트는 페인팅 레이어/뷰 드래그 모드에 클릭이 막힐 수 있어
        # QGraphicsItem 이벤트에 맡기지 않고 View 레벨에서 직접 hit-test/드래그한다.
        self._raster_view_drag_item = None
        self._raster_view_drag_scene_press = None
        self._raster_view_drag_item_press = None
        self._raster_view_drag_old_offsets = None
        self._raster_view_drag_moved = False

        # VIEW_ZOOM_PAN_FASTPATH_FIX:
        # 확대/스크롤/팬 조작 중에는 고해상도 배경/오버레이를 매 프레임
        # 고품질로 다시 그리지 않도록 렌더 힌트와 viewport update mode를
        # 잠깐 가볍게 낮추고, 조작이 멈춘 뒤 원래 품질로 복원한다.
        self._view_interaction_fast_path_active = False
        self._view_interaction_fast_path_finish_pending = False
        self._view_interaction_fast_path_reason = None
        self._view_interaction_fast_path_old_hints = None
        self._view_interaction_fast_path_old_viewport_mode = None
        self._view_interaction_fast_path_old_cache_mode = None
        self._view_interaction_fast_path_timer = QTimer(self)
        self._view_interaction_fast_path_timer.setSingleShot(True)
        self._view_interaction_fast_path_timer.timeout.connect(self._finish_view_interaction_fast_path)
        try:
            self.horizontalScrollBar().valueChanged.connect(lambda *_: self._begin_view_interaction_fast_path('scroll', delay_ms=160))
            self.verticalScrollBar().valueChanged.connect(lambda *_: self._begin_view_interaction_fast_path('scroll', delay_ms=160))
        except Exception:
            pass

    def ui_visual_scale(self):
        """Return a scene-pixel scale for non-output guide UI.

        This affects only editor overlays such as analysis boxes, OCR regions,
        magic-wand outlines, selection rectangles and preview borders.
        It must not be used for real text stroke / mask / paint output.
        """
        try:
            rect = self.scene.sceneRect()
            w = float(rect.width())
            h = float(rect.height())
            if w <= 1 or h <= 1:
                base_item = getattr(self, "_layer_base_item", None)
                if base_item is not None and not base_item.pixmap().isNull():
                    w = float(base_item.pixmap().width())
                    h = float(base_item.pixmap().height())
            if w <= 1 or h <= 1:
                items_rect = self.scene.itemsBoundingRect()
                w = float(items_rect.width())
                h = float(items_rect.height())
            scale = max(w / self.GUIDE_BASE_W, h / self.GUIDE_BASE_H)
            return max(1.0, min(float(scale), self.GUIDE_SCALE_MAX))
        except Exception:
            return 1.0

    def ui_pen_width(self, base=2.0, minimum=1.0):
        try:
            return max(float(minimum), float(base) * self.ui_visual_scale())
        except Exception:
            return float(base or minimum or 1.0)

    def ui_handle_size(self, base=14.0, minimum=8.0):
        try:
            return max(float(minimum), float(base) * self.ui_visual_scale())
        except Exception:
            return float(base or minimum or 8.0)

    def ui_font_size(self, base=11.0, minimum=8.0):
        try:
            return max(int(minimum), int(round(float(base) * self.ui_visual_scale())))
        except Exception:
            return int(base or minimum or 8)

    def ui_pad(self, base=4.0, minimum=2.0):
        try:
            return max(float(minimum), float(base) * self.ui_visual_scale())
        except Exception:
            return float(base or minimum or 2.0)

    def _view_fast_path_log(self, event_name, **payload):
        try:
            main = getattr(self, "main", None)
            if main is not None and hasattr(main, "audit_boundary_event"):
                main.audit_boundary_event(event_name, **payload)
        except Exception:
            pass

    def _begin_view_interaction_fast_path(self, reason='view', delay_ms=180):
        """Temporarily use cheap render settings while zooming/scrolling/panning.

        This is intentionally view-only.  It does not change page data, Undo payloads,
        mask caches, text data or project state.  It only reduces expensive repaint
        cost while the user is actively moving the view over a high-resolution page.
        """
        try:
            delay_ms = int(delay_ms or 180)
        except Exception:
            delay_ms = 180
        delay_ms = max(80, min(delay_ms, 800))

        try:
            main = getattr(self, "main", None)
            if main is not None and getattr(main, "_text_scene_mutation_lock", False):
                self._view_interaction_fast_path_finish_pending = True
                self._view_fast_path_log(
                    'TEXT_SCENE_MUTATION_TIMER_GUARD_BLOCKED_VIEW_FASTPATH',
                    action='begin',
                    reason=str(reason or 'view'),
                    throttle_ms=100,
                )
                return
        except Exception:
            pass

        if not getattr(self, '_view_interaction_fast_path_active', False):
            self._view_interaction_fast_path_active = True
            self._view_interaction_fast_path_reason = str(reason or 'view')
            try:
                self._view_interaction_fast_path_old_hints = self.renderHints()
            except Exception:
                self._view_interaction_fast_path_old_hints = None
            try:
                self._view_interaction_fast_path_old_viewport_mode = self.viewportUpdateMode()
            except Exception:
                self._view_interaction_fast_path_old_viewport_mode = None
            try:
                self._view_interaction_fast_path_old_cache_mode = self.cacheMode()
            except Exception:
                self._view_interaction_fast_path_old_cache_mode = None

            try:
                # 확대/스크롤 중에는 품질보다 응답성이 우선이다.  정지 후 원복한다.
                self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
                self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
                self.setRenderHint(QPainter.RenderHint.TextAntialiasing, False)
            except Exception:
                pass
            try:
                # 기존 기본값이 FullViewportUpdate인 경우 고해상도 화면 전체 repaint가 무겁다.
                # 조작 중에는 변경 영역 중심으로 줄이고, 종료 시 원래 모드로 복원한다.
                self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
            except Exception:
                pass
            try:
                # 배경 brush/scene background는 이동 중 재사용되도록 시도한다.
                # 문제 발생 시 종료 시점에 원래 CacheNone 등으로 복구된다.
                self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
            except Exception:
                pass
            self._view_fast_path_log(
                'VIEW_FAST_PATH_BEGIN',
                reason=str(reason or 'view'),
                delay_ms=delay_ms,
                smooth_pixmap=False,
                antialiasing=False,
                viewport='BoundingRectViewportUpdate',
                cache='CacheBackground',
            )
        else:
            # 연속 휠/스크롤 입력은 같은 fast path burst로 묶는다.
            self._view_interaction_fast_path_reason = str(reason or getattr(self, '_view_interaction_fast_path_reason', None) or 'view')

        try:
            self._view_interaction_fast_path_timer.start(delay_ms)
        except Exception:
            pass

    def _finish_view_interaction_fast_path(self, force=False):
        if not getattr(self, '_view_interaction_fast_path_active', False):
            return
        reason = getattr(self, '_view_interaction_fast_path_reason', None) or 'view'
        try:
            main = getattr(self, "main", None)
            if main is not None and getattr(main, "_text_scene_mutation_lock", False):
                self._view_interaction_fast_path_finish_pending = True
                try:
                    timer = getattr(self, "_view_interaction_fast_path_timer", None)
                    if timer is not None and timer.isActive():
                        timer.stop()
                except Exception:
                    pass
                self._view_fast_path_log(
                    'TEXT_SCENE_MUTATION_TIMER_GUARD_BLOCKED_VIEW_FASTPATH',
                    action='finish',
                    reason=str(reason),
                    throttle_ms=100,
                )
                return
        except Exception:
            pass
        try:
            old_hints = getattr(self, '_view_interaction_fast_path_old_hints', None)
            if old_hints is not None:
                self.setRenderHints(old_hints)
            else:
                self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        except Exception:
            pass
        try:
            old_mode = getattr(self, '_view_interaction_fast_path_old_viewport_mode', None)
            if old_mode is not None:
                self.setViewportUpdateMode(old_mode)
        except Exception:
            pass
        try:
            old_cache = getattr(self, '_view_interaction_fast_path_old_cache_mode', None)
            if old_cache is not None:
                self.setCacheMode(old_cache)
            else:
                self.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)
        except Exception:
            pass

        self._view_interaction_fast_path_active = False
        self._view_interaction_fast_path_reason = None
        self._view_interaction_fast_path_old_hints = None
        self._view_interaction_fast_path_old_viewport_mode = None
        self._view_interaction_fast_path_old_cache_mode = None
        try:
            self.viewport().update()
        except Exception:
            pass
        self._view_fast_path_log('VIEW_FAST_PATH_END', reason=str(reason))

    def fit_image_to_current_viewport(self):
        """현재 QGraphicsView 뷰포트 크기에 맞춰 이미지를 최대 크기로 맞춘다.

        마우스 휠 버튼(가운데 버튼) 더블클릭용. 현재 창/분할 영역 크기를 기준으로
        scene 안의 실제 이미지/작업물 영역을 KeepAspectRatio로 맞춘다.
        """
        try:
            rect = self.scene.itemsBoundingRect()
            if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
                rect = self.scene.sceneRect()
            if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
                return False

            try:
                if not self._view_undo_is_suppressed() and hasattr(self.main, "begin_page_view_undo"):
                    self.main.begin_page_view_undo("화면 확대/축소")
            except Exception:
                pass

            self._begin_view_interaction_fast_path('fit', delay_ms=140)
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)

            try:
                if hasattr(self.main, "remember_current_view_state"):
                    self.main.remember_current_view_state()
                if hasattr(self.main, "schedule_source_compare_sync"):
                    self.main.schedule_source_compare_sync(180)
            except Exception:
                pass
            try:
                if not self._view_undo_is_suppressed() and hasattr(self.main, "finish_page_view_undo"):
                    self.main.finish_page_view_undo(force=True)
            except Exception:
                pass
            return True
        except Exception:
            return False

    def _active_transform_item_obj(self):
        active = self.main.current_transform_data_item() if hasattr(self.main, 'current_transform_data_item') else None
        if active is None:
            return None
        active_id = active.get('id')
        for item in self.scene.items():
            if isinstance(item, TypesettingItem) and not getattr(item, "is_paste_preview", False):
                if item.data is active or item.data.get('id') == active_id:
                    return item
        return None

    def _scene_text_item_at(self, scene_pos):
        active_item = self._active_transform_item_obj()
        if active_item is not None:
            try:
                local = active_item.mapFromScene(scene_pos)
                action = active_item.transform_action_at(local) if active_item.data.get('_transform_mode', False) else None
                if not action and active_item.data.get('_skew_mode', False):
                    action = active_item.skew_action_at(local)
                if not action and active_item.data.get('_trapezoid_mode', False):
                    action = active_item.trapezoid_action_at(local)
                if not action and active_item.data.get('_arc_mode', False):
                    action = active_item.arc_action_at(local)
                if action or active_item.shape().contains(local):
                    return active_item
            except Exception:
                pass
        for item in self.scene.items(scene_pos):
            if isinstance(item, TypesettingItem) and not getattr(item, "is_paste_preview", False):
                return item
        return None

    def _final_text_hit_debug_enabled(self):
        try:
            return bool(getattr(self.main, "debug_text_hit_test", False) or getattr(self, "debug_text_hit_test", False))
        except Exception:
            return False

    def _log_final_text_hit_debug(self, message):
        if not self._final_text_hit_debug_enabled():
            return
        try:
            if hasattr(self.main, "log"):
                self.main.log(message)
        except Exception:
            pass

    def _is_final_move_mode(self):
        try:
            return (
                getattr(self.main, "cb_mode", None) is not None
                and self.main.cb_mode.currentIndex() == 4
                and self.draw_mode is None
            )
        except Exception:
            return False

    def _raster_text_alpha_hit(self, item, scene_pos, radius=3):
        """객체화 텍스트의 실제 보이는 픽셀을 기준으로 hit-test한다.

        itemAt()/scene.items(scene_pos)는 최상단 페인팅 레이어나 아이템 shape 때문에
        실제 글자 클릭과 다르게 동작할 수 있다. 그래서 객체화 텍스트는 알파 채널을
        직접 검사한다. 얇은 획/안티앨리어싱을 고려해 작은 반경도 같이 본다.
        """
        if item is None or not getattr(item, "data", {}).get('rasterized_text'):
            return False
        img = getattr(item, '_raster_image', None)
        rect = getattr(item, '_raster_rect', QRectF())
        if img is None or img.isNull() or rect.isNull():
            return False
        try:
            local = item.mapFromScene(QPointF(scene_pos))
        except Exception:
            return False
        if not rect.adjusted(-radius, -radius, radius, radius).contains(local):
            return False
        w = img.width()
        h = img.height()
        cx = int(round(local.x()))
        cy = int(round(local.y()))
        r = max(0, int(radius or 0))
        for yy in range(max(0, cy - r), min(h - 1, cy + r) + 1):
            for xx in range(max(0, cx - r), min(w - 1, cx + r) + 1):
                try:
                    if img.pixelColor(xx, yy).alpha() > 8:
                        return True
                except Exception:
                    return False
        return False

    def _raster_text_rect_hit(self, item, scene_pos):
        if item is None or not getattr(item, "data", {}).get('rasterized_text'):
            return False
        rect = getattr(item, '_raster_rect', QRectF())
        if rect.isNull():
            return False
        try:
            return rect.contains(item.mapFromScene(QPointF(scene_pos)))
        except Exception:
            return False

    def _raster_text_item_at(self, scene_pos):
        """객체화 텍스트를 페인팅 레이어보다 먼저 직접 찾는다.

        기존 scene.items(scene_pos) / itemAt() 경로는 최종 페인팅 레이어, 배경 픽스맵,
        ScrollHandDrag 상태에 막혀 객체화 텍스트가 선택되지 않을 수 있다.
        그래서 모든 TypesettingItem을 직접 검사한다.
        """
        raster_items = []
        try:
            for item in self.scene.items():
                if isinstance(item, TypesettingItem) and not getattr(item, "is_paste_preview", False):
                    if bool(getattr(item, "data", {}).get('rasterized_text')):
                        raster_items.append(item)
        except Exception:
            return None

        # 이미 선택된 객체는 투명 영역 안쪽을 눌러도 다시 잡히게 한다.
        for item in raster_items:
            try:
                if item.isSelected() and self._raster_text_rect_hit(item, scene_pos):
                    return item
            except Exception:
                pass

        # 우선순위 1: 실제 보이는 알파 픽셀.
        for item in raster_items:
            if self._raster_text_alpha_hit(item, scene_pos, radius=3):
                return item

        # 우선순위 2: 투명 여백 포함 래스터 박스.
        # 얇은 글자나 완전히 지워진 객체도 선택/이동할 수 있게 마지막 폴백으로 둔다.
        for item in raster_items:
            if self._raster_text_rect_hit(item, scene_pos):
                return item
        return None

    def _begin_raster_text_view_drag(self, item, scene_pos, event):
        if item is None:
            return False
        try:
            if not (event.modifiers() & Qt.KeyboardModifier.ControlModifier):
                for selected in list(self.scene.selectedItems()):
                    if selected is not item:
                        selected.setSelected(False)
            item.setSelected(True)
            if hasattr(self.main, "on_scene_selection_changed"):
                self.main.on_scene_selection_changed()
        except Exception:
            pass

        self._raster_view_drag_item = item
        self._raster_view_drag_scene_press = QPointF(scene_pos)
        self._raster_view_drag_item_press = QPointF(item.pos())
        try:
            self._raster_view_drag_old_offsets = (
                int(item.data.get('x_off', 0) or 0),
                int(item.data.get('y_off', 0) or 0),
            )
        except Exception:
            self._raster_view_drag_old_offsets = (0, 0)
        self._raster_view_drag_moved = False
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self._log_final_text_hit_debug(f"🔎 객체 텍스트 선택: ID {item.data.get('id')}")
        return True

    def _finish_raster_text_view_drag(self):
        item = self._raster_view_drag_item
        if item is None:
            return
        old_offsets = self._raster_view_drag_old_offsets or (
            int(item.data.get('x_off', 0) or 0),
            int(item.data.get('y_off', 0) or 0),
        )
        self._raster_view_drag_item = None
        self._raster_view_drag_scene_press = None
        self._raster_view_drag_item_press = None
        self._raster_view_drag_old_offsets = None
        self._raster_view_drag_moved = False
        self.unsetCursor()

        try:
            rect = list(item.data.get('rect') or [0, 0, 1, 1])
            while len(rect) < 4:
                rect.append(1)
            new_x_off = int(round(float(item.pos().x()) - float(rect[0])))
            new_y_off = int(round(float(item.pos().y()) - float(rect[1])))
        except Exception:
            return

        old_x_off, old_y_off = old_offsets
        if new_x_off == old_x_off and new_y_off == old_y_off:
            return

        before_geometry = {
            "x_off": {"exists": 'x_off' in item.data, "value": old_x_off},
            "y_off": {"exists": 'y_off' in item.data, "value": old_y_off},
        }
        use_command_undo = bool(hasattr(self.main, 'push_text_geometry_command'))
        if not use_command_undo:
            try:
                if hasattr(self.main, 'undo_text_checkpoint'):
                    self.main.undo_text_checkpoint('텍스트 객체 이동')
            except Exception:
                pass

        item.data['x_off'] = new_x_off
        item.data['y_off'] = new_y_off
        try:
            item.update()
        except Exception:
            pass

        if use_command_undo:
            try:
                self.main.push_text_geometry_command(
                    item.data,
                    before_values=before_geometry,
                    after_values={
                        "x_off": {"exists": True, "value": new_x_off},
                        "y_off": {"exists": True, "value": new_y_off},
                    },
                    reason='텍스트 객체 이동',
                    fields=['x_off', 'y_off'],
                    component_type='text_position',
                )
            except Exception:
                pass

        try:
            if hasattr(self.main, 'sync_final_text_scene_to_data'):
                self.main.sync_final_text_scene_to_data()
        except Exception:
            pass

        if getattr(item, 'update_cb', None):
            try:
                item.update_cb(f"📍 텍스트 객체 이동됨 (ID: {item.data.get('id')})")
                return
            except Exception:
                pass

        try:
            if hasattr(self.main, 'schedule_deferred_auto_save_project'):
                self.main.schedule_deferred_auto_save_project()
            elif hasattr(self.main, 'auto_save_project'):
                self.main.auto_save_project()
        except Exception:
            pass


    def _cursor_for_transform_action(self, action):
        if action == 'rotate':
            return Qt.CursorShape.CrossCursor
        if action == 'move':
            return Qt.CursorShape.SizeAllCursor
        if action in ('left', 'right'):
            return Qt.CursorShape.SizeHorCursor
        if action in ('top', 'bottom'):
            return Qt.CursorShape.SizeVerCursor
        if action in ('top_left', 'bottom_right'):
            return Qt.CursorShape.SizeFDiagCursor
        if action in ('top_right', 'bottom_left'):
            return Qt.CursorShape.SizeBDiagCursor
        return Qt.CursorShape.ArrowCursor

    def _clear_stroke_preview(self):
        # 실시간 브러시 미리보기는 여러 개의 작은 path chunk로 나눈다.
        # 하나의 큰 QPainterPath를 매 mouseMove마다 setPath하면 스트로크가 길어질수록 O(n) 복사가 반복되어 느려진다.
        items = []
        try:
            items.extend(list(getattr(self, "_stroke_preview_items", []) or []))
        except Exception:
            pass
        try:
            if self._stroke_preview_item is not None and self._stroke_preview_item not in items:
                items.append(self._stroke_preview_item)
        except Exception:
            pass
        for item in items:
            try:
                if item is not None and item.scene() is not None:
                    self.scene.removeItem(item)
            except Exception:
                pass
        self._stroke_preview_item = None
        self._stroke_preview_items = []
        self._stroke_preview_path = None
        self._stroke_preview_paths = []
        self._stroke_preview_last_pos = None
        self._stroke_preview_segment_count = 0
        self._stroke_preview_target = None
        self._stroke_preview_dirty_rect = None
        self._stroke_preview_color = None
        self._stroke_preview_final_mode = False

    def _make_stroke_preview_item(self, path, color, final_mode=False):
        item = QGraphicsPathItem(path)
        item.setPen(QPen(color, self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        item.setBrush(Qt.BrushStyle.NoBrush)
        # 최종결과/마스크/가이드 전부 위에 떠야 "그리는 중" 체감이 바로 난다.
        item.setZValue(5000 if final_mode else 4900)
        item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        try:
            item.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        except Exception:
            pass
        self.scene.addItem(item)
        return item

    def _start_stroke_preview(self, target_item, start_pos, color, final_mode=False):
        self._clear_stroke_preview()
        self._stroke_preview_target = target_item
        self._stroke_preview_final_mode = bool(final_mode)
        self._stroke_preview_color = QColor(color) if isinstance(color, QColor) else color
        path = QPainterPath(start_pos)
        # 한 점짜리 path는 실제로 그릴 선분이 없어 누른 직후 브러시가 보이지 않을 수 있다.
        # 아주 짧은 선분을 넣어 round-cap 점이 즉시 보이게 한다.
        path.lineTo(QPointF(start_pos) + QPointF(0.15, 0.0))
        self._stroke_preview_path = path
        self._stroke_preview_paths = [path]
        self._stroke_preview_last_pos = QPointF(start_pos)
        self._stroke_preview_segment_count = 0
        pad = max(2, int(self.brush_size or 1) + 4)
        self._stroke_preview_dirty_rect = QRectF(start_pos, start_pos).normalized().adjusted(-pad, -pad, pad, pad)
        try:
            item = self._make_stroke_preview_item(path, color, final_mode=final_mode)
            self._stroke_preview_item = item
            self._stroke_preview_items = [item]
            try:
                _r = self.mapFromScene(self._stroke_preview_dirty_rect).boundingRect().adjusted(-4, -4, 4, 4)
                self.viewport().update(_r)
                self.viewport().repaint(_r)
            except Exception:
                self.viewport().update()
        except Exception:
            self._stroke_preview_item = None

    def _extend_stroke_preview(self, pos):
        if self._stroke_preview_path is None:
            return False
        try:
            now = QPointF(pos)
            last = QPointF(getattr(self, "_stroke_preview_last_pos", now) or now)
            # 너무 촘촘한 mouseMove는 같은 선분으로 보고 생략한다. 화면 반응은 유지하면서 path 폭증을 막는다.
            dx = now.x() - last.x()
            dy = now.y() - last.y()
            if (dx * dx + dy * dy) < 1.5:
                return True
            # 긴 스트로크는 작은 path chunk로 나눈다. setPath 비용이 누적되지 않게 하는 핵심.
            if int(getattr(self, "_stroke_preview_segment_count", 0) or 0) >= 24:
                new_path = QPainterPath(last)
                self._stroke_preview_path = new_path
                self._stroke_preview_paths.append(new_path)
                self._stroke_preview_segment_count = 0
                item = self._make_stroke_preview_item(new_path, self._stroke_preview_color, final_mode=self._stroke_preview_final_mode)
                self._stroke_preview_item = item
                self._stroke_preview_items.append(item)
            self._stroke_preview_path.lineTo(now)
            if self._stroke_preview_item is not None:
                self._stroke_preview_item.setPath(self._stroke_preview_path)
            self._stroke_preview_segment_count += 1
            self._stroke_preview_last_pos = now
            pad = max(2, int(self.brush_size or 1) + 4)
            r = QRectF(last, now).normalized().adjusted(-pad, -pad, pad, pad)
            self._stroke_preview_dirty_rect = self._stroke_preview_dirty_rect.united(r) if self._stroke_preview_dirty_rect is not None else r
            try:
                _r = self.mapFromScene(r).boundingRect().adjusted(-4, -4, 4, 4)
                self.viewport().update(_r)
                self.viewport().repaint(_r)
            except Exception:
                self.viewport().update()
            return True
        except Exception:
            return False

    def _commit_stroke_preview_to_layer(self):
        target_item = self._stroke_preview_target
        paths = list(getattr(self, "_stroke_preview_paths", []) or [])
        if target_item is None or not paths:
            self._clear_stroke_preview()
            return False
        try:
            pix = target_item.pixmap()
            pix_rect = pix.rect()
            dirty = self._stroke_preview_dirty_rect
            if dirty is None:
                for path in paths:
                    dirty = path.boundingRect() if dirty is None else dirty.united(path.boundingRect())
            qrect = dirty.toAlignedRect().adjusted(-2, -2, 2, 2).intersected(pix_rect)
            if qrect.isEmpty():
                self._clear_stroke_preview()
                return False
            before_patch = pix.copy(qrect)
            painter = QPainter(pix)
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            painter.setPen(QPen(self._stroke_preview_color, self.brush_size, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
            for path in paths:
                painter.drawPath(path)
            painter.end()
            target_item.setPixmap(pix)
            target_item.update(QRectF(qrect))
            try:
                self.viewport().update(self.mapFromScene(QRectF(qrect)).boundingRect().adjusted(-4, -4, 4, 4))
            except Exception:
                self.viewport().update()
            if target_item is self.final_paint_above_item:
                self.final_paint_above_img = pix.toImage()
            elif target_item is self.final_paint_item:
                self.final_paint_img = pix.toImage()
            elif target_item is self.user_mask_item:
                self.user_mask_img = pix.toImage()
            rec = {"target_item": target_item, "dirty_rect": qrect, "patch": before_patch}
            kind = "final_paint" if self._stroke_preview_final_mode else "mask"
            reason = "최종 페인팅" if kind == "final_paint" else "마스크 브러시"
            try:
                if hasattr(self.main, "undo_push_paint_record"):
                    self.main.undo_push_paint_record(self, rec, kind=kind, reason=reason, max_history=40)
                else:
                    self.history.append(rec)
                    if len(self.history) > 40:
                        self.history.pop(0)
                    try:
                        self.redo_history.clear()
                    except Exception:
                        pass
                    self._append_paint_history_undo_marker(kind, reason)
            except Exception:
                pass
            return True
        except Exception:
            return False
        finally:
            self._clear_stroke_preview()

    def _view_undo_enabled(self):
        """Return whether pan/zoom view changes should be recorded to Undo.

        View navigation Undo is important for real editing, so the default is ON.
        Continuous wheel/scroll movement is still coalesced by MainWindow so one
        burst becomes one Undo step instead of many tiny records.
        """
        try:
            main = getattr(self, "main", None)
            if main is not None and hasattr(main, "view_navigation_undo_enabled"):
                return bool(getattr(main, "view_navigation_undo_enabled", True))
            opts = getattr(main, "app_options", {}) if main is not None else {}
            if isinstance(opts, dict) and "view_navigation_undo_enabled" in opts:
                return bool(opts.get("view_navigation_undo_enabled", True))
        except Exception:
            pass
        return True

    def _view_undo_is_suppressed(self):
        """Return True while view changes are being restored programmatically.

        Scrollbars emit valueChanged during Undo/Redo/view restoration.  Those
        signals must not create another ViewCommand, otherwise Ctrl+Z can recurse
        or keep adding phantom scroll actions.
        """
        try:
            if not self._view_undo_enabled():
                return True
            if bool(getattr(self, "_suppress_view_history", False)):
                return True
            ve = getattr(getattr(self, "main", None), "view_engine", None)
            if ve is not None and bool(getattr(ve, "suppress", False)):
                return True
            if bool(getattr(getattr(self, "main", None), "_is_rebuilding_text_layer", False)):
                return True
            if bool(getattr(getattr(self, "main", None), "_project_undo_restore_lock", False)):
                return True
            return False
        except Exception:
            return True

    def _begin_scroll_view_undo(self):
        try:
            if hasattr(self.main, 'note_ui_interaction_activity'):
                self.main.note_ui_interaction_activity(1200)
        except Exception:
            pass
        """Begin/coalesce a scrollbar view undo action.

        This method is connected directly to QScrollBar.actionTriggered.  It used
        to be referenced without an implementation, which caused AttributeError
        storms whenever the user scrolled or Qt restored a view state.
        """
        if self._view_undo_is_suppressed():
            return
        self._scrollbar_view_undo_active = True
        try:
            if not self._view_undo_is_suppressed() and hasattr(self.main, "begin_coalesced_view_undo"):
                self.main.begin_coalesced_view_undo("화면 이동", delay_ms=500)
            elif hasattr(self.main, "begin_page_view_undo"):
                self.main.begin_page_view_undo("화면 이동")
        except Exception:
            pass

    def _schedule_scroll_view_undo_finish(self):
        """Coalesce scrollbar value changes into one page-local ViewCommand."""
        if self._view_undo_is_suppressed():
            return
        try:
            if not self._scrollbar_view_undo_active:
                self._begin_scroll_view_undo()
            elif hasattr(self.main, "begin_coalesced_view_undo"):
                # Restart MainWindow's coalescing timer; finish_page_view_undo() will
                # be called by that timer after scrolling settles.
                self.main.begin_coalesced_view_undo("화면 이동", delay_ms=500)
            elif hasattr(self.main, "finish_page_view_undo"):
                self.main.finish_page_view_undo(force=False)
            if hasattr(self.main, "remember_current_view_state"):
                self.main.remember_current_view_state()
            if hasattr(self.main, "schedule_source_compare_sync"):
                self.main.schedule_source_compare_sync(180)
        except Exception:
            pass

    def _begin_view_pan_undo(self):
        try:
            if hasattr(self.main, 'note_ui_interaction_activity'):
                self.main.note_ui_interaction_activity(1200)
        except Exception:
            pass
        self._view_pan_undo_key = None
        self._view_pan_start_state = None
        try:
            if not self._view_undo_is_suppressed() and hasattr(self.main, "begin_page_view_undo"):
                self.main.begin_page_view_undo("화면 이동")
        except Exception:
            pass

    def _finish_view_pan_undo(self):
        self._view_pan_undo_key = None
        self._view_pan_start_state = None
        try:
            if not self._view_undo_is_suppressed() and hasattr(self.main, "finish_page_view_undo"):
                self.main.finish_page_view_undo(force=False)
            elif hasattr(self.main, "remember_current_view_state"):
                self.main.remember_current_view_state()
        except Exception:
            pass

    def _paint_history_kind_for_item(self, target_item):
        try:
            if target_item is self.final_paint_item or target_item is self.final_paint_above_item:
                return "final_paint"
            if target_item is self.user_mask_item:
                return "mask"
        except Exception:
            pass
        return None

    def _apply_paint_history_record(self, record):
        if isinstance(record, dict) and record.get("_brush_record"):
            try:
                return self.brush_engine.apply_record(record, "undo")
            except Exception:
                return None
        if isinstance(record, dict) and record.get("dirty_rect") is not None:
            target_item = record.get("target_item")
            patch = record.get("patch")
            rect = record.get("dirty_rect")
            if target_item is None or patch is None or rect is None:
                return None
            try:
                pix = target_item.pixmap()
                p = QPainter(pix)
                p.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
                p.drawPixmap(rect.topLeft(), patch)
                p.end()
                target_item.setPixmap(pix)
                target_item.update(QRectF(rect))
                if target_item is self.final_paint_above_item:
                    self.final_paint_above_img = pix.toImage()
                elif target_item is self.final_paint_item:
                    self.final_paint_img = pix.toImage()
                elif target_item is self.user_mask_item:
                    self.user_mask_img = pix.toImage()
                try:
                    self.viewport().update(self.mapFromScene(target_item.mapRectToScene(QRectF(rect))).boundingRect())
                except Exception:
                    pass
            except Exception:
                return None
            return self._paint_history_kind_for_item(target_item)

        if isinstance(record, tuple) and len(record) == 2:
            target_item, pixmap = record
        else:
            target_item = self.user_mask_item
            pixmap = record
        if target_item is None or pixmap is None:
            return None
        target_item.setPixmap(pixmap)
        try:
            if target_item is self.final_paint_above_item:
                self.final_paint_above_img = pixmap.toImage()
            elif target_item is self.final_paint_item:
                self.final_paint_img = pixmap.toImage()
            elif target_item is self.user_mask_item:
                self.user_mask_img = pixmap.toImage()
        except Exception:
            pass
        try:
            target_item.update()
            self.viewport().update()
        except Exception:
            pass
        return self._paint_history_kind_for_item(target_item)

    def _append_paint_history_undo_marker(self, kind=None, reason=None):
        """viewer.history에 직접 쌓은 patch record를 Ctrl+Z 타임라인에 연결한다.

        일반 브러시는 PageBrushEngine.commit()이 page undo marker를 추가하지만,
        영역 페인팅/영역 마스킹/요술봉 영역 칠하기는 viewer.py에서 직접 patch를 만들기 때문에
        같은 marker를 여기서 수동으로 넣어야 한다.
        """
        try:
            page_idx = int(getattr(self.main, "idx", 0) or 0)
            mode = int(self.main.cb_mode.currentIndex()) if hasattr(self.main, "cb_mode") else 0
            reason_s = str(reason or ("최종 페인팅" if kind == "final_paint" else "마스크 편집"))
            if hasattr(self.main, "undo_push_paint_marker"):
                ok = self.main.undo_push_paint_marker(kind=kind, reason=reason_s, page_idx=page_idx, mode=mode)
            elif hasattr(self.main, "undo_push_page"):
                ok = self.main.undo_push_page({
                    "reason": reason_s,
                    "page_idx": page_idx,
                    "mode": mode,
                    "paint_history": True,
                    "_undo_scope": "page",
                }, page_idx=page_idx)
            else:
                ok = False
            try:
                if hasattr(self.main, "audit_boundary_event"):
                    self.main.audit_boundary_event("PAINT_UNDO_MARKER_PUSH", reason=reason_s, ok=bool(ok), page_idx=page_idx, mode=mode, throttle_ms=100)
            except Exception:
                pass
            try:
                if hasattr(self.main, "update_undo_redo_buttons"):
                    self.main.update_undo_redo_buttons()
            except Exception:
                pass
        except Exception:
            pass

    def _current_paint_history_record_for(self, target_item, like_record=None):
        try:
            if target_item is None:
                target_item = self.user_mask_item
            if target_item is None:
                return None
            if isinstance(like_record, dict) and like_record.get("dirty_rect") is not None:
                rect = like_record.get("dirty_rect")
                patch = target_item.pixmap().copy(rect)
                return {
                    "target_item": target_item,
                    "dirty_rect": rect,
                    "patch": patch,
                }
            return (target_item, target_item.pixmap().copy())
        except Exception:
            pass
        return None

    def undo(self):
        try:
            if hasattr(self.main, "undo_bind_paint_viewer"):
                self.main.undo_bind_paint_viewer(self)
        except Exception:
            pass
        if not self.history:
            self.main.log("⚠️ 실행 취소할 내역이 없습니다.")
            if hasattr(self.main, "update_undo_redo_buttons"):
                self.main.update_undo_redo_buttons()
            return False

        record = self.history.pop()
        if isinstance(record, dict) and record.get("_brush_record"):
            redo_record = record
            try:
                kind = self.brush_engine.apply_record(record, "undo")
            except Exception:
                kind = None
        else:
            if isinstance(record, tuple) and len(record) == 2:
                target_item, _last_pixmap = record
            else:
                target_item = self.user_mask_item
            redo_record = self._current_paint_history_record_for(target_item, record)
            kind = self._apply_paint_history_record(record)
        if redo_record is not None:
            self.redo_history.append(redo_record)
            if len(self.redo_history) > 20:
                self.redo_history.pop(0)

        if kind == "final_paint":
            self.main.log("↩️ 최종 페인팅 실행 취소됨")
        elif kind == "mask":
            self.main.log("↩️ 마스크 브러시 실행 취소됨")
        else:
            self.main.log("↩️ 실행 취소됨")
        try:
            if hasattr(self.main, "schedule_deferred_view_layer_commit"):
                self.main.schedule_deferred_view_layer_commit(kind, delay_ms=1200)
        except Exception:
            pass
        if hasattr(self.main, "update_undo_redo_buttons"):
            self.main.update_undo_redo_buttons()
        return True

    def redo(self):
        try:
            if hasattr(self.main, "undo_bind_paint_viewer"):
                self.main.undo_bind_paint_viewer(self)
        except Exception:
            pass
        if not getattr(self, "redo_history", None):
            self.main.log("⚠️ 다시 실행할 내역이 없습니다.")
            if hasattr(self.main, "update_undo_redo_buttons"):
                self.main.update_undo_redo_buttons()
            return False

        record = self.redo_history.pop()
        if isinstance(record, dict) and record.get("_brush_record"):
            undo_record = record
            try:
                kind = self.brush_engine.apply_record(record, "redo")
            except Exception:
                kind = None
        else:
            if isinstance(record, tuple) and len(record) == 2:
                target_item, _pixmap = record
            else:
                target_item = self.user_mask_item
            undo_record = self._current_paint_history_record_for(target_item, record)
            kind = self._apply_paint_history_record(record)
        if undo_record is not None:
            self.history.append(undo_record)
            if len(self.history) > 20:
                self.history.pop(0)

        if kind == "final_paint":
            self.main.log("↷ 최종 페인팅 다시 실행됨")
        elif kind == "mask":
            self.main.log("↷ 마스크 브러시 다시 실행됨")
        else:
            self.main.log("↷ 다시 실행됨")
        try:
            if hasattr(self.main, "schedule_deferred_view_layer_commit"):
                self.main.schedule_deferred_view_layer_commit(kind, delay_ms=1200)
        except Exception:
            pass
        if hasattr(self.main, "update_undo_redo_buttons"):
            self.main.update_undo_redo_buttons()
        return True


    def _set_layer_tag(self, item, tag):
        try:
            item.setData(0, str(tag))
        except Exception:
            pass
        return item

    def hard_clear_runtime_cache(self, reason=""):
        """Completely detach every preview/base pixmap owned by this viewer.

        Project close/open is a hard boundary: cached base pixmaps from the old
        project must never be reused by the next project even if page index and
        work-mode keys look identical.
        """
        try:
            self.scene.clear()
        except Exception:
            pass
        for attr in (
            "user_mask_item", "user_mask_img",
            "final_paint_item", "final_paint_above_item",
            "final_paint_img", "final_paint_above_img",
            "last_pt", "_active_transform_item",
            "_layer_base_item", "_layer_base_key", "_layer_items",
        ):
            try:
                if attr == "_layer_items":
                    setattr(self, attr, {})
                else:
                    setattr(self, attr, None)
            except Exception:
                pass
        for attr in (
            "magic_preview_items", "paste_preview_items",
            "history", "redo_history",
            "_layer_base_pixmap_cache_order",
        ):
            try:
                setattr(self, attr, [])
            except Exception:
                pass
        try:
            self._layer_base_pixmap_cache = {}
        except Exception:
            pass
        for fn in (
            "clear_mask_wrap_preview", "clear_mask_cut_preview",
            "clear_ocr_region_preview", "clear_ocr_region_overlay",
            "clear_quick_ocr_preview", "clear_paste_preview",
            "clear_raster_erase_preview", "clear_area_paint_preview",
        ):
            try:
                getattr(self, fn)()
            except Exception:
                pass
        try:
            self.brush_engine.clear_runtime()
        except Exception:
            pass
        try:
            self.resetTransform()
        except Exception:
            pass
        try:
            self.scene.setSceneRect(QRectF(0, 0, 1, 1))
        except Exception:
            pass
        try:
            self.setCacheMode(QGraphicsView.CacheModeFlag.CacheNone)
            self.resetCachedContent()
        except Exception:
            pass
        try:
            self.viewport().update()
        except Exception:
            pass

    def _item_layer_tag(self, item):
        """Return the QGraphicsItem layer tag without being fooled by TypesettingItem.data.

        TypesettingItem intentionally stores its text-line dictionary as ``self.data``.
        That shadows QGraphicsItem.data(index), so calling ``item.data(0)`` raises
        ``dict is not callable`` and old text items are not removed.  Use the
        unbound QGraphicsItem.data() API for layer tags.
        """
        try:
            return QGraphicsItem.data(item, 0)
        except Exception:
            try:
                return item.data(0)
            except Exception:
                return None

    def _remove_scene_items_by_tags(self, *tags):
        tags = {str(t) for t in tags if t is not None}
        if not tags:
            return
        for item in list(self.scene.items()):
            try:
                if str(self._item_layer_tag(item)) in tags:
                    self.scene.removeItem(item)
            except Exception:
                pass

    def clear_mode_layers(self, *, clear_boxes=True, clear_text=True, clear_mask=True, clear_final_paint=True):
        """Remove page-mode overlay layers without rebuilding the base image.

        LayerEngine 2nd pass: tab changes inside the same page should not
        force scene.clear()/set_image() every time.  Keep the base pixmap and
        only replace mode-specific layers.
        """
        tags = []
        if clear_boxes:
            tags.extend(["analysis_box", "analysis_label"])
        if clear_text:
            tags.append("movable_text")
        if clear_mask:
            tags.append("mask_overlay")
            self.user_mask_item = None
            self.user_mask_img = None
        if clear_final_paint:
            tags.extend(["final_paint_below", "final_paint_above"])
            self.final_paint_item = None
            self.final_paint_above_item = None
            self.final_paint_img = None
            self.final_paint_above_img = None
        self._remove_scene_items_by_tags(*tags)
        # Transient previews are mode-local; keep the base layer but drop them.
        try:
            self.clear_mask_wrap_preview()
            self.clear_mask_cut_preview()
            self.clear_ocr_region_preview()
            self.clear_quick_ocr_preview()
            self.clear_paste_preview()
        except Exception:
            pass

    def set_layer_base_image(self, img, key=None, fit=True, clear_paint_history=True):
        """Set or reuse the base pixmap layer.

        If the requested key matches the current base, the scene is not cleared.
        This is the core fast path for same-page tab switching.
        """
        if img is None:
            self.scene.clear()
            self._layer_base_key = None
            self._layer_base_item = None
            self.user_mask_item = None
            self.final_paint_item = None
            self.final_paint_above_item = None
            return False

        key = str(key or "")
        base_item = getattr(self, "_layer_base_item", None)
        if key and getattr(self, "_layer_base_key", None) == key and base_item is not None:
            try:
                if base_item.scene() is self.scene:
                    if fit:
                        self.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
                    return False
            except Exception:
                pass

        self.scene.clear()
        self.user_mask_item = None
        self.final_paint_item = None
        self.final_paint_above_item = None
        self.final_paint_img = None
        self.final_paint_above_img = None
        self.magic_preview_items = []
        self.clear_mask_wrap_preview()
        self.clear_mask_cut_preview()
        self.clear_ocr_region_preview()
        self.clear_ocr_region_overlay()
        self.clear_quick_ocr_preview()
        self.clear_paste_preview()
        try:
            self.brush_engine.clear_runtime()
        except Exception:
            pass
        # A true page/base change may invalidate legacy viewer-local paint
        # histories.  Same-page work-tab switching uses this method too, but that
        # is only a display-base swap; clearing paint history there is slow and
        # can make mask Undo look stale.  The caller can therefore suppress it.
        if clear_paint_history:
            try:
                if hasattr(self.main, "undo_clear_paint_history"):
                    self.main.undo_clear_paint_history(self, undo=True, redo=True, reason="base image changed")
                else:
                    self.history.clear()
                    self.redo_history.clear()
            except Exception:
                try:
                    self.history.clear()
                    self.redo_history.clear()
                except Exception:
                    pass
            if hasattr(self.main, "update_undo_redo_buttons"):
                self.main.update_undo_redo_buttons()

        pix = None
        try:
            cache = getattr(self, "_layer_base_pixmap_cache", None)
            if isinstance(cache, dict) and key and key in cache:
                cached = cache.get(key)
                if isinstance(cached, QPixmap) and not cached.isNull():
                    pix = cached
        except Exception:
            pix = None
        if pix is None:
            if isinstance(img, bytes):
                q_img = QImage.fromData(img)
            else:
                q_img = self._np2pix(img).toImage()
            pix = QPixmap.fromImage(q_img)
            try:
                if key:
                    cache = getattr(self, "_layer_base_pixmap_cache", None)
                    order = getattr(self, "_layer_base_pixmap_cache_order", None)
                    if not isinstance(cache, dict):
                        cache = {}
                    if not isinstance(order, list):
                        order = []
                    cache[key] = pix
                    if key in order:
                        order.remove(key)
                    order.append(key)
                    while len(order) > 6:
                        old_key = order.pop(0)
                        cache.pop(old_key, None)
                    self._layer_base_pixmap_cache = cache
                    self._layer_base_pixmap_cache_order = order
            except Exception:
                pass
        item = self.scene.addPixmap(pix)
        item.setZValue(0)
        self._set_layer_tag(item, "base")
        self._layer_base_item = item
        self._layer_base_key = key
        self.scene.setSceneRect(QRectF(pix.rect()))
        if fit:
            self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        return True

    def set_mask_overlay_layer(self, mask, color):
        """Replace only the mask overlay layer on the current base image."""
        self._remove_scene_items_by_tags("mask_overlay")
        self.user_mask_item = None
        rect = self.scene.sceneRect()
        w, h = int(rect.width()), int(rect.height())
        if w <= 0 or h <= 0:
            return
        self.user_mask_img = QImage(w, h, QImage.Format.Format_ARGB32)
        self.user_mask_img.fill(Qt.GlobalColor.transparent)
        if mask is not None:
            m_qimg = self._np2pix(mask).toImage().convertToFormat(QImage.Format.Format_Grayscale8)
            if m_qimg.width() != w or m_qimg.height() != h:
                m_qimg = m_qimg.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
            target_color_img = QImage(w, h, QImage.Format.Format_ARGB32)
            target_color_img.fill(color)
            target_color_img.setAlphaChannel(m_qimg)
            p = QPainter(self.user_mask_img)
            p.drawImage(0, 0, target_color_img)
            p.end()
        self.user_mask_item = self.scene.addPixmap(QPixmap.fromImage(self.user_mask_img))
        self.user_mask_item.setZValue(10)
        self.user_mask_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self._set_layer_tag(self.user_mask_item, "mask_overlay")

    def set_image(self, img, fit=True):
        """2.3.1 안정 방식: 화면 탭 갱신은 scene을 통째로 비우고 다시 만든다.

        2.4.0의 레이어 재사용(set_layer_base_image/clear_mode_layers)은 성능상 유리하지만,
        텍스트 객체 변환/삭제/변형 직후 남아 있는 QGraphicsItem 참조와 충돌하기 쉽다.
        B단계에서는 사용자가 직접 만지는 화면 반응 로직을 2.3.1처럼 전체 재구성으로 되돌린다.
        """
        self.scene.clear()
        self.user_mask_item = None
        self.final_paint_item = None
        self.final_paint_above_item = None
        self.final_paint_img = None
        self.final_paint_above_img = None
        self.magic_preview_items = []
        self.paste_preview_items = []
        self._layer_base_item = None
        self._layer_base_key = None
        self._layer_items = {}
        try:
            self._active_transform_item = None
        except Exception:
            pass
        self.clear_mask_wrap_preview()
        self.clear_mask_cut_preview()
        self.clear_ocr_region_preview()
        self.clear_ocr_region_overlay()
        self.clear_quick_ocr_preview()
        self.clear_paste_preview()
        try:
            self.clear_raster_erase_preview()
        except Exception:
            pass
        try:
            self.clear_area_paint_preview()
        except Exception:
            pass
        try:
            if hasattr(self.main, "undo_clear_paint_history"):
                self.main.undo_clear_paint_history(self, undo=True, redo=True, reason="set_image rebuild")
            else:
                self.history.clear()
                self.redo_history.clear()
        except Exception:
            try:
                self.history.clear()
                self.redo_history.clear()
            except Exception:
                pass
        if hasattr(self.main, "update_undo_redo_buttons"):
            self.main.update_undo_redo_buttons()
        if img is None:
            try:
                self._layer_base_pixmap_cache = {}
                self._layer_base_pixmap_cache_order = []
            except Exception:
                pass
            try:
                self.resetCachedContent()
                self.viewport().update()
            except Exception:
                pass
            return

        if isinstance(img, bytes):
            q_img = QImage.fromData(img)
        else:
            q_img = self._np2pix(img).toImage()

        pix = QPixmap.fromImage(q_img)
        item = self.scene.addPixmap(pix)
        item.setZValue(0)
        try:
            self._set_layer_tag(item, "base")
        except Exception:
            pass
        self._layer_base_item = item
        self.scene.setSceneRect(QRectF(pix.rect()))
        if fit:
            self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def set_overlay(self, bg, mask, color, fit=True):
        """2.3.1 안정 방식: 마스크 화면도 통째로 다시 만든다."""
        self.scene.clear()
        self.user_mask_item = None
        self.final_paint_item = None
        self.final_paint_above_item = None
        self.final_paint_img = None
        self.final_paint_above_img = None
        self.magic_preview_items = []
        self.paste_preview_items = []
        self._layer_base_item = None
        self._layer_base_key = None
        self._layer_items = {}
        self.clear_mask_wrap_preview()
        self.clear_mask_cut_preview()
        self.clear_ocr_region_preview()
        self.clear_ocr_region_overlay()
        self.clear_quick_ocr_preview()
        try:
            self.clear_raster_erase_preview()
        except Exception:
            pass
        try:
            self.clear_area_paint_preview()
        except Exception:
            pass
        if bg is None:
            return

        if isinstance(bg, bytes):
            bg_pix = QPixmap.fromImage(QImage.fromData(bg))
        else:
            bg_pix = self._np2pix(bg)
        bg_item = self.scene.addPixmap(bg_pix)
        bg_item.setZValue(0)
        try:
            self._set_layer_tag(bg_item, "base")
        except Exception:
            pass
        self._layer_base_item = bg_item

        w, h = bg_pix.width(), bg_pix.height()
        self.user_mask_img = QImage(w, h, QImage.Format.Format_ARGB32)
        self.user_mask_img.fill(Qt.GlobalColor.transparent)

        if mask is not None:
            m_qimg = self._np2pix(mask).toImage().convertToFormat(QImage.Format.Format_Grayscale8)
            if m_qimg.width() != w or m_qimg.height() != h:
                m_qimg = m_qimg.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
            target_color_img = QImage(w, h, QImage.Format.Format_ARGB32)
            target_color_img.fill(color)
            target_color_img.setAlphaChannel(m_qimg)

            p = QPainter(self.user_mask_img)
            p.drawImage(0, 0, target_color_img)
            p.end()

        self.user_mask_item = self.scene.addPixmap(QPixmap.fromImage(self.user_mask_img))
        self.user_mask_item.setZValue(10)
        self.user_mask_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        try:
            self._set_layer_tag(self.user_mask_item, "mask_overlay")
        except Exception:
            pass

        self.scene.setSceneRect(QRectF(bg_pix.rect()))
        if fit:
            self.fitInView(self.scene.itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def _paint_qimage_from_data(self, paint_data, w, h):
        qimg = QImage(w, h, QImage.Format.Format_ARGB32)
        qimg.fill(Qt.GlobalColor.transparent)

        if paint_data is None:
            return qimg

        try:
            if isinstance(paint_data, (bytes, bytearray)):
                loaded = QImage.fromData(bytes(paint_data))
                if not loaded.isNull():
                    qimg = loaded.convertToFormat(QImage.Format.Format_ARGB32)
            elif isinstance(paint_data, QImage):
                qimg = paint_data.convertToFormat(QImage.Format.Format_ARGB32)
            elif isinstance(paint_data, np.ndarray):
                arr = paint_data
                if arr.ndim == 3 and arr.shape[2] == 4:
                    h2, w2 = arr.shape[:2]
                    qimg = QImage(arr.data, w2, h2, 4 * w2, QImage.Format.Format_RGBA8888).copy()
                elif arr.ndim == 3 and arr.shape[2] == 3:
                    h2, w2 = arr.shape[:2]
                    qimg = QImage(arr.data, w2, h2, 3 * w2, QImage.Format.Format_RGB888).copy().convertToFormat(QImage.Format.Format_ARGB32)
            if qimg.width() != w or qimg.height() != h:
                qimg = qimg.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation)
        except Exception:
            qimg = QImage(w, h, QImage.Format.Format_ARGB32)
            qimg.fill(Qt.GlobalColor.transparent)

        return qimg

    def set_final_paint_overlay(self, paint_data=None, paint_above_data=None, fit=False):
        """최종화면용 투명 페인팅 레이어를 만든다.
        아래 레이어는 텍스트보다 아래, 위 레이어는 텍스트보다 위에 고정된다.
        토글은 기존 레이어 순서를 바꾸지 않고, 새 붓질이 들어갈 레이어만 선택한다.
        """
        rect = self.scene.sceneRect()
        w = int(rect.width())
        h = int(rect.height())
        if w <= 0 or h <= 0:
            return

        below_qimg = self._paint_qimage_from_data(paint_data, w, h)
        above_qimg = self._paint_qimage_from_data(paint_above_data, w, h)

        self.final_paint_img = below_qimg
        self.final_paint_item = self.scene.addPixmap(QPixmap.fromImage(below_qimg))
        self._set_layer_tag(self.final_paint_item, "final_paint_below")
        self.final_paint_item.setZValue(8)
        # 페인팅 레이어는 화면에는 보이지만 선택/이동 클릭을 잡아먹으면 안 된다.
        # 특히 위쪽 페인팅 레이어(z=80)는 텍스트보다 위에 있어서,
        # 마우스를 받으면 객체화된 텍스트가 클릭/선택/이동되지 않는다.
        self.final_paint_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

        self.final_paint_above_img = above_qimg
        self.final_paint_above_item = self.scene.addPixmap(QPixmap.fromImage(above_qimg))
        self._set_layer_tag(self.final_paint_above_item, "final_paint_above")
        self.final_paint_above_item.setZValue(80)
        self.final_paint_above_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def get_final_paint_layer_png_bytes(self, above=False):
        item = self.final_paint_above_item if above else self.final_paint_item
        if not item:
            return None
        qimg = item.pixmap().toImage().convertToFormat(QImage.Format.Format_ARGB32)
        # 완전 투명 레이어면 저장하지 않는다.
        w, h = qimg.width(), qimg.height()
        ptr = qimg.bits()
        ptr.setsize(qimg.sizeInBytes())
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((h, qimg.bytesPerLine() // 4, 4))
        alpha = arr[:, :w, 3]
        if not np.any(alpha > 0):
            return None

        from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        qimg.save(buf, "PNG")
        return bytes(ba)

    def get_final_paint_png_bytes(self):
        return self.get_final_paint_layer_png_bytes(False)

    def get_final_paint_above_png_bytes(self):
        return self.get_final_paint_layer_png_bytes(True)


    def draw_static_boxes(self, data):
        base_w = int(round(self.ui_handle_size(int(getattr(self.main, "analysis_number_box_width", 40) or 40), minimum=20)))
        font_size = max(8, int(base_w * 0.40))
        font = QFont("Arial", font_size, QFont.Weight.Bold)

        visible_items = [d for d in data]
        total_items = len(visible_items)
        for order_idx, d in enumerate(visible_items):
            is_active = d.get('use_inpaint', True)
            x, y, w, h = d['rect']

            pen_w = self.ui_pen_width(2)
            pen_box = QPen(QColor(255, 0, 0), pen_w) if is_active else QPen(QColor(150, 150, 150), pen_w, Qt.PenStyle.DotLine)

            rect_item = ToggleBoxItem(
                [x, y, w, h],
                d,
                self.main,
                pen_box,
                brush=QBrush(Qt.BrushStyle.NoBrush),
                z_value=20,
            )
            self._set_layer_tag(rect_item, "analysis_box")
            self.scene.addItem(rect_item)

            id_str = str(d.get('id', ''))
            bg_w = max(20, base_w + (len(id_str) - 1) * max(8, int(base_w * 0.4)))
            bg_h = max(18, int(base_w * 0.9))

            bx, by = x, y - bg_h
            if by < 0:
                by = y

            if is_active:
                brush_bg = QBrush(QColor(255, 215, 0))
                text_color = Qt.GlobalColor.black
            else:
                brush_bg = QBrush(QColor(100, 100, 100))
                text_color = Qt.GlobalColor.white

            handle_item = ToggleBoxItem(
                [bx, by, bg_w, bg_h],
                d,
                self.main,
                QPen(Qt.PenStyle.NoPen),
                brush=brush_bg,
                z_value=21,
            )
            self._set_layer_tag(handle_item, "analysis_box")
            self.scene.addItem(handle_item)

            t_item = self.scene.addText(id_str, font)
            t_item.setDefaultTextColor(text_color)
            br = t_item.boundingRect()
            t_item.setPos(bx + (bg_w - br.width()) / 2, by + (bg_h - br.height()) / 2)
            t_item.setZValue(22)
            t_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self._set_layer_tag(t_item, "analysis_label")

    def draw_movable_texts(
        self,
        data,
        font,
        size_px,
        stroke,
        show_text=True,
        text_color="#000000",
        stroke_color="#FFFFFF",
        align="center",
    ):
        if not show_text:
            return

        visible_items = []
        for d in data:
            if not isinstance(d, dict):
                continue
            # 쯔꾸르붕이: 대사는 캔버스 텍스트 객체가 아니라 게임식 대사창/선택지 프리뷰로만 표시한다.
            if isinstance(d.get('maker_text_unit'), dict):
                continue
            if not d.get('use_inpaint', True):
                continue
            if not str(d.get('translated_text', '') or '').strip() and not d.get('force_show'):
                continue
            visible_items.append(d)

        total_items = len(visible_items)
        for order_idx, d in enumerate(visible_items):
            item = TypesettingItem(
                d,
                font,
                size_px,
                stroke,
                self.main.on_text_item_moved,
                text_color=text_color,
                stroke_color=stroke_color,
                align=align,
            )
            item.main_window = self.main
            # 번호가 빠른 텍스트가 겹칠 때 위에 보이도록 역순 z값을 준다.
            item.setZValue(30 + (total_items - order_idx))
            self._set_layer_tag(item, "movable_text")
            self.scene.addItem(item)

    def clear_mask_wrap_preview(self):
        item = getattr(self, "mask_wrap_preview_item", None)
        if item is not None:
            try:
                self.scene.removeItem(item)
            except Exception:
                pass
        self.mask_wrap_preview_item = None

    def _mask_wrap_pen(self):
        return QPen(QColor(255, 230, 0), self.ui_pen_width(2), Qt.PenStyle.SolidLine)

    def _draw_mask_wrap_preview(self, now):
        self.clear_mask_wrap_preview()
        if self.mask_wrap_start is None:
            return
        pen = self._mask_wrap_pen()
        brush = QBrush(Qt.BrushStyle.NoBrush)
        if getattr(self, "mask_wrap_shape", "rect") == "rect":
            rect = QRectF(self.mask_wrap_start, now).normalized()
            self.mask_wrap_preview_item = self.scene.addRect(rect, pen, brush)
        else:
            path = QPainterPath()
            points = list(getattr(self, "mask_wrap_points", []) or [])
            if not points:
                points = [self.mask_wrap_start, now]
            path.moveTo(points[0])
            for pt in points[1:]:
                path.lineTo(pt)
            self.mask_wrap_preview_item = self.scene.addPath(path, pen, brush)
        if self.mask_wrap_preview_item is not None:
            self.mask_wrap_preview_item.setZValue(42)
            self.mask_wrap_preview_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def _mask_wrap_region_np(self, end_pos):
        if self.user_mask_img is None or self.mask_wrap_start is None:
            return None
        import cv2
        h = int(self.user_mask_img.height())
        w = int(self.user_mask_img.width())
        if w <= 0 or h <= 0:
            return None
        region = np.zeros((h, w), dtype=np.uint8)
        if getattr(self, "mask_wrap_shape", "rect") == "rect":
            x1 = int(round(min(self.mask_wrap_start.x(), end_pos.x())))
            y1 = int(round(min(self.mask_wrap_start.y(), end_pos.y())))
            x2 = int(round(max(self.mask_wrap_start.x(), end_pos.x())))
            y2 = int(round(max(self.mask_wrap_start.y(), end_pos.y())))
            x1 = max(0, min(w - 1, x1)); x2 = max(0, min(w - 1, x2))
            y1 = max(0, min(h - 1, y1)); y2 = max(0, min(h - 1, y2))
            if x2 <= x1 or y2 <= y1:
                return None
            cv2.rectangle(region, (x1, y1), (x2, y2), 255, thickness=-1)
            return region

        points = list(getattr(self, "mask_wrap_points", []) or [])
        if end_pos is not None:
            points.append(end_pos)
        if len(points) < 3:
            return None
        arr = []
        for pt in points:
            x = max(0, min(w - 1, int(round(pt.x()))))
            y = max(0, min(h - 1, int(round(pt.y()))))
            arr.append([x, y])
        if len(arr) < 3:
            return None
        cv2.fillPoly(region, [np.array(arr, dtype=np.int32)], 255)
        return region


    def clear_mask_cut_preview(self):
        item = getattr(self, "mask_cut_preview_item", None)
        if item is not None:
            try:
                self.scene.removeItem(item)
            except Exception:
                pass
        self.mask_cut_preview_item = None

    def _mask_cut_pen(self):
        return QPen(QColor(255, 80, 40), self.ui_pen_width(2), Qt.PenStyle.SolidLine)

    def _draw_mask_cut_preview(self, now):
        self.clear_mask_cut_preview()
        if self.mask_cut_start is None:
            return
        pen = self._mask_cut_pen()
        brush = QBrush(Qt.BrushStyle.NoBrush)
        if getattr(self, "mask_cut_shape", "rect") == "rect":
            rect = QRectF(self.mask_cut_start, now).normalized()
            self.mask_cut_preview_item = self.scene.addRect(rect, pen, brush)
        else:
            path = QPainterPath()
            points = list(getattr(self, "mask_cut_points", []) or [])
            if not points:
                points = [self.mask_cut_start, now]
            path.moveTo(points[0])
            for pt in points[1:]:
                path.lineTo(pt)
            self.mask_cut_preview_item = self.scene.addPath(path, pen, brush)
        if self.mask_cut_preview_item is not None:
            self.mask_cut_preview_item.setZValue(43)
            self.mask_cut_preview_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def _mask_cut_region_np(self, end_pos):
        if self.user_mask_img is None or self.mask_cut_start is None:
            return None
        import cv2
        h = int(self.user_mask_img.height())
        w = int(self.user_mask_img.width())
        if w <= 0 or h <= 0:
            return None
        region = np.zeros((h, w), dtype=np.uint8)
        if getattr(self, "mask_cut_shape", "rect") == "rect":
            x1 = int(round(min(self.mask_cut_start.x(), end_pos.x())))
            y1 = int(round(min(self.mask_cut_start.y(), end_pos.y())))
            x2 = int(round(max(self.mask_cut_start.x(), end_pos.x())))
            y2 = int(round(max(self.mask_cut_start.y(), end_pos.y())))
            x1 = max(0, min(w - 1, x1)); x2 = max(0, min(w - 1, x2))
            y1 = max(0, min(h - 1, y1)); y2 = max(0, min(h - 1, y2))
            if x2 <= x1 or y2 <= y1:
                return None
            cv2.rectangle(region, (x1, y1), (x2, y2), 255, thickness=-1)
            return region

        points = list(getattr(self, "mask_cut_points", []) or [])
        if end_pos is not None:
            points.append(end_pos)
        if len(points) < 3:
            return None
        arr = []
        for pt in points:
            x = max(0, min(w - 1, int(round(pt.x()))))
            y = max(0, min(h - 1, int(round(pt.y()))))
            arr.append([x, y])
        if len(arr) < 3:
            return None
        cv2.fillPoly(region, [np.array(arr, dtype=np.int32)], 255)
        return region

    def clear_ocr_region_preview(self):
        item = getattr(self, "ocr_region_preview_item", None)
        if item is not None:
            try:
                self.scene.removeItem(item)
            except Exception:
                pass
        self.ocr_region_preview_item = None

    def clear_quick_ocr_preview(self):
        item = getattr(self, "quick_ocr_preview_item", None)
        if item is not None:
            try:
                self.scene.removeItem(item)
            except Exception:
                pass
        self.quick_ocr_preview_item = None

    def clear_ocr_region_overlay(self):
        if not hasattr(self, "ocr_region_overlay_items"):
            self.ocr_region_overlay_items = []
        for item in list(self.ocr_region_overlay_items):
            try:
                if item.scene() is not None:
                    self.scene.removeItem(item)
            except Exception:
                pass
        self.ocr_region_overlay_items = []

    def _ocr_region_preview_pen(self):
        return QPen(QColor(199, 138, 144, 220), self.ui_pen_width(2), Qt.PenStyle.SolidLine)

    def _draw_ocr_region_preview(self, now):
        self.clear_ocr_region_preview()
        if self.ocr_region_start is None:
            return
        pen = self._ocr_region_preview_pen()
        brush = QBrush(QColor(138, 74, 82, 55))
        if getattr(self, "ocr_region_shape", "rect") == "rect":
            rect = QRectF(self.ocr_region_start, now).normalized()
            self.ocr_region_preview_item = self.scene.addRect(rect, pen, brush)
        else:
            path = QPainterPath()
            points = list(getattr(self, "ocr_region_points", []) or [])
            if not points:
                points = [self.ocr_region_start, now]
            path.moveTo(points[0])
            for pt in points[1:]:
                path.lineTo(pt)
            self.ocr_region_preview_item = self.scene.addPath(path, pen, brush)
        if self.ocr_region_preview_item is not None:
            self.ocr_region_preview_item.setZValue(86)
            self.ocr_region_preview_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def _draw_quick_ocr_preview(self, now):
        self.clear_quick_ocr_preview()
        if self.quick_ocr_start is None:
            return
        rect = QRectF(self.quick_ocr_start, now).normalized()
        pen = QPen(QColor(168, 93, 102, 215), self.ui_pen_width(2), Qt.PenStyle.DashLine)
        brush = QBrush(QColor(138, 74, 82, 55))
        self.quick_ocr_preview_item = self.scene.addRect(rect, pen, brush)
        self.quick_ocr_preview_item.setZValue(87)
        self.quick_ocr_preview_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def clear_raster_erase_preview(self):
        item = getattr(self, "raster_erase_preview_item", None)
        if item is not None:
            try:
                self.scene.removeItem(item)
            except Exception:
                pass
        self.raster_erase_preview_item = None

    def _draw_raster_erase_preview(self, now):
        self.clear_raster_erase_preview()
        if self.raster_erase_start is None:
            return
        rect = QRectF(self.raster_erase_start, now).normalized()
        pen = QPen(QColor(255, 80, 80), self.ui_pen_width(2), Qt.PenStyle.DashLine)
        brush = QBrush(QColor(255, 80, 80, 45))
        self.raster_erase_preview_item = self.scene.addRect(rect, pen, brush)
        self.raster_erase_preview_item.setZValue(91)
        self.raster_erase_preview_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def clear_area_paint_preview(self):
        item = getattr(self, "area_paint_preview_item", None)
        if item is not None:
            try:
                self.scene.removeItem(item)
            except Exception:
                pass
        self.area_paint_preview_item = None

    def _draw_area_paint_preview(self, now):
        self.clear_area_paint_preview()
        if self.area_paint_start is None:
            return
        mode = self.main.cb_mode.currentIndex() if getattr(self.main, "cb_mode", None) is not None else 4
        if mode in (2, 3):
            color = QColor(0, 0, 255, 150) if mode == 3 else QColor(168, 93, 102, 140)
        else:
            color = QColor(str(getattr(self.main, "final_paint_color", "#FFFFFF") or "#FFFFFF"))
            if not color.isValid():
                color = QColor("#FFFFFF")
        preview = QColor(color)
        preview.setAlpha(90)
        pen = QPen(QColor(255, 215, 0, 220), self.ui_pen_width(2), Qt.PenStyle.DashLine)
        brush = QBrush(preview)

        if getattr(self, "area_paint_shape", "rect") == "free":
            points = list(getattr(self, "area_paint_points", []) or [])
            if len(points) < 2:
                points = [self.area_paint_start, now]
            path = QPainterPath(points[0])
            for pt in points[1:]:
                path.lineTo(pt)
            path.lineTo(now)
            self.area_paint_preview_item = self.scene.addPath(path, pen, brush)
        else:
            rect = QRectF(self.area_paint_start, now).normalized()
            if rect.width() < 1 or rect.height() < 1:
                return
            self.area_paint_preview_item = self.scene.addRect(rect, pen, brush)
        self.area_paint_preview_item.setZValue(88)
        self.area_paint_preview_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def _area_paint_region_path(self, end_pos):
        if self.area_paint_start is None:
            return None
        if getattr(self, "area_paint_shape", "rect") == "free":
            points = list(getattr(self, "area_paint_points", []) or [])
            if not points:
                points = [self.area_paint_start]
            points.append(end_pos)
            if len(points) < 2:
                return None
            path = QPainterPath(points[0])
            for pt in points[1:]:
                path.lineTo(pt)
            path.closeSubpath()
            if path.boundingRect().width() < 2 or path.boundingRect().height() < 2:
                return None
            return path

        rect = QRectF(self.area_paint_start, end_pos).normalized()
        if rect.width() < 2 or rect.height() < 2:
            return None
        path = QPainterPath()
        path.addRect(rect)
        return path

    def _area_paint_region_mask_np(self, region_path, width, height):
        """QPainterPath 영역을 uint8 mask로 rasterize한다."""
        if region_path is None or width <= 0 or height <= 0:
            return None
        qimg = QImage(int(width), int(height), QImage.Format.Format_Grayscale8)
        qimg.fill(0)
        painter = QPainter(qimg)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        painter.fillPath(region_path, QBrush(QColor(255, 255, 255)))
        painter.end()
        ptr = qimg.bits()
        ptr.setsize(qimg.sizeInBytes())
        arr = np.frombuffer(ptr, dtype=np.uint8).reshape((qimg.height(), qimg.bytesPerLine()))
        return arr[:, :qimg.width()].copy()

    def _apply_area_paint_rect(self, end_pos):
        if self.area_paint_start is None:
            return False
        mode = self.main.cb_mode.currentIndex() if getattr(self.main, "cb_mode", None) is not None else 4
        if mode not in (2, 3, 4):
            return False
        region_path = self._area_paint_region_path(end_pos)
        if region_path is None:
            return False

        if mode in (2, 3):
            if self.user_mask_item is None:
                return False
            before_mask = self.get_mask_np()
            if before_mask is None:
                rect = self.scene.sceneRect()
                before_mask = np.zeros((max(1, int(rect.height())), max(1, int(rect.width()))), dtype=np.uint8)
            h, w = before_mask.shape[:2]
            region_mask = self._area_paint_region_mask_np(region_path, w, h)
            if region_mask is None:
                return False
            try:
                qrect = region_path.boundingRect().toAlignedRect().adjusted(-2, -2, 2, 2).intersected(self.user_mask_item.pixmap().rect())
            except Exception:
                qrect = self.user_mask_item.pixmap().rect()
            if qrect is None or qrect.isEmpty():
                return False
            before_patch = self.user_mask_item.pixmap().copy(qrect)

            combined = cv2.bitwise_or(before_mask.astype(np.uint8), region_mask.astype(np.uint8))
            color = QColor(0, 0, 255, 150) if mode == 3 else QColor(168, 93, 102, 140)
            self.set_user_mask_np(combined, color)
            after_patch = self.user_mask_item.pixmap().copy(qrect)
            try:
                record = {
                    "_brush_record": True,
                    "target_item": self.user_mask_item,
                    "kind": "mask",
                    "patches": [{"rect": qrect, "before": before_patch, "after": after_patch}],
                }
                if hasattr(self.main, "undo_push_paint_record"):
                    self.main.undo_push_paint_record(self, record, kind="mask", reason="영역 마스킹", max_history=80)
                else:
                    self.history.append(record)
                    if len(self.history) > 80:
                        self.history.pop(0)
                    self.redo_history.clear()
                    self._append_paint_history_undo_marker("mask", "영역 마스킹")
            except Exception:
                pass
            try:
                curr = self.main.data.get(self.main.idx)
                if isinstance(curr, dict):
                    self.main.set_active_mask(curr, combined, mode)
            except Exception:
                pass
            return True

        target_item = self.final_paint_above_item if getattr(self.main, "final_paint_above_text", False) else self.final_paint_item
        if target_item is None:
            return False
        pix = target_item.pixmap()
        if pix.isNull():
            return False

        # 영역 페인팅은 일반 브러시와 달리 PageBrushEngine을 거치지 않기 때문에,
        # 여기서 직접 before/after 패치 히스토리를 만들어야 Ctrl+Z/Ctrl+Y가 동작한다.
        # 전체 레이어를 복사하면 큰 페이지에서 무겁기 때문에, 선택 path의 bounding rect만 patch로 잡는다.
        try:
            qrect = region_path.boundingRect().toAlignedRect().adjusted(-2, -2, 2, 2).intersected(pix.rect())
        except Exception:
            qrect = pix.rect()
        if qrect is None or qrect.isEmpty():
            return False
        before_patch = pix.copy(qrect)

        color = QColor(str(getattr(self.main, "final_paint_color", "#FFFFFF") or "#FFFFFF"))
        if not color.isValid():
            color = QColor("#FFFFFF")
        opacity = max(1, min(100, int(getattr(self.main, "final_paint_opacity", 100) or 100)))
        color.setAlpha(int(round(255 * opacity / 100)))
        p = QPainter(pix)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.fillPath(region_path, QBrush(color))
        p.end()
        after_patch = pix.copy(qrect)
        target_item.setPixmap(pix)
        if target_item is self.final_paint_above_item:
            self.final_paint_above_img = pix.toImage()
        else:
            self.final_paint_img = pix.toImage()

        try:
            record = {
                "_brush_record": True,
                "target_item": target_item,
                "kind": "final_paint",
                "patches": [{"rect": qrect, "before": before_patch, "after": after_patch}],
            }
            if hasattr(self.main, "undo_push_paint_record"):
                self.main.undo_push_paint_record(self, record, kind="final_paint", reason="영역 페인팅", max_history=80)
            else:
                self.history.append(record)
                if len(self.history) > 80:
                    self.history.pop(0)
                self.redo_history.clear()
                self._append_paint_history_undo_marker("final_paint", "영역 페인팅")
        except Exception:
            pass
        return True

    def apply_magic_wand_final_paint(self, mask):
        """요술봉 선택 영역을 현재 최종 페인팅 색상으로 칠한다."""
        if mask is None:
            return False
        target_item = self.final_paint_above_item if getattr(self.main, "final_paint_above_text", False) else self.final_paint_item
        if target_item is None:
            return False
        pix = target_item.pixmap()
        if pix.isNull():
            return False
        try:
            m = (mask.astype(np.uint8) > 0).astype(np.uint8) * 255
        except Exception:
            return False
        h, w = m.shape[:2]
        if w != pix.width() or h != pix.height():
            try:
                m = cv2.resize(m, (pix.width(), pix.height()), interpolation=cv2.INTER_NEAREST)
                h, w = m.shape[:2]
            except Exception:
                return False
        ys, xs = np.where(m > 0)
        if xs.size == 0 or ys.size == 0:
            return False
        qrect = QRect(int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)).adjusted(-2, -2, 2, 2).intersected(pix.rect())
        if qrect.isEmpty():
            return False
        before_patch = pix.copy(qrect)

        color = QColor(str(getattr(self.main, "final_paint_color", "#FFFFFF") or "#FFFFFF"))
        if not color.isValid():
            color = QColor("#FFFFFF")
        opacity = max(1, min(100, int(getattr(self.main, "final_paint_opacity", 100) or 100)))
        color.setAlpha(int(round(255 * opacity / 100)))

        overlay = QImage(w, h, QImage.Format.Format_ARGB32)
        overlay.fill(color)
        qmask = QImage(m.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
        overlay.setAlphaChannel(qmask)

        painter = QPainter(pix)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
        painter.drawImage(0, 0, overlay)
        painter.end()

        after_patch = pix.copy(qrect)
        target_item.setPixmap(pix)
        if target_item is self.final_paint_above_item:
            self.final_paint_above_img = pix.toImage()
        else:
            self.final_paint_img = pix.toImage()
        try:
            record = {
                "_brush_record": True,
                "target_item": target_item,
                "kind": "final_paint",
                "patches": [{"rect": qrect, "before": before_patch, "after": after_patch}],
            }
            if hasattr(self.main, "undo_push_paint_record"):
                self.main.undo_push_paint_record(self, record, kind="final_paint", reason="요술봉 영역 칠하기", max_history=80)
            else:
                self.history.append(record)
                if len(self.history) > 80:
                    self.history.pop(0)
                self.redo_history.clear()
                self._append_paint_history_undo_marker("final_paint", "요술봉 영역 칠하기")
        except Exception:
            pass
        return True

    def _scene_rect_bounds(self):
        rect = self.scene.sceneRect()
        return max(1.0, float(rect.width())), max(1.0, float(rect.height()))

    def _norm_rect_from_scene(self, rect):
        w, h = self._scene_rect_bounds()
        x1 = max(0.0, min(w, float(rect.left())))
        y1 = max(0.0, min(h, float(rect.top())))
        x2 = max(0.0, min(w, float(rect.right())))
        y2 = max(0.0, min(h, float(rect.bottom())))
        if x2 <= x1 or y2 <= y1:
            return None
        return [x1 / w, y1 / h, x2 / w, y2 / h]

    def _norm_points_from_scene(self, points):
        w, h = self._scene_rect_bounds()
        out = []
        for pt in points or []:
            x = max(0.0, min(w, float(pt.x()))) / w
            y = max(0.0, min(h, float(pt.y()))) / h
            out.append([x, y])
        return out

    def current_ocr_region_payload(self, end_pos):
        if self.ocr_region_start is None:
            return None
        if getattr(self, "ocr_region_shape", "rect") == "rect":
            rect = QRectF(self.ocr_region_start, end_pos).normalized()
            norm_rect = self._norm_rect_from_scene(rect)
            if not norm_rect:
                return None
            return {"shape": "rect", "rect_norm": norm_rect}
        points = list(getattr(self, "ocr_region_points", []) or [])
        if end_pos is not None:
            points.append(end_pos)
        norm_points = self._norm_points_from_scene(points)
        if len(norm_points) < 3:
            return None
        return {"shape": "free", "points_norm": norm_points}

    def quick_ocr_rect_payload(self, end_pos):
        if self.quick_ocr_start is None:
            return None
        rect = QRectF(self.quick_ocr_start, end_pos).normalized()
        return self._norm_rect_from_scene(rect)

    def _quick_ocr_rect_changed_significantly(self, old_rect, new_rect, tolerance=0.004):
        """빠른 OCR 드래그 중 손떨림 수준의 작은 이동은 같은 영역으로 본다.

        tolerance는 정규화 좌표 기준이다. 0.004면 1000px 이미지에서 약 4px 정도라
        사용자가 영역을 유지하고 있는 상태와 새 영역으로 옮긴 상태를 적당히 가른다.
        """
        if not old_rect or not new_rect:
            return True
        try:
            old_vals = [float(x) for x in old_rect]
            new_vals = [float(x) for x in new_rect]
            if len(old_vals) != 4 or len(new_vals) != 4:
                return True
            return max(abs(a - b) for a, b in zip(old_vals, new_vals)) > float(tolerance)
        except Exception:
            return True

    def _schedule_quick_ocr_hold_check(self, end_pos):
        rect_norm = self.quick_ocr_rect_payload(end_pos)
        old_rect = copy.deepcopy(getattr(self, "quick_ocr_current_rect_norm", None))
        if not rect_norm:
            if old_rect is not None:
                self.quick_ocr_current_rect_norm = None
                self.quick_ocr_revision += 1
            return

        if old_rect is not None and not self._quick_ocr_rect_changed_significantly(old_rect, rect_norm):
            # 미세한 손떨림은 같은 영역으로 보고 기존 결과/타이머를 유지한다.
            return

        self.quick_ocr_current_rect_norm = copy.deepcopy(rect_norm)
        self.quick_ocr_revision += 1
        # 이미 인식된 결과가 있다면 새 영역을 읽는 동안에도 마우스를 떼기 전까지 유지한다.
        try:
            latest = str(getattr(self.main, "quick_ocr_latest_text", "") or "").strip()
            if latest and hasattr(self.main, "show_quick_ocr_result_popup"):
                self.main.show_quick_ocr_result_popup(latest)
        except Exception:
            pass
        try:
            self.quick_ocr_hold_timer.start(200)
        except Exception:
            pass

    def _trigger_quick_ocr_if_still_holding(self):
        if self.draw_mode != 'quick_ocr' or not getattr(self, "is_quick_ocr_drawing", False):
            return
        rect_norm = copy.deepcopy(getattr(self, "quick_ocr_current_rect_norm", None))
        if not rect_norm:
            return
        revision = int(getattr(self, "quick_ocr_revision", 0) or 0)
        if revision == int(getattr(self, "quick_ocr_last_requested_revision", -1) or -1):
            return
        self.quick_ocr_last_requested_revision = revision
        if hasattr(self.main, "run_quick_ocr_region_live"):
            self.main.run_quick_ocr_region_live(rect_norm, request_id=revision)
        elif hasattr(self.main, "run_quick_ocr_region"):
            self.main.run_quick_ocr_region(rect_norm)

    def draw_ocr_analysis_regions(self, regions):
        self.clear_ocr_region_overlay()
        if not regions:
            return
        w, h = self._scene_rect_bounds()
        red_pen = QPen(QColor(199, 138, 144, 225), self.ui_pen_width(3), Qt.PenStyle.SolidLine)
        no_brush = QBrush(Qt.BrushStyle.NoBrush)
        label_font = QFont("Arial", self.ui_font_size(11), QFont.Weight.Bold)
        for region in regions or []:
            if not isinstance(region, dict):
                continue
            shape = str(region.get("shape") or "rect")
            item = None
            label_x = 0.0
            label_y = 0.0
            if shape == "free":
                pts = region.get("points_norm") or []
                if len(pts) < 3:
                    continue
                path = QPainterPath()
                try:
                    first = pts[0]
                    path.moveTo(float(first[0]) * w, float(first[1]) * h)
                    label_x = float(first[0]) * w
                    label_y = float(first[1]) * h
                    for pt in pts[1:]:
                        path.lineTo(float(pt[0]) * w, float(pt[1]) * h)
                    path.closeSubpath()
                except Exception:
                    continue
                item = self.scene.addPath(path, red_pen, no_brush)
            else:
                r = region.get("rect_norm") or []
                if len(r) < 4:
                    continue
                try:
                    x1, y1, x2, y2 = [float(v) for v in r[:4]]
                except Exception:
                    continue
                rect = QRectF(x1 * w, y1 * h, (x2 - x1) * w, (y2 - y1) * h).normalized()
                if rect.width() < 1 or rect.height() < 1:
                    continue
                label_x, label_y = rect.left(), rect.top()
                item = self.scene.addRect(rect, red_pen, no_brush)
            if item is not None:
                item.setZValue(84)
                item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                self.ocr_region_overlay_items.append(item)

                text = self.scene.addText("OCR 분석 영역", label_font)
                text.setDefaultTextColor(Qt.GlobalColor.black)
                br = text.boundingRect()
                pad_x, pad_y = self.ui_pad(5.0), self.ui_pad(2.0)
                label_bg = self.scene.addRect(
                    QRectF(label_x, max(0.0, label_y - br.height() - pad_y * 2), br.width() + pad_x * 2, br.height() + pad_y * 2),
                    QPen(Qt.PenStyle.NoPen),
                    QBrush(QColor(165, 245, 120, 235))
                )
                label_bg.setZValue(85)
                label_bg.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                text.setPos(label_bg.rect().left() + pad_x, label_bg.rect().top() + pad_y)
                text.setZValue(86)
                text.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
                self.ocr_region_overlay_items.append(label_bg)
                self.ocr_region_overlay_items.append(text)

    def clear_magic_wand_preview(self):
        if not hasattr(self, "magic_preview_items"):
            self.magic_preview_items = []
        for item in list(self.magic_preview_items):
            try:
                self.scene.removeItem(item)
            except Exception:
                pass
        self.magic_preview_items = []

    def draw_magic_wand_preview(self, mask):
        self.clear_magic_wand_preview()
        if mask is None:
            return

        import cv2
        _, bin_mask = cv2.threshold(mask, 10, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(bin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        pen = QPen(QColor(255, 230, 0), self.ui_pen_width(2), Qt.PenStyle.SolidLine)
        brush = QBrush(Qt.BrushStyle.NoBrush)

        for cnt in contours:
            if cnt is None or len(cnt) < 2:
                continue

            path = QPainterPath()
            first = cnt[0][0]
            path.moveTo(float(first[0]), float(first[1]))

            for p in cnt[1:]:
                x, y = p[0]
                path.lineTo(float(x), float(y))

            path.closeSubpath()
            item = self.scene.addPath(path, pen, brush)
            item.setZValue(35)
            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.magic_preview_items.append(item)

    def set_mask_overlay_layer(self, mask, color):
        """Add/replace only the mask overlay on the current base layer.

        This is the lightweight path for same-page tab switching. Unlike
        set_overlay(), it does not clear the whole scene or rebuild the base
        image.
        """
        try:
            if self.user_mask_item is not None:
                self.scene.removeItem(self.user_mask_item)
        except Exception:
            pass
        self.user_mask_item = None
        self.user_mask_img = None

        rect = self.scene.sceneRect()
        w = int(rect.width())
        h = int(rect.height())
        if w <= 0 or h <= 0:
            try:
                base_item = getattr(self, "_layer_base_item", None)
                if base_item is not None and not base_item.pixmap().isNull():
                    w = int(base_item.pixmap().width())
                    h = int(base_item.pixmap().height())
            except Exception:
                pass
        if w <= 0 or h <= 0:
            return False

        self.user_mask_img = QImage(w, h, QImage.Format.Format_ARGB32)
        self.user_mask_img.fill(Qt.GlobalColor.transparent)

        if mask is not None:
            try:
                m = mask
                if getattr(m, "ndim", 2) == 3:
                    import cv2
                    m = cv2.cvtColor(m, cv2.COLOR_RGB2GRAY)
                m_qimg = self._np2pix(m).toImage().convertToFormat(QImage.Format.Format_Grayscale8)
                if m_qimg.width() != w or m_qimg.height() != h:
                    m_qimg = m_qimg.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.FastTransformation)
                target_color_img = QImage(w, h, QImage.Format.Format_ARGB32)
                target_color_img.fill(color)
                target_color_img.setAlphaChannel(m_qimg)
                painter = QPainter(self.user_mask_img)
                painter.drawImage(0, 0, target_color_img)
                painter.end()
            except Exception:
                pass

        self.user_mask_item = self.scene.addPixmap(QPixmap.fromImage(self.user_mask_img))
        self.user_mask_item.setZValue(10)
        self.user_mask_item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        try:
            self._set_layer_tag(self.user_mask_item, "mask_overlay")
        except Exception:
            pass
        return True

    def set_user_mask_np(self, mask, color):
        if self.user_mask_item is None or mask is None:
            return

        if mask.ndim == 3:
            import cv2
            mask = cv2.cvtColor(mask, cv2.COLOR_RGB2GRAY)

        h, w = mask.shape[:2]
        color_img = QImage(w, h, QImage.Format.Format_ARGB32)
        color_img.fill(color)

        qmask = QImage(mask.data, w, h, w, QImage.Format.Format_Grayscale8).copy()
        color_img.setAlphaChannel(qmask)

        pix = QPixmap.fromImage(color_img)
        self.user_mask_item.setPixmap(pix)
        self.user_mask_img = color_img

    def get_mask_np(self):
        if not self.user_mask_item:
            return None

        # 화면 표시용 색상값이 아니라, ARGB32의 알파 채널을 직접 읽는다.
        # 그래야 페이지 이동/자동저장 반복 시 마스크가 연해지지 않는다.
        qimg = self.user_mask_item.pixmap().toImage().convertToFormat(
            QImage.Format.Format_ARGB32
        )

        w = qimg.width()
        h = qimg.height()
        bytes_per_line = qimg.bytesPerLine()

        ptr = qimg.bits()
        ptr.setsize(qimg.sizeInBytes())

        buf = np.frombuffer(ptr, dtype=np.uint8)

        # Format_ARGB32는 한 픽셀당 4바이트.
        # Windows/little-endian 환경에서는 메모리 순서가 B, G, R, A라서 3번 채널이 alpha.
        arr = buf.reshape((h, bytes_per_line // 4, 4))
        alpha = arr[:, :w, 3].copy()

        # 저장용 마스크는 반투명값을 그대로 저장하지 말고 0/255로 고정
        mask = np.where(alpha > 10, 255, 0).astype(np.uint8)

        return mask

    def _np2pix(self, np_img):
        if isinstance(np_img, QImage):
            return QPixmap.fromImage(np_img)
        if np_img.ndim == 2:
            h, w = np_img.shape
            q = QImage(np_img.data, w, h, w, QImage.Format.Format_Grayscale8)
            return QPixmap.fromImage(q)
        if np_img.ndim == 3:
            h, w, c = np_img.shape
            if c == 3:
                q = QImage(np_img.data, w, h, c * w, QImage.Format.Format_RGB888).rgbSwapped()
            elif c == 4:
                q = QImage(np_img.data, w, h, c * w, QImage.Format.Format_RGBA8888)
            else:
                return QPixmap()
            return QPixmap.fromImage(q)
        return QPixmap()

    def clear_paste_preview(self):
        if not hasattr(self, "paste_preview_items"):
            self.paste_preview_items = []
        for item in list(self.paste_preview_items):
            try:
                if item.scene() is not None:
                    self.scene.removeItem(item)
            except Exception:
                pass
        self.paste_preview_items = []

    def show_paste_preview(self, data_items, scene_pos):
        """Ctrl+V 후 실제 붙여넣기 전, 커서 위치에 반투명 미리보기만 표시한다."""
        self.clear_paste_preview()

        if not data_items:
            return

        try:
            px, py = float(scene_pos.x()), float(scene_pos.y())
        except Exception:
            px, py = 0.0, 0.0

        src_items = [copy.deepcopy(d) for d in (data_items or []) if isinstance(d, dict)]
        if not src_items:
            return

        try:
            base_x, base_y = self.main.text_clipboard_visible_anchor(src_items)
        except Exception:
            first = src_items[0].get('rect') or [0, 0, 1, 1]
            try:
                base_x = float(first[0]) + float(src_items[0].get('x_off', 0) or 0)
                base_y = float(first[1]) + float(src_items[0].get('y_off', 0) or 0)
            except Exception:
                base_x, base_y = 0.0, 0.0
        try:
            px, py = self.main.text_clipboard_paste_origin_from_cursor(src_items, scene_pos)
        except Exception:
            px -= 263.0
            py -= 83.0

        for d in src_items:
            rect = list(d.get('rect') or [0, 0, 260, 80])
            while len(rect) < 4:
                rect.append(1)

            try:
                old_x = float(rect[0]) + float(d.get('x_off', 0) or 0)
                old_y = float(rect[1]) + float(d.get('y_off', 0) or 0)
                dx = old_x - base_x
                dy = old_y - base_y
                rect[0] = int(round(px + dx))
                rect[1] = int(round(py + dy))
            except Exception:
                rect[0] = int(round(px))
                rect[1] = int(round(py))

            d['rect'] = [int(rect[0]), int(rect[1]), max(1, int(rect[2])), max(1, int(rect[3]))]
            d['x_off'] = 0
            d['y_off'] = 0
            d['manual_text_rect'] = True
            d['_paste_preview'] = True

            item = TypesettingItem(
                d,
                self.main.cb_font.currentFont().family(),
                self.main.sb_font_size.value(),
                self.main.sb_strk.value(),
                None,
                text_color=getattr(self.main, "default_text_color", "#000000"),
                stroke_color=getattr(self.main, "default_stroke_color", "#FFFFFF"),
                align=getattr(self.main, "default_align", "center"),
            )
            item.main_window = self.main
            item.is_paste_preview = True
            item.setOpacity(0.55)
            item.setZValue(95)
            item.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            try:
                item.setFlag(item.GraphicsItemFlag.ItemIsSelectable, False)
                item.setFlag(item.GraphicsItemFlag.ItemIsMovable, False)
            except Exception:
                pass

            self.scene.addItem(item)
            self.paste_preview_items.append(item)


    def _analysis_toggle_target_at(self, scene_pos):
        """분석도에서 단일 클릭으로 ON/OFF 토글할 대상 박스를 찾는다.

        QGraphicsItem 이벤트만 믿으면 텍스트 번호 라벨이나 ScrollHandDrag 상태에 따라
        첫 클릭이 뷰 쪽으로 흘러가서 더블클릭처럼 느껴지는 경우가 생길 수 있다.
        그래서 분석도에서는 뷰 레벨에서 먼저 hit-test를 수행해 단일 클릭을 확정 처리한다.
        """
        if getattr(self.main, "cb_mode", None) is None or self.main.cb_mode.currentIndex() != 1:
            return None
        try:
            curr = self.main.data.get(self.main.idx)
            rows = curr.get('data', []) if curr else []
        except Exception:
            return None
        if not rows:
            return None

        try:
            base_w = int(getattr(self.main, "analysis_number_box_width", 40) or 40)
        except Exception:
            base_w = 40
        bg_h = max(18, int(base_w * 0.9))

        x0 = float(scene_pos.x())
        y0 = float(scene_pos.y())

        # 위에 그려진 번호 박스/나중에 추가된 박스가 우선 잡히도록 역순으로 검사한다.
        for d in reversed(rows):
            try:
                x, y, w, h = d['rect']
            except Exception:
                continue

            # 텍스트 본체 박스
            if x <= x0 <= x + w and y <= y0 <= y + h:
                return d

            # 번호 라벨 박스. draw_static_boxes와 같은 계산을 사용한다.
            id_str = str(d.get('id', ''))
            bg_w = max(20, base_w + (len(id_str) - 1) * max(8, int(base_w * 0.4)))
            bx, by = x, y - bg_h
            if by < 0:
                by = y
            if bx <= x0 <= bx + bg_w and by <= y0 <= by + bg_h:
                return d
        return None

    def contextMenuEvent(self, e):
        if (
            getattr(self.main, "cb_mode", None) is not None
            and self.main.cb_mode.currentIndex() == 4
        ):
            scene_pos = self.mapToScene(e.pos())
            clicked = self.itemAt(e.pos())

            # 위쪽 페인팅 레이어/픽스맵 등이 itemAt으로 잡혀도,
            # 같은 위치의 텍스트 객체를 우선 찾는다.
            text_item = clicked if isinstance(clicked, TypesettingItem) and not getattr(clicked, "is_paste_preview", False) else None
            if text_item is None:
                for item in self.scene.items(scene_pos):
                    if isinstance(item, TypesettingItem) and not getattr(item, "is_paste_preview", False):
                        text_item = item
                        break

            if text_item is not None:
                self.main.show_final_text_context_menu(text_item, e.globalPos(), scene_pos)
            else:
                self.main.show_final_background_context_menu(e.globalPos(), scene_pos)

            e.accept()
            return

        super().contextMenuEvent(e)

    def mousePressEvent(self, e):
        # 분석도에서는 영역/번호 라벨을 한 번 클릭하면 즉시 사용 여부를 토글한다.
        # 이 처리는 분석도에만 한정해 마스크 편집/최종 식질 클릭 동작에는 영향을 주지 않는다.
        if e.button() == Qt.MouseButton.LeftButton:
            target = self._analysis_toggle_target_at(self.mapToScene(e.pos()))
            if target is not None:
                self.main.toggle_check_from_box(target)
                e.accept()
                return


        # Final tab eyedropper must win over text transform/move handling.
        # Otherwise Alt+click on a selected text box can be interpreted as a move.
        if (
            e.button() == Qt.MouseButton.LeftButton
            and getattr(self.main, "cb_mode", None) is not None
            and self.main.cb_mode.currentIndex() == 4
            and e.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
            pt = self.mapToScene(e.pos())
            self.main.pick_final_paint_color_from_scene(int(pt.x()), int(pt.y()), global_pos=e.globalPosition().toPoint())
            e.accept()
            return

        if (
            e.button() == Qt.MouseButton.LeftButton
            and self._is_final_move_mode()
            and not (e.modifiers() & Qt.KeyboardModifier.AltModifier)
        ):
            pt = self.mapToScene(e.pos())
            raster_item = self._raster_text_item_at(pt)
            if raster_item is not None:
                if self._begin_raster_text_view_drag(raster_item, pt, e):
                    e.accept()
                    return
            else:
                try:
                    if self._final_text_hit_debug_enabled():
                        clicked = self.itemAt(e.pos())
                        clicked_name = type(clicked).__name__ if clicked is not None else 'None'
                        stack = []
                        for item in self.scene.items(pt):
                            stack.append(f"{type(item).__name__}:z={item.zValue()}")
                        self._log_final_text_hit_debug(f"🔎 객체 텍스트 선택 실패: itemAt={clicked_name}, stack={', '.join(stack[:8])}")
                except Exception:
                    pass

        if getattr(self.main, "cb_mode", None) is not None and self.main.cb_mode.currentIndex() == 4:
            active_transform = self.main.current_transform_data_item() if hasattr(self.main, 'current_transform_data_item') else None
            if active_transform is not None:
                pt = self.mapToScene(e.pos())
                active_item = self._active_transform_item_obj()
                hit_item = self._scene_text_item_at(pt)
                active_id = active_transform.get('id')

                # 핸들/테두리/회전 핸들이 QGraphicsView 기본 hit-test에 안 잡히는 경우를 직접 처리한다.
                if active_item is not None and e.button() == Qt.MouseButton.LeftButton:
                    local = active_item.mapFromScene(pt)
                    if active_item.data.get('_skew_mode', False):
                        action = active_item.skew_action_at(local)
                        if action and active_item.begin_skew_action(action, local, pt):
                            self._active_transform_item = active_item
                            self.setCursor(self._cursor_for_transform_action(action))
                            e.accept()
                            return
                    elif active_item.data.get('_trapezoid_mode', False):
                        action = active_item.trapezoid_action_at(local)
                        if action and active_item.begin_trapezoid_action(action, local, pt):
                            self._active_transform_item = active_item
                            self.setCursor(self._cursor_for_transform_action(action))
                            e.accept()
                            return
                    elif active_item.data.get('_arc_mode', False):
                        action = active_item.arc_action_at(local)
                        if not action:
                            action = active_item.create_or_replace_arc_handle_at(local)
                        if action and active_item.begin_arc_action(action, local, pt):
                            self._active_transform_item = active_item
                            self.setCursor(self._cursor_for_transform_action(action))
                            e.accept()
                            return
                    else:
                        action = active_item.transform_action_at(local)

                        if e.modifiers() & Qt.KeyboardModifier.AltModifier:
                            hit_pad = active_item._guide_pad(10.0) if hasattr(active_item, "_guide_pad") else 10.0
                            if active_item.transform_rect().adjusted(-hit_pad, -hit_pad, hit_pad, hit_pad).contains(local):
                                action = 'move'

                        if action:
                            if active_item.begin_transform_action(action, local, pt):
                                self._active_transform_item = active_item
                                self.setCursor(self._cursor_for_transform_action(action))
                                e.accept()
                                return

                if (
                    e.button() == Qt.MouseButton.LeftButton
                    and not (e.modifiers() & Qt.KeyboardModifier.AltModifier)
                ):
                    if hit_item is None or hit_item.data.get('id') != active_id:
                        self.main.end_active_text_transform(refresh=True)
                        e.accept()
                        return

        if self.draw_mode == 'paste_text' and e.button() == Qt.MouseButton.LeftButton:
            if getattr(self.main, "cb_mode", None) is not None and self.main.cb_mode.currentIndex() == 4:
                pt = self.mapToScene(e.pos())
                self.main.finish_text_paste_at(pt)
                return

        if self.draw_mode == 'final_text' and e.button() == Qt.MouseButton.LeftButton:
            if getattr(self.main, "cb_mode", None) is not None and self.main.cb_mode.currentIndex() == 4:
                # 텍스트 작성 중에는 새 텍스트 박스를 또 만들지 않는다.
                # 편집기 내부 클릭은 커서 이동으로 넘기고, 편집기 밖 클릭은 현재 텍스트 작성 완료만 한다.
                editor = getattr(self.main, "inline_text_editor", None)
                if editor is not None:
                    clicked = self.itemAt(e.pos())
                    if clicked is editor:
                        super().mousePressEvent(e)
                    else:
                        self.main.finish_inline_text_edit(commit=True, refresh=True)
                    return

                pt = self.mapToScene(e.pos())
                hit_item = self._scene_text_item_at(pt)
                if hit_item is not None:
                    # 텍스트 도구가 켜진 상태에서도 기존 텍스트를 바로 선택/드래그 이동한다.
                    # 빈 곳 클릭만 새 텍스트 생성으로 사용한다.
                    try:
                        super().mousePressEvent(e)
                    except Exception:
                        try:
                            if not (e.modifiers() & Qt.KeyboardModifier.ControlModifier):
                                for item in self.scene.selectedItems():
                                    if isinstance(item, TypesettingItem) and item is not hit_item:
                                        item.setSelected(False)
                            hit_item.setSelected(True)
                            if hasattr(self.main, "on_scene_selection_changed"):
                                self.main.on_scene_selection_changed()
                        except Exception:
                            pass
                    e.accept()
                    return

                self.main.create_final_text_at(int(pt.x()), int(pt.y()))
                return

        if self.draw_mode == 'raster_erase' and e.button() == Qt.MouseButton.LeftButton:
            if getattr(self.main, "cb_mode", None) is None or self.main.cb_mode.currentIndex() != 4:
                e.accept()
                return
            self.is_raster_erasing = True
            self.raster_erase_start = self.mapToScene(e.pos())
            self._draw_raster_erase_preview(self.raster_erase_start)
            e.accept()
            return

        if self.draw_mode == 'area_paint' and e.button() == Qt.MouseButton.LeftButton:
            mode = self.main.cb_mode.currentIndex() if getattr(self.main, "cb_mode", None) is not None else 4
            if mode not in (2, 3, 4):
                e.accept()
                return
            self.is_area_painting = True
            self.area_paint_start = self.mapToScene(e.pos())
            self.area_paint_points = [self.area_paint_start]
            # 영역 페인팅/마스킹은 QPixmap patch history로 Undo한다.
            # project undo를 같이 만들면 Ctrl+Z가 paint patch가 아니라 project snapshot을 먼저 타서
            # 실제 칠한 픽셀이 되돌아가지 않는 문제가 생긴다.
            self._area_paint_undo_key = None
            self._draw_area_paint_preview(self.area_paint_start)
            e.accept()
            return

        if self.draw_mode == 'ocr_region_select' and e.button() == Qt.MouseButton.LeftButton:
            self.is_ocr_region_drawing = True
            self.ocr_region_start = self.mapToScene(e.pos())
            self.ocr_region_points = [self.ocr_region_start]
            self._draw_ocr_region_preview(self.ocr_region_start)
            e.accept()
            return

        if self.draw_mode == 'quick_ocr' and e.button() == Qt.MouseButton.LeftButton:
            self.is_quick_ocr_drawing = True
            self.quick_ocr_start = self.mapToScene(e.pos())
            self.quick_ocr_current_rect_norm = None
            self.quick_ocr_revision += 1
            self.quick_ocr_last_requested_revision = -1
            try:
                self.quick_ocr_hold_timer.stop()
            except Exception:
                pass
            if hasattr(self.main, "begin_quick_ocr_drag"):
                self.main.begin_quick_ocr_drag()
            self._draw_quick_ocr_preview(self.quick_ocr_start)
            e.accept()
            return

        if self.draw_mode == 'mask_wrap' and e.button() == Qt.MouseButton.LeftButton:
            if getattr(self.main, "cb_mode", None) is None or self.main.cb_mode.currentIndex() not in (2, 3):
                e.accept()
                return
            self.is_mask_wrapping = True
            self.mask_wrap_start = self.mapToScene(e.pos())
            self.mask_wrap_points = [self.mask_wrap_start]
            self._draw_mask_wrap_preview(self.mask_wrap_start)
            e.accept()
            return

        if self.draw_mode == 'mask_cut' and e.button() == Qt.MouseButton.LeftButton:
            if getattr(self.main, "cb_mode", None) is None or self.main.cb_mode.currentIndex() not in (2, 3):
                e.accept()
                return
            self.is_mask_cutting = True
            self.mask_cut_start = self.mapToScene(e.pos())
            self.mask_cut_points = [self.mask_cut_start]
            self._draw_mask_cut_preview(self.mask_cut_start)
            e.accept()
            return

        if self.draw_mode == 'magic_wand' and e.button() == Qt.MouseButton.LeftButton:
            pt = self.mapToScene(e.pos())
            self.main.magic_wand_pick(int(pt.x()), int(pt.y()))
            return

        if self.draw_mode and e.button() == Qt.MouseButton.LeftButton:
            self.is_mask_painting = True
            final_mode = (
                getattr(self.main, "cb_mode", None) is not None
                and self.main.cb_mode.currentIndex() == 4
                and self.draw_mode in ('draw', 'erase')
            )
            if final_mode and self.draw_mode == 'erase':
                # 최종화면 지우개는 배경 페인팅 레이어와 텍스트 객체 레이어를 같이 지나갈 수 있어야 한다.
                # 이전 방식은 첫 클릭 지점이 객체 위일 때만 객체 지우개로 전환되어,
                # 바깥에서 글자 쪽으로 긁으면 래스터 텍스트가 지워지지 않았다.
                # 이제는 지우개 스트로크 전체가 항상 객체화 텍스트도 함께 검사한다.
                pt = self.mapToScene(e.pos())
                self.is_raster_text_brush_erasing = True
                if hasattr(self.main, "erase_raster_text_brush_line"):
                    self.main.erase_raster_text_brush_line(pt, pt, self.brush_size)

            if final_mode:
                target_item = self.final_paint_above_item if getattr(self.main, "final_paint_above_text", False) else self.final_paint_item
            else:
                target_item = self.user_mask_item

            if target_item:
                self._paint_undo_key = None
                self.last_pt = self.mapToScene(e.pos())
                if final_mode:
                    color = QColor(str(getattr(self.main, "final_paint_color", "#FFFFFF") or "#FFFFFF"))
                    if not color.isValid():
                        color = QColor("#FFFFFF")
                    opacity = max(1, min(100, int(getattr(self.main, "final_paint_opacity", 100) or 100)))
                    color.setAlpha(int(round(255 * opacity / 100)))
                else:
                    idx = self.main.cb_mode.currentIndex()
                    color = QColor(0, 0, 255, 150) if idx == 3 else QColor(168, 93, 102, 140)
                try:
                    self.brush_engine.begin(target_item, self.last_pt, self.draw_mode, color, self.brush_size, final_mode=final_mode)
                except Exception:
                    pass
                try:
                    if hasattr(self.main, "undo_clear_page_redo"):
                        self.main.undo_clear_page_redo(int(getattr(self.main, 'idx', 0) or 0), reason="paint begin")
                except Exception:
                    pass
                if hasattr(self.main, "update_undo_redo_buttons"):
                    self.main.update_undo_redo_buttons()
            else:
                self.last_pt = self.mapToScene(e.pos())
            return
        elif (
            e.button() == Qt.MouseButton.LeftButton
            and getattr(self.main, "cb_mode", None) is not None
            and self.main.cb_mode.currentIndex() == 4
        ):
            # 최종 화면에서는 배경 클릭으로 기존 텍스트 선택을 지우지 않는다.
            # 단, 배경을 누른 채 드래그하면 이미지 이동은 되어야 하므로 super()는 통과시킨다.
            clicked = self.itemAt(e.pos())
            if not isinstance(clicked, TypesettingItem):
                selected = [x for x in self.scene.selectedItems() if isinstance(x, TypesettingItem)]
                self._begin_view_pan_undo()
                self.scene.blockSignals(True)
                try:
                    super().mousePressEvent(e)
                    for item in selected:
                        item.setSelected(True)
                finally:
                    self.scene.blockSignals(False)
                if selected:
                    self.main.on_scene_selection_changed()
                return

        if e.button() == Qt.MouseButton.LeftButton:
            self._begin_view_pan_undo()
        super().mousePressEvent(e)


    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.MouseButton.MiddleButton:
            # 마우스 휠 버튼 더블클릭: 현재 창/뷰포트 크기에 맞춰 이미지 전체를 최대 크기로 표시한다.
            if self.fit_image_to_current_viewport():
                e.accept()
                return

        # 분석도 박스는 단일 클릭 토글이 원칙이다.
        # 더블클릭 이벤트는 추가 토글 없이 소비해서 상태가 두 번 바뀌는 일을 막는다.
        if e.button() == Qt.MouseButton.LeftButton:
            target = self._analysis_toggle_target_at(self.mapToScene(e.pos()))
            if target is not None:
                e.accept()
                return

            if getattr(self.main, "cb_mode", None) is not None and self.main.cb_mode.currentIndex() == 4:
                active_item = self._active_transform_item_obj()
                if active_item is not None and active_item.data.get('_skew_mode', False):
                    pt = self.mapToScene(e.pos())
                    local = active_item.mapFromScene(pt)
                    action = active_item.skew_action_at(local)
                    if action:
                        current_pct = float(active_item.data.get('skew_x' if action in ('top', 'bottom') else 'skew_y', 0) or 0)
                        current_angle = math.degrees(math.atan(current_pct / 100.0))
                        angle, ok = QInputDialog.getDouble(self, "평행사변형 변형", "기울임 각도(도):", current_angle, -45.0, 45.0, 1)
                        if ok:
                            try:
                                if hasattr(self.main, 'undo_text_checkpoint'):
                                    self.main.undo_text_checkpoint('평행사변형 변형 각도 지정')
                            except Exception:
                                pass
                            active_item.set_text_skew_angle(action, angle)
                            try:
                                if hasattr(self.main, 'schedule_deferred_auto_save_project'):
                                    self.main.schedule_deferred_auto_save_project()
                                else:
                                    self.main.auto_save_project()
                                self.main.reselect_text_items([active_item.data.get('id')])
                                self.main.log(f"🔷 평행사변형 변형 각도 지정: {angle}°")
                            except Exception:
                                pass
                        e.accept()
                        return
                if active_item is not None and active_item.data.get('_trapezoid_mode', False):
                    pt = self.mapToScene(e.pos())
                    local = active_item.mapFromScene(pt)
                    action = active_item.trapezoid_action_at(local)
                    if action:
                        if action in ('top_left', 'bottom_left', 'left'):
                            side_key = 'trap_left'
                            side_name = '왼쪽'
                        elif action in ('top_right', 'bottom_right', 'right'):
                            side_key = 'trap_right'
                            side_name = '오른쪽'
                        elif action == 'top':
                            side_key = 'trap_top'
                            side_name = '위쪽'
                        else:
                            side_key = 'trap_bottom'
                            side_name = '아래쪽'
                        current_pct = int(round(float(active_item.data.get(side_key, 0) or 0)))
                        value, ok = QInputDialog.getInt(self, '사다리꼴 변형', f'{side_name} 크기(%)', current_pct, -95, 95, 1)
                        if ok:
                            try:
                                if hasattr(self.main, 'undo_text_checkpoint'):
                                    self.main.undo_text_checkpoint('사다리꼴 변형 수치 지정')
                            except Exception:
                                pass
                            if side_key == 'trap_left':
                                active_item.set_text_trapezoid_values(left_pct=value)
                            elif side_key == 'trap_right':
                                active_item.set_text_trapezoid_values(right_pct=value)
                            elif side_key == 'trap_top':
                                active_item.set_text_trapezoid_values(top_pct=value)
                            else:
                                active_item.set_text_trapezoid_values(bottom_pct=value)
                            try:
                                if hasattr(self.main, 'schedule_deferred_auto_save_project'):
                                    self.main.schedule_deferred_auto_save_project()
                                else:
                                    self.main.auto_save_project()
                                self.main.reselect_text_items([active_item.data.get('id')])
                                self.main.log(f"🔷 사다리꼴 변형 수치 지정: {side_name} {value}%")
                            except Exception:
                                pass
                        e.accept()
                        return
                if active_item is not None and active_item.data.get('_arc_mode', False):
                    pt = self.mapToScene(e.pos())
                    local = active_item.mapFromScene(pt)
                    action = active_item.arc_action_at(local)
                    if action:
                        idx = active_item._arc_index_from_action(action) if hasattr(active_item, '_arc_index_from_action') else -1
                        handles = active_item._arc_handles() if hasattr(active_item, '_arc_handles') else []
                        if 0 <= idx < len(handles):
                            handle = handles[idx]
                            side = str(handle.get('side') or '')
                            side_name = {'top':'위쪽','bottom':'아래쪽','left':'왼쪽','right':'오른쪽'}.get(side, side)
                            current_pct = int(round(float(handle.get('value', 0) or 0)))
                            value, ok = QInputDialog.getInt(self, '부채꼴 변형', f'{side_name} 제어점 휘어짐(%)', current_pct, -100, 100, 1)
                            if ok:
                                try:
                                    if hasattr(self.main, 'undo_text_checkpoint'):
                                        self.main.undo_text_checkpoint('부채꼴 변형 수치 지정')
                                except Exception:
                                    pass
                                active_item.set_text_arc_handle_value(idx, value)
                                try:
                                    if hasattr(self.main, 'schedule_deferred_auto_save_project'):
                                        self.main.schedule_deferred_auto_save_project()
                                    else:
                                        self.main.auto_save_project()
                                    self.main.reselect_text_items([active_item.data.get('id')])
                                    self.main.log(f"🔷 부채꼴 변형 수치 지정: {side_name} 제어점 {value}%")
                                except Exception:
                                    pass
                        e.accept()
                        return
        super().mouseDoubleClickEvent(e)

    def mouseMoveEvent(self, e):
        try:
            if e.buttons() and hasattr(self.main, 'note_ui_interaction_activity'):
                self.main.note_ui_interaction_activity(900)
        except Exception:
            pass
        if (
            e.buttons() & Qt.MouseButton.LeftButton
            and getattr(self.main, "cb_mode", None) is not None
            and self.main.cb_mode.currentIndex() == 4
            and e.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
            try:
                pt = self.mapToScene(e.pos())
                self.main.pick_final_paint_color_from_scene(int(pt.x()), int(pt.y()), global_pos=e.globalPosition().toPoint())
            except Exception:
                pass
            e.accept()
            return

        if self._raster_view_drag_item is not None:
            item = self._raster_view_drag_item
            try:
                pt = self.mapToScene(e.pos())
                delta = QPointF(pt) - QPointF(self._raster_view_drag_scene_press)
                item.setPos(QPointF(self._raster_view_drag_item_press) + delta)
                item.update()
                self._raster_view_drag_moved = True
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            except Exception:
                pass
            e.accept()
            return

        if self._active_transform_item is not None:
            item = self._active_transform_item
            pt = self.mapToScene(e.pos())
            try:
                if getattr(item, '_skew_action', None):
                    item.update_skew_action(item.mapFromScene(pt), pt)
                    self.setCursor(self._cursor_for_transform_action(getattr(item, '_skew_action', None)))
                elif getattr(item, '_trapezoid_action', None):
                    item.update_trapezoid_action(item.mapFromScene(pt), pt)
                    self.setCursor(self._cursor_for_transform_action(getattr(item, '_trapezoid_action', None)))
                elif getattr(item, '_arc_action', None):
                    item.update_arc_action(item.mapFromScene(pt), pt)
                    self.setCursor(self._cursor_for_transform_action(getattr(item, '_arc_action', None)))
                else:
                    item.update_transform_action(item.mapFromScene(pt), pt)
                    self.setCursor(self._cursor_for_transform_action(getattr(item, '_transform_action', None)))
            except Exception:
                pass
            e.accept()
            return

        if getattr(self.main, "cb_mode", None) is not None and self.main.cb_mode.currentIndex() == 4:
            active_item = self._active_transform_item_obj()
            if active_item is not None and (active_item.data.get('_transform_mode', False) or active_item.data.get('_skew_mode', False) or active_item.data.get('_trapezoid_mode', False) or active_item.data.get('_arc_mode', False)):
                pt = self.mapToScene(e.pos())
                local = active_item.mapFromScene(pt)
                if active_item.data.get('_skew_mode', False):
                    action = active_item.skew_action_at(local)
                elif active_item.data.get('_trapezoid_mode', False):
                    action = active_item.trapezoid_action_at(local)
                elif active_item.data.get('_arc_mode', False):
                    action = active_item.arc_action_at(local)
                else:
                    action = active_item.transform_action_at(local)
                    if e.modifiers() & Qt.KeyboardModifier.AltModifier:
                        hit_pad = active_item._guide_pad(10.0) if hasattr(active_item, "_guide_pad") else 10.0
                        if active_item.transform_rect().adjusted(-hit_pad, -hit_pad, hit_pad, hit_pad).contains(local):
                            action = 'move'
                if action:
                    self.setCursor(self._cursor_for_transform_action(action))
                else:
                    self.unsetCursor()

        if self.draw_mode == 'raster_erase' and getattr(self, "is_raster_erasing", False):
            now = self.mapToScene(e.pos())
            self._draw_raster_erase_preview(now)
            e.accept()
            return


        if self.draw_mode == 'area_paint' and getattr(self, "is_area_painting", False):
            now = self.mapToScene(e.pos())
            if getattr(self, "area_paint_shape", "rect") == "free":
                pts = getattr(self, "area_paint_points", []) or []
                if not pts:
                    self.area_paint_points = [now]
                else:
                    last = pts[-1]
                    dx = now.x() - last.x()
                    dy = now.y() - last.y()
                    if (dx * dx + dy * dy) >= 9:
                        pts.append(now)
                        self.area_paint_points = pts
            self._draw_area_paint_preview(now)
            e.accept()
            return

        if self.draw_mode == 'ocr_region_select' and getattr(self, "is_ocr_region_drawing", False):
            now = self.mapToScene(e.pos())
            if getattr(self, "ocr_region_shape", "rect") == "free":
                pts = getattr(self, "ocr_region_points", []) or []
                if not pts:
                    self.ocr_region_points = [now]
                else:
                    last = pts[-1]
                    dx = now.x() - last.x()
                    dy = now.y() - last.y()
                    if (dx * dx + dy * dy) >= 9:
                        pts.append(now)
                        self.ocr_region_points = pts
            self._draw_ocr_region_preview(now)
            e.accept()
            return

        if self.draw_mode == 'quick_ocr' and getattr(self, "is_quick_ocr_drawing", False):
            now = self.mapToScene(e.pos())
            self._draw_quick_ocr_preview(now)
            self._schedule_quick_ocr_hold_check(now)
            e.accept()
            return

        if self.draw_mode == 'ocr_region_select' and getattr(self, "is_ocr_region_drawing", False):
            end_pos = self.mapToScene(e.pos())
            payload = self.current_ocr_region_payload(end_pos)
            self.is_ocr_region_drawing = False
            self.ocr_region_start = None
            self.ocr_region_points = []
            self.clear_ocr_region_preview()
            if payload is not None and hasattr(self.main, "add_ocr_analysis_region_payload"):
                self.main.add_ocr_analysis_region_payload(payload)
            e.accept()
            return

        if self.draw_mode == 'quick_ocr' and getattr(self, "is_quick_ocr_drawing", False):
            self.is_quick_ocr_drawing = False
            self.quick_ocr_start = None
            self.quick_ocr_current_rect_norm = None
            try:
                self.quick_ocr_hold_timer.stop()
            except Exception:
                pass
            self.clear_quick_ocr_preview()
            if hasattr(self.main, "finish_quick_ocr_drag"):
                self.main.finish_quick_ocr_drag()
            e.accept()
            return

        if self.draw_mode == 'mask_wrap' and getattr(self, "is_mask_wrapping", False):
            now = self.mapToScene(e.pos())
            if getattr(self, "mask_wrap_shape", "rect") == "free":
                pts = getattr(self, "mask_wrap_points", []) or []
                if not pts:
                    self.mask_wrap_points = [now]
                else:
                    last = pts[-1]
                    dx = now.x() - last.x()
                    dy = now.y() - last.y()
                    if (dx * dx + dy * dy) >= 9:
                        pts.append(now)
                        self.mask_wrap_points = pts
            self._draw_mask_wrap_preview(now)
            e.accept()
            return

        if self.draw_mode == 'mask_cut' and getattr(self, "is_mask_cutting", False):
            now = self.mapToScene(e.pos())
            if getattr(self, "mask_cut_shape", "rect") == "free":
                pts = getattr(self, "mask_cut_points", []) or []
                if not pts:
                    self.mask_cut_points = [now]
                else:
                    last = pts[-1]
                    dx = now.x() - last.x()
                    dy = now.y() - last.y()
                    if (dx * dx + dy * dy) >= 9:
                        pts.append(now)
                        self.mask_cut_points = pts
            self._draw_mask_cut_preview(now)
            e.accept()
            return

        if (
            self.draw_mode == 'paste_text'
            and getattr(self.main, "cb_mode", None) is not None
            and self.main.cb_mode.currentIndex() == 4
        ):
            self.show_paste_preview(getattr(self.main, "text_clipboard", []), self.mapToScene(e.pos()))
            return

        if self.draw_mode == 'erase' and getattr(self, "is_raster_text_brush_erasing", False) and self.last_pt:
            now = self.mapToScene(e.pos())
            if hasattr(self.main, "erase_raster_text_brush_line"):
                self.main.erase_raster_text_brush_line(self.last_pt, now, self.brush_size)
            # 여기서 return하지 않는다. 같은 스트로크가 기존 최종 페인팅 레이어도
            # 계속 지울 수 있어야 지우개 동작이 자연스럽다. last_pt 갱신은 아래
            # 일반 draw/erase 처리에서 한 번만 한다.

        if self.draw_mode in ('draw', 'erase') and self.last_pt:
            now = self.mapToScene(e.pos())
            try:
                if getattr(self, "brush_engine", None) is not None and self.brush_engine.active:
                    self.brush_engine.extend(now)
                    self.last_pt = now
                    e.accept()
                    return
            except Exception:
                pass

        # 아무 버튼도 누르지 않은 단순 마우스 이동은 QGraphicsScene hover/hit-test를 깨우지 않는다.
        # 큰 텍스트 path가 많은 최종결과 탭에서 이 super() 호출이 마우스 이동 렉의 주범이 될 수 있다.
        if e.buttons() == Qt.MouseButton.NoButton and self.draw_mode is None:
            e.accept()
            return

        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            try:
                if hasattr(self.main, '_hide_eyedropper_color_feedback'):
                    self.main._hide_eyedropper_color_feedback()
            except Exception:
                pass

        if self._raster_view_drag_item is not None:
            self._finish_raster_text_view_drag()
            e.accept()
            return

        if self._active_transform_item is not None:
            try:
                if getattr(self._active_transform_item, '_transform_action', None):
                    self._active_transform_item.finish_transform_action()
                elif getattr(self._active_transform_item, '_skew_action', None):
                    self._active_transform_item.finish_skew_action()
                elif getattr(self._active_transform_item, '_trapezoid_action', None):
                    self._active_transform_item.finish_trapezoid_action()
                elif getattr(self._active_transform_item, '_arc_action', None):
                    self._active_transform_item.finish_arc_action()
            except Exception:
                pass
            self._active_transform_item = None
            self.unsetCursor()
            e.accept()
            return

        if self.draw_mode == 'erase' and getattr(self, "is_raster_text_brush_erasing", False):
            self.is_raster_text_brush_erasing = False
            if hasattr(self.main, "finish_raster_text_brush_erase"):
                self.main.finish_raster_text_brush_erase()
            # return하지 않는다. 같은 지우개 스트로크에서 일반 최종 페인팅 레이어도
            # 지웠다면 아래 was_painting 정리/Undo 확정까지 같이 지나가야 한다.


        if self.draw_mode == 'raster_erase' and getattr(self, "is_raster_erasing", False):
            end_pos = self.mapToScene(e.pos())
            rect = QRectF(self.raster_erase_start, end_pos).normalized() if self.raster_erase_start is not None else QRectF()
            self.is_raster_erasing = False
            self.raster_erase_start = None
            self.clear_raster_erase_preview()
            if hasattr(self.main, "apply_raster_text_erase_rect"):
                self.main.apply_raster_text_erase_rect(rect)
            try:
                self.main.set_tool(None)
            except Exception:
                self.draw_mode = None
            e.accept()
            return

        if self.draw_mode == 'area_paint' and getattr(self, "is_area_painting", False):
            end_pos = self.mapToScene(e.pos())
            self.is_area_painting = False
            applied = self._apply_area_paint_rect(end_pos)
            self.area_paint_start = None
            self.area_paint_points = []
            self.clear_area_paint_preview()
            if applied:
                mode = self.main.cb_mode.currentIndex() if getattr(self.main, "cb_mode", None) is not None else 4
                if hasattr(self.main, "undo_commit_paint_layer"):
                    self.main.undo_commit_paint_layer("mask" if mode in (2, 3) else "final_paint", delay_ms=1200)
                elif hasattr(self.main, "schedule_deferred_view_layer_commit"):
                    self.main.schedule_deferred_view_layer_commit("mask" if mode in (2, 3) else "final_paint", delay_ms=1200)
            self._area_paint_undo_key = None
            e.accept()
            return

        if self.draw_mode == 'ocr_region_select' and getattr(self, "is_ocr_region_drawing", False):
            end_pos = self.mapToScene(e.pos())
            if getattr(self, "ocr_region_shape", "rect") == "free":
                pts = getattr(self, "ocr_region_points", []) or []
                if not pts:
                    self.ocr_region_points = [end_pos]
                else:
                    last = pts[-1]
                    dx = end_pos.x() - last.x()
                    dy = end_pos.y() - last.y()
                    if (dx * dx + dy * dy) >= 9:
                        pts.append(end_pos)
                        self.ocr_region_points = pts
            payload = self.current_ocr_region_payload(end_pos)
            self.is_ocr_region_drawing = False
            self.ocr_region_start = None
            self.ocr_region_points = []
            self.clear_ocr_region_preview()
            if payload is not None and hasattr(self.main, "add_ocr_analysis_region_payload"):
                self.main.add_ocr_analysis_region_payload(payload)
            e.accept()
            return

        if self.draw_mode == 'quick_ocr' and getattr(self, "is_quick_ocr_drawing", False):
            self.is_quick_ocr_drawing = False
            self.quick_ocr_start = None
            self.quick_ocr_current_rect_norm = None
            try:
                self.quick_ocr_hold_timer.stop()
            except Exception:
                pass
            self.clear_quick_ocr_preview()
            if hasattr(self.main, "finish_quick_ocr_drag"):
                self.main.finish_quick_ocr_drag()
            e.accept()
            return

        if self.draw_mode == 'mask_wrap' and getattr(self, "is_mask_wrapping", False):
            end_pos = self.mapToScene(e.pos())
            region = self._mask_wrap_region_np(end_pos)
            self.is_mask_wrapping = False
            self.mask_wrap_start = None
            self.mask_wrap_points = []
            self.clear_mask_wrap_preview()
            if region is not None and hasattr(self.main, "apply_mask_wrapping"):
                self.main.apply_mask_wrapping(region)
            e.accept()
            return

        if self.draw_mode == 'mask_cut' and getattr(self, "is_mask_cutting", False):
            end_pos = self.mapToScene(e.pos())
            region = self._mask_cut_region_np(end_pos)
            self.is_mask_cutting = False
            self.mask_cut_start = None
            self.mask_cut_points = []
            self.clear_mask_cut_preview()
            if region is not None and hasattr(self.main, "apply_mask_cutting"):
                self.main.apply_mask_cutting(region)
            e.accept()
            return

        was_painting = self.is_mask_painting
        self.is_mask_painting = False
        self.last_pt = None

        if was_painting:
            try:
                if getattr(self, "brush_engine", None) is not None and self.brush_engine.active:
                    self.brush_engine.commit()
                elif self._stroke_preview_path is not None:
                    self._commit_stroke_preview_to_layer()
            except Exception:
                pass
            if getattr(self.main, "cb_mode", None) is not None and self.main.cb_mode.currentIndex() == 4:
                if hasattr(self.main, "undo_commit_paint_layer"):
                    self.main.undo_commit_paint_layer("final_paint", delay_ms=1200)
                elif hasattr(self.main, "schedule_deferred_view_layer_commit"):
                    self.main.schedule_deferred_view_layer_commit("final_paint", delay_ms=1200)
                elif hasattr(self.main, "on_final_paint_edited"):
                    self.main.on_final_paint_edited()
            elif self.user_mask_item:
                if hasattr(self.main, "undo_commit_paint_layer"):
                    self.main.undo_commit_paint_layer("mask", delay_ms=1200)
                elif hasattr(self.main, "schedule_deferred_view_layer_commit"):
                    self.main.schedule_deferred_view_layer_commit("mask", delay_ms=1200)
                elif hasattr(self.main, "on_view_mask_edited"):
                    self.main.on_view_mask_edited()
            self._paint_undo_key = None

        super().mouseReleaseEvent(e)
        self._finish_view_pan_undo()
        

    def wheelEvent(self, e):
        try:
            if hasattr(self.main, 'note_ui_interaction_activity'):
                self.main.note_ui_interaction_activity(1200)
        except Exception:
            pass
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            # 확대/축소는 같은 페이지 내부 ViewUndo로 묶는다.
            # 연속 휠 입력은 하나의 Ctrl+Z 단계가 되도록 coalesce한다.
            try:
                if not self._view_undo_is_suppressed() and hasattr(self.main, "begin_coalesced_view_undo"):
                    self.main.begin_coalesced_view_undo("화면 확대/축소", delay_ms=500)
            except Exception:
                pass
            self._begin_view_interaction_fast_path('zoom', delay_ms=180)
            factor = 1.25 if e.angleDelta().y() > 0 else 0.8
            self._view_fast_path_log('VIEW_FAST_PATH_ZOOM', factor=float(factor), delta=int(e.angleDelta().y()))
            self.scale(factor, factor)
            try:
                if hasattr(self.main, "remember_current_view_state"):
                    self.main.remember_current_view_state()
                if hasattr(self.main, "schedule_source_compare_sync"):
                    self.main.schedule_source_compare_sync(220)
            except Exception:
                pass
            e.accept()
            return

        # 일반 휠 스크롤도 사용자의 보기 조작이다. Ctrl+Z 타임라인에
        # "화면 이동"으로 묶어 넣되, 연속 휠은 하나의 Undo 단계로 합친다.
        try:
            if hasattr(self.main, "begin_coalesced_view_undo"):
                self.main.begin_coalesced_view_undo("화면 이동", delay_ms=500)
        except Exception:
            pass
        self._begin_view_interaction_fast_path('wheel_scroll', delay_ms=160)
        self._view_fast_path_log('VIEW_FAST_PATH_SCROLL', source='wheel', delta=int(e.angleDelta().y()))
        super().wheelEvent(e)
        try:
            if hasattr(self.main, "remember_current_view_state"):
                self.main.remember_current_view_state()
            if hasattr(self.main, "schedule_source_compare_sync"):
                self.main.schedule_source_compare_sync(180)
        except Exception:
            pass

import copy
import os
import threading

from PyQt6.QtCore import QThread, pyqtSignal

from ysb.utils.runtime_logger import (
    append_block,
    append_log,
    exception_text,
    make_log_path,
    memory_text,
)

from ysb.tools.maker_project import (
    is_maker_text_item,
    load_maker_character_prompts,
    load_maker_translation_settings,
    normalize_maker_database_translation_result,
    prepare_maker_translation_payload,
    restore_maker_translation_text,
)


SUPPORTED_BATCH_MODES = {"translate"}
UNSUPPORTED_WORKER_MESSAGE = "쯔꾸르붕이에서는 이미지 OCR/인페인팅/출력 워커를 사용하지 않습니다."


def _copy_data_list(data_list):
    return copy.deepcopy(data_list or [])


def _safe_provider_from_window(main_window):
    try:
        return main_window.cb_trans_provider.currentData() or "openai"
    except Exception:
        return "openai"


def _safe_project_dir(main_window):
    try:
        return getattr(main_window, "project_dir", None)
    except Exception:
        return None


def _safe_paths(main_window):
    try:
        return list(getattr(main_window, "paths", []) or [])
    except Exception:
        return []


def _clean_page_indices(page_indices, total):
    if page_indices is None:
        return list(range(total))
    clean_indices = []
    seen_indices = set()
    for raw_idx in page_indices:
        try:
            page_idx = int(raw_idx)
        except Exception:
            continue
        if 0 <= page_idx < total and page_idx not in seen_indices:
            clean_indices.append(page_idx)
            seen_indices.add(page_idx)
    return clean_indices or list(range(total))


class UniversalBatchWorker(QThread):
    """쯔꾸르붕이용 일괄 워커.

    3단계 정리 기준으로 일괄 작업은 번역만 남긴다.
    기존 역식붕이의 analyze/reanalyze/inpaint/export 분기는 UI·호출 경로에서 이미 막았고,
    여기서도 방어적으로 실행을 거부한다.
    """

    progress = pyqtSignal(str)
    active_item = pyqtSignal(int, str)
    finished_item = pyqtSignal(int, object)
    finished_all = pyqtSignal()

    def __init__(self, main_window, mode, page_indices=None):
        super().__init__()
        self.main = main_window
        self.mode = str(mode or "")
        self.engine = main_window.engine
        self.is_running = True
        self._item_applied_event = threading.Event()
        self._waiting_item_index = None

        self.paths = _safe_paths(main_window)
        self.page_indices = _clean_page_indices(page_indices, len(self.paths))
        self.provider = _safe_provider_from_window(main_window)
        self.project_dir = _safe_project_dir(main_window)

        try:
            self.maker_character_prompts = load_maker_character_prompts(self.project_dir) if self.project_dir else None
        except Exception:
            self.maker_character_prompts = None
        try:
            self.maker_translation_settings = load_maker_translation_settings(self.project_dir) if self.project_dir else None
        except Exception:
            self.maker_translation_settings = None

        self.batch_log_path = make_log_path(f"batch_{self.mode or 'unknown'}")
        append_log(
            self.batch_log_path,
            "TKTOOL BATCH WORKER INIT",
            mode=self.mode,
            supported=self.mode in SUPPORTED_BATCH_MODES,
            total_paths=len(self.paths),
            selected_pages=len(self.page_indices),
            selected_indices=self.page_indices[:50],
            project_dir=self.project_dir or "",
            translate_provider=self.provider,
            memory=memory_text(),
        )

    def mark_item_applied(self, page_idx=None):
        try:
            if page_idx is None or self._waiting_item_index is None or int(page_idx) == int(self._waiting_item_index):
                self._item_applied_event.set()
        except Exception:
            self._item_applied_event.set()

    def _wait_until_item_applied(self, page_idx):
        self._waiting_item_index = page_idx
        try:
            while self.is_running and not self._item_applied_event.wait(0.05):
                pass
        finally:
            self._waiting_item_index = None

    def _emit_finished_item_and_wait(self, page_idx, payload):
        self._item_applied_event.clear()
        append_log(
            self.batch_log_path,
            "FINISHED ITEM EMIT BEGIN",
            index=page_idx,
            payload_keys=list((payload or {}).keys()) if isinstance(payload, dict) else type(payload).__name__,
            memory=memory_text(),
        )
        self.finished_item.emit(page_idx, payload)
        append_log(self.batch_log_path, "FINISHED ITEM EMIT DONE", index=page_idx, memory=memory_text())
        self._wait_until_item_applied(page_idx)

    def _snapshot_page_for_translate(self, page_idx, path):
        try:
            src = (getattr(self.main, "data", {}) or {}).get(page_idx) or {}
        except Exception:
            src = {}
        return {
            "data": _copy_data_list(src.get("data", [])),
            "original_name": src.get("original_name") or os.path.basename(str(path or f"page_{page_idx + 1}")),
        }

    def _translate_page(self, page_idx, path, order_idx, total):
        curr_data = self._snapshot_page_for_translate(page_idx, path)
        base_name = curr_data.get("original_name") or os.path.basename(str(path or f"page_{page_idx + 1}"))
        prefix = f"[{order_idx + 1}/{total}]"

        self.active_item.emit(page_idx, self.mode)

        if not curr_data.get("data"):
            self.progress.emit(f"{prefix} 번역 건너뜀: 분석/대사 데이터 없음")
            self._emit_finished_item_and_wait(page_idx, {"_batch_status": "skipped", "_batch_message": "분석/대사 데이터 없음"})
            return

        self.progress.emit(f"{prefix} 번역: {base_name}")
        append_log(
            self.batch_log_path,
            "TRANSLATE ENTER",
            index=page_idx,
            provider=self.provider,
            data_count=len(curr_data.get("data") or []),
            memory=memory_text(),
        )

        new_data = _copy_data_list(curr_data.get("data", []))
        maker_items = [item for item in new_data if is_maker_text_item(item)]
        if maker_items:
            target_items = []
            for item in maker_items:
                try:
                    if not str(item.get("text") or "").strip():
                        continue
                    unit = item.get("maker_text_unit") if isinstance(item.get("maker_text_unit"), dict) else {}
                    if str((unit or {}).get("source_kind") or "").strip().lower() == "database":
                        checker = getattr(self.main, "_is_maker_database_row_translatable", None)
                        if callable(checker) and not bool(checker(item)):
                            continue
                    target_items.append(item)
                except Exception:
                    if str(item.get("text") or "").strip():
                        target_items.append(item)
        else:
            target_items = [item for item in new_data if item.get("use_inpaint", True)]
        if not target_items:
            self.progress.emit(f"{prefix} 번역 건너뜀: 번역 대상 없음")
            self._emit_finished_item_and_wait(page_idx, {"_batch_status": "skipped", "_batch_message": "번역 대상 없음"})
            return

        maker_mode = bool(maker_items)
        token_maps = []
        contexts = []
        if maker_mode:
            texts = []
            for item in target_items:
                payload = prepare_maker_translation_payload(item, self.maker_character_prompts, self.maker_translation_settings)
                texts.append(payload.get("text", ""))
                contexts.append(payload.get("context", ""))
                token_maps.append(payload.get("control_map", []))
        else:
            texts = [item.get("text", "") for item in target_items]
            contexts = None
            token_maps = [[] for _ in target_items]

        append_log(
            self.batch_log_path,
            "TRANSLATE REQUEST",
            index=page_idx,
            target_count=len(target_items),
            maker_mode=maker_mode,
            memory=memory_text(),
        )
        trans = self.engine.translate_text_batch(texts, provider=self.provider, contexts=contexts)
        trans = list(trans or [])
        append_log(self.batch_log_path, "TRANSLATE RESPONSE", index=page_idx, response_count=len(trans), memory=memory_text())

        if len(trans) != len(target_items):
            raise ValueError(f"번역 개수 불일치: 요청 {len(target_items)}개 / 응답 {len(trans)}개")

        for item, t, token_map in zip(target_items, trans, token_maps):
            translated_text = str(t) if t is not None else ""
            if maker_mode and is_maker_text_item(item):
                translated_text = restore_maker_translation_text(translated_text, token_map)
                try:
                    unit = item.get("maker_text_unit") if isinstance(item.get("maker_text_unit"), dict) else {}
                    if str((unit or {}).get("source_kind") or "").strip().lower() == "database":
                        translated_text = normalize_maker_database_translation_result(translated_text, item.get("text", ""))
                except Exception:
                    pass
                item["maker_status"] = "번역완료" if translated_text.strip() else "미번역"
            item["translated_text"] = translated_text

        self._emit_finished_item_and_wait(page_idx, {"data": new_data, "_batch_status": "done", "_batch_message": ""})
        append_log(self.batch_log_path, "TRANSLATE PAYLOAD APPLIED", index=page_idx, data_count=len(new_data or []), memory=memory_text())

    def run(self):
        if self.mode not in SUPPORTED_BATCH_MODES:
            msg = f"⛔ 쯔꾸르붕이에서는 지원하지 않는 일괄 작업입니다: {self.mode}"
            append_log(self.batch_log_path, "UNSUPPORTED BATCH MODE", mode=self.mode, memory=memory_text())
            self.progress.emit(msg)
            self.finished_all.emit()
            return

        selected_indices = list(self.page_indices)
        total = len(selected_indices)
        append_log(
            self.batch_log_path,
            "BATCH RUN START",
            mode=self.mode,
            total=total,
            selected_indices=selected_indices[:50],
            memory=memory_text(),
        )

        for order_idx, page_idx in enumerate(selected_indices):
            if not self.is_running:
                break
            if page_idx < 0 or page_idx >= len(self.paths):
                continue
            try:
                self._translate_page(page_idx, self.paths[page_idx], order_idx, total)
            except Exception as e:
                append_log(self.batch_log_path, "PAGE EXCEPTION", index=page_idx, error=repr(e), memory=memory_text())
                append_block(self.batch_log_path, "TRACEBACK", exception_text(e))
                self.progress.emit(f"[{order_idx + 1}/{total}] ❌ 에러: {e}")
                try:
                    self._emit_finished_item_and_wait(page_idx, {"_batch_status": "failed", "_batch_message": str(e)})
                except Exception:
                    pass

        append_log(self.batch_log_path, "BATCH LOOP END", mode=self.mode, running=self.is_running, memory=memory_text())
        if self.is_running:
            self.progress.emit("✅ 일괄 번역 완료!")
        else:
            self.progress.emit("⏹️ 일괄 번역 취소 요청 반영: 현재 항목 완료 후 중단")
        self.finished_all.emit()

    def stop(self):
        self.is_running = False
        self._item_applied_event.set()


class AnalysisWorker(QThread):
    """3단계 정리: 쯔꾸르붕이에서는 OCR 분석 워커를 사용하지 않는다."""

    finished = pyqtSignal(object, object, object, object)
    log = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__()
        self.cancel_requested = False

    def stop(self):
        self.cancel_requested = True

    def run(self):
        self.log.emit(f"⛔ {UNSUPPORTED_WORKER_MESSAGE}")
        self.finished.emit(None, [], None, None)


class QuickOCRWorker(QThread):
    """3단계 정리: 쯔꾸르붕이에서는 빠른 OCR 워커를 사용하지 않는다."""

    finished = pyqtSignal(str, object)
    log = pyqtSignal(str)

    def __init__(self, *args, **kwargs):
        super().__init__()

    def run(self):
        self.log.emit(f"⛔ {UNSUPPORTED_WORKER_MESSAGE}")
        self.finished.emit("", UNSUPPORTED_WORKER_MESSAGE)


class InpaintWorker(QThread):
    """3단계 정리: 쯔꾸르붕이에서는 인페인팅 워커를 사용하지 않는다."""

    finished = pyqtSignal(int, object)
    log = pyqtSignal(str)

    def __init__(self, *args, page_idx=-1, **kwargs):
        super().__init__()
        try:
            self.page_idx = int(page_idx)
        except Exception:
            self.page_idx = -1
        self.cancel_requested = False

    def stop(self):
        self.cancel_requested = True

    def run(self):
        self.log.emit(f"⛔ {UNSUPPORTED_WORKER_MESSAGE}")
        self.finished.emit(self.page_idx, b"")


class TranslationWorker(QThread):
    progress = pyqtSignal(str, int, int)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)
    canceled = pyqtSignal(object)

    def __init__(self, engine, texts, provider="openai", chunk_size=50, contexts=None):
        super().__init__()
        self.engine = engine
        self.texts = [str(t or "") for t in (texts or [])]
        self.contexts = [str(c or "") for c in (contexts or [])] if contexts is not None else None
        if self.contexts is not None and len(self.contexts) != len(self.texts):
            fixed = []
            for i in range(len(self.texts)):
                fixed.append(self.contexts[i] if i < len(self.contexts) else "")
            self.contexts = fixed
        self.provider = provider or "openai"
        try:
            self.chunk_size = max(1, min(int(chunk_size or 50), 100))
        except Exception:
            self.chunk_size = 50
        self.cancel_requested = False

    def stop(self):
        self.cancel_requested = True

    def run(self):
        total = len(self.texts)
        results = []
        try:
            if total <= 0:
                self.finished.emit([])
                return
            for start in range(0, total, self.chunk_size):
                if self.cancel_requested:
                    self.canceled.emit(results)
                    return
                end = min(total, start + self.chunk_size)
                self.progress.emit(f"번역 중: {start + 1}-{end} / {total}", start, total)
                chunk = self.texts[start:end]
                context_chunk = self.contexts[start:end] if self.contexts is not None else None
                translated = self.engine.translate_text_batch(
                    chunk,
                    provider=self.provider,
                    chunk_size=len(chunk),
                    contexts=context_chunk,
                )
                translated = list(translated or [])
                if len(translated) < len(chunk):
                    translated.extend(chunk[len(translated):])
                elif len(translated) > len(chunk):
                    translated = translated[:len(chunk)]
                results.extend(translated)
                self.progress.emit(f"번역 완료: {end} / {total}", end, total)
                if self.cancel_requested:
                    self.canceled.emit(results)
                    return
            self.finished.emit(results)
        except Exception as e:
            self.error.emit(str(e))

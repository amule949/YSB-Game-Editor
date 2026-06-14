# -*- coding: utf-8 -*-
"""Gemini Flex / Batch delayed translation status dialog.

The dialog is application-modal so the project cannot be edited while delayed
responses are being applied.  Network I/O uses QNetworkAccessManager, therefore
no request, poll, retry, or cancel path blocks the Qt UI thread.
"""

from __future__ import annotations

import heapq
import json
import threading
import time
from collections import Counter, deque
from typing import Any, Callable, Dict, List, Optional

import requests

from PyQt6.QtCore import (
    QAbstractTableModel,
    QEvent,
    QModelIndex,
    QObject,
    QTimer,
    Qt,
    QUrl,
    QUrlQuery,
    pyqtSignal,
)
from PyQt6.QtGui import QCloseEvent, QMouseEvent
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStyle,
    QStyleOptionButton,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ysb.i18n.lang_text import LANG_EN, LANG_KO, tr_ui


FINAL_STATES = {"completed", "failed", "canceled"}
ACTIVE_STATES = {"submitting", "pending", "running", "requesting", "applying"}


class GeminiChunkTableModel(QAbstractTableModel):
    COLUMNS = (
        "청크",
        "대상 범위",
        "방식",
        "상태",
        "경과 시간",
        "재시도 횟수",
        "재시도",
        "상세",
    )

    def __init__(self, rows: List[Dict[str, Any]], language: str = LANG_KO, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.rows = rows
        self.language = LANG_EN if str(language or "").lower().startswith("en") else LANG_KO

    def _tr(self, text: str, **kwargs) -> str:
        return tr_ui(text, self.language, **kwargs)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.COLUMNS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(self.COLUMNS):
            return self._tr(self.COLUMNS[section])
        if orientation == Qt.Orientation.Vertical:
            return str(section + 1)
        return None

    def _elapsed_text(self, row: Dict[str, Any]) -> str:
        started = float(row.get("started_at") or 0.0)
        if not started:
            return "-"
        ended = float(row.get("finished_at") or 0.0)
        seconds = max(0, int((ended or time.monotonic()) - started))
        if seconds < 60:
            return self._tr("{seconds}초", seconds=seconds)
        minutes, sec = divmod(seconds, 60)
        if minutes < 60:
            return self._tr("{minutes}분 {seconds}초", minutes=minutes, seconds=sec)
        hours, minutes = divmod(minutes, 60)
        return self._tr("{hours}시간 {minutes}분", hours=hours, minutes=minutes)

    def _status_text(self, code: str) -> str:
        mapping = {
            "queued": "대기",
            "submitting": "제출 중",
            "pending": "제출됨",
            "running": "처리 중",
            "requesting": "응답 대기",
            "applying": "결과 적용 중",
            "completed": "완료",
            "failed": "실패",
            "canceled": "취소됨",
        }
        return self._tr(mapping.get(str(code or ""), str(code or "")))

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.rows)):
            return None
        row = self.rows[index.row()]
        col = index.column()
        status = str(row.get("status") or "queued")

        if role == Qt.ItemDataRole.DisplayRole:
            if col == 0:
                return str(int(row.get("index", index.row())) + 1)
            if col == 1:
                start = int(row.get("start", 0)) + 1
                end = int(row.get("end", start))
                return f"{start:,}–{end:,}"
            if col == 2:
                return "Flex" if row.get("mode") == "flex" else "Batch"
            if col == 3:
                return self._status_text(status)
            if col == 4:
                return self._elapsed_text(row)
            if col == 5:
                return str(max(0, int(row.get("attempts", 0)) - 1))
            if col == 6:
                return self._tr("재시도") if status == "failed" else ""
            if col == 7:
                return str(row.get("detail") or "")

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col in (0, 1, 2, 3, 4, 5, 6):
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        if role == Qt.ItemDataRole.ToolTipRole:
            if col == 7 or status == "failed":
                return str(row.get("detail") or self._status_text(status))

        if role == Qt.ItemDataRole.UserRole:
            return row
        return None

    def update_row(self, row_index: int):
        if not (0 <= row_index < len(self.rows)):
            return
        left = self.index(row_index, 0)
        right = self.index(row_index, self.columnCount() - 1)
        self.dataChanged.emit(left, right, [])

    def update_elapsed_range(self, first_row: int, last_row: int):
        """Refresh elapsed time only for rows currently visible in the viewport.

        Off-screen rows calculate their elapsed text lazily when scrolled into
        view. This keeps the one-second timer constant-cost even for enormous
        chunk lists.
        """
        if not self.rows:
            return
        first = max(0, int(first_row))
        last = min(len(self.rows) - 1, int(last_row))
        if first > last:
            return
        active_rows = [
            i for i in range(first, last + 1)
            if str(self.rows[i].get("status") or "") in ACTIVE_STATES
        ]
        if not active_rows:
            return
        start = prev = active_rows[0]
        for row in active_rows[1:]:
            if row != prev + 1:
                self.dataChanged.emit(self.index(start, 4), self.index(prev, 4), [Qt.ItemDataRole.DisplayRole])
                start = row
            prev = row
        self.dataChanged.emit(self.index(start, 4), self.index(prev, 4), [Qt.ItemDataRole.DisplayRole])


class RetryButtonDelegate(QStyledItemDelegate):
    retryRequested = pyqtSignal(int)

    def __init__(self, language: str = LANG_KO, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.language = LANG_EN if str(language or "").lower().startswith("en") else LANG_KO

    def _is_retryable(self, index: QModelIndex) -> bool:
        row = index.data(Qt.ItemDataRole.UserRole)
        return isinstance(row, dict) and str(row.get("status") or "") == "failed"

    def paint(self, painter, option, index):
        if self._is_retryable(index):
            btn = QStyleOptionButton()
            btn.rect = option.rect.adjusted(5, 3, -5, -3)
            btn.text = tr_ui("재시도", self.language)
            btn.state = QStyle.StateFlag.State_Enabled
            if option.state & QStyle.StateFlag.State_MouseOver:
                btn.state |= QStyle.StateFlag.State_MouseOver
            QApplication.style().drawControl(QStyle.ControlElement.CE_PushButton, btn, painter)
            return
        super().paint(painter, option, index)

    def editorEvent(self, event, model, option, index):
        if not self._is_retryable(index):
            return False
        if event.type() == QEvent.Type.MouseButtonRelease and isinstance(event, QMouseEvent):
            if event.button() == Qt.MouseButton.LeftButton and option.rect.contains(event.position().toPoint()):
                self.retryRequested.emit(index.row())
                return True
        return False


class GeminiDelayedTranslationController(QObject):
    chunkChanged = pyqtSignal(int)
    translationReady = pyqtSignal(int, object)
    summaryChanged = pyqtSignal(int, int, int, int)
    allCompleted = pyqtSignal()
    canceled = pyqtSignal()

    def __init__(
        self,
        engine,
        chunks: List[Dict[str, Any]],
        *,
        mode: str,
        api_key: str,
        model: str,
        source_texts: Optional[List[str]] = None,
        source_contexts: Optional[List[str]] = None,
        language: str = LANG_KO,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.engine = engine
        self.language = LANG_EN if str(language or "").lower().startswith("en") else LANG_KO
        self.mode = "batch" if str(mode or "").lower() == "batch" else "flex"
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "").strip()
        # Keep one shared source/context list.  Chunk rows only store ranges, so
        # large jobs do not duplicate every input string a second time.
        self._source_texts = source_texts if isinstance(source_texts, list) else list(source_texts or [])
        self._source_contexts = source_contexts if isinstance(source_contexts, list) else (
            list(source_contexts or []) if source_contexts is not None else None
        )
        self.rows: List[Dict[str, Any]] = []
        for i, chunk in enumerate(chunks or []):
            row = dict(chunk or {})
            row.update({
                "index": i,
                "mode": self.mode,
                "status": "queued",
                "detail": "",
                "attempts": 0,
                "started_at": 0.0,
                "finished_at": 0.0,
                "job_name": "",
                "next_poll_at": 0.0,
            })
            self.rows.append(row)

        self._network = QNetworkAccessManager(self)
        self._reply_meta: Dict[QNetworkReply, Dict[str, Any]] = {}
        self._generation = 1
        self._canceled = False
        self._completed_emitted = False
        # Large jobs must not repeatedly scan every row on every network event.
        # Keep an O(1) state counter and O(1) submission queue instead.
        self._state_counts = Counter({"queued": len(self.rows)})
        self._queued_indices = deque(range(len(self.rows)))
        # Batch polling uses a due-time heap. Only jobs whose poll time has
        # arrived are touched, even when tens of thousands of chunks exist.
        self._batch_poll_heap: List[tuple[float, int, int]] = []
        self._poll_sequence = 0
        # API replies may finish close together, but project application must be
        # strictly serialized: one chunk is applied and acknowledged before the
        # next result is handed to the UI.  This bounds result memory and avoids
        # a burst of queued UI updates.
        self._pending_apply_results = deque()
        self._apply_in_progress = False
        self._active_apply_row = -1
        self._active_apply_results = None
        self._pump_timer = QTimer(self)
        self._pump_timer.setInterval(250)
        self._pump_timer.timeout.connect(self._pump)
        self._max_flex_requests = 3
        self._max_batch_submits = 4
        self._max_batch_polls = 8

    def _tr(self, text: str, **kwargs) -> str:
        return tr_ui(text, self.language, **kwargs)

    def start(self):
        if self._canceled:
            return
        self._pump_timer.start()
        self._emit_summary()
        self._pump()

    def _emit_summary(self):
        completed = int(self._state_counts.get("completed", 0))
        failed = int(self._state_counts.get("failed", 0))
        active = sum(int(self._state_counts.get(state, 0)) for state in ACTIVE_STATES)
        self.summaryChanged.emit(completed, failed, active, len(self.rows))
        if self.rows and completed == len(self.rows) and not self._completed_emitted:
            self._completed_emitted = True
            self._pump_timer.stop()
            self.allCompleted.emit()
            return
        # No request or poll is pending. Stop the periodic pump until a retry
        # explicitly starts it again, so a large failed list does not wake the
        # UI thread four times per second for no reason.
        if (
            not self._queued_indices
            and not self._reply_meta
            and not self._batch_poll_heap
            and not self._pending_apply_results
            and not self._apply_in_progress
        ):
            self._pump_timer.stop()

    def _texts_for_row(self, row: Dict[str, Any]) -> List[str]:
        if row.get("texts") is not None:
            return list(row.get("texts") or [])
        start = max(0, int(row.get("start", 0) or 0))
        end = max(start, int(row.get("end", start) or start))
        return self._source_texts[start:end]

    def _contexts_for_row(self, row: Dict[str, Any]):
        if row.get("contexts") is not None:
            return list(row.get("contexts") or [])
        if self._source_contexts is None:
            return None
        start = max(0, int(row.get("start", 0) or 0))
        end = max(start, int(row.get("end", start) or start))
        return self._source_contexts[start:end]

    def _set_status(self, row_index: int, status: str, detail: str = "", *, emit_summary: bool = True):
        if not (0 <= row_index < len(self.rows)):
            return
        row = self.rows[row_index]
        old_status = str(row.get("status") or "queued")
        new_status = str(status)
        if old_status != new_status:
            self._state_counts[old_status] = max(0, int(self._state_counts.get(old_status, 0)) - 1)
            self._state_counts[new_status] = int(self._state_counts.get(new_status, 0)) + 1
        row["status"] = new_status
        row["detail"] = str(detail or "")
        now = time.monotonic()
        if status in ACTIVE_STATES and not row.get("started_at"):
            row["started_at"] = now
        if status in FINAL_STATES:
            row["finished_at"] = now
        elif status == "queued":
            row["finished_at"] = 0.0
        self.chunkChanged.emit(row_index)
        if emit_summary:
            self._emit_summary()

    def _schedule_batch_poll(self, row_index: int, delay_seconds: float):
        if not (0 <= row_index < len(self.rows)):
            return
        row = self.rows[row_index]
        due = time.monotonic() + max(0.0, float(delay_seconds))
        row["next_poll_at"] = due
        self._poll_sequence += 1
        row["poll_ticket"] = self._poll_sequence
        heapq.heappush(self._batch_poll_heap, (due, self._poll_sequence, row_index))

    def retry_chunk(self, row_index: int):
        if self._canceled or not (0 <= row_index < len(self.rows)):
            return
        row = self.rows[row_index]
        if row.get("status") != "failed":
            return
        row["job_name"] = ""
        row["next_poll_at"] = 0.0
        row["started_at"] = 0.0
        row["finished_at"] = 0.0
        self._completed_emitted = False
        row["poll_ticket"] = int(row.get("poll_ticket", 0)) + 1
        self._set_status(row_index, "queued", "")
        self._queued_indices.append(row_index)
        if not self._pump_timer.isActive():
            self._pump_timer.start()
        self._pump()

    def retry_all_failed(self):
        changed = False
        for i, row in enumerate(self.rows):
            if row.get("status") == "failed":
                row["job_name"] = ""
                row["next_poll_at"] = 0.0
                row["started_at"] = 0.0
                row["finished_at"] = 0.0
                row["poll_ticket"] = int(row.get("poll_ticket", 0)) + 1
                self._set_status(i, "queued", "", emit_summary=False)
                self._queued_indices.append(i)
                changed = True
        if not changed:
            return
        self._completed_emitted = False
        self._emit_summary()
        if not self._pump_timer.isActive():
            self._pump_timer.start()
        self._pump()

    def acknowledge_applied(self, row_index: int, ok: bool, error: str = ""):
        if self._canceled or not (0 <= row_index < len(self.rows)):
            return
        if self._apply_in_progress and int(row_index) != int(self._active_apply_row):
            return
        self._apply_in_progress = False
        self._active_apply_row = -1
        try:
            if isinstance(self._active_apply_results, list):
                self._active_apply_results.clear()
        except Exception:
            pass
        self._active_apply_results = None
        if ok:
            self._set_status(row_index, "completed", "")
        else:
            self._set_status(row_index, "failed", error or self._tr("번역 결과 적용 실패"))
        QTimer.singleShot(0, self._dispatch_next_apply)

    def _queue_translation_for_apply(self, row_index: int, results: List[str]):
        if self._canceled:
            return
        self._set_status(row_index, "applying", "")
        self._pending_apply_results.append((int(row_index), results))
        self._dispatch_next_apply()

    def _dispatch_next_apply(self):
        if self._canceled or self._apply_in_progress or not self._pending_apply_results:
            return
        row_index, results = self._pending_apply_results.popleft()
        if not (0 <= int(row_index) < len(self.rows)):
            QTimer.singleShot(0, self._dispatch_next_apply)
            return
        self._apply_in_progress = True
        self._active_apply_row = int(row_index)
        self._active_apply_results = results
        self.translationReady.emit(int(row_index), results)

    def _pump(self):
        if self._canceled:
            return
        if self.mode == "flex":
            active = sum(1 for meta in self._reply_meta.values() if meta.get("kind") == "flex")
            while active < self._max_flex_requests and self._queued_indices:
                row_index = self._queued_indices.popleft()
                if not (0 <= row_index < len(self.rows)) or self.rows[row_index].get("status") != "queued":
                    continue
                self._start_flex(row_index)
                active += 1
            return

        active_submit = sum(1 for meta in self._reply_meta.values() if meta.get("kind") == "batch_submit")
        while active_submit < self._max_batch_submits and self._queued_indices:
            row_index = self._queued_indices.popleft()
            if not (0 <= row_index < len(self.rows)) or self.rows[row_index].get("status") != "queued":
                continue
            self._start_batch_submit(row_index)
            active_submit += 1

        now = time.monotonic()
        active_poll = sum(1 for meta in self._reply_meta.values() if meta.get("kind") == "batch_poll")
        while active_poll < self._max_batch_polls and self._batch_poll_heap:
            due, ticket, row_index = self._batch_poll_heap[0]
            if due > now:
                break
            heapq.heappop(self._batch_poll_heap)
            if not (0 <= row_index < len(self.rows)):
                continue
            row = self.rows[row_index]
            if int(row.get("poll_ticket", -1)) != int(ticket):
                continue
            if row.get("status") not in ("pending", "running") or not row.get("job_name"):
                continue
            self._start_batch_poll(row_index)
            active_poll += 1

    def _gemini_url(self, suffix: str) -> QUrl:
        url = QUrl(f"https://generativelanguage.googleapis.com/v1beta/{suffix}")
        query = QUrlQuery(url)
        query.addQueryItem("key", self.api_key)
        url.setQuery(query)
        return url

    def _send_json(self, url: QUrl, payload: Dict[str, Any], *, kind: str, row_index: int, timeout_ms: int):
        request = QNetworkRequest(url)
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        try:
            request.setTransferTimeout(int(timeout_ms))
        except Exception:
            pass
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        reply = self._network.post(request, body)
        meta = {"kind": kind, "row": row_index, "generation": self._generation}
        self._reply_meta[reply] = meta
        reply.finished.connect(lambda r=reply: self._on_reply_finished(r))
        return reply

    def _start_flex(self, row_index: int):
        row = self.rows[row_index]
        row["attempts"] = int(row.get("attempts", 0)) + 1
        row["started_at"] = time.monotonic()
        row["finished_at"] = 0.0
        try:
            payload = self.engine.build_gemini_translation_request(
                self._texts_for_row(row),
                base_id=0,
                contexts=self._contexts_for_row(row),
                model_override=self.model,
                service_tier="flex",
            )
        except Exception as exc:
            self._set_status(row_index, "failed", str(exc))
            return
        self._set_status(row_index, "requesting", "")
        self._send_json(
            self._gemini_url(f"models/{self.model}:generateContent"),
            payload,
            kind="flex",
            row_index=row_index,
            timeout_ms=15 * 60 * 1000,
        )

    def _start_batch_submit(self, row_index: int):
        row = self.rows[row_index]
        row["attempts"] = int(row.get("attempts", 0)) + 1
        row["started_at"] = time.monotonic()
        row["finished_at"] = 0.0
        try:
            request_payload = self.engine.build_gemini_translation_request(
                self._texts_for_row(row),
                base_id=0,
                contexts=self._contexts_for_row(row),
                model_override=self.model,
                service_tier=None,
            )
        except Exception as exc:
            self._set_status(row_index, "failed", str(exc))
            return
        payload = {
            "batch": {
                "display_name": f"ysb-chunk-{int(row.get('index', row_index)) + 1}-{int(time.time())}",
                "input_config": {
                    "requests": {
                        "requests": [
                            {
                                "request": request_payload,
                                "metadata": {"key": f"ysb-chunk-{int(row.get('index', row_index)) + 1}"},
                            }
                        ]
                    }
                },
            }
        }
        self._set_status(row_index, "submitting", "")
        self._send_json(
            self._gemini_url(f"models/{self.model}:batchGenerateContent"),
            payload,
            kind="batch_submit",
            row_index=row_index,
            timeout_ms=120000,
        )

    def _start_batch_poll(self, row_index: int):
        row = self.rows[row_index]
        job_name = str(row.get("job_name") or "").lstrip("/")
        if not job_name:
            self._set_status(row_index, "failed", self._tr("Batch 작업 ID가 비어 있습니다."))
            return
        row["next_poll_at"] = 0.0
        request = QNetworkRequest(self._gemini_url(job_name))
        try:
            request.setTransferTimeout(60000)
        except Exception:
            pass
        reply = self._network.get(request)
        self._reply_meta[reply] = {"kind": "batch_poll", "row": row_index, "generation": self._generation}
        reply.finished.connect(lambda r=reply: self._on_reply_finished(r))

    def _response_error_text(self, payload: Any, fallback: str = "") -> str:
        if isinstance(payload, dict):
            err = payload.get("error")
            if isinstance(err, dict):
                return str(err.get("message") or err.get("status") or json.dumps(err, ensure_ascii=False))
            if err:
                return str(err)
        return str(fallback or self._tr("알 수 없는 API 오류"))

    def _on_reply_finished(self, reply: QNetworkReply):
        meta = self._reply_meta.pop(reply, None) or {}
        try:
            body = bytes(reply.readAll()).decode("utf-8", errors="replace")
        except Exception:
            body = ""
        try:
            status = int(reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute) or 0)
        except Exception:
            status = 0
        network_error = reply.error()
        network_error_text = str(reply.errorString() or "")
        reply.deleteLater()

        if self._canceled or int(meta.get("generation", -1)) != self._generation:
            return
        row_index = int(meta.get("row", -1))
        if not (0 <= row_index < len(self.rows)):
            return
        try:
            payload = json.loads(body) if body.strip() else {}
        except Exception:
            payload = {}

        if network_error != QNetworkReply.NetworkError.NoError or not (200 <= status < 300):
            detail = self._response_error_text(payload, network_error_text or f"HTTP {status}")
            if status:
                detail = f"HTTP {status}: {detail}"
            self._set_status(row_index, "failed", detail)
            self._pump()
            return

        kind = str(meta.get("kind") or "")
        if kind == "flex":
            self._handle_flex_success(row_index, payload)
        elif kind == "batch_submit":
            self._handle_batch_submit_success(row_index, payload)
        elif kind == "batch_poll":
            self._handle_batch_poll_success(row_index, payload)
        self._pump()

    def _handle_flex_success(self, row_index: int, payload: Dict[str, Any]):
        if self._canceled:
            return
        row = self.rows[row_index]
        row_texts = self._texts_for_row(row)
        try:
            results = self.engine.parse_gemini_translation_response(
                payload,
                row_texts,
                base_id=0,
                provider_name="Gemini Flex",
            )
        except Exception as exc:
            self._set_status(row_index, "failed", str(exc))
            return
        self._queue_translation_for_apply(row_index, results)

    def _handle_batch_submit_success(self, row_index: int, payload: Dict[str, Any]):
        if self._canceled:
            return
        job_name = str(payload.get("name") or "").strip()
        if not job_name:
            self._set_status(row_index, "failed", self._response_error_text(payload, self._tr("Batch 작업 ID를 받지 못했습니다.")))
            return
        row = self.rows[row_index]
        row["job_name"] = job_name
        self._schedule_batch_poll(row_index, 2.0)
        state = str((payload.get("metadata") or {}).get("state") or "JOB_STATE_PENDING")
        self._set_status(row_index, "running" if state == "JOB_STATE_RUNNING" else "pending", state)

    @staticmethod
    def _batch_state(payload: Dict[str, Any]) -> str:
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        return str(metadata.get("state") or payload.get("state") or "")

    @staticmethod
    def _first_inline_response(payload: Dict[str, Any]) -> Dict[str, Any]:
        response = payload.get("response") if isinstance(payload.get("response"), dict) else {}
        candidates = response.get("inlinedResponses") or response.get("inlined_responses") or []
        if not candidates:
            dest = payload.get("dest") if isinstance(payload.get("dest"), dict) else {}
            candidates = dest.get("inlinedResponses") or dest.get("inlined_responses") or []
        first = candidates[0] if isinstance(candidates, list) and candidates else {}
        return first if isinstance(first, dict) else {}

    def _handle_batch_poll_success(self, row_index: int, payload: Dict[str, Any]):
        if self._canceled:
            return
        row = self.rows[row_index]
        state = self._batch_state(payload)
        done = bool(payload.get("done"))
        if state == "JOB_STATE_SUCCEEDED" or (done and payload.get("response")):
            inline = self._first_inline_response(payload)
            if inline.get("error"):
                self._set_status(row_index, "failed", self._response_error_text(inline, self._tr("Batch 요청이 실패했습니다.")))
                return
            generation_response = inline.get("response") if isinstance(inline.get("response"), dict) else inline
            row_texts = self._texts_for_row(row)
            try:
                results = self.engine.parse_gemini_translation_response(
                    generation_response,
                    row_texts,
                    base_id=0,
                    provider_name="Gemini Batch",
                )
            except Exception as exc:
                self._set_status(row_index, "failed", str(exc))
                return
            self._queue_translation_for_apply(row_index, results)
            return
        if state in ("JOB_STATE_FAILED", "JOB_STATE_CANCELLED", "JOB_STATE_EXPIRED"):
            detail = self._response_error_text(payload, state or self._tr("Batch 작업이 실패했습니다."))
            self._set_status(row_index, "failed", detail)
            return
        self._schedule_batch_poll(row_index, 10.0)
        self._set_status(row_index, "running" if state == "JOB_STATE_RUNNING" else "pending", state or "JOB_STATE_PENDING")

    def cancel_all(self):
        if self._canceled:
            return
        self._canceled = True
        self._generation += 1
        self._pump_timer.stop()
        batch_jobs = [str(row.get("job_name") or "") for row in self.rows if row.get("job_name")]
        for reply in list(self._reply_meta.keys()):
            try:
                reply.abort()
            except Exception:
                pass
        self._reply_meta.clear()
        self._queued_indices.clear()
        self._batch_poll_heap.clear()
        while self._pending_apply_results:
            try:
                _, results = self._pending_apply_results.popleft()
                if isinstance(results, list):
                    results.clear()
            except Exception:
                break
        try:
            if isinstance(self._active_apply_results, list):
                self._active_apply_results.clear()
        except Exception:
            pass
        self._active_apply_results = None
        self._active_apply_row = -1
        self._apply_in_progress = False
        for i, row in enumerate(self.rows):
            if row.get("status") != "completed":
                self._set_status(i, "canceled", "", emit_summary=False)
        self._emit_summary()
        if batch_jobs:
            threading.Thread(target=self._cancel_batch_jobs_best_effort, args=(batch_jobs,), daemon=True).start()
        self.canceled.emit()

    def _cancel_batch_jobs_best_effort(self, job_names: List[str]):
        for job_name in job_names:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/{str(job_name).lstrip('/')}:cancel"
                requests.post(url, params={"key": self.api_key}, timeout=10)
            except Exception:
                pass


class GeminiDelayedTranslationDialog(QDialog):
    def __init__(
        self,
        controller: GeminiDelayedTranslationController,
        *,
        apply_chunk: Callable[[int, List[str]], bool],
        language: str = LANG_KO,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self.controller = controller
        self.apply_chunk = apply_chunk
        self.language = LANG_EN if str(language or "").lower().startswith("en") else LANG_KO
        self._completed = False
        self._canceling = False
        self._close_allowed = False

        self.setWindowTitle(self._tr("Gemini 지연 번역 청크 현황"))
        self.setWindowModality(Qt.WindowModality.ApplicationModal)
        self.setModal(True)
        self.resize(1080, 700)
        self.setMinimumSize(820, 480)
        self.setSizeGripEnabled(True)

        try:
            if parent is not None and hasattr(parent, "settings_dialog_style"):
                self.setStyleSheet(parent.settings_dialog_style())
        except Exception:
            pass

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        title = QLabel(self._tr("Gemini 지연 번역 청크 현황"), self)
        title.setStyleSheet("font-size:18px; font-weight:800;")
        layout.addWidget(title)

        mode_text = "Flex" if controller.mode == "flex" else "Batch"
        self.info_label = QLabel(
            self._tr(
                "{mode} 요청을 청크별로 처리합니다. 완료된 청크는 즉시 번역문에 반영됩니다. 작업 중에는 이 창만 조작할 수 있습니다.",
                mode=mode_text,
            ),
            self,
        )
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.summary_label = QLabel(self)
        self.summary_label.setStyleSheet("font-weight:700;")
        layout.addWidget(self.summary_label)

        self.model = GeminiChunkTableModel(controller.rows, self.language, self)
        self.table = QTableView(self)
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setWordWrap(False)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setHorizontalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QTableView.ScrollMode.ScrollPerPixel)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        widths = (58, 110, 72, 105, 105, 90, 88)
        for i, width in enumerate(widths):
            self.table.setColumnWidth(i, width)
        delegate = RetryButtonDelegate(self.language, self.table)
        delegate.retryRequested.connect(controller.retry_chunk)
        self.table.setItemDelegateForColumn(6, delegate)
        self._retry_delegate = delegate
        layout.addWidget(self.table, 1)

        buttons = QHBoxLayout()
        self.retry_all_btn = QPushButton(self._tr("실패 청크 전체 재시도"), self)
        self.retry_all_btn.clicked.connect(controller.retry_all_failed)
        self.retry_all_btn.setEnabled(False)
        buttons.addWidget(self.retry_all_btn)
        buttons.addStretch(1)
        self.cancel_btn = QPushButton(self._tr("작업 취소"), self)
        self.cancel_btn.clicked.connect(self._request_cancel)
        buttons.addWidget(self.cancel_btn)
        self.ok_btn = QPushButton(self._tr("확인"), self)
        self.ok_btn.setEnabled(False)
        self.ok_btn.clicked.connect(self._accept_completed)
        buttons.addWidget(self.ok_btn)
        layout.addLayout(buttons)

        self.elapsed_timer = QTimer(self)
        self.elapsed_timer.setInterval(1000)
        self.elapsed_timer.timeout.connect(self._update_visible_elapsed)
        self.elapsed_timer.start()

        controller.chunkChanged.connect(self.model.update_row)
        controller.translationReady.connect(self._on_translation_ready)
        controller.summaryChanged.connect(self._on_summary_changed)
        controller.allCompleted.connect(self._on_all_completed)
        controller.canceled.connect(self._on_canceled)
        QTimer.singleShot(0, controller.start)

    def _tr(self, text: str, **kwargs) -> str:
        return tr_ui(text, self.language, **kwargs)

    def _update_visible_elapsed(self):
        viewport = self.table.viewport()
        first = self.table.rowAt(0)
        if first < 0:
            return
        last = self.table.rowAt(max(0, viewport.height() - 1))
        if last < 0:
            last = min(self.model.rowCount() - 1, first + 100)
        self.model.update_elapsed_range(first, last)

    def _on_summary_changed(self, completed: int, failed: int, active: int, total: int):
        waiting = max(0, int(total) - int(completed) - int(failed) - int(active))
        self.summary_label.setText(
            self._tr(
                "전체 {total}개 · 완료 {completed}개 · 처리 중 {active}개 · 실패 {failed}개 · 대기 {waiting}개",
                total=total,
                completed=completed,
                active=active,
                failed=failed,
                waiting=waiting,
            )
        )
        self.retry_all_btn.setEnabled(failed > 0 and not self._completed and not self._canceling)

    def _on_translation_ready(self, row_index: int, results: List[str]):
        if self._canceling:
            return
        ok = False
        error = ""
        try:
            # The controller already serializes application.  Do not duplicate
            # the chunk result list again on the UI thread.
            ok = bool(self.apply_chunk(int(row_index), results or []))
            if not ok:
                error = self._tr("번역 결과를 프로젝트에 적용하지 못했습니다.")
        except Exception as exc:
            error = str(exc)
            ok = False
        self.controller.acknowledge_applied(row_index, ok, error)

    def _on_all_completed(self):
        self._completed = True
        self.ok_btn.setEnabled(True)
        self.ok_btn.setDefault(True)
        self.cancel_btn.setEnabled(False)
        self.retry_all_btn.setEnabled(False)
        self.info_label.setText(self._tr("모든 청크가 완료되어 번역문에 반영되었습니다. 확인을 눌러 작업 화면으로 돌아가세요."))
        try:
            self.ok_btn.setFocus(Qt.FocusReason.OtherFocusReason)
        except Exception:
            pass

    def _on_canceled(self):
        self._canceling = True

    def _accept_completed(self):
        if not self._completed:
            return
        self._close_allowed = True
        self.accept()

    def _request_cancel(self):
        if self._completed:
            self._accept_completed()
            return
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setWindowTitle(self._tr("Gemini 지연 번역 취소"))
        msg.setText(
            self._tr(
                "현재 지연 번역 작업을 취소할까요?\n\n이미 완료되어 반영된 청크는 유지합니다. 대기·처리 중인 청크는 중단하고, 뒤늦게 도착한 응답은 번역문에 반영하지 않습니다."
            )
        )
        msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg.setDefaultButton(QMessageBox.StandardButton.No)
        yes_btn = msg.button(QMessageBox.StandardButton.Yes)
        no_btn = msg.button(QMessageBox.StandardButton.No)
        if yes_btn is not None:
            yes_btn.setText(self._tr("작업 취소"))
        if no_btn is not None:
            no_btn.setText(self._tr("계속하기"))
        if msg.exec() != QMessageBox.StandardButton.Yes:
            return
        self._canceling = True
        self.cancel_btn.setEnabled(False)
        self.retry_all_btn.setEnabled(False)
        self.controller.cancel_all()
        self._close_allowed = True
        self.reject()

    def closeEvent(self, event: QCloseEvent):
        if self._close_allowed:
            event.accept()
            return
        if self._completed:
            self._close_allowed = True
            event.accept()
            return
        event.ignore()
        QTimer.singleShot(0, self._request_cancel)

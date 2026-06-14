"""쯔꾸르붕이 번역 전용 엔진.

4단계 정리 기준:
- RPG Maker 텍스트 번역에 필요한 API 번역 기능만 실제 동작한다.
- OCR/마스크/인페인팅/이미지 출력은 호환용 스텁으로만 남긴다.
- 기존 코드가 `ysb.engine.manga_engine.Config` 또는 `MangaProcessEngine`을 import해도
  같은 Config 객체/엔진 클래스를 보도록 `manga_engine.py`에서 이 파일을 재수출한다.
"""

from __future__ import annotations

import html
import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests

from ysb.settings.translation_prompt_presets import (
    PROMPT_BLOCK_BEGIN,
    PROMPT_BLOCK_END,
    get_runtime_prompt_templates,
    render_prompt_template,
)

try:
    from openai import OpenAI
except Exception:  # pragma: no cover - 사용자가 Google/Gemini만 쓰는 경우 import 실패 방어
    OpenAI = None


class Config:
    """앱 설정 캐시가 주입되는 전역 Config.

    아직 UI/설정 코드 일부가 역식붕이 시절 이름을 참조하므로,
    4단계에서는 호환을 위해 OCR/인페인팅 설정 이름도 보관만 한다.
    실제 동작 엔진은 번역 관련 값만 사용한다.
    """

    # OCR 호환용 보관값. 쯔꾸르붕이 번역 엔진에서는 사용하지 않는다.
    OCR_PROVIDER = "clova"
    CLOVA_API_URL = ""
    CLOVA_SECRET_KEY = ""
    CLOVA_MODEL = "clova_ocr_v2"
    CLOVA_OCR_LANGUAGE = "ja"
    GOOGLE_VISION_CREDENTIAL_JSON_PATH = ""
    GOOGLE_VISION_API_KEY = ""
    GOOGLE_VISION_MODEL = "DOCUMENT_TEXT_DETECTION"
    GOOGLE_VISION_OCR_LANGUAGE = "en"
    GOOGLE_VISION_LANGUAGE_HINTS = "ja,ko,en"
    LOCAL_PADDLE_MASK_DEVICE = "auto"
    LOCAL_PADDLE_MASK_INPUT_SIZE = "auto"
    LOCAL_PADDLE_OCR_LANGUAGE = "ja"
    LOCAL_MANGA_OCR_LANGUAGE = "ja"
    OCR_TILE_HEIGHT = 7000
    OCR_TILE_OVERLAP = 500

    # 번역 설정. 쯔꾸르붕이 핵심 사용값.
    TRANSLATION_PROVIDER = "openai"
    OPENAI_API_KEY = ""
    DEEPSEEK_API_KEY = ""
    GOOGLE_TRANSLATE_API_KEY = ""
    GEMINI_API_KEY = ""
    CUSTOM_TRANSLATION_API_KEY = ""
    CUSTOM_TRANSLATION_BASE_URL = ""
    CUSTOM_TRANSLATION_MODEL = ""
    CUSTOM_TRANSLATION_PRESET_NAME = "Custom Compatible"
    LM_STUDIO_BASE_URL = "http://localhost:1234/v1"
    LM_STUDIO_MODEL = ""
    LM_STUDIO_API_KEY = ""

    OPENAI_TRANSLATION_MODEL = "gpt-4o-mini"
    DEEPSEEK_TRANSLATION_MODEL = "deepseek-v4-flash"
    GOOGLE_TRANSLATE_MODEL = "google_translate_basic_v2"
    GEMINI_TRANSLATION_MODEL = "gemini-2.5-flash-lite"
    GEMINI_DELAYED_API_KEY = ""
    GEMINI_DELAYED_TRANSLATION_MODEL = "gemini-2.5-flash-lite"
    GEMINI_DELAYED_MODE = "flex"

    TRANSLATION_PROMPT = ""
    TRANSLATION_PROMPT_TEMPLATES = {}
    TRANSLATION_GLOSSARY_TEXT = ""  # free-form user notes / legacy compatibility
    TRANSLATION_AUTO_DB_GLOSSARY = {}
    TRANSLATION_USER_GLOSSARY = {}
    TRANSLATION_GLOSSARY_REVISION = 0
    # 데이터베이스 단어장은 전체를 매번 프롬프트에 넣지 않고,
    # 현재 번역 묶음에 실제 등장한 항목만 추려 넣는다.
    TRANSLATION_MATCHED_GLOSSARY_MAX_TERMS = 80

    # 인페인팅 호환용 보관값. 쯔꾸르붕이 번역 엔진에서는 사용하지 않는다.
    REPLICATE_API_TOKEN = ""
    LAMA_REPLICATE_API_TOKEN = ""
    STABLE_REPLICATE_API_TOKEN = ""
    INPAINT_PROVIDER = "replicate_lama"
    INPAINT_MODEL = ""
    REPAINT_MODEL = ""
    REPLICATE_LAMA_WAIT_SECONDS = 3
    STABLE_INPAINT_MODEL = "stability-ai/stable-diffusion-inpainting:95b7223104132402a9ae91cc677285bc5eb997834bd2349fa486f53910fd68b3"
    STABLE_INPAINT_PROMPT = "remove text and restore the original background"
    STABLE_INPAINT_WAIT_SECONDS = 3
    LOCAL_LAMA_WAIT_SECONDS = 0
    GEMINI_INPAINT_MODEL = "gemini-2.5-flash-image"
    GEMINI_INPAINT_PROMPT = (
        "Remove the text only inside the white mask area and reconstruct the original manga background. "
        "Keep all characters, panel borders, screentones, line art, and unmasked areas unchanged. "
        "Return only the edited full image."
    )

    # 마스크 호환용 보관값. 쯔꾸르붕이 번역 엔진에서는 사용하지 않는다.
    INPAINT_RATIO = 0.1
    MERGE_RATIO = 0.2
    MERGE_MIN_STROKE_PX = 5
    MIN_STROKE_PX = 1


class TranslationProcessEngine:
    """RPG Maker 텍스트 번역 전용 엔진."""

    UNSUPPORTED_IMAGE_FEATURE_MESSAGE = "쯔꾸르붕이에서는 이미지 OCR/인페인팅/이미지 출력 엔진을 사용하지 않습니다."

    def __init__(self):
        print(">>> [System] 쯔꾸르붕이 번역 엔진 시동")
        self.openai_client = self._make_openai_client(getattr(Config, "OPENAI_API_KEY", ""))
        self.deepseek_client = self._make_openai_client(
            getattr(Config, "DEEPSEEK_API_KEY", ""),
            base_url="https://api.deepseek.com",
        )
        self.custom_translation_client = None
        custom_base_url = str(getattr(Config, "CUSTOM_TRANSLATION_BASE_URL", "") or "").strip()
        custom_api_key = str(getattr(Config, "CUSTOM_TRANSLATION_API_KEY", "") or "").strip()
        if custom_api_key and custom_base_url:
            self.custom_translation_client = self._make_openai_client(custom_api_key, base_url=custom_base_url.rstrip("/"))

        self.lm_studio_client = None
        lm_base_url = str(getattr(Config, "LM_STUDIO_BASE_URL", "http://localhost:1234/v1") or "http://localhost:1234/v1").strip().rstrip("/")
        if lm_base_url:
            # LM Studio's OpenAI-compatible server generally accepts any Bearer
            # token or no real key; the OpenAI SDK object still expects a string.
            lm_api_key = str(getattr(Config, "LM_STUDIO_API_KEY", "") or "lm-studio").strip() or "lm-studio"
            self.lm_studio_client = self._make_openai_client(lm_api_key, base_url=lm_base_url)

    @staticmethod
    def _make_openai_client(api_key: str, base_url: Optional[str] = None):
        api_key = str(api_key or "").strip()
        if not api_key:
            return None
        if OpenAI is None:
            raise RuntimeError("openai 패키지를 불러오지 못했습니다. requirements를 확인해 주세요.")
        kwargs = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAI(**kwargs)

    # ---------------------------------------------------------
    # [CORE] 번역
    # ---------------------------------------------------------
    def translate_text_batch(self, texts: Sequence[str], provider: str = "openai", chunk_size: Optional[int] = None, contexts: Optional[Sequence[str]] = None) -> List[str]:
        if not texts:
            return []

        provider = (provider or "openai").lower()
        input_texts = [str(t or "") for t in texts]
        context_list = [str(c or "") for c in (contexts or [])] if contexts is not None else None
        if context_list is not None and len(context_list) != len(input_texts):
            context_list = [(context_list[i] if i < len(context_list) else "") for i in range(len(input_texts))]

        self._validate_translation_provider(provider)

        if provider in ("local_argos", "local_hf_jako", "local_hf_enko", "local_nllb"):
            # 쯔꾸르붕이 4단계에서는 로컬 번역 모델을 별도 유지하지 않는다.
            # 기존 캐시 호환을 위해 OpenAI 번역으로 돌린다.
            provider = "openai"

        if chunk_size is None:
            # API 번역 기본 묶음 수는 제공자와 무관하게 50개로 통일한다.
            # 필요하면 API 관리 > 번역 탭에서 사용자가 직접 줄이거나 늘린다.
            chunk_size = 50
        else:
            try:
                chunk_size = int(chunk_size)
            except Exception:
                chunk_size = 50
            chunk_size = max(1, min(chunk_size, 100))

        final_results: List[str] = []
        for start in range(0, len(input_texts), chunk_size):
            chunk = input_texts[start:start + chunk_size]
            context_chunk = context_list[start:start + len(chunk)] if context_list is not None else None
            try:
                translated_chunk = self._translate_text_chunk(chunk, provider, start, contexts=context_chunk)
                final_results.extend(translated_chunk)
            except Exception as e:
                print(f"Chunk Translate Error: {e}")
                if self._is_api_config_error(e):
                    raise
                for offset, one_text in enumerate(chunk):
                    try:
                        one_context = [context_list[start + offset]] if context_list is not None and start + offset < len(context_list) else None
                        one_result = self._translate_text_chunk([one_text], provider, start + offset, contexts=one_context)
                        final_results.extend(one_result)
                    except Exception as e2:
                        print(f"Single Translate Error: {e2}")
                        if self._is_api_config_error(e2):
                            raise
                        final_results.append(one_text)

        if len(final_results) != len(input_texts):
            print(f"Translate Count Mismatch Fixed: input={len(input_texts)}, output={len(final_results)}")
            if len(final_results) < len(input_texts):
                final_results.extend(input_texts[len(final_results):])
            else:
                final_results = final_results[:len(input_texts)]
        return final_results

    @staticmethod
    def _is_api_config_error(err: Exception) -> bool:
        s = str(err)
        return (
            "API 키가 비어" in s
            or "API 설정이 비어" in s
            or "모델명이 비어" in s
            or "openai 패키지" in s
        )

    @staticmethod
    def _lm_studio_models_url(base_url: str) -> str:
        base = str(base_url or "").strip().rstrip("/")
        if not base:
            return ""
        if base.lower().endswith("/v1"):
            return base + "/models"
        return base + "/v1/models"

    def _check_lm_studio_server_ready(self) -> None:
        base_url = str(getattr(Config, "LM_STUDIO_BASE_URL", "") or "").strip().rstrip("/")
        model_name = str(getattr(Config, "LM_STUDIO_MODEL", "") or "").strip()
        models_url = self._lm_studio_models_url(base_url)
        if not models_url:
            raise ValueError("LM Studio 서버 설정이 비어있습니다. Base URL을 확인하고 LM Studio Developer 서버를 켜 주세요.")
        try:
            resp = requests.get(models_url, timeout=2)
            if resp.status_code < 200 or resp.status_code >= 300:
                raise RuntimeError(f"HTTP {resp.status_code}")
            try:
                payload = resp.json()
            except Exception:
                payload = {}
            data = payload.get("data") if isinstance(payload, dict) else None
            if isinstance(data, list) and not data:
                raise ValueError("LM Studio 서버는 켜져 있지만 로드된 모델이 없습니다. LM Studio에서 모델을 로드한 뒤 다시 시도해 주세요.")
        except ValueError:
            raise
        except Exception as e:
            raise ValueError(
                "LM Studio 서버에 연결할 수 없습니다. "
                "LM Studio > Developer > Local Server에서 서버를 켠 뒤 다시 시도해 주세요. "
                f"Base URL: {base_url} / 확인 주소: {models_url} / 상세: {e}"
            ) from e

    def _validate_translation_provider(self, provider: str) -> None:
        provider = (provider or "openai").lower()
        if provider == "deepseek":
            if self.deepseek_client is None:
                raise ValueError("DeepSeek API 키가 비어있습니다.")
        elif provider == "google":
            if not getattr(Config, "GOOGLE_TRANSLATE_API_KEY", ""):
                raise ValueError("Google Translate API 키가 비어있습니다.")
        elif provider == "gemini":
            if not getattr(Config, "GEMINI_API_KEY", ""):
                raise ValueError("Gemini API 키가 비어있습니다.")
        elif provider == "custom":
            if self.custom_translation_client is None or not getattr(Config, "CUSTOM_TRANSLATION_MODEL", ""):
                raise ValueError("Custom 번역 API 설정이 비어있습니다. Base URL, Model, API Key를 확인해주세요.")
        elif provider == "lm_studio":
            if self.lm_studio_client is None or not getattr(Config, "LM_STUDIO_BASE_URL", ""):
                raise ValueError("LM Studio 서버 설정이 비어있습니다. Base URL을 확인하고 LM Studio Developer 서버를 켜 주세요.")
            if not getattr(Config, "LM_STUDIO_MODEL", ""):
                raise ValueError("LM Studio 모델명이 비어있습니다. LM Studio에서 모델을 로드한 뒤 모델명을 입력해 주세요.")
            self._check_lm_studio_server_ready()
        else:
            if self.openai_client is None:
                raise ValueError("OpenAI API 키가 비어있습니다.")

    def _translate_text_chunk_google(self, texts: Sequence[str]) -> List[str]:
        """Google Translation Basic v2 API."""
        key = str(getattr(Config, "GOOGLE_TRANSLATE_API_KEY", "") or "").strip()
        if not key:
            raise ValueError("Google Translate API 키가 비어있습니다.")

        url = "https://translation.googleapis.com/language/translate/v2"
        payload = {
            "q": [str(t or "") for t in texts],
            "source": "ja",
            "target": "ko",
            "format": "text",
        }
        r = requests.post(url, params={"key": key}, json=payload, timeout=60)
        if r.status_code != 200:
            raise ValueError(f"Google Translate Error: {r.status_code} / {r.text[:300]}")

        data = r.json()
        translations = data.get("data", {}).get("translations", [])
        results = []
        for i, original in enumerate(texts):
            if i < len(translations):
                translated = str(translations[i].get("translatedText", "") or "")
                results.append(html.unescape(translated))
            else:
                results.append(str(original or ""))
        return results

    def build_gemini_translation_request(
        self,
        texts: Sequence[str],
        base_id: int = 0,
        contexts: Optional[Sequence[str]] = None,
        *,
        model_override: Optional[str] = None,
        service_tier: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Build one REST GenerateContent request without performing network I/O.

        Flex and Batch status management use Qt's asynchronous network stack, so
        they share the exact same prompt/JSON construction as the normal Gemini
        translation path without blocking the UI thread.
        """
        model = str(model_override or getattr(Config, "GEMINI_TRANSLATION_MODEL", "gemini-2.5-flash-lite") or "gemini-2.5-flash-lite").strip()
        if not model:
            raise ValueError("Gemini 모델명이 비어있습니다.")

        context_list_raw = [str(c or "") for c in (contexts or [])] if contexts is not None else None
        chunk_character_prompt, cleaned_contexts = self._chunk_character_prompt_block(context_list_raw)
        prompt = self._build_translation_system_prompt(texts=texts, contexts=cleaned_contexts if cleaned_contexts is not None else contexts)
        if chunk_character_prompt:
            prompt = (chunk_character_prompt + "\n\n" + prompt).strip()

        input_items = []
        context_list = [str(c or "") for c in (cleaned_contexts or [])] if cleaned_contexts is not None else ([str(c or "") for c in (contexts or [])] if contexts is not None else None)
        for i, text in enumerate(texts):
            item_text = str(text or "")
            item = {"id": base_id + i, "text": item_text}
            if "\n" in item_text:
                line_count = item_text.count("\n") + 1
                item["line_count"] = line_count
                item["line_rule"] = render_prompt_template(
                    get_runtime_prompt_templates().get("line_rule_prompt", ""),
                    LINE_COUNT=line_count,
                )
            if context_list is not None and i < len(context_list) and context_list[i].strip():
                item["context"] = context_list[i]
            input_items.append(item)

        user_text = render_prompt_template(
            get_runtime_prompt_templates().get("gemini_input_wrapper", ""),
            SYSTEM_PROMPT=prompt.strip(),
            INPUT_JSON=json.dumps(input_items, ensure_ascii=False),
        )
        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": user_text}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json",
            },
        }
        if service_tier:
            payload["service_tier"] = str(service_tier)
        return payload

    def parse_gemini_translation_response(
        self,
        data: Dict[str, Any],
        texts: Sequence[str],
        base_id: int = 0,
        provider_name: str = "Gemini",
    ) -> List[str]:
        """Extract and validate translated JSON from a REST GenerateContent response."""
        candidates = data.get("candidates", []) if isinstance(data, dict) else []
        if not candidates:
            raise ValueError(f"{provider_name} 번역 응답이 비어있습니다.")
        parts = candidates[0].get("content", {}).get("parts", [])
        content = "".join(str(part.get("text", "")) for part in parts if isinstance(part, dict)).strip()
        if not content:
            raise ValueError(f"{provider_name} 번역 텍스트가 비어있습니다.")
        return self._parse_translation_json_response(content, texts, base_id, provider_name=provider_name)

    @staticmethod
    def _gemini_http_error(response, model: str = "") -> ValueError:
        err_text = str(getattr(response, "text", "") or "")[:800]
        try:
            err = response.json().get("error", {})
            msg = str(err.get("message", "") or err_text)
            code = int(err.get("code", getattr(response, "status_code", 0)) or getattr(response, "status_code", 0))
        except Exception:
            msg = err_text
            code = int(getattr(response, "status_code", 0) or 0)
        if code == 429:
            return ValueError(
                "Gemini Translate Error: 429 / Gemini API 할당량 또는 속도 제한을 초과했습니다. "
                "AI Studio의 Rate limits와 결제 설정을 확인해 주세요. 무료 등급에서 limit: 0으로 표시되면 "
                "해당 프로젝트에 사용 가능한 무료 할당량이 없거나 결제 설정이 필요한 상태일 수 있습니다. "
                f"원문: {msg[:400]}"
            )
        if code == 404:
            model_text = str(model or "").strip()
            if model_text:
                return ValueError(
                    f"Gemini Translate Error: 404 / Gemini 모델명을 찾을 수 없습니다. 현재 모델명 '{model_text}'을 확인해 주세요. "
                    "예: gemini-2.5-flash-lite"
                )
            return ValueError(f"Gemini Translate Error: 404 / Gemini 모델명을 찾을 수 없습니다. 원문: {msg[:400]}")
        return ValueError(f"Gemini Translate Error: {code} / {msg[:500]}")

    def _translate_text_chunk_gemini(self, texts: Sequence[str], base_id: int = 0, contexts: Optional[Sequence[str]] = None) -> List[str]:
        """Google AI Studio Gemini API translation."""
        key = str(getattr(Config, "GEMINI_API_KEY", "") or "").strip()
        if not key:
            raise ValueError("Gemini API 키가 비어있습니다.")

        model = str(getattr(Config, "GEMINI_TRANSLATION_MODEL", "gemini-2.5-flash-lite") or "gemini-2.5-flash-lite").strip()
        payload = self.build_gemini_translation_request(texts, base_id=base_id, contexts=contexts, model_override=model)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        r = requests.post(url, params={"key": key}, json=payload, timeout=90)
        if r.status_code != 200:
            raise self._gemini_http_error(r, model=model)
        return self.parse_gemini_translation_response(r.json(), texts, base_id, provider_name="Gemini")

    _AUTO_DB_GLOSSARY_BEGIN = "# YSB_AUTO_DB_GLOSSARY_BEGIN"
    _AUTO_DB_GLOSSARY_END = "# YSB_AUTO_DB_GLOSSARY_END"
    _glossary_cache_text: str = ""
    _glossary_cache_entries: List[Dict[str, str]] = []
    _glossary_cache_manual_text: str = ""
    _glossary_cache_signature = None

    @staticmethod
    def _parse_glossary_line(line: str) -> Tuple[str, str] | None:
        line = str(line or "").strip()
        if not line or line.startswith("#"):
            return None
        # 데이터베이스 단어장 기본 형식: 원문<TAB>번역문
        if "\t" in line:
            left, right = line.split("\t", 1)
        elif "=>" in line:
            left, right = line.split("=>", 1)
        elif "->" in line:
            left, right = line.split("->", 1)
        elif "=" in line:
            left, right = line.split("=", 1)
        else:
            return None
        src = str(left or "").strip()
        dst = str(right or "").strip()
        if not src or not dst or src == dst:
            return None
        return src, dst

    @staticmethod
    def _normalize_structured_glossary(value: Any) -> Dict[str, str]:
        out: Dict[str, str] = {}
        if isinstance(value, dict):
            items = value.items()
        elif isinstance(value, (list, tuple)):
            items = []
            for item in value:
                if isinstance(item, dict):
                    items.append((item.get("source"), item.get("target")))
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    items.append((item[0], item[1]))
        else:
            items = []
        for raw_source, raw_target in items:
            source = str(raw_source or "").strip()
            target = str(raw_target or "").strip()
            if source and target and source != target:
                out[source] = target
        return out

    @classmethod
    def _split_glossary_for_matching(cls, glossary_text: str) -> Tuple[str, List[Dict[str, str]]]:
        """Return free-form notes plus deduplicated structured glossary entries.

        Priority is deliberately ``user > legacy manual > automatic DB`` so a
        user's explicit translation always wins when the same source term exists
        in the scanned game database.
        """
        glossary_text = str(glossary_text or "")
        auto_raw = getattr(Config, "TRANSLATION_AUTO_DB_GLOSSARY", {})
        user_raw = getattr(Config, "TRANSLATION_USER_GLOSSARY", {})
        signature = (
            int(getattr(Config, "TRANSLATION_GLOSSARY_REVISION", 0) or 0),
            glossary_text,
            id(auto_raw),
            id(user_raw),
        )
        if signature == cls._glossary_cache_signature:
            return cls._glossary_cache_manual_text, cls._glossary_cache_entries

        auto_dict = cls._normalize_structured_glossary(auto_raw)
        user_dict = cls._normalize_structured_glossary(user_raw)
        auto_from_legacy: Dict[str, str] = {}
        manual_entries: Dict[str, str] = {}

        def collect_auto_block(match: re.Match) -> str:
            for raw_line in str(match.group(1) or "").splitlines():
                parsed = cls._parse_glossary_line(raw_line)
                if parsed:
                    source, target = parsed
                    auto_from_legacy[source] = target
            return "\n"

        pattern = re.compile(
            re.escape(cls._AUTO_DB_GLOSSARY_BEGIN) + r"(.*?)" + re.escape(cls._AUTO_DB_GLOSSARY_END),
            flags=re.S,
        )
        manual_text = pattern.sub(collect_auto_block, glossary_text).strip()
        note_lines: List[str] = []
        for raw_line in manual_text.splitlines():
            parsed = cls._parse_glossary_line(raw_line)
            if parsed:
                source, target = parsed
                manual_entries[source] = target
            else:
                note_lines.append(raw_line)
        manual_text = "\n".join(note_lines).strip()

        entries: List[Dict[str, str]] = []
        seen = set()
        for origin, mapping in (
            ("user", user_dict),
            ("manual", manual_entries),
            ("db", auto_dict),
            ("db", auto_from_legacy),
        ):
            for source, target in mapping.items():
                if source in seen:
                    continue
                entries.append({"source": source, "target": target, "origin": origin})
                seen.add(source)
        entries.sort(key=lambda item: (-len(item.get("source", "")), item.get("source", "")))

        cls._glossary_cache_signature = signature
        cls._glossary_cache_text = glossary_text
        cls._glossary_cache_manual_text = manual_text
        cls._glossary_cache_entries = list(entries)
        return manual_text, cls._glossary_cache_entries

    @classmethod
    def _has_glossary_data(cls, glossary_text: str = "") -> bool:
        return bool(
            str(glossary_text or "").strip()
            or getattr(Config, "TRANSLATION_AUTO_DB_GLOSSARY", {})
            or getattr(Config, "TRANSLATION_USER_GLOSSARY", {})
        )

    @staticmethod
    def _compact_for_term_matching(values: Optional[Sequence[str]]) -> str:
        if values is None:
            return ""
        return "\n".join(str(v or "") for v in values)

    def _matched_glossary_block(self, glossary_text: str, texts: Optional[Sequence[str]] = None, contexts: Optional[Sequence[str]] = None) -> Tuple[str, str]:
        manual_text, entries = self._split_glossary_for_matching(glossary_text)
        if not entries:
            return manual_text, ""

        haystack = self._compact_for_term_matching(texts) + "\n" + self._compact_for_term_matching(contexts)
        if not haystack.strip():
            return manual_text, ""

        matched: List[Dict[str, str]] = []
        matched_sources: List[str] = []
        seen = set()
        max_terms = int(getattr(Config, "TRANSLATION_MATCHED_GLOSSARY_MAX_TERMS", 80) or 80)
        max_terms = max(1, min(max_terms, 200))
        for e in entries:
            src = str(e.get("source") or "").strip()
            dst = str(e.get("target") or "").strip()
            if not src or not dst or src in seen:
                continue
            if src not in haystack:
                continue
            # Glossary entries are sorted longest-first.  If a longer matched
            # term already contains this shorter source term, omit the shorter
            # one from the API prompt.  Example: when "毒キノコ" is matched,
            # do not also send "毒" just because it appears inside that word.
            if any(src != long_src and len(src) < len(long_src) and src in long_src for long_src in matched_sources):
                continue
            matched.append(e)
            matched_sources.append(src)
            seen.add(src)
            if len(matched) >= max_terms:
                break

        if not matched:
            return manual_text, ""
        templates = get_runtime_prompt_templates()
        lines = []
        entry_template = templates.get("matched_glossary_entry", "")
        for e in matched:
            src = str(e.get("source") or "").strip()
            dst = str(e.get("target") or "").strip()
            origin = str(e.get("origin") or "").strip()
            tag = "DB" if origin == "db" else "사용자"
            lines.append(render_prompt_template(
                entry_template,
                SOURCE=src,
                TARGET=dst,
                ORIGIN=tag,
            ))
        block = render_prompt_template(
            templates.get("matched_glossary_prompt", ""),
            ENTRIES="\n".join(line for line in lines if str(line or "").strip()),
        )
        return manual_text, block

    def _extract_chunk_character_prompts(self, contexts: Optional[Sequence[str]] = None) -> Tuple[List[str], List[str]]:
        """Lift editable prompt blocks out of per-row context once per chunk.

        New contexts use non-editable internal begin/end markers so users may
        freely rewrite every prompt in any language without breaking parsing.
        The old ``Character prompt:``/``Chunk prompt:`` form is still accepted
        for compatibility with older project data and tests.
        """
        if contexts is None:
            return [], []
        prompt_blocks: List[str] = []
        seen = set()
        cleaned_contexts: List[str] = []
        legacy_prompt_markers = {"Character prompt:", "Chunk prompt:"}
        legacy_tail_prefixes = (
            "RPG Maker control codes",
            "RPG Maker message placeholders",
        )
        legacy_row_prefixes = (
            "RPG Maker game translation context",
            "Page:",
            "Map:",
            "Event:",
            "Common event:",
            "Troop battle event:",
            "Battle event page:",
            "Database group:",
            "Database entry ID:",
            "Database field:",
            "Text type:",
            "Face image:",
            "Troop:",
            "Battle page:",
            "DB:",
            "DB ID:",
            "Field:",
            "Type:",
            "Speaker:",
            "Face:",
        )

        def append_block(lines):
            block = "\n".join(x.rstrip() for x in lines).strip()
            if block and block not in seen:
                seen.add(block)
                prompt_blocks.append(block)

        for raw in contexts:
            lines = str(raw or "").splitlines()
            out_lines: List[str] = []
            block_lines: List[str] = []
            in_block = False
            legacy_mode = False
            for line in lines:
                stripped = line.strip()
                if stripped == PROMPT_BLOCK_BEGIN:
                    if in_block and block_lines:
                        append_block(block_lines)
                    block_lines = []
                    in_block = True
                    legacy_mode = False
                    continue
                if stripped == PROMPT_BLOCK_END and in_block and not legacy_mode:
                    append_block(block_lines)
                    block_lines = []
                    in_block = False
                    legacy_mode = False
                    continue
                if not in_block and stripped in legacy_prompt_markers:
                    block_lines = []
                    in_block = True
                    legacy_mode = True
                    continue
                if in_block:
                    if legacy_mode and any(stripped.startswith(prefix) for prefix in legacy_tail_prefixes + legacy_row_prefixes):
                        append_block(block_lines)
                        block_lines = []
                        in_block = False
                        legacy_mode = False
                        out_lines.append(line)
                    else:
                        block_lines.append(line)
                    continue
                out_lines.append(line)
            if in_block and block_lines:
                append_block(block_lines)
            cleaned_contexts.append("\n".join(x for x in out_lines if str(x or "").strip()).strip())
        return prompt_blocks, cleaned_contexts

    def _chunk_character_prompt_block(self, contexts: Optional[Sequence[str]] = None) -> Tuple[str, Optional[List[str]]]:
        blocks, cleaned = self._extract_chunk_character_prompts(contexts)
        if not blocks:
            return "", cleaned if contexts is not None else None
        templates = get_runtime_prompt_templates()
        body = []
        item_template = templates.get("chunk_prompt_item", "")
        for i, block in enumerate(blocks, 1):
            body.append(render_prompt_template(item_template, INDEX=i, PROMPT=block))
        return render_prompt_template(
            templates.get("chunk_prompt_wrapper", ""),
            BLOCKS="\n\n".join(x for x in body if str(x or "").strip()),
        ), cleaned

    def preview_translation_request(self, texts: Sequence[str], contexts: Optional[Sequence[str]] = None, base_id: int = 0) -> Dict[str, Any]:
        """Build a dry-run view of the actual prompt/payload shape for UI verification."""
        context_list = [str(c or "") for c in (contexts or [])] if contexts is not None else None
        chunk_prompt, cleaned_contexts = self._chunk_character_prompt_block(context_list)
        effective_contexts = cleaned_contexts if cleaned_contexts is not None else context_list
        glossary_text = str(getattr(Config, "TRANSLATION_GLOSSARY_TEXT", "") or "").strip()
        manual_glossary, matched_glossary = self._matched_glossary_block(
            glossary_text,
            texts=texts,
            contexts=effective_contexts,
        ) if self._has_glossary_data(glossary_text) else ("", "")
        prompt = self._build_translation_system_prompt(texts=texts, contexts=effective_contexts)
        if chunk_prompt and chunk_prompt not in prompt:
            prompt = (chunk_prompt + "\n\n" + prompt).strip()
        input_items = []
        for i, text in enumerate(texts or []):
            item = {"id": int(base_id) + i, "text": str(text or "")}
            if cleaned_contexts is not None and i < len(cleaned_contexts) and str(cleaned_contexts[i] or "").strip():
                item["context"] = str(cleaned_contexts[i] or "")
            input_items.append(item)
        return {
            "system_prompt": prompt,
            "items": input_items,
            "character_prompt_block": chunk_prompt,
            "cleaned_contexts": cleaned_contexts or [],
            "matched_glossary_block": matched_glossary,
            "manual_glossary_text": manual_glossary,
        }

    def _is_database_translation_chunk(self, contexts: Optional[Sequence[str]] = None) -> bool:
        """Return True when the current chunk is RPG Maker database text."""
        for raw in contexts or []:
            text = str(raw or "")
            padded = "\n" + text
            if "Page: Database" in text or "\nDB:" in padded or "\nField:" in padded:
                return True
        return False

    def _build_translation_system_prompt(self, texts: Optional[Sequence[str]] = None, contexts: Optional[Sequence[str]] = None) -> str:
        """Build the active preset's fully editable system prompt."""
        templates = get_runtime_prompt_templates()
        custom_prompt = str(templates.get("common_prompt") or getattr(Config, "TRANSLATION_PROMPT", "") or "").strip()
        glossary_text = str(getattr(Config, "TRANSLATION_GLOSSARY_TEXT", "") or "").strip()

        parts = []
        if custom_prompt:
            parts.append(custom_prompt)

        manual_glossary, matched_glossary = self._matched_glossary_block(
            glossary_text,
            texts=texts,
            contexts=contexts,
        ) if self._has_glossary_data(glossary_text) else ("", "")

        if manual_glossary:
            manual_block = render_prompt_template(
                templates.get("manual_glossary_prompt", ""),
                GLOSSARY=manual_glossary,
            )
            if manual_block:
                parts.append(manual_block)

        if matched_glossary:
            parts.append(matched_glossary)

        control_token_mode = any("⟦YSB_CC_" in str(text or "") for text in (texts or []))
        if control_token_mode:
            control_code_rule = str(templates.get("control_token_prompt") or "").strip()
        else:
            control_code_rule = str(templates.get("control_code_absent_prompt") or "").strip()

        output_rules = render_prompt_template(
            templates.get("output_format_prompt", ""),
            CONTROL_CODE_RULE=control_code_rule,
        )
        if output_rules:
            parts.append(output_rules)

        return "\n\n".join(part for part in parts if str(part or "").strip()).strip()

    def _translate_text_chunk(self, texts: Sequence[str], provider: str = "openai", base_id: int = 0, contexts: Optional[Sequence[str]] = None) -> List[str]:
        context_list_for_prompt = [str(c or "") for c in (contexts or [])] if contexts is not None else None
        chunk_character_prompt, cleaned_contexts = self._chunk_character_prompt_block(context_list_for_prompt)
        prompt = self._build_translation_system_prompt(texts=texts, contexts=cleaned_contexts if cleaned_contexts is not None else contexts)
        if chunk_character_prompt:
            prompt = (chunk_character_prompt + "\n\n" + prompt).strip()
        contexts = cleaned_contexts if cleaned_contexts is not None else contexts
        provider = (provider or "openai").lower()

        if provider == "google":
            return self._translate_text_chunk_google(texts)
        if provider == "gemini":
            return self._translate_text_chunk_gemini(texts, base_id, contexts=contexts)
        if provider in ("local_argos", "local_hf_jako", "local_hf_enko", "local_nllb"):
            provider = "openai"

        if provider == "deepseek":
            if self.deepseek_client is None:
                raise ValueError("DeepSeek API 키가 비어있습니다.")
            client = self.deepseek_client
            model = Config.DEEPSEEK_TRANSLATION_MODEL
        elif provider == "custom":
            if self.custom_translation_client is None:
                raise ValueError("Custom 번역 API 설정이 비어있습니다. Base URL, Model, API Key를 확인해주세요.")
            client = self.custom_translation_client
            model = str(getattr(Config, "CUSTOM_TRANSLATION_MODEL", "") or "").strip()
            if not model:
                raise ValueError("Custom 번역 모델명이 비어있습니다.")
        elif provider == "lm_studio":
            if self.lm_studio_client is None:
                raise ValueError("LM Studio 서버 설정이 비어있습니다. Base URL을 확인하고 LM Studio Developer 서버를 켜 주세요.")
            client = self.lm_studio_client
            model = str(getattr(Config, "LM_STUDIO_MODEL", "") or "").strip()
            if not model:
                raise ValueError("LM Studio 모델명이 비어있습니다.")
        else:
            if self.openai_client is None:
                raise ValueError("OpenAI API 키가 비어있습니다.")
            client = self.openai_client
            model = Config.OPENAI_TRANSLATION_MODEL

        input_items = []
        context_list = [str(c or "") for c in (contexts or [])] if contexts is not None else None
        for i, text in enumerate(texts):
            item_text = str(text or "")
            item = {"id": base_id + i, "text": item_text}
            if "\n" in item_text:
                line_count = item_text.count("\n") + 1
                item["line_count"] = line_count
                item["line_rule"] = render_prompt_template(
                    get_runtime_prompt_templates().get("line_rule_prompt", ""),
                    LINE_COUNT=line_count,
                )
            if context_list is not None and i < len(context_list) and context_list[i].strip():
                item["context"] = context_list[i]
            input_items.append(item)

        r = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": prompt.strip()},
                {"role": "user", "content": json.dumps(input_items, ensure_ascii=False)},
            ],
            temperature=0.2,
        )

        content = r.choices[0].message.content.strip()
        return self._parse_translation_json_response(content, texts, base_id, provider_name="번역")

    def _parse_translation_json_response(self, content: str, texts: Sequence[str], base_id: int, provider_name: str = "번역") -> List[str]:
        content = str(content or "").strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]

        parsed = json.loads(content.strip())
        if isinstance(parsed, dict):
            items = parsed.get("items", [])
        elif isinstance(parsed, list):
            items = parsed
        else:
            raise ValueError(f"{provider_name} 응답 JSON 형식이 올바르지 않습니다.")

        by_id = {}
        for item in items:
            if isinstance(item, dict):
                try:
                    by_id[int(item.get("id"))] = str(item.get("translation", ""))
                except Exception:
                    pass

        results = []
        missing_ids = []
        for i in range(len(texts)):
            item_id = base_id + i
            if item_id in by_id:
                results.append(by_id[item_id])
            else:
                missing_ids.append(item_id)

        if missing_ids:
            raise ValueError(f"{provider_name} 누락 ID 발생: {missing_ids}")
        return results

    # ---------------------------------------------------------
    # [COMPAT] 역식붕이 이미지 엔진 호환 스텁
    # ---------------------------------------------------------
    def _unsupported_image_feature(self, name: str = "image feature"):
        raise RuntimeError(f"{self.UNSUPPORTED_IMAGE_FEATURE_MESSAGE} ({name})")

    def analyze_image(self, *args, **kwargs):
        self._unsupported_image_feature("analyze_image")

    def analyze_image_quick(self, *args, **kwargs):
        self._unsupported_image_feature("analyze_image_quick")

    def analyze_image_with_provider(self, *args, **kwargs):
        self._unsupported_image_feature("analyze_image_with_provider")

    def execute_inpainting(self, *args, **kwargs):
        self._unsupported_image_feature("execute_inpainting")

    def export_project_result(self, *args, **kwargs):
        self._unsupported_image_feature("export_project_result")

    def _ocr_regions_to_mask(self, regions, w, h):
        """숨은 레거시 호출 방어용 빈 마스크 반환."""
        try:
            import numpy as np
            return np.zeros((int(h), int(w)), dtype=np.uint8)
        except Exception:
            return None


# 기존 코드 호환 이름.
MangaProcessEngine = TranslationProcessEngine

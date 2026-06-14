import json
import time
from dataclasses import dataclass, asdict

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QGridLayout, QLabel, QLineEdit,
    QDialogButtonBox, QMessageBox, QCheckBox, QPushButton, QHBoxLayout,
    QGroupBox, QRadioButton, QButtonGroup, QComboBox, QFileDialog,
    QFrame, QWidget, QScrollArea, QTabWidget, QSpinBox
)

from ysb.core.cache_utils import get_cache_file

CACHE_FILE_NAME = "api_cache.json"


def cache_file():
    return get_cache_file(CACHE_FILE_NAME)

LANG_KO = "ko"
LANG_EN = "en"

from ysb.i18n.lang_text import API_TR_KO_EN

def resolve_ui_language(widget=None):
    cur = widget
    while cur is not None:
        lang = getattr(cur, "ui_language", None) or getattr(cur, "_ui_language", None)
        if lang:
            lang = str(lang).lower()
            if lang.startswith("en"):
                return LANG_EN
            return LANG_KO
        try:
            cur = cur.parent()
        except Exception:
            break
    return LANG_KO

def tr_api(text, lang=LANG_KO):
    text = str(text)
    if str(lang).lower().startswith("en"):
        return API_TR_KO_EN.get(text, text)
    return text


def _is_local_edition_runtime() -> bool:
    """Return True only for the Local edition.

    Lite and Local share most UI/code files, so Local-only providers must be
    filtered at runtime instead of being hard-coded into the common API dialog.
    """
    try:
        from ysb.editions.current import is_local_edition
        return bool(is_local_edition())
    except Exception:
        return False


def resolve_ui_theme(widget=None):
    cur = widget
    while cur is not None:
        theme = getattr(cur, "ui_theme", None) or getattr(cur, "_ui_theme", None)
        if theme:
            return str(theme).lower()
        try:
            cur = cur.parent()
        except Exception:
            break
    return "dark"


def api_dialog_soft_qss(theme="dark"):
    light = str(theme or "").lower().startswith("light")
    if light:
        return """
            QDialog { background:#f6f7f9; color:#202124; }
            QScrollArea { background:transparent; border:0; }
            QWidget#ApiDialogBody { background:transparent; }
            QLabel { color:#202124; }
            QLabel#SettingsDialogTitle { font-size:22px; font-weight:800; color:#141416; }
            QLabel#SettingsDescription { color:#625A61; }
            QLabel#SettingsSectionTitle { font-size:16px; font-weight:750; color:#141416; }
            QLabel#SettingsItemTitle { font-size:13px; font-weight:700; color:#141416; }
            QFrame#SettingsBlock { background:#ffffff; border:1px solid #DAD4D8; border-radius:12px; }
            QFrame#SettingsItem { background:#FAF5F7; border:1px solid #e3e7ee; border-radius:10px; }
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
                background:#ffffff; color:#202124; border:1px solid #c8ced8; border-radius:5px; padding:5px;
                selection-background-color:#cfe3ff; selection-color:#000000;
            }
            QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
                border:1px solid #7da7df; background:#ffffff;
            }
            QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled { background:#F0EAED; color:#8a93a2; }
            QPushButton { background:#ffffff; color:#202124; border:1px solid #B2ABB0; border-radius:7px; padding:7px 12px; }
            QPushButton:hover { background:#e9eef7; border-color:#8fa7c8; }
            QPushButton:pressed { background:#dfe7f3; }
            QPushButton:disabled { background:#edf0f4; color:#9aa0aa; border-color:#d3d7df; }
            QCheckBox, QRadioButton { color:#202124; spacing:8px; }
            QCheckBox::indicator, QRadioButton::indicator { width:14px; height:14px; border:1px solid #8d96a4; background:#ffffff; }
            QCheckBox::indicator:checked, QRadioButton::indicator:checked { background:#4b8de8; border:1px solid #4b8de8; }
            QTabWidget::pane {
                border:1px solid #DED8DC;
                border-radius:0px;
                background:#ffffff;
                top:-1px;
            }
            QTabBar::tab {
                background:#EEEFF3;
                color:#555056;
                border:1px solid #DAD4D8;
                border-bottom:none;
                border-top-left-radius:10px;
                border-top-right-radius:10px;
                padding:4px 10px;
                min-width:100px;
            }
            QTabBar::tab:selected { background:#ffffff; color:#211F23; font-weight:700; }
            QTabBar::tab:!selected { background:#EEEFF3; color:#6F666D; }
            QTabBar::tab:hover { background:#FBF5F6; color:#111827; }
            QScrollBar:vertical { background:#F0EAED; width:12px; margin:0; border:0; }
            QScrollBar::handle:vertical { background:#c7ceda; min-height:30px; border-radius:5px; }
            QScrollBar::handle:vertical:hover { background:#aeb8c8; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        """
    return """
        QDialog { background:#1f1f22; color:#f2f2f2; }
        QScrollArea { background:transparent; border:0; }
        QWidget#ApiDialogBody { background:transparent; }
        QLabel { color:#f2f2f2; }
        QLabel#SettingsDialogTitle { font-size:22px; font-weight:800; color:#ffffff; }
        QLabel#SettingsDescription { color:#b6bdc9; }
        QLabel#SettingsSectionTitle { font-size:16px; font-weight:750; color:#ffffff; }
        QLabel#SettingsItemTitle { font-size:13px; font-weight:700; color:#ffffff; }
        QFrame#SettingsBlock { background:#292c33; border:1px solid #49434A; border-radius:12px; }
        QFrame#SettingsItem { background:#24272e; border:1px solid #3d414b; border-radius:10px; }
        QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {
            background:#202228; color:#f5f5f5; border:1px solid #49434A; border-radius:5px; padding:5px;
            selection-background-color:#4b79ff; selection-color:#ffffff;
        }
        QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus, QDoubleSpinBox:focus {
            border:1px solid #6f8fca; background:#23262d;
        }
        QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled { background:#1d1f25; color:#838996; }
        QPushButton { background:#383238; color:#f2f2f2; border:1px solid #625C63; border-radius:7px; padding:7px 12px; }
        QPushButton:hover { background:#454047; border-color:#788094; }
        QPushButton:pressed { background:#2d3038; }
        QPushButton:disabled { background:#2a2b2f; color:#8b8d93; border-color:#44474f; }
        QCheckBox, QRadioButton { color:#f2f2f2; spacing:8px; }
        QCheckBox::indicator, QRadioButton::indicator { width:14px; height:14px; border:1px solid #72757f; background:#202228; }
        QCheckBox::indicator:checked, QRadioButton::indicator:checked { background:#5da9ff; border:1px solid #5da9ff; }
        QTabWidget::pane {
            border:1px solid #3A363B;
            border-radius:0px;
            background:#252328;
            top:-1px;
        }
        QTabBar::tab {
            background:#2B282D;
            color:#BDB6BB;
            border:1px solid #3A363B;
            border-bottom:none;
            border-top-left-radius:10px;
            border-top-right-radius:10px;
            padding:4px 10px;
            min-width:100px;
        }
        QTabBar::tab:selected { background:#373136; color:#ffffff; font-weight:700; }
        QTabBar::tab:!selected { background:#2B282D; color:#BDB6BB; }
        QTabBar::tab:hover { background:#3A343A; color:#ffffff; }
        QScrollBar:vertical { background:#202228; width:12px; margin:0; border:0; }
        QScrollBar::handle:vertical { background:#49434A; min-height:30px; border-radius:5px; }
        QScrollBar::handle:vertical:hover { background:#5a6170; }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
    """


@dataclass
class ApiSettings:
    # 선택 제공자
    selected_ocr_provider: str = "clova"
    selected_inpaint_provider: str = "replicate_lama"
    selected_translation_provider: str = "openai"

    # OCR API
    clova_api_url: str = ""
    clova_secret_key: str = ""
    clova_model: str = "clova_ocr_v2"
    clova_ocr_language: str = "ja"
    # 과거 테스트 버전 호환용: JSON 경로 값은 로드만 유지하고 UI에서는 API Key 방식을 사용한다.
    google_vision_credential_json_path: str = ""
    google_vision_api_key: str = ""
    google_vision_model: str = "DOCUMENT_TEXT_DETECTION"
    google_vision_ocr_language: str = "en"
    google_vision_language_hints: str = "ja,ko,en"

    # Local OCR
    # v2.1.0: comic_text_detector로 안전 마스크를 만들고 PaddleOCR로 문자 인식한다.
    local_paddle_mask_device: str = "auto"
    local_paddle_ocr_language: str = "ja"

    # Translation API
    openai_api_key: str = ""
    deepseek_api_key: str = ""
    google_translate_api_key: str = ""
    gemini_api_key: str = ""
    custom_translation_api_key: str = ""
    custom_translation_base_url: str = ""
    custom_translation_model: str = ""
    custom_translation_preset_name: str = "Custom Compatible"
    lm_studio_base_url: str = "http://localhost:1234/v1"
    lm_studio_model: str = ""
    lm_studio_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    deepseek_model: str = "deepseek-v4-flash"
    google_translate_model: str = "google_translate_basic_v2"
    gemini_model: str = "gemini-2.5-flash-lite"
    gemini_delayed_api_key: str = ""
    gemini_delayed_model: str = "gemini-2.5-flash-lite"
    gemini_delayed_mode: str = "flex"

    # Translation chunk sizes
    # 상단 툴바에서는 숨기고, API 관리 > 번역 탭에서 제공자별로 관리한다.
    # 기본값은 모든 API 제공자를 50개로 통일한다.
    translation_chunk_defaults_version: int = 2
    openai_chunk_size: int = 50
    deepseek_chunk_size: int = 50
    google_translate_chunk_size: int = 50
    gemini_chunk_size: int = 50
    gemini_delayed_chunk_size: int = 50
    custom_translation_chunk_size: int = 50
    lm_studio_chunk_size: int = 20

    # Inpainting API
    # replicate_api_token은 구버전 캐시 호환용으로만 유지한다.
    # 실제 UI/실행은 LaMa와 Stable 토큰을 완전히 분리해서 사용한다.
    replicate_api_token: str = ""
    lama_replicate_api_token: str = ""
    stable_replicate_api_token: str = ""
    repaint_model: str = "allenhooo/lama:cdac78a1bec5b23c07fd29692fb70baa513ea403a39e643c48ec5edadb15fe72"
    replicate_lama_wait_seconds: int = 3
    stable_inpaint_model: str = "stability-ai/stable-diffusion-inpainting:95b7223104132402a9ae91cc677285bc5eb997834bd2349fa486f53910fd68b3"
    stable_inpaint_prompt: str = "remove text and restore the original background"
    stable_inpaint_wait_seconds: int = 3
    local_lama_wait_seconds: int = 0
    gemini_inpaint_model: str = "gemini-2.5-flash-image"
    gemini_inpaint_prompt: str = (
        "Remove the text only inside the white mask area and reconstruct the original manga background. "
        "Keep all characters, panel borders, screentones, line art, and unmasked areas unchanged. "
        "Return only the edited full image."
    )


class ApiSettingsStore:
    @staticmethod
    def load() -> ApiSettings:
        p = cache_file()
        if not p.exists():
            return ApiSettings()
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            base = asdict(ApiSettings())

            # 쯔꾸르붕이 경량화 후 첫 실행 안전장치:
            # 기존 AppData 캐시가 구버전/깨진 형태(list 등)로 남아 있으면
            # 시작 중 data.items()에서 바로 크래시가 났다.
            # API 캐시는 사용자 환경 파일이므로 타입이 맞지 않으면 기본값으로 복구한다.
            if not isinstance(data, dict):
                try:
                    backup = p.with_suffix(p.suffix + f".invalid_{int(time.time())}")
                    p.replace(backup)
                except Exception:
                    pass
                return ApiSettings()

            # 과거 캐시 호환: 알 수 없는 키는 무시하고, 새 키는 기본값 유지
            base.update({k: v for k, v in data.items() if k in base})

            # 쯔꾸르붕이 번역 기본 묶음 수 통일 마이그레이션:
            # 구버전 기본값(DeepSeek 8, Gemini 10 등)을 그대로 쓰던 캐시는 50으로 올린다.
            # 사용자가 업데이트 후 직접 바꾼 값은 version marker로 다시 덮어쓰지 않는다.
            try:
                chunk_defaults_version = int(data.get("translation_chunk_defaults_version", 1) or 1)
            except Exception:
                chunk_defaults_version = 1
            if chunk_defaults_version < 2:
                legacy_chunk_defaults = {
                    "openai_chunk_size": 20,
                    "deepseek_chunk_size": 8,
                    "google_translate_chunk_size": 50,
                    "gemini_chunk_size": 10,
                    "custom_translation_chunk_size": 20,
                    "lm_studio_chunk_size": 20,
                }
                for _key, _legacy in legacy_chunk_defaults.items():
                    try:
                        if int(base.get(_key, _legacy) or 0) == int(_legacy):
                            base[_key] = 50
                    except Exception:
                        base[_key] = 50
                base["translation_chunk_defaults_version"] = 2

            # v2.1.0: Local translation engines are hidden from the regular UI.
            # Translation stays API-based because local translation models are too large for the core Local build.
            legacy_provider = str(base.get("selected_translation_provider", "") or "").lower()
            if legacy_provider in ("local_argos", "local_hf_jako", "local_hf_enko", "local_nllb"):
                base["selected_translation_provider"] = "openai"

            local_enabled = _is_local_edition_runtime()

            # Lite판에서는 API 관리창과 실행 설정에서 Local 모델을 노출/사용하지 않는다.
            # Local판에서만 안정 조합인 LOCAL Paddle OCR / LOCAL LaMa를 허용한다.
            legacy_ocr_provider = str(base.get("selected_ocr_provider", "") or "").lower()
            if legacy_ocr_provider.startswith("local_"):
                if local_enabled and legacy_ocr_provider in ("local_paddle_ocr", "local_manga_ocr"):
                    base["selected_ocr_provider"] = legacy_ocr_provider
                else:
                    base["selected_ocr_provider"] = "local_paddle_ocr" if local_enabled else "clova"

            legacy_inpaint_provider = str(base.get("selected_inpaint_provider", "") or "").lower()
            if legacy_inpaint_provider.startswith("local_"):
                base["selected_inpaint_provider"] = "local_lama" if local_enabled else "replicate_lama"

            # v1.6 이전 캐시는 replicate_api_token 하나를 LaMa/Stable이 공유했다.
            # 새 구조에서는 두 토큰을 분리하되, 기존 사용자가 바로 깨지지 않도록 최초 로드 시 양쪽에 복사한다.
            legacy_token = str(base.get("replicate_api_token", "") or "").strip()
            if legacy_token:
                if not str(base.get("lama_replicate_api_token", "") or "").strip():
                    base["lama_replicate_api_token"] = legacy_token
                if not str(base.get("stable_replicate_api_token", "") or "").strip():
                    base["stable_replicate_api_token"] = legacy_token

            return ApiSettings(**base)
        except Exception:
            return ApiSettings()

    @staticmethod
    def save(settings: ApiSettings):
        p = cache_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(asdict(settings), f, ensure_ascii=False, indent=2)

    @staticmethod
    def cache_path() -> str:
        return str(cache_file())


def apply_settings_to_config(settings: ApiSettings):
    """Inject cached API settings into manga_engine.Config."""
    try:
        import os as _os
        from ysb.engine.manga_engine import Config

        local_enabled = _is_local_edition_runtime()

        # OCR
        Config.OCR_PROVIDER = (settings.selected_ocr_provider or "clova").strip() or "clova"
        if Config.OCR_PROVIDER.startswith("local_"):
            if local_enabled and Config.OCR_PROVIDER in ("local_paddle_ocr", "local_manga_ocr"):
                Config.OCR_PROVIDER = Config.OCR_PROVIDER
            else:
                Config.OCR_PROVIDER = "local_paddle_ocr" if local_enabled else "clova"
        Config.CLOVA_API_URL = settings.clova_api_url.strip()
        Config.CLOVA_SECRET_KEY = settings.clova_secret_key.strip()
        Config.CLOVA_MODEL = settings.clova_model.strip() or "clova_ocr_v2"
        Config.CLOVA_OCR_LANGUAGE = (settings.clova_ocr_language or "ja").strip() or "ja"
        Config.GOOGLE_VISION_CREDENTIAL_JSON_PATH = settings.google_vision_credential_json_path.strip()  # 구버전 캐시 호환
        Config.GOOGLE_VISION_API_KEY = settings.google_vision_api_key.strip()
        Config.GOOGLE_VISION_MODEL = settings.google_vision_model.strip() or "DOCUMENT_TEXT_DETECTION"
        Config.GOOGLE_VISION_OCR_LANGUAGE = (settings.google_vision_ocr_language or "en").strip() or "en"
        # 구버전 호환용 값은 유지하되, UI에서는 더 이상 직접 입력받지 않는다.
        Config.GOOGLE_VISION_LANGUAGE_HINTS = settings.google_vision_language_hints.strip() or Config.GOOGLE_VISION_OCR_LANGUAGE
        Config.LOCAL_PADDLE_MASK_DEVICE = (settings.local_paddle_mask_device or "auto").strip() or "auto"
        Config.LOCAL_PADDLE_MASK_INPUT_SIZE = "auto"
        Config.LOCAL_PADDLE_OCR_LANGUAGE = (settings.local_paddle_ocr_language or "ja").strip() or "ja"
        # Translation
        Config.TRANSLATION_PROVIDER = (settings.selected_translation_provider or "openai").strip() or "openai"
        Config.OPENAI_API_KEY = settings.openai_api_key.strip()
        Config.DEEPSEEK_API_KEY = settings.deepseek_api_key.strip()
        Config.GOOGLE_TRANSLATE_API_KEY = settings.google_translate_api_key.strip()
        Config.GEMINI_API_KEY = settings.gemini_api_key.strip()
        Config.GEMINI_DELAYED_API_KEY = settings.gemini_delayed_api_key.strip()
        Config.CUSTOM_TRANSLATION_API_KEY = settings.custom_translation_api_key.strip()
        Config.CUSTOM_TRANSLATION_BASE_URL = settings.custom_translation_base_url.strip()
        Config.CUSTOM_TRANSLATION_MODEL = settings.custom_translation_model.strip()
        Config.CUSTOM_TRANSLATION_PRESET_NAME = settings.custom_translation_preset_name.strip() or "Custom Compatible"
        Config.LM_STUDIO_BASE_URL = (settings.lm_studio_base_url.strip() or "http://localhost:1234/v1").rstrip("/")
        Config.LM_STUDIO_MODEL = settings.lm_studio_model.strip()
        # LM Studio's OpenAI-compatible server normally does not require an API key.
        # The OpenAI Python client still needs a non-empty token string, so the
        # engine will use a harmless local dummy key when this field is blank.
        Config.LM_STUDIO_API_KEY = settings.lm_studio_api_key.strip()
        Config.OPENAI_TRANSLATION_MODEL = settings.openai_model.strip() or "gpt-4o-mini"
        Config.DEEPSEEK_TRANSLATION_MODEL = settings.deepseek_model.strip() or "deepseek-v4-flash"
        Config.GOOGLE_TRANSLATE_MODEL = settings.google_translate_model.strip() or "google_translate_basic_v2"
        Config.GEMINI_TRANSLATION_MODEL = settings.gemini_model.strip() or "gemini-2.5-flash-lite"
        Config.GEMINI_DELAYED_TRANSLATION_MODEL = settings.gemini_delayed_model.strip() or "gemini-2.5-flash-lite"
        Config.GEMINI_DELAYED_MODE = (settings.gemini_delayed_mode or "flex").strip().lower() or "flex"

        # Inpainting
        Config.INPAINT_PROVIDER = (settings.selected_inpaint_provider or "replicate_lama").strip() or "replicate_lama"
        if Config.INPAINT_PROVIDER.startswith("local_"):
            Config.INPAINT_PROVIDER = "local_lama" if local_enabled else "replicate_lama"

        legacy_token = settings.replicate_api_token.strip()
        Config.LAMA_REPLICATE_API_TOKEN = (settings.lama_replicate_api_token.strip() or legacy_token)
        Config.STABLE_REPLICATE_API_TOKEN = (settings.stable_replicate_api_token.strip() or legacy_token)

        # 구버전 호환용 전역 토큰. 실제 호출은 각 provider 전용 토큰을 우선 사용한다.
        Config.REPLICATE_API_TOKEN = Config.STABLE_REPLICATE_API_TOKEN if Config.INPAINT_PROVIDER == "replicate_stable" else Config.LAMA_REPLICATE_API_TOKEN

        Config.INPAINT_MODEL = settings.repaint_model.strip()
        Config.REPAINT_MODEL = Config.INPAINT_MODEL  # 구버전 호환
        Config.REPLICATE_LAMA_WAIT_SECONDS = max(0, int(getattr(settings, "replicate_lama_wait_seconds", 3) or 0))
        Config.STABLE_INPAINT_MODEL = settings.stable_inpaint_model.strip() or "stability-ai/stable-diffusion-inpainting:95b7223104132402a9ae91cc677285bc5eb997834bd2349fa486f53910fd68b3"
        Config.STABLE_INPAINT_PROMPT = settings.stable_inpaint_prompt.strip() or "remove text and restore the original background"
        Config.STABLE_INPAINT_WAIT_SECONDS = max(0, int(getattr(settings, "stable_inpaint_wait_seconds", 3) or 0))
        Config.LOCAL_LAMA_WAIT_SECONDS = max(0, int(getattr(settings, "local_lama_wait_seconds", 0) or 0))
        gemini_inpaint_model = settings.gemini_inpaint_model.strip() or "gemini-2.5-flash-image"
        # The old preview model was shut down; auto-migrate old cache values.
        if gemini_inpaint_model == "gemini-2.5-flash-image":
            gemini_inpaint_model = "gemini-2.5-flash-image"
        Config.GEMINI_INPAINT_MODEL = gemini_inpaint_model
        Config.GEMINI_INPAINT_PROMPT = settings.gemini_inpaint_prompt.strip() or (
            "Remove the text only inside the white mask area and reconstruct the original manga background. "
            "Keep all characters, panel borders, screentones, line art, and unmasked areas unchanged. "
            "Return only the edited full image."
        )

        if Config.REPLICATE_API_TOKEN:
            _os.environ["REPLICATE_API_TOKEN"] = Config.REPLICATE_API_TOKEN
    except Exception:
        pass


class ApiSettingsDialog(QDialog):
    def __init__(self, settings: ApiSettings, parent=None, show_cache_path=False):
        super().__init__(parent)
        self._show_cache_path = bool(show_cache_path)
        self._ui_language = resolve_ui_language(parent)
        self._ui_theme = resolve_ui_theme(parent)
        self.setWindowTitle(tr_api("API 관리", self._ui_language))
        self.resize(920, 640)
        try:
            self.setStyleSheet(parent.settings_dialog_style() if parent is not None and hasattr(parent, "settings_dialog_style") else api_dialog_soft_qss(self._ui_theme))
        except Exception:
            self.setStyleSheet(api_dialog_soft_qss(self._ui_theme))
        self.setMinimumSize(760, 420)
        self.setSizeGripEnabled(True)
        self.settings = settings
        self.edits = {}
        self.combos = {}
        self.buttons = {}
        self.button_groups = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel(tr_api("API 관리", self._ui_language), self)
        title.setObjectName("SettingsDialogTitle")
        layout.addWidget(title)

        intro = QLabel(
            tr_api(
                "쯔꾸르붕이에서 사용할 번역 API 주소·키·모델명을 관리합니다.\n"
                "확인을 누르면 사용자 설정 캐시에 저장되고, 닫기를 누르면 저장하지 않습니다.",
                self._ui_language
            ),
            self,
        )
        intro.setObjectName("SettingsDescription")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        if self._show_cache_path:
            cache = QLabel(tr_api("캐시 위치: ", self._ui_language) + ApiSettingsStore.cache_path(), self)
            cache.setObjectName("SettingsDescription")
            cache.setWordWrap(True)
            layout.addWidget(cache)

        tabs = QTabWidget(self)
        tabs.setObjectName("SettingsTabs")
        tabs.setDocumentMode(False)
        tabs.setMovable(False)
        tabs.setUsesScrollButtons(False)
        try:
            tabs.tabBar().setExpanding(False)
        except Exception:
            pass
        tabs.setStyleSheet("""
            QTabWidget#SettingsTabs::pane { border:1px solid #3A363B; background:#252328; top:-1px; }
            QTabWidget#SettingsTabs QTabBar::tab {
                background:#2B282D; color:#BDB6BB; border:1px solid #3A363B; border-bottom:none;
                border-top-left-radius:8px; border-top-right-radius:8px;
                padding:7px 18px; min-width:78px; font-weight:600;
            }
            QTabWidget#SettingsTabs QTabBar::tab:selected { background:#373136; color:#ffffff; font-weight:800; }
            QTabWidget#SettingsTabs QTabBar::tab:hover { background:#3A343A; color:#ffffff; }
        """)
        layout.addWidget(tabs, 1)

        trans_content_layout, trans_tab = self._create_api_tab_content()

        tabs.addTab(trans_tab, tr_api("번역", self._ui_language))

        self._add_api_section(trans_content_layout, tr_api("번역", self._ui_language), [
            {"_category": True, "title": "API 기반 모델", "description": "외부 API를 사용하는 번역 모델입니다. API 키가 필요합니다."},
            {
                "provider": "openai",
                "title": "OpenAI",
                "fields": [
                    ("Model", "openai_model", False, "gpt-4o-mini"),
                    ("묶음 수", "openai_chunk_size", False, 50, "spin", (1, 100)),
                    ("API Key", "openai_api_key", True, "OpenAI API Key"),
                ],
            },
            {
                "provider": "deepseek",
                "title": "DeepSeek",
                "fields": [
                    ("Model", "deepseek_model", False, "deepseek-chat"),
                    ("묶음 수", "deepseek_chunk_size", False, 50, "spin", (1, 100)),
                    ("API Key", "deepseek_api_key", True, "DeepSeek API Key"),
                ],
            },
            {
                "provider": "google",
                "title": "Google Translate",
                "fields": [
                    ("Model", "google_translate_model", False, "google_translate_basic_v2"),
                    ("묶음 수", "google_translate_chunk_size", False, 50, "spin", (1, 100)),
                    ("API Key", "google_translate_api_key", True, "Google Translate API Key"),
                ],
            },
            {
                "provider": "gemini",
                "title": "Gemini / Google AI Studio",
                "fields": [
                    ("Model", "gemini_model", False, "gemini-2.5-flash-lite"),
                    ("묶음 수", "gemini_chunk_size", False, 50, "spin", (1, 100)),
                    ("API Key", "gemini_api_key", True, "Google AI Studio Gemini API Key"),
                ],
            },
            {
                "provider": "gemini_deferred",
                "title": "Gemini Flex / Batch",
                "description": "일반 번역 진행창 대신 청크 현황 창을 사용합니다. 완료된 청크는 즉시 반영되고, 실패한 청크만 다시 시도할 수 있습니다. 작업 중에는 다른 프로젝트 작업을 할 수 없습니다.",
                "fields": [
                    ("요청 방식", "gemini_delayed_mode", False, "Flex API", "combo", [("Flex API", "flex"), ("Batch API", "batch")]),
                    ("Model", "gemini_delayed_model", False, "gemini-2.5-flash-lite"),
                    ("묶음 수", "gemini_delayed_chunk_size", False, 50, "spin", (1, 100)),
                    ("API Key", "gemini_delayed_api_key", True, "Google AI Studio Gemini API Key"),
                ],
            },
            {
                "provider": "lm_studio",
                "title": "LM Studio / Local OpenAI-Compatible",
                "description": "LM Studio의 Developer 서버를 켠 뒤 사용할 수 있습니다. 기본 주소는 http://localhost:1234/v1 입니다. 모델은 LM Studio에서 먼저 다운로드/로드해야 합니다. API Key는 보통 비워도 됩니다.",
                "fields": [
                    ("Base URL", "lm_studio_base_url", False, "http://localhost:1234/v1"),
                    ("Model", "lm_studio_model", False, "LM Studio에서 로드한 모델명"),
                    ("묶음 수", "lm_studio_chunk_size", False, 20, "spin", (1, 100)),
                    ("API Key", "lm_studio_api_key", True, "비워도 됨 / optional"),
                ],
            },
            {
                "provider": "custom",
                "title": "Custom / OpenAI-Compatible",
                "description": "OpenAI Chat Completions 호환 API만 사용할 수 있습니다. Base URL, Model, API Key를 입력하세요.\n호환 예시: OpenRouter, Groq, xAI Grok, Together, vLLM, Ollama OpenAI 호환 서버",
                "fields": [
                    ("Preset Name", "custom_translation_preset_name", False, "OpenRouter / Groq / xAI"),
                    ("Base URL", "custom_translation_base_url", False, "https://api.x.ai/v1"),
                    ("Model", "custom_translation_model", False, "grok-4.3"),
                    ("묶음 수", "custom_translation_chunk_size", False, 50, "spin", (1, 100)),
                    ("API Key", "custom_translation_api_key", True, "OpenAI-compatible API Key"),
                ],
            },
        ], "selected_translation_provider")

        trans_content_layout.addStretch(1)

        option_line = QHBoxLayout()
        self.show_keys = QCheckBox(tr_api("키 보이기", self._ui_language))
        self.show_keys.toggled.connect(self.toggle_key_visibility)
        option_line.addWidget(self.show_keys)

        btn_clear = QPushButton(tr_api("입력칸 비우기", self._ui_language))
        btn_clear.clicked.connect(self.clear_all)
        option_line.addWidget(btn_clear)
        option_line.addStretch()
        layout.addLayout(option_line)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr_api("확인", self._ui_language))
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText(tr_api("닫기", self._ui_language))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


    def _create_api_tab_content(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget(self)
        content.setObjectName("ApiDialogBody")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        scroll.setWidget(content)
        return content_layout, scroll

    def _add_separator(self, layout):
        # 새 카드형 UI에서는 굵은 구분선 대신 섹션 카드 자체의 여백/외곽선으로 구분한다.
        return

    def _add_api_section(self, parent_layout, section_title, cards, selected_attr):
        block = QFrame(self)
        block.setObjectName("SettingsBlock")
        block_layout = QVBoxLayout(block)
        block_layout.setContentsMargins(16, 14, 16, 14)
        block_layout.setSpacing(10)

        title = QLabel(section_title, block)
        title.setObjectName("SettingsSectionTitle")
        block_layout.addWidget(title)

        if str(section_title).upper().startswith("OCR"):
            desc_text = "이미지의 글자를 읽어올 OCR 제공자를 선택합니다. 선택한 제공자 한 개만 분석 작업에 사용됩니다."
        elif "인페인" in str(section_title) or "Inpaint" in str(section_title):
            desc_text = "마스크 영역의 배경을 복원할 인페인팅 제공자를 선택합니다. 선택한 제공자 한 개만 인페인팅 작업에 사용됩니다."
        else:
            desc_text = "AI 번역에 사용할 번역 제공자를 선택합니다. 선택한 제공자 한 개만 번역 작업에 사용됩니다."
        desc = QLabel(tr_api(desc_text, self._ui_language), block)
        desc.setObjectName("SettingsDescription")
        desc.setWordWrap(True)
        block_layout.addWidget(desc)

        group = QButtonGroup(self)
        group.setExclusive(True)
        self.button_groups[selected_attr] = group
        selected_value = str(getattr(self.settings, selected_attr, "") or "")
        data = asdict(self.settings)

        for card in cards:
            if card.get("_category"):
                cat = QLabel(tr_api(str(card.get("title", "")), self._ui_language), block)
                cat.setObjectName("SettingsItemTitle")
                cat.setStyleSheet("font-size:14px; font-weight:800; margin-top:8px; padding-top:4px;")
                block_layout.addWidget(cat)
                cat_desc = str(card.get("description", "") or "").strip()
                if cat_desc:
                    cat_desc_label = QLabel(tr_api(cat_desc, self._ui_language), block)
                    cat_desc_label.setObjectName("SettingsDescription")
                    cat_desc_label.setWordWrap(True)
                    block_layout.addWidget(cat_desc_label)
                continue
            provider = card["provider"]
            item = QFrame(block)
            item.setObjectName("SettingsItem")
            item_layout = QVBoxLayout(item)
            item_layout.setContentsMargins(12, 10, 12, 10)
            item_layout.setSpacing(8)

            header = QHBoxLayout()
            header.setContentsMargins(0, 0, 0, 0)
            header.setSpacing(8)
            radio = QRadioButton(item)
            radio.setToolTip(f"{section_title} {tr_api('제공자를 사용합니다.', self._ui_language)}" if self._ui_language == LANG_EN else f"이 {section_title} 제공자를 사용합니다.")
            group.addButton(radio)
            self.buttons[provider] = radio
            header.addWidget(radio, 0)
            card_title = QLabel(card["title"], item)
            card_title.setObjectName("SettingsItemTitle")
            header.addWidget(card_title, 1)
            item_layout.addLayout(header)

            desc_text = str(card.get("description", "") or "").strip()
            if desc_text:
                desc_label = QLabel(tr_api(desc_text, self._ui_language), item)
                desc_label.setObjectName("SettingsDescription")
                desc_label.setWordWrap(True)
                item_layout.addWidget(desc_label)

            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(7)
            grid.setColumnStretch(1, 1)
            for r, field in enumerate(card["fields"]):
                label, key, secret, placeholder = field[:4]
                field_type = field[4] if len(field) >= 5 else "text"
                field_choices = field[5] if len(field) >= 6 else []
                field_suffix = field[6] if len(field) >= 7 else None
                lab = QLabel(tr_api(label, self._ui_language), item)
                lab.setMinimumWidth(110)
                grid.addWidget(lab, r, 0)
                if field_type == "combo":
                    edit = QComboBox(item)
                    for choice_label, choice_value in field_choices:
                        edit.addItem(tr_api(choice_label, self._ui_language), str(choice_value))
                    current_value = str(data.get(key, "") or "")
                    found_index = edit.findData(current_value)
                    if found_index < 0:
                        found_index = edit.findText(current_value)
                    if found_index < 0:
                        found_index = 0
                    edit.setCurrentIndex(found_index)
                    grid.addWidget(edit, r, 1)
                elif field_type == "spin":
                    edit = QSpinBox(item)
                    min_v, max_v = (1, 100)
                    try:
                        if field_choices and len(field_choices) >= 2:
                            min_v, max_v = int(field_choices[0]), int(field_choices[1])
                    except Exception:
                        min_v, max_v = (1, 100)
                    edit.setRange(min_v, max_v)
                    try:
                        edit.setValue(int(data.get(key, placeholder) or placeholder or min_v))
                    except Exception:
                        edit.setValue(min_v)
                    if field_suffix is None:
                        edit.setSuffix(" items" if self._ui_language == LANG_EN else "개")
                    else:
                        edit.setSuffix(str(field_suffix))
                    grid.addWidget(edit, r, 1)
                else:
                    edit = QLineEdit(item)
                    edit.setText(str(data.get(key, "")))
                    edit.setPlaceholderText(str(placeholder))
                    if secret:
                        edit.setEchoMode(QLineEdit.EchoMode.Password)
                    if field_type == "file":
                        file_row = QHBoxLayout()
                        file_row.setContentsMargins(0, 0, 0, 0)
                        file_row.setSpacing(8)
                        file_row.addWidget(edit, 1)
                        btn_browse = QPushButton(tr_api("찾아보기", self._ui_language), item)
                        btn_browse.clicked.connect(lambda _=False, e=edit: self.browse_json_file(e))
                        file_row.addWidget(btn_browse)
                        grid.addLayout(file_row, r, 1)
                    else:
                        grid.addWidget(edit, r, 1)
                self.edits.setdefault(key, []).append(edit)
            item_layout.addLayout(grid)
            block_layout.addWidget(item)
            if provider == selected_value:
                radio.setChecked(True)

        if not any(btn.isChecked() for btn in group.buttons()) and group.buttons():
            group.buttons()[0].setChecked(True)

        parent_layout.addWidget(block)

    def browse_json_file(self, edit: QLineEdit):
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr_api("JSON 파일 선택", self._ui_language),
            edit.text().strip() or "",
            "JSON Files (*.json);;All Files (*.*)"
        )
        if path:
            edit.setText(path)

    def toggle_key_visibility(self, checked: bool):
        secret_keys = [
            "openai_api_key", "deepseek_api_key", "google_translate_api_key",
            "gemini_api_key", "gemini_delayed_api_key", "custom_translation_api_key", "lm_studio_api_key"
        ]
        for key in secret_keys:
            for edit in self.edits.get(key, []):
                edit.setEchoMode(QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password)

    def clear_all(self):
        if QMessageBox.question(self, tr_api("입력칸 비우기", self._ui_language), tr_api("입력칸을 전부 비울까요?", self._ui_language)) != QMessageBox.StandardButton.Yes:
            return
        seen = set()
        for key, edits in self.edits.items():
            for edit in edits:
                if id(edit) in seen:
                    continue
                seen.add(id(edit))
                if isinstance(edit, QComboBox):
                    if edit.count() > 0:
                        edit.setCurrentIndex(0)
                else:
                    edit.clear()

    def _selected_provider_for(self, attr_name: str, default: str) -> str:
        group = self.button_groups.get(attr_name)
        if not group:
            return default
        for provider, btn in self.buttons.items():
            if btn.isChecked() and group.id(btn) != -1:
                # 다른 그룹 버튼도 self.buttons에 섞여 있으므로, 이 그룹 소속인지 확인
                if btn in group.buttons():
                    return provider
        for btn in group.buttons():
            if btn.isChecked():
                for provider, candidate in self.buttons.items():
                    if candidate is btn:
                        return provider
        return default

    def _first_edit_text(self, key: str) -> str:
        edits = self.edits.get(key, [])
        if not edits:
            return ""
        # 같은 키가 여러 카드에 중복 표시될 수 있다.
        # 사용자가 어느 칸에 입력해도 저장되도록 비어있지 않은 값을 우선 사용한다.
        for edit in edits:
            if isinstance(edit, QComboBox):
                value = str(edit.currentData() or edit.currentText() or "").strip()
            elif isinstance(edit, QSpinBox):
                value = str(edit.value()).strip()
            else:
                value = edit.text().strip()
            if value:
                return value
        first = edits[0]
        if isinstance(first, QComboBox):
            return str(first.currentData() or first.currentText() or "").strip()
        if isinstance(first, QSpinBox):
            return str(first.value()).strip()
        return first.text().strip()

    def get_settings(self) -> ApiSettings:
        return ApiSettings(
            # 5단계부터 API 관리 창은 번역 전용이다.
            # OCR/인페인팅 값은 구버전 캐시 호환을 위해 보존만 하고 UI에서 새로 입력받지 않는다.
            selected_ocr_provider=self.settings.selected_ocr_provider,
            selected_inpaint_provider=self.settings.selected_inpaint_provider,
            selected_translation_provider=self._selected_provider_for("selected_translation_provider", "openai"),
            clova_api_url=self.settings.clova_api_url,
            clova_secret_key=self.settings.clova_secret_key,
            clova_model=self.settings.clova_model or "clova_ocr_v2",
            clova_ocr_language=self.settings.clova_ocr_language or "ja",
            google_vision_credential_json_path=self.settings.google_vision_credential_json_path,
            google_vision_api_key=self.settings.google_vision_api_key,
            google_vision_model=self.settings.google_vision_model or "DOCUMENT_TEXT_DETECTION",
            google_vision_ocr_language=self.settings.google_vision_ocr_language or "en",
            google_vision_language_hints=self.settings.google_vision_language_hints,
            local_paddle_mask_device=self.settings.local_paddle_mask_device or "auto",
            local_paddle_ocr_language=self.settings.local_paddle_ocr_language or "ja",
            openai_api_key=self._first_edit_text("openai_api_key"),
            deepseek_api_key=self._first_edit_text("deepseek_api_key"),
            google_translate_api_key=self._first_edit_text("google_translate_api_key"),
            gemini_api_key=self._first_edit_text("gemini_api_key"),
            gemini_delayed_api_key=self._first_edit_text("gemini_delayed_api_key"),
            custom_translation_api_key=self._first_edit_text("custom_translation_api_key"),
            custom_translation_base_url=self._first_edit_text("custom_translation_base_url"),
            custom_translation_model=self._first_edit_text("custom_translation_model"),
            custom_translation_preset_name=self._first_edit_text("custom_translation_preset_name") or "Custom Compatible",
            lm_studio_base_url=self._first_edit_text("lm_studio_base_url") or "http://localhost:1234/v1",
            lm_studio_model=self._first_edit_text("lm_studio_model"),
            lm_studio_api_key=self._first_edit_text("lm_studio_api_key"),
            openai_model=self._first_edit_text("openai_model") or "gpt-4o-mini",
            deepseek_model=self._first_edit_text("deepseek_model") or "deepseek-v4-flash",
            google_translate_model=self._first_edit_text("google_translate_model") or "google_translate_basic_v2",
            gemini_model=self._first_edit_text("gemini_model") or "gemini-2.5-flash-lite",
            gemini_delayed_model=self._first_edit_text("gemini_delayed_model") or "gemini-2.5-flash-lite",
            gemini_delayed_mode=self._first_edit_text("gemini_delayed_mode") or "flex",
            openai_chunk_size=int(self._first_edit_text("openai_chunk_size") or 50),
            deepseek_chunk_size=int(self._first_edit_text("deepseek_chunk_size") or 50),
            google_translate_chunk_size=int(self._first_edit_text("google_translate_chunk_size") or 50),
            gemini_chunk_size=int(self._first_edit_text("gemini_chunk_size") or 50),
            gemini_delayed_chunk_size=int(self._first_edit_text("gemini_delayed_chunk_size") or 50),
            custom_translation_chunk_size=int(self._first_edit_text("custom_translation_chunk_size") or 50),
            lm_studio_chunk_size=int(self._first_edit_text("lm_studio_chunk_size") or 20),
            # 구버전 캐시 호환: 인페인팅 값은 더 이상 UI에서 노출하지 않고 기존 값을 유지한다.
            replicate_api_token=self.settings.replicate_api_token,
            lama_replicate_api_token=self.settings.lama_replicate_api_token or self.settings.replicate_api_token,
            stable_replicate_api_token=self.settings.stable_replicate_api_token or self.settings.replicate_api_token,
            repaint_model=self.settings.repaint_model or "allenhooo/lama:cdac78a1bec5b23c07fd29692fb70baa513ea403a39e643c48ec5edadb15fe72",
            replicate_lama_wait_seconds=int(self.settings.replicate_lama_wait_seconds or 3),
            stable_inpaint_model=self.settings.stable_inpaint_model or "stability-ai/stable-diffusion-inpainting:95b7223104132402a9ae91cc677285bc5eb997834bd2349fa486f53910fd68b3",
            stable_inpaint_prompt=self.settings.stable_inpaint_prompt or "remove text and restore the original background",
            stable_inpaint_wait_seconds=int(self.settings.stable_inpaint_wait_seconds or 3),
            local_lama_wait_seconds=int(self.settings.local_lama_wait_seconds or 0),
            gemini_inpaint_model=self.settings.gemini_inpaint_model or "gemini-2.5-flash-image",
            gemini_inpaint_prompt=self.settings.gemini_inpaint_prompt or (
                "Remove the text only inside the white mask area and reconstruct the original manga background. "
                "Keep all characters, panel borders, screentones, line art, and unmasked areas unchanged. "
                "Return only the edited full image."
            ),
        )

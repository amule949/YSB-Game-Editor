import ctypes
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from ysb.version_info import (
    APP_FAMILY_ID,
    COMPANY_NAME,
    PRODUCT_NAME,
    YSB_ROLE_LAUNCHER as VERSION_ROLE_LAUNCHER,
    YSB_ROLE_MAIN as VERSION_ROLE_MAIN,
    main_exe_candidates,
)

try:
    import tkinter as tk
except Exception:
    tk = None

CONFIG_FOLDER_NAME = "YSBGameEditor"
OPEN_QUEUE_FILE_NAME = "open_queue.jsonl"
RUNTIME_INFO_FILE_NAME = "main_instance.json"
LAUNCH_STATS_FILE_NAME = "launcher_launch_stats.json"
ASSOCIATION_PREFLIGHT_FILE_NAME = "association_preflight.json"
STARTUP_SIGNAL_FILE_NAME = "main_startup_signal.json"
LAUNCHER_CLOSED_SIGNAL_FILE_NAME = "launcher_closed_signal.json"
LAUNCHER_PROGRESS_FILE_NAME = "launcher_progress.json"
YSBG_PROG_ID = "YSBGameEditor.YSBGProject"
YSBG_EXTENSION = ".ysbg"
DEFAULT_LAUNCH_ESTIMATE_SEC = 18.0
MIN_LAUNCH_ESTIMATE_SEC = 6.0
MAX_LAUNCH_ESTIMATE_SEC = 60.0
MAIN_EXE_MIN_SIZE_FOR_GUESS = 30 * 1024 * 1024  # 메인 EXE는 보통 런처보다 훨씬 크다.
OPENER_EXE_MAX_SIZE_FOR_GUESS = 30 * 1024 * 1024

YSB_COMPANY_NAME = COMPANY_NAME
YSB_PRODUCT_NAME = PRODUCT_NAME
YSB_APP_FAMILY_ID = APP_FAMILY_ID
YSB_ROLE_MAIN = VERSION_ROLE_MAIN
YSB_ROLE_LAUNCHER = VERSION_ROLE_LAUNCHER
YSB_ROLE_OPENER = YSB_ROLE_LAUNCHER

MAIN_EXE_CANDIDATES = main_exe_candidates()

MAIN_EXE_SUBDIR_CANDIDATES = [
    "YSB",
    "YSB Game Editor",
    "YSB Game Editor",
    "YSB TRANSLATE",
    "YSB_Translator",
    "app",
    "program",
]


def infer_edition_from_main_exe(main_exe: Path | None) -> str:
    """Infer Lite/Local for launcher diagnostics and source-like runs.

Compiled main entry points select their own edition. This helper only sets an
extra environment value so logs/runtime files know which distribution launched.
"""
    name = str(getattr(main_exe, "name", "") or "").lower()
    if "local" in name:
        return "local"
    return "lite"



def set_process_dpi_awareness_for_launcher():
    """Tkinter 런처 스플래시가 Windows 배율 때문에 메인보다 크게 보이지 않게 DPI 인식을 맞춘다."""
    if not sys.platform.startswith("win"):
        return
    try:
        # Windows 8.1+
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
        return
    except Exception:
        pass
    try:
        # Windows 7 fallback
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Tk 창을 만들기 전에 DPI 인식을 먼저 고정한다.
set_process_dpi_awareness_for_launcher()

def app_config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / CONFIG_FOLDER_NAME
    return Path.home() / ".YSB_Translator"


def resource_path(name: str) -> Path:
    """PyInstaller onefile/onedir/소스 실행에서 런처 리소스를 안정적으로 찾는다.

    v2.0.1 리팩토링 이후 스플래시와 아이콘은 assets/ 아래에서 관리한다.
    기존 호출이 resource_path("ysb_splash.png")처럼 파일명만 넘겨도
    assets/ysb_splash.png를 먼저 찾도록 보정한다.
    """
    rel = str(name).replace("\\", "/").lstrip("/")
    aliases = {
        "ysb_icon.ico": ["assets/ysbg_main_icon.ico", "assets/ysb_icon.ico", "assets/YSB_icon.ico", "ysbg_main_icon.ico", "ysb_icon.ico", "YSB_icon.ico"],
        "YSB_icon.ico": ["assets/ysbg_main_icon.ico", "assets/ysb_icon.ico", "assets/YSB_icon.ico", "ysbg_main_icon.ico", "ysb_icon.ico", "YSB_icon.ico"],
        "ysbg_main_icon.ico": ["assets/ysbg_main_icon.ico", "assets/ysb_icon.ico", "ysbg_main_icon.ico", "ysb_icon.ico"],
        "ysbt_file_icon.ico": ["assets/ysbg_file_icon.ico", "assets/ysbt_file_icon.ico", "ysbg_file_icon.ico", "ysbt_file_icon.ico"],
        "ysbg_file_icon.ico": ["assets/ysbg_file_icon.ico", "assets/ysbt_file_icon.ico", "ysbg_file_icon.ico", "ysbt_file_icon.ico"],
        "YSBG_file_icon.ico": ["assets/ysbg_file_icon.ico", "assets/ysbt_file_icon.ico", "ysbg_file_icon.ico", "ysbt_file_icon.ico"],
        "ysb_launcher_icon.ico": ["assets/ysbg_main_icon.ico", "assets/ysb_icon.ico", "ysb_launcher_icon.ico"],
        "YSB_launcher_icon.ico": ["assets/ysbg_main_icon.ico", "assets/ysb_icon.ico", "YSB_launcher_icon.ico"],
        "ysb_splash.png": ["assets/ysb_splash.png", "ysb_splash.png"],
        "ysb_splash_boot.png": ["assets/ysb_splash_boot.png", "assets/ysb_splash.png", "ysb_splash_boot.png", "ysb_splash.png"],
        "ysb_logo.png": ["assets/ysb_logo.png", "ysb_logo.png"],
    }
    candidates = []
    candidates.extend(aliases.get(rel, []))
    candidates.append(rel)
    if not rel.startswith("assets/"):
        candidates.append(f"assets/{rel}")

    seen = set()
    unique_candidates = []
    for item in candidates:
        if item not in seen:
            seen.add(item)
            unique_candidates.append(item)

    roots = []
    try:
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            roots.append(Path(sys._MEIPASS))
    except Exception:
        pass

    try:
        here = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
        roots.append(here)
        roots.extend(here.parents)
    except Exception:
        pass

    for root in roots:
        for item in unique_candidates:
            p = root / item
            if p.exists():
                return p

    return Path(rel)


def queue_path() -> Path:
    return app_config_dir() / OPEN_QUEUE_FILE_NAME


def runtime_info_path() -> Path:
    return app_config_dir() / "runtime" / RUNTIME_INFO_FILE_NAME


def launch_stats_path() -> Path:
    return app_config_dir() / LAUNCH_STATS_FILE_NAME


def association_preflight_path() -> Path:
    return app_config_dir() / ASSOCIATION_PREFLIGHT_FILE_NAME


def startup_signal_path() -> Path:
    return app_config_dir() / "runtime" / STARTUP_SIGNAL_FILE_NAME


def launcher_closed_signal_path() -> Path:
    return app_config_dir() / "runtime" / LAUNCHER_CLOSED_SIGNAL_FILE_NAME


def launcher_progress_path() -> Path:
    return app_config_dir() / "runtime" / LAUNCHER_PROGRESS_FILE_NAME


def show_error(message: str):
    if sys.platform.startswith("win"):
        try:
            ctypes.windll.user32.MessageBoxW(None, str(message), "YSB Launcher", 0x10)
            return
        except Exception:
            pass
    try:
        print(message, file=sys.stderr)
    except Exception:
        pass


def opener_log(message: str):
    try:
        p = app_config_dir() / "ysb_launcher.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " " + str(message) + "\n")
    except Exception:
        pass


def is_pid_running(pid: int) -> bool:
    if not pid or pid <= 0:
        return False
    if not sys.platform.startswith("win"):
        try:
            os.kill(pid, 0)
            return True
        except Exception:
            return False
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    SYNCHRONIZE = 0x00100000
    STILL_ACTIVE = 259
    try:
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, int(pid))
        if not handle:
            return False
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return bool(ok and code.value == STILL_ACTIVE)
    except Exception:
        return False


def main_is_running() -> bool:
    try:
        p = runtime_info_path()
        if not p.exists():
            return False
        data = json.loads(p.read_text(encoding="utf-8"))
        return is_pid_running(int(data.get("pid") or 0))
    except Exception:
        return False


def append_open_queue(project_path: str):
    append_queue("open", project_path)


def append_activate_queue():
    append_queue("activate", "")


def append_queue(command: str, project_path: str = ""):
    p = queue_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "id": str(uuid.uuid4()),
        "command": str(command or "activate"),
        "source": "YSB Launcher",
        "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "time_epoch": time.time(),
    }
    if project_path:
        payload["path"] = str(Path(project_path).resolve())
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")



def load_launch_estimate_seconds() -> float:
    """런처 1단계 로딩의 예상 시간을 읽는다.

    첫 실행에는 기록이 없으므로 DEFAULT_LAUNCH_ESTIMATE_SEC를 사용한다.
    이후에는 실제 메인 준비 시간을 완만하게 반영한다.
    """
    try:
        p = launch_stats_path()
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            value = float(data.get("estimated_seconds", DEFAULT_LAUNCH_ESTIMATE_SEC))
            return max(MIN_LAUNCH_ESTIMATE_SEC, min(MAX_LAUNCH_ESTIMATE_SEC, value))
    except Exception:
        pass
    return DEFAULT_LAUNCH_ESTIMATE_SEC


def save_launch_duration_seconds(duration: float):
    """이번 실행에서 메인 준비까지 걸린 시간을 저장해 다음 진행률 추정에 반영한다."""
    try:
        duration = float(duration)
        if duration < 1.0 or duration > 180.0:
            return
        old = load_launch_estimate_seconds()
        # 너무 급격히 변하지 않게 이전값 70%, 이번값 30%로 완만하게 반영.
        new_estimate = (old * 0.70) + (duration * 0.30)
        new_estimate = max(MIN_LAUNCH_ESTIMATE_SEC, min(MAX_LAUNCH_ESTIMATE_SEC, new_estimate))
        p = launch_stats_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "estimated_seconds": new_estimate,
            "last_duration_seconds": duration,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    except Exception:
        pass


def _candidate_search_dirs() -> list[Path]:
    here = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
    search_dirs = [here]

    for folder in MAIN_EXE_SUBDIR_CANDIDATES:
        search_dirs.append(here / folder)

    try:
        parent = here.parent
        if parent != here:
            search_dirs.append(parent)
            for folder in MAIN_EXE_SUBDIR_CANDIDATES:
                search_dirs.append(parent / folder)
    except Exception:
        pass

    seen = set()
    final_dirs = []
    for d in search_dirs:
        try:
            rd = d.resolve()
            if rd in seen:
                continue
            seen.add(rd)
            final_dirs.append(rd)
        except Exception:
            continue
    return final_dirs



def read_windows_exe_version_strings(exe_path: Path) -> dict:
    """EXE의 Windows 버전 리소스 문자열을 읽는다.

    PyInstaller onefile 내부 압축을 풀지 않아도 읽을 수 있는 PE 리소스 정보다.
    파일명이 바뀌어도 CompanyName/ProductName/InternalName/커스텀 키로 앱을 식별한다.
    """
    if not sys.platform.startswith("win"):
        return {}
    try:
        exe_text = str(Path(exe_path))
        version = ctypes.windll.version
        handle = ctypes.c_uint(0)
        size = version.GetFileVersionInfoSizeW(exe_text, ctypes.byref(handle))
        if not size:
            return {}

        buffer = ctypes.create_string_buffer(size)
        if not version.GetFileVersionInfoW(exe_text, 0, size, buffer):
            return {}

        translations = []
        trans_ptr = ctypes.c_void_p()
        trans_len = ctypes.c_uint(0)
        if version.VerQueryValueW(buffer, r"\VarFileInfo\Translation", ctypes.byref(trans_ptr), ctypes.byref(trans_len)):
            count = int(trans_len.value // 4)
            arr_type = ctypes.c_ushort * (count * 2)
            arr = arr_type.from_address(trans_ptr.value)
            for i in range(count):
                lang = arr[i * 2]
                codepage = arr[i * 2 + 1]
                translations.append((lang, codepage))

        if not translations:
            translations = [
                (0x0409, 0x04B0),  # Unicode English
                (0x0409, 0x04E4),
                (0x0412, 0x04B0),  # Korean fallback
                (0x0000, 0x04B0),
            ]

        keys = [
            "CompanyName",
            "ProductName",
            "FileDescription",
            "InternalName",
            "OriginalFilename",
            "ProductVersion",
            "FileVersion",
            "YSBAppFamilyId",
            "YSBAppRole",
        ]

        out = {}
        for lang, codepage in translations:
            base = rf"\StringFileInfo\{lang:04x}{codepage:04x}"
            for key in keys:
                if key in out:
                    continue
                ptr = ctypes.c_void_p()
                length = ctypes.c_uint(0)
                query = base + "\\" + key
                if version.VerQueryValueW(buffer, query, ctypes.byref(ptr), ctypes.byref(length)) and ptr.value:
                    try:
                        out[key] = ctypes.wstring_at(ptr.value)
                    except Exception:
                        pass
            if out:
                break
        return out
    except Exception:
        return {}


def is_ysb_main_exe_by_metadata(exe_path: Path) -> bool:
    info = read_windows_exe_version_strings(exe_path)
    if not info:
        return False

    company = str(info.get("CompanyName", "")).strip()
    product = str(info.get("ProductName", "")).strip()
    family = str(info.get("YSBAppFamilyId", "")).strip()
    role = str(info.get("YSBAppRole", "")).strip()
    internal = str(info.get("InternalName", "")).strip()

    family_ok = (
        company == YSB_COMPANY_NAME
        and (
            family == YSB_APP_FAMILY_ID
            or product == YSB_PRODUCT_NAME
        )
    )
    role_ok = role == YSB_ROLE_MAIN or internal == YSB_ROLE_MAIN
    return bool(family_ok and role_ok)


def is_ysb_launcher_exe_by_metadata(exe_path: Path) -> bool:
    info = read_windows_exe_version_strings(exe_path)
    if not info:
        return False

    company = str(info.get("CompanyName", "")).strip()
    product = str(info.get("ProductName", "")).strip()
    family = str(info.get("YSBAppFamilyId", "")).strip()
    role = str(info.get("YSBAppRole", "")).strip()
    internal = str(info.get("InternalName", "")).strip()

    family_ok = (
        company == YSB_COMPANY_NAME
        and (
            family == YSB_APP_FAMILY_ID
            or product == YSB_PRODUCT_NAME
        )
    )
    role_ok = (role == YSB_ROLE_LAUNCHER or internal == YSB_ROLE_LAUNCHER)
    return bool(family_ok and role_ok)


def find_main_exe() -> Path | None:
    """메인 EXE를 찾는다.

    1순위는 EXE 버전 리소스 메타데이터다.
    - CompanyName: Zerostress8
    - ProductName: YSB Game Editor
    - InternalName 또는 YSBAppRole: YSB_MAIN

    파일명이 바뀌어도 이 정보는 유지되므로, 이름/크기 추정보다 훨씬 안전하다.
    """
    try:
        current_exe = Path(sys.executable).resolve()
    except Exception:
        current_exe = None

    final_dirs = _candidate_search_dirs()

    # 1. EXE 내부 메타데이터로 진짜 메인 EXE 식별
    metadata_candidates = []
    try:
        for base in final_dirs:
            if not base.exists() or not base.is_dir():
                continue
            for candidate in base.glob("*.exe"):
                try:
                    if current_exe is not None and candidate.resolve() == current_exe:
                        continue
                except Exception:
                    pass
                if is_ysb_main_exe_by_metadata(candidate):
                    try:
                        metadata_candidates.append((candidate.stat().st_size, candidate))
                    except Exception:
                        metadata_candidates.append((0, candidate))
    except Exception:
        pass

    if metadata_candidates:
        metadata_candidates.sort(key=lambda x: x[0], reverse=True)
        return metadata_candidates[0][1]

    # 2. 알려진 기본 이름 후보
    for base in final_dirs:
        for name in MAIN_EXE_CANDIDATES:
            candidate = base / name
            if candidate.exists() and candidate.is_file():
                try:
                    if current_exe is None or candidate.resolve() != current_exe:
                        return candidate
                except Exception:
                    return candidate

    # 3. 구버전/미표식 EXE fallback: 이름/크기 추정
    named_candidates = []
    size_candidates = []
    try:
        for base in final_dirs:
            if not base.exists() or not base.is_dir():
                continue
            for candidate in base.glob("*.exe"):
                try:
                    if current_exe is not None and candidate.resolve() == current_exe:
                        continue
                except Exception:
                    pass
                low = candidate.name.lower()
                if "opener" in low or "launcher" in low:
                    continue
                try:
                    size = candidate.stat().st_size
                except Exception:
                    size = 0

                if "ysb" in low or "역식" in candidate.name or "붕이" in candidate.name:
                    named_candidates.append((size, candidate))

                if size >= MAIN_EXE_MIN_SIZE_FOR_GUESS:
                    size_candidates.append((size, candidate))
    except Exception:
        pass

    if named_candidates:
        named_candidates.sort(key=lambda x: x[0], reverse=True)
        return named_candidates[0][1]

    if size_candidates:
        size_candidates.sort(key=lambda x: x[0], reverse=True)
        return size_candidates[0][1]

    return None

# =========================================================
# 런처 1단계 로딩창
# =========================================================
class LauncherLoadingWindow:
    """YSB Launcher 전용 스플래시.

    런처가 실행한 경우에는 이 창 하나가 스플래시를 끝까지 소유한다.
    메인과 같은 500x500 기준, 하단 문구/퍼센트/진행바 1개만 표시한다.
    """
    WIDTH = 500
    HEIGHT = 500

    def __init__(self):
        self.enabled = sys.platform.startswith("win") and tk is not None
        self.root = None
        self.canvas = None
        self._image = None
        self._progress = 0
        self._message = "로딩 중..."
        self._sub_message = ""
        self._created = False

    def show(self):
        if not self.enabled:
            opener_log("Launcher loading window disabled: tkinter unavailable or non-Windows")
            return
        try:
            self._create_window()
            self._created = True
            self.pump()
        except Exception as e:
            opener_log(f"Launcher Tk loading window failed: {e}")
            self.enabled = False

    def set_message(self, message, sub_message=None):
        self._message = str(message or "")
        if sub_message is not None:
            self._sub_message = str(sub_message or "")
        self._redraw()
        self.pump()

    def set_progress(self, progress, message=None, sub_message=None):
        try:
            self._progress = max(0, min(100, int(progress)))
        except Exception:
            self._progress = 0
        if message is not None:
            self._message = str(message)
        if sub_message is not None:
            self._sub_message = str(sub_message or "")
        self._redraw()
        self.pump()

    def close(self):
        if self.root is not None:
            try:
                self.root.destroy()
            except Exception:
                pass
        self.root = None
        self.canvas = None

    def pump(self):
        if not self.enabled or self.root is None:
            return
        try:
            self.root.update_idletasks()
            self.root.update()
        except Exception:
            pass

    def _create_window(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.overrideredirect(True)
        self.root.configure(bg="black")
        try:
            self.root.attributes("-topmost", True)
        except Exception:
            pass

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = int((sw - self.WIDTH) / 2)
        y = int((sh - self.HEIGHT) / 2)
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")

        self.canvas = tk.Canvas(
            self.root,
            width=self.WIDTH,
            height=self.HEIGHT,
            bg="black",
            highlightthickness=0,
            bd=0,
        )
        self.canvas.pack(fill="both", expand=True)

        img_path = resource_path("ysb_splash.png")
        try:
            img = tk.PhotoImage(file=str(img_path))
            # 메인 스플래시는 500x500으로 사용한다. 런처도 500x500 창에 맞춘다.
            # tkinter는 정밀 리사이즈가 약하므로, 500x500 리소스를 그대로 쓰는 것을 기준으로 한다.
            self._image = img
        except Exception as e:
            opener_log(f"failed to load launcher splash image {img_path}: {e}")
            self._image = None

        self.root.deiconify()
        self.root.lift()
        try:
            self.root.focus_force()
        except Exception:
            pass
        self._redraw()

    def _redraw(self):
        if self.canvas is None:
            return

        c = self.canvas
        c.delete("all")
        c.create_rectangle(0, 0, self.WIDTH, self.HEIGHT, fill="black", outline="black")

        if self._image is not None:
            c.create_image(self.WIDTH // 2, self.HEIGHT // 2, image=self._image)
        else:
            c.create_text(
                self.WIDTH // 2,
                self.HEIGHT // 2 - 60,
                text="YSB",
                fill="#ff2020",
                font=("Segoe UI", 64, "bold"),
            )

        left = 36
        right = self.WIDTH - 36
        text_y = self.HEIGHT - 70
        bar_y = self.HEIGHT - 42
        bar_h = 18

        c.create_text(
            left,
            text_y,
            text=self._message,
            fill="white",
            anchor="w",
            font=("Malgun Gothic", 10, "bold"),
        )
        c.create_text(
            right,
            text_y,
            text=f"{self._progress}%",
            fill="white",
            anchor="e",
            font=("Segoe UI", 10, "bold"),
        )

        c.create_rectangle(left, bar_y, right, bar_y + bar_h, fill="#121212", outline="#333333")
        fill_w = int((right - left) * (self._progress / 100.0))
        if fill_w > 0:
            c.create_rectangle(left, bar_y, left + fill_w, bar_y + bar_h, fill="#ff3030", outline="#ff3030")


_ACTIVE_LOADING_WINDOW = None


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", ctypes.c_uint),
        ("lpfnWndProc", ctypes.c_void_p),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", ctypes.c_void_p),
        ("hIcon", ctypes.c_void_p),
        ("hCursor", ctypes.c_void_p),
        ("hbrBackground", ctypes.c_void_p),
        ("lpszMenuName", ctypes.c_wchar_p),
        ("lpszClassName", ctypes.c_wchar_p),
    ]


class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


class PAINTSTRUCT(ctypes.Structure):
    _fields_ = [
        ("hdc", ctypes.c_void_p),
        ("fErase", ctypes.c_int),
        ("rcPaint", RECT),
        ("fRestore", ctypes.c_int),
        ("fIncUpdate", ctypes.c_int),
        ("rgbReserved", ctypes.c_byte * 32),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


class MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_void_p),
        ("lParam", ctypes.c_void_p),
        ("time", ctypes.c_uint),
        ("pt", POINT),
    ]


WNDPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_void_p)


def _loading_wnd_proc(hwnd, msg, wparam, lparam):
    WM_PAINT = 0x000F
    WM_DESTROY = 0x0002
    if msg == WM_PAINT:
        try:
            ps = PAINTSTRUCT()
            hdc = ctypes.windll.user32.BeginPaint(hwnd, ctypes.byref(ps))
            if _ACTIVE_LOADING_WINDOW is not None:
                _ACTIVE_LOADING_WINDOW.paint(hwnd, hdc)
            ctypes.windll.user32.EndPaint(hwnd, ctypes.byref(ps))
            return 0
        except Exception:
            pass
    if msg == WM_DESTROY:
        return 0
    return ctypes.windll.user32.DefWindowProcW(hwnd, msg, wparam, lparam)





def cleanup_launch_handshake_files(session_id: str):
    """이번 런처 실행에 방해될 수 있는 이전 hand-shake/progress 파일을 정리한다."""
    for p in (launcher_closed_signal_path(), launcher_progress_path()):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass


def write_launcher_closed_signal(session_id: str, pid: int | None = None):
    """런처 스플래시가 100% 후 닫혔음을 메인 프로세스에 알린다."""
    if not session_id:
        return
    try:
        p = launcher_closed_signal_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "session_id": str(session_id),
            "pid": int(pid or 0),
            "time_epoch": time.time(),
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source": "YSB Launcher",
        }
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    except Exception as e:
        opener_log(f"write_launcher_closed_signal failed: {e}")


def read_launcher_progress(session_id: str | None = None) -> dict:
    """main.py가 런처 소유 스플래시에 표시하라고 남긴 진행률을 읽는다."""
    try:
        p = launcher_progress_path()
        if not p.exists():
            return {}
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        if session_id and str(data.get("session_id") or "") != str(session_id):
            return {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def current_opener_executable_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    return Path(__file__).resolve()


def opener_association_command() -> str:
    exe = current_opener_executable_path()
    if getattr(sys, "frozen", False):
        return f'"{exe}" "%1"'
    return f'"{sys.executable}" "{exe}" "%1"'


def _stable_ysbt_icon_path() -> Path | None:
    """Windows DefaultIcon에 넣을 .ysbg 전용 아이콘을 안정 경로에 준비한다."""
    try:
        src = resource_path("ysbg_file_icon.ico")
        if not src.exists():
            return None
        dst_dir = app_config_dir() / "assets"
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / "ysbg_file_icon.ico"
        try:
            if (
                (not dst.exists())
                or src.stat().st_size != dst.stat().st_size
                or int(src.stat().st_mtime) > int(dst.stat().st_mtime)
            ):
                import shutil as _shutil
                _shutil.copy2(src, dst)
        except Exception:
            if not dst.exists():
                return None
        return dst
    except Exception:
        return None


def opener_association_icon() -> str:
    exe = current_opener_executable_path()
    ico = _stable_ysbt_icon_path()
    if ico and ico.exists():
        return f'"{ico}",0'

    ico = resource_path("ysbg_file_icon.ico")
    if ico.exists():
        return f'"{ico}",0'
    return f'"{exe}",0'


def get_ysbt_prog_id() -> str | None:
    if not sys.platform.startswith("win"):
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{YSBG_EXTENSION}") as k:
            value, _ = winreg.QueryValueEx(k, "")
        return str(value)
    except Exception:
        return None


def get_registered_ysbt_command() -> str | None:
    if not sys.platform.startswith("win"):
        return None
    try:
        import winreg
        if get_ysbt_prog_id() != YSBG_PROG_ID:
            return None
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{YSBG_PROG_ID}\shell\open\command") as k:
            command, _ = winreg.QueryValueEx(k, "")
        return str(command)
    except Exception:
        return None


def get_registered_ysbt_icon() -> str | None:
    if not sys.platform.startswith("win"):
        return None
    try:
        import winreg
        if get_ysbt_prog_id() != YSBG_PROG_ID:
            return None
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{YSBG_PROG_ID}\DefaultIcon") as k:
            icon, _ = winreg.QueryValueEx(k, "")
        return str(icon)
    except Exception:
        return None


def _normalize_registry_value(value: str | None) -> str:
    return str(value or "").strip().strip('"').replace("/", "\\").lower()


def is_ysbt_association_icon_current_for_opener() -> bool:
    registered = _normalize_registry_value(get_registered_ysbt_icon())
    current = _normalize_registry_value(opener_association_icon())
    return bool(registered and current and registered == current)


def is_ysbt_association_current_for_opener() -> bool:
    registered = (get_registered_ysbt_command() or "").strip().lower()
    current = opener_association_command().strip().lower()
    return bool(registered and registered == current and is_ysbt_association_icon_current_for_opener())


def is_ysbt_association_ours_but_different() -> bool:
    if get_ysbt_prog_id() != YSBG_PROG_ID:
        return False
    registered = (get_registered_ysbt_command() or "").strip().lower()
    current = opener_association_command().strip().lower()
    if bool(registered and registered != current):
        return True
    return not is_ysbt_association_icon_current_for_opener()


def register_ysbt_association_to_opener():
    if not sys.platform.startswith("win"):
        return False
    import winreg
    import ctypes as _ctypes

    command = opener_association_command()
    icon = opener_association_icon()

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{YSBG_EXTENSION}") as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, YSBG_PROG_ID)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{YSBG_PROG_ID}") as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, "YSBG Project File")
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{YSBG_PROG_ID}\DefaultIcon") as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, icon)
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, rf"Software\Classes\{YSBG_PROG_ID}\shell\open\command") as k:
        winreg.SetValueEx(k, "", 0, winreg.REG_SZ, command)

    try:
        _ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
        _ctypes.windll.shell32.SHChangeNotify(0x00002000, 0x0000, None, None)
    except Exception:
        pass
    return True


def write_association_preflight_status(status: str, detail: str = ""):
    try:
        p = association_preflight_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": str(status),
            "detail": str(detail or ""),
            "time": time.time(),
            "source": "YSB Launcher",
            "command": opener_association_command(),
        }
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    except Exception:
        pass


def messagebox_yes_no_topmost(title: str, message: str, default_yes: bool = True) -> bool:
    if not sys.platform.startswith("win"):
        return False
    MB_YESNO = 0x00000004
    MB_ICONQUESTION = 0x00000020
    MB_TOPMOST = 0x00040000
    MB_SETFOREGROUND = 0x00010000
    MB_DEFBUTTON1 = 0x00000000
    MB_DEFBUTTON2 = 0x00000100
    flags = MB_YESNO | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND | (MB_DEFBUTTON1 if default_yes else MB_DEFBUTTON2)
    try:
        result = ctypes.windll.user32.MessageBoxW(None, str(message), str(title), flags)
        return result == 6  # IDYES
    except Exception as e:
        opener_log(f"MessageBoxW failed: {e}")
        return False


def _launcher_workspace_setup_reason():
    """PyQt6 없이 런처 단계에서 작업 폴더 설정 필요 여부를 확인한다."""
    try:
        from ysb.core.workspace_manager import load_workspace_config, configured_workspace_root_raw, _is_unsafe_workspace_root
        cfg = load_workspace_config()
        if not cfg.get("workspace_root"):
            return True, "처음 실행입니다.\n작업 폴더 위치를 확인해 주세요.", "info"
        root = configured_workspace_root_raw()
        if root is None:
            return True, "저장된 작업 폴더 경로를 읽을 수 없습니다.\n작업 폴더 위치를 다시 지정해 주세요.", "warning"
        try:
            if _is_unsafe_workspace_root(root):
                return True, "저장된 작업 폴더 경로가 안전하지 않습니다.\n작업 폴더 위치를 다시 지정해 주세요.", "warning"
        except Exception:
            pass
        if not root.exists() or not root.is_dir():
            return True, "저장된 작업 폴더를 찾을 수 없습니다.\n작업 폴더 위치를 다시 지정해 주세요.", "warning"
        return False, "", "info"
    except Exception as e:
        opener_log(f"workspace setup lightweight check failed: {e}")
        return True, f"저장된 작업 폴더를 확인하지 못했습니다.\n작업 폴더 위치를 다시 지정해 주세요.\n\n{e}", "warning"


def _launcher_read_workspace_language(default="ko") -> str:
    try:
        from ysb.core.workspace_manager import configured_workspace_root_raw, default_workspace_root
        root = configured_workspace_root_raw() or default_workspace_root()
        p = Path(root) / "cache" / "app_options.json"
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            value = str(data.get("ui_language") or default).lower()
            if value in ("en", "english", "en-us", "en_us"):
                return "en"
    except Exception:
        pass
    return "ko"


def _launcher_save_workspace_language(root: Path, lang: str):
    try:
        value = "en" if str(lang).lower().startswith("en") else "ko"
        cache = Path(root) / "cache"
        cache.mkdir(parents=True, exist_ok=True)
        p = cache / "app_options.json"
        data = {}
        if p.exists():
            try:
                loaded = json.loads(p.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except Exception:
                data = {}
        data["ui_language"] = value
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        opener_log(f"launcher save language failed: {e}")


def _launcher_show_workspace_setup_dialog(reason: str = "", reason_kind: str = "info") -> bool:
    """런처 전용 경량 작업 폴더 설정창. PyQt6를 import하지 않는다."""
    if tk is None:
        show_error("작업 폴더 설정창을 열 수 없습니다.\n런처 실행 환경에서 tkinter를 사용할 수 없습니다.")
        return False
    try:
        from tkinter import filedialog
        from ysb.core.workspace_manager import default_workspace_root, ensure_workspace_writable, set_workspace_root
    except Exception as e:
        show_error(f"작업 폴더 설정에 필요한 모듈을 불러오지 못했습니다.\n프로그램을 시작할 수 없습니다.\n\n{e}")
        return False

    state = {"ok": False}
    initial_lang = _launcher_read_workspace_language()
    TEXT = {
        "ko": {
            "window": "작업 폴더 설정",
            "title": "쯔꾸르붕이 작업 폴더 설정",
            "reason_missing": "저장된 작업 폴더를 찾을 수 없습니다.\n작업 폴더 위치를 다시 지정해 주세요.",
            "folder": "작업 폴더 위치",
            "browse": "찾아보기",
            "default": "기본값으로\n변경",
            "language": "Language",
            "assoc": ".ysbg 확장자 연결 등록",
            "assoc_decline_title": ".ysbg 확장자 연결 확인",
            "assoc_decline_message": ".ysbg 확장자 연결을 등록하지 않으면 .ysbg 파일을 더블클릭해서 바로 열 수 없습니다.\n\n정말 등록하지 않고 계속 진행할까요?",
            "ok": "확인",
            "close": "닫기",
            "select": "작업 폴더 위치 선택",
            "save_fail": "작업 폴더 설정을 저장하지 못했습니다.",
            "desc": (
                "작업 폴더는 캐시, 임시 작업, 실제 프로젝트 작업 폴더를 저장하는 기준 위치입니다.\n"
                "기본값은 Windows의 실제 문서 폴더 아래 YSB_Translator 폴더입니다. 선택한 폴더가 YSB_Translator가 아니면 그 안에\n"
                "YSB_Translator 폴더를 만들어 사용합니다. [기본값으로 변경]을 누르면 이 실제 문서 위치로 되돌립니다.\n\n"
                ".ysbg 확장자 연결을 등록하면 .ysbg 프로젝트 파일을 더블클릭했을 때 쯔꾸르붕이로 바로 열 수 있습니다. 이 설정은 현재\n"
                "Windows 사용자 계정에만 적용되며, 옵션에서 해제할 수 있습니다.\n"
                "작업 폴더 위치 설정은 Windows 사용자 설정 폴더의 workspace_config.json에 저장됩니다."
            ),
        },
        "en": {
            "window": "Workspace Folder Settings",
            "title": "YSB Game Editor Workspace Folder Settings",
            "reason_missing": "The saved workspace folder could not be found.\nPlease choose the workspace folder again.",
            "folder": "Workspace Folder",
            "browse": "Browse",
            "default": "Reset to\nDefault",
            "language": "Language",
            "assoc": "Register .ysbg file association",
            "assoc_decline_title": "Confirm .ysbg File Association",
            "assoc_decline_message": "If you do not register the .ysbg file association, double-clicking .ysbg project files will not open them directly.\n\nContinue without registering the file association?",
            "ok": "OK",
            "close": "Close",
            "select": "Select Workspace Folder",
            "save_fail": "Failed to save workspace folder settings.",
            "desc": (
                "The workspace folder stores caches, temporary work, and actual project work folders.\n"
                "The default is the YSB_Translator folder under the real Windows Documents folder. If the selected folder is not YSB_Translator,\n"
                "a YSB_Translator folder will be created inside it. [Reset to Default] returns to the real Documents location.\n\n"
                "Registering the .ysbg file association lets you open .ysbg projects by double-clicking them. This setting applies only to the current\n"
                "Windows user account and can be disabled later in Options.\n"
                "The workspace folder setting is saved in workspace_config.json under the Windows user settings folder."
            ),
        },
    }

    def normalize_lang(value):
        return "en" if str(value).lower().startswith("en") else "ko"

    def t(key):
        return TEXT[normalize_lang(lang_var.get())].get(key, key)

    def normalize_user_root(value: str) -> Path:
        raw = str(value or "").strip().strip('"')
        if not raw:
            raise ValueError("empty")
        pth = Path(raw).expanduser()
        if pth.name.lower() not in ("ysb_translator", "ysbtranslator"):
            pth = pth / "YSB_Translator"
        return pth

    root = tk.Tk()
    root.withdraw()
    root.title(TEXT[initial_lang]["window"])
    root.configure(bg="#1E1D20")
    root.resizable(False, False)
    try:
        root.attributes("-topmost", True)
    except Exception:
        pass

    lang_var = tk.StringVar(value=initial_lang)
    path_var = tk.StringVar(value=str(default_workspace_root()))
    assoc_var = tk.BooleanVar(value=True)
    reason_text = str(reason or TEXT[initial_lang]["reason_missing"])

    frame = tk.Frame(root, bg="#1E1D20", padx=12, pady=12)
    frame.pack(fill="both", expand=True)
    title_label = tk.Label(frame, bg="#1E1D20", fg="#ffffff", font=("Malgun Gothic", 12, "bold"), anchor="w")
    title_label.grid(row=0, column=0, columnspan=5, sticky="ew", pady=(0, 8))
    reason_label = tk.Label(frame, bg="#1E1D20", fg="#ffd966", font=("Malgun Gothic", 9, "bold"), justify="left", anchor="w")
    reason_label.grid(row=1, column=0, columnspan=5, sticky="ew", pady=(0, 10))
    folder_label = tk.Label(frame, bg="#1E1D20", fg="#ffffff", font=("Malgun Gothic", 9), anchor="w")
    folder_label.grid(row=2, column=0, sticky="w", pady=(0, 8))
    path_entry = tk.Entry(frame, textvariable=path_var, width=56, bg="#2B282D", fg="#ffffff", insertbackground="#ffffff", relief="solid", bd=1)
    path_entry.grid(row=2, column=1, columnspan=2, sticky="ew", padx=(6, 6), pady=(0, 8))
    browse_btn = tk.Button(frame, bg="#3A343A", fg="#ffffff", activebackground="#51464D", activeforeground="#ffffff", relief="solid", bd=1, padx=12)
    browse_btn.grid(row=2, column=3, sticky="ew", padx=(0, 6), pady=(0, 8))
    default_btn = tk.Button(frame, bg="#4a5366", fg="#ffffff", activebackground="#58657c", activeforeground="#ffffff", relief="solid", bd=1, padx=8)
    default_btn.grid(row=2, column=4, sticky="ew", pady=(0, 8))
    language_label = tk.Label(frame, bg="#1E1D20", fg="#ffffff", font=("Malgun Gothic", 9), anchor="w")
    language_label.grid(row=3, column=0, sticky="w", pady=(0, 8))
    lang_menu = tk.OptionMenu(frame, lang_var, "ko", "en")
    lang_menu.configure(bg="#2B282D", fg="#ffffff", activebackground="#3A343A", activeforeground="#ffffff", relief="solid", bd=1, width=8, highlightthickness=0)
    try:
        lang_menu["menu"].configure(bg="#2B282D", fg="#ffffff", activebackground="#51464D", activeforeground="#ffffff")
        lang_menu["menu"].entryconfig(0, label="한국어")
        lang_menu["menu"].entryconfig(1, label="English")
    except Exception:
        pass
    lang_menu.grid(row=3, column=1, sticky="w", padx=(6, 0), pady=(0, 8))
    assoc_check = tk.Checkbutton(frame, variable=assoc_var, bg="#1E1D20", fg="#ffffff", selectcolor="#2B282D", activebackground="#1E1D20", activeforeground="#ffffff", font=("Malgun Gothic", 9))
    assoc_check.grid(row=3, column=2, columnspan=3, sticky="w", pady=(0, 8))
    desc_label = tk.Label(frame, bg="#1E1D20", fg="#F4EEF2", font=("Malgun Gothic", 8), justify="left", anchor="w", wraplength=660)
    desc_label.grid(row=4, column=0, columnspan=5, sticky="ew", pady=(0, 12))
    btn_frame = tk.Frame(frame, bg="#1E1D20")
    btn_frame.grid(row=5, column=0, columnspan=5, sticky="e")
    ok_btn = tk.Button(btn_frame, bg="#51464D", fg="#ffffff", activebackground="#566684", activeforeground="#ffffff", relief="solid", bd=1, padx=14)
    ok_btn.pack(side="left", padx=(0, 8))
    close_btn = tk.Button(btn_frame, bg="#3A343A", fg="#ffffff", activebackground="#51464D", activeforeground="#ffffff", relief="solid", bd=1, padx=14)
    close_btn.pack(side="left")
    frame.grid_columnconfigure(2, weight=1)

    def refresh_texts(*_args):
        root.title(t("window"))
        title_label.configure(text=t("title"))
        shown_reason = reason_text
        if reason_text == TEXT[initial_lang]["reason_missing"]:
            shown_reason = t("reason_missing")
        reason_label.configure(text=shown_reason)
        folder_label.configure(text=t("folder"))
        browse_btn.configure(text=t("browse"))
        default_btn.configure(text=t("default"))
        language_label.configure(text=t("language"))
        assoc_check.configure(text=t("assoc"))
        desc_label.configure(text=t("desc"))
        ok_btn.configure(text=t("ok"))
        close_btn.configure(text=t("close"))

    def browse():
        current = str(path_var.get() or default_workspace_root())
        selected = filedialog.askdirectory(title=t("select"), initialdir=current if Path(current).exists() else str(Path.home()))
        if selected:
            path_var.set(str(normalize_user_root(selected)))

    def on_ok():
        try:
            if not bool(assoc_var.get()):
                try:
                    import tkinter.messagebox as messagebox
                    proceed = messagebox.askyesno(t("assoc_decline_title"), t("assoc_decline_message"), parent=root, icon="warning")
                except Exception:
                    proceed = messagebox_yes_no_topmost(t("assoc_decline_title"), t("assoc_decline_message"), default_yes=False)
                if not proceed:
                    try:
                        assoc_var.set(True)
                    except Exception:
                        pass
                    return

            target = normalize_user_root(path_var.get())
            target = ensure_workspace_writable(target)
            set_workspace_root(target)
            _launcher_save_workspace_language(target, lang_var.get())
            if bool(assoc_var.get()):
                register_ysbt_association_to_opener()
            state["ok"] = True
            root.destroy()
        except Exception as e:
            try:
                import tkinter.messagebox as messagebox
                messagebox.showerror(t("window"), f"{t('save_fail')}\n\n{e}", parent=root)
            except Exception:
                show_error(f"{t('save_fail')}\n\n{e}")

    browse_btn.configure(command=browse)
    default_btn.configure(command=lambda: path_var.set(str(default_workspace_root())))
    ok_btn.configure(command=on_ok)
    close_btn.configure(command=lambda: (state.update(ok=False), root.destroy()))
    root.protocol("WM_DELETE_WINDOW", lambda: (state.update(ok=False), root.destroy()))
    root.bind("<Escape>", lambda _e: (state.update(ok=False), root.destroy()))
    root.bind("<Return>", lambda _e: on_ok())
    lang_var.trace_add("write", refresh_texts)
    refresh_texts()
    root.update_idletasks()
    try:
        w = max(720, root.winfo_reqwidth())
        h = max(330, root.winfo_reqheight())
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        x = int((sw - w) / 2)
        y = int((sh - h) / 2)
        root.geometry(f"{w}x{h}+{x}+{y}")
    except Exception:
        pass
    root.deiconify()
    root.lift()
    try:
        root.focus_force()
        path_entry.focus_set()
        path_entry.selection_range(0, tk.END)
    except Exception:
        pass
    root.mainloop()
    return bool(state.get("ok"))


def run_workspace_setup_preflight_before_loading() -> bool:
    """런처 단계에서도 첫 실행/복구 작업 폴더 설정창을 먼저 처리한다.

    런처는 PyQt6를 포함하지 않을 수 있으므로 본 프로그램의 PyQt6 설정창을
    import하지 않는다. 대신 tkinter 기반의 런처 전용 경량 설정창을 사용한다.
    """
    try:
        needs_setup, reason, reason_kind = _launcher_workspace_setup_reason()
        if not needs_setup:
            return True
        opener_log(f"workspace setup preflight required: kind={reason_kind}, reason={reason!r}")
        ok = bool(_launcher_show_workspace_setup_dialog(reason, reason_kind))
        if not ok:
            opener_log("workspace setup preflight canceled by user")
        return ok
    except Exception as e:
        opener_log(f"workspace setup preflight failed: {e}")
        show_error(f"작업 폴더 설정창을 열지 못했습니다.\n프로그램을 시작할 수 없습니다.\n\n{e}")
        return False


def run_association_preflight_before_loading():
    """런처 단계에서 확장자 갱신 알림을 먼저 처리한다.

    이 함수가 끝나기 전에는 메인 실행/런처 스플래시를 시작하지 않는다.
    따라서 확장자 알림창이 떠 있는 동안 뒤에서 로딩이 진행되지 않는다.
    """
    if not sys.platform.startswith("win"):
        return

    try:
        if is_ysbt_association_current_for_opener():
            write_association_preflight_status("already_current")
            return

        if not is_ysbt_association_ours_but_different():
            write_association_preflight_status("checked_no_action")
            return

        registered = get_registered_ysbt_command() or "알 수 없음"
        message = (
            "현재 .ysbg 확장자가 다른 위치의 쯔꾸르붕이에 연결되어 있습니다.\n"
            "포터블 EXE를 새 버전으로 교체했거나, 파일 위치를 옮긴 경우에 생길 수 있습니다.\n\n"
            f"현재 등록된 실행 명령:\n{registered}\n\n"
            "현재 런처 기준으로 .ysbg 연결을 먼저 갱신할까요?\n\n"
            "[예]를 누르면 .ysbg 파일 연결만 현재 YSB Launcher 경로로 덮어씁니다. 프로젝트 파일은 변경되지 않습니다."
        )
        if messagebox_yes_no_topmost(".ysbg 확장자 연결 갱신", message, default_yes=True):
            try:
                register_ysbt_association_to_opener()
                write_association_preflight_status("registered")
            except Exception as e:
                write_association_preflight_status("failed", str(e))
                show_error(f".ysbg 확장자 연결 갱신에 실패했습니다.\n{e}")
        else:
            write_association_preflight_status("declined")
    except Exception as e:
        write_association_preflight_status("failed", str(e))
        opener_log(f"association preflight failed: {e}")


def read_startup_signal() -> dict:
    try:
        p = startup_signal_path()
        if not p.exists():
            return {}
        return json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}


def main_python_started(launched_pid: int | None = None, launched_after: float | None = None, session_id: str | None = None) -> bool:
    data = read_startup_signal()
    if not data:
        return False
    try:
        pid = int(data.get("pid") or 0)
    except Exception:
        pid = 0
    try:
        signal_time = float(data.get("time_epoch") or 0)
    except Exception:
        signal_time = 0

    if session_id and str(data.get("launcher_session_id") or "") != str(session_id):
        return False
    if launched_pid and pid and pid != int(launched_pid):
        return False
    if launched_after and signal_time and signal_time < float(launched_after) - 1.0:
        return False
    return bool(pid and is_pid_running(pid))



def write_launcher_launch_debug(session_id: str | None, main_exe: Path | None = None):
    try:
        p = app_config_dir() / "runtime" / "launcher_launch_debug.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "session_id": str(session_id or ""),
            "main_exe": str(main_exe or ""),
            "time_epoch": time.time(),
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "source": "YSB Launcher",
        }
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)
    except Exception:
        pass


def launch_main(launcher_session_id: str | None = None, project_path: str | None = None) -> subprocess.Popen | None:
    main_exe = find_main_exe()
    if main_exe is None:
        show_error("쯔꾸르붕이 실행 파일을 찾지 못했습니다.\nYSB Launcher.exe를 메인 EXE와 같은 폴더에 두세요.")
        return None

    write_launcher_launch_debug(launcher_session_id, main_exe)

    creationflags = 0
    if sys.platform.startswith("win"):
        for flag_name in ("CREATE_NO_WINDOW", "DETACHED_PROCESS", "CREATE_NEW_PROCESS_GROUP"):
            creationflags |= int(getattr(subprocess, flag_name, 0))

    env = os.environ.copy()
    # 메인 onefile EXE가 이전 _MEI를 재사용하지 않게 한다.
    env["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    env["YSB_TOOL_EDITION"] = infer_edition_from_main_exe(main_exe)
    if launcher_session_id:
        env["YSB_LAUNCHER_SESSION_ID"] = str(launcher_session_id)
        env["YSB_SPLASH_OWNER"] = "launcher"
    for key in (
        "QT_PLUGIN_PATH",
        "QT_QPA_PLATFORM_PLUGIN_PATH",
        "QT_QPA_FONTDIR",
        "QT_DEBUG_PLUGINS",
    ):
        env.pop(key, None)

    try:
        args = [str(main_exe)]
        if project_path:
            args.append(str(project_path))
        return subprocess.Popen(
            args,
            cwd=str(main_exe.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=False,
            creationflags=creationflags,
            env=env,
        )
    except Exception as e:
        show_error(f"쯔꾸르붕이을 실행하지 못했습니다.\n{e}")
        return None


def wait_for_main_start(window: LauncherLoadingWindow, timeout_sec: float | None = None, launched_pid: int | None = None, launched_after: float | None = None, session_id: str | None = None) -> bool:
    """런처 소유 스플래시를 끝까지 유지한다.

    main.py가 시작되기 전에는 런처가 추정 진행률을 표시하고,
    main.py가 시작된 뒤에는 launcher_progress.json을 읽어 같은 창에서 메인 진행률을 이어서 표시한다.
    """
    estimate = load_launch_estimate_seconds()
    timeout = timeout_sec if timeout_sec is not None else max(60.0, estimate * 4.0)
    start_time = time.time()
    saw_main_progress = False
    last_main_progress_time = 0.0
    last_main_progress_value = 0
    last_main_progress_message = ""

    stage_messages = [
        (0, "실행 준비 중..."),
        (18, "메인 프로그램 압축 해제 중..."),
        (46, "라이브러리 준비 중..."),
        (55, "메인 초기화 대기 중..."),
    ]

    while time.time() - start_time < timeout:
        progress_data = read_launcher_progress(session_id=session_id)
        if progress_data:
            saw_main_progress = True
            try:
                progress = int(progress_data.get("progress", 0))
            except Exception:
                progress = 0
            message = str(progress_data.get("message") or "인터페이스 로딩 중...")
            done = bool(progress_data.get("done")) or progress >= 100

            window.set_progress(progress, message, "")
            now = time.time()
            if progress != last_main_progress_value or message != last_main_progress_message:
                last_main_progress_time = now
                last_main_progress_value = progress
                last_main_progress_message = message

            if done:
                save_launch_duration_seconds(time.time() - start_time)
                window.set_progress(100, message or "시작 완료", "")
                time.sleep(0.05)
                window.pump()
                return True

            # 메인 쪽에서 90%대 진행률을 쓴 뒤 마지막 100%/done 신호가 누락되는 경우가 있다.
            # 이때 메인 창은 이미 뜰 수 있는데 런처 스플래시만 92% 같은 상태로 남는다.
            # 90% 이상에서 진행률 갱신이 잠시 멈췄고 메인 프로세스가 살아 있으면 완료로 간주해 닫는다.
            if (
                progress >= 90
                and last_main_progress_time
                and (now - last_main_progress_time) > 1.25
                and (
                    main_is_running()
                    or main_python_started(launched_pid=launched_pid, launched_after=launched_after, session_id=session_id)
                )
            ):
                save_launch_duration_seconds(time.time() - start_time)
                window.set_progress(100, "시작 완료", "")
                time.sleep(0.05)
                window.pump()
                return True
        else:
            elapsed = time.time() - start_time
            # main.py가 아직 진행률을 쓰기 전. 55%까지만 추정 진행.
            progress = int(min(55, (elapsed / max(estimate, 1.0)) * 55))
            message = stage_messages[0][1]
            for threshold, msg in stage_messages:
                if progress >= threshold:
                    message = msg
            window.set_progress(progress, message, "")

        # fallback: 메인은 실행 중인데 진행률 파일이 계속 없으면 무한대기하지 않는다.
        # 메인 창이 이미 뜬 상태에서 런처만 남는 상황을 막기 위해 짧게 끊는다.
        if not saw_main_progress and main_is_running() and (time.time() - start_time) > 3.0:
            window.set_progress(100, "메인 프로그램으로 전환 중...", "")
            time.sleep(0.05)
            window.pump()
            return True

        # startup signal은 왔는데 launcher_progress가 없는 경우도 오래 기다리지 않는다.
        if not saw_main_progress and main_python_started(launched_pid=launched_pid, launched_after=launched_after, session_id=session_id) and (time.time() - start_time) > 3.0:
            window.set_progress(100, "메인 프로그램으로 전환 중...", "")
            time.sleep(0.05)
            window.pump()
            return True

        time.sleep(0.10)
        window.pump()

    window.set_progress(100, "메인 프로그램으로 전환 중...", "")
    time.sleep(0.05)
    window.pump()
    return False


def wait_until_pid_exits(pid: int, window: LauncherLoadingWindow | None = None, timeout_sec: float = 10.0):
    if not pid:
        return
    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        if not is_pid_running(pid):
            return
        if window is not None:
            elapsed = time.time() - start_time
            progress = min(12, int((elapsed / max(timeout_sec, 1.0)) * 12))
            window.set_progress(progress, "재기동 준비 중...", "기존 프로그램이 종료되기를 기다리고 있습니다.")
        time.sleep(0.12)
        if window is not None:
            window.pump()


def main() -> int:
    args = list(sys.argv[1:])
    restart_pid = None
    force_launch = False
    project_path = ""

    if args and args[0] == "--restart-main":
        force_launch = True
        if len(args) >= 2:
            try:
                restart_pid = int(args[1])
            except Exception:
                restart_pid = None
    elif args and args[0] == "--launch-main":
        force_launch = True
    elif args:
        project_path = args[0] or ""

    if project_path:
        try:
            project_path = str(Path(project_path).resolve())
        except Exception:
            project_path = str(project_path)

    launcher_session_id = uuid.uuid4().hex
    cleanup_launch_handshake_files(launcher_session_id)

    # 작업 폴더 설정은 런처 스플래시/메인 실행보다 먼저 처리한다.
    # workspace_config.json이 없거나 저장된 작업 폴더가 사라진 상태라면
    # 메인 앱을 띄우기 전에 같은 작업 폴더 설정창을 먼저 띄운다.
    if not run_workspace_setup_preflight_before_loading():
        return 0

    # 확장자 갱신 알림은 런처 스플래시/메인 실행보다 먼저 처리한다.
    # 이 알림이 떠 있는 동안에는 뒤에서 로딩이 진행되지 않는다.
    run_association_preflight_before_loading()

    # 위치 변경 후 재기동 등: 기존 메인 PID가 내려갈 때까지 기다린 뒤 런처 로딩창으로 새 메인을 실행한다.
    if force_launch:
        loading = LauncherLoadingWindow()
        loading.show()
        loading.set_progress(3, "쯔꾸르붕이 재기동 중...", "프로그램을 새 위치 기준으로 다시 시작합니다.")
        if restart_pid:
            wait_until_pid_exits(restart_pid, loading)
        launch_started = time.time()
        proc = launch_main(launcher_session_id)
        if proc is None:
            loading.close()
            return 1
        wait_for_main_start(loading, launched_pid=getattr(proc, "pid", None), launched_after=launch_started, session_id=launcher_session_id)
        loading.close()
        write_launcher_closed_signal(launcher_session_id, getattr(proc, "pid", None))
        return 0

    # 런처를 직접 더블클릭한 경우:
    # - 메인 앱이 켜져 있으면 앞으로 가져오기 요청만 전달
    # - 메인 앱이 꺼져 있으면 메인 앱을 실행
    if not project_path:
        if main_is_running():
            try:
                append_activate_queue()
                return 0
            except Exception:
                return 0

        loading = LauncherLoadingWindow()
        loading.show()
        loading.set_progress(3, "쯔꾸르붕이 실행 중...", "메인 프로그램을 시작하고 있습니다.")

        launch_started = time.time()
        proc = launch_main(launcher_session_id)
        if proc is None:
            loading.close()
            return 1

        wait_for_main_start(loading, launched_pid=getattr(proc, "pid", None), launched_after=launch_started, session_id=launcher_session_id)
        loading.close()
        write_launcher_closed_signal(launcher_session_id, getattr(proc, "pid", None))
        return 0

    # 이미 메인 앱이 켜져 있으면 로딩창 없이 파일 경로만 즉시 전달한다.
    if main_is_running():
        try:
            append_open_queue(project_path)
            return 0
        except Exception as e:
            show_error(f"실행 중인 쯔꾸르붕이에 파일 열기 요청을 전달하지 못했습니다.\n{e}")
            return 1

    # 메인 앱이 꺼져 있으면 프로젝트 경로를 메인 인자로 직접 넘긴다.
    # 큐만 남기면 첫 화면이 런처로 보이거나, 오래된 큐 때문에 이전 프로젝트가 열릴 수 있다.
    loading = LauncherLoadingWindow()
    loading.show()
    loading.set_progress(3, "쯔꾸르붕이 실행 중...", "메인 프로그램을 시작하고 있습니다.")

    launch_started = time.time()
    proc = launch_main(launcher_session_id, project_path=project_path)
    if proc is None:
        loading.close()
        return 1

    wait_for_main_start(loading, launched_pid=getattr(proc, "pid", None), launched_after=launch_started, session_id=launcher_session_id)
    loading.close()
    write_launcher_closed_signal(launcher_session_id, getattr(proc, "pid", None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

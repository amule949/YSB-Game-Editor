import json
import os
import shutil
import sys
from pathlib import Path

APP_FOLDER_NAME = "YSB_Game_Editor"
CONFIG_FOLDER_NAME = "YSBGameEditor"
CONFIG_FILE_NAME = "workspace_config.json"


def _path_key(path: str | Path) -> str:
    """경로 비교용 정규화 문자열. Windows 대소문자 차이와 슬래시 차이를 흡수한다."""
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _same_path(a: str | Path, b: str | Path) -> bool:
    try:
        return _path_key(a) == _path_key(b)
    except Exception:
        return False


def _windows_known_documents_dir() -> Path | None:
    """Windows Known Folder API로 실제 '문서/Documents' 위치를 가져온다.

    한국어 Windows처럼 탐색기에 '문서'로 표시되거나 OneDrive/회사 계정으로
    리디렉션된 경우, Path.home() / "Documents"를 직접 만들면 엉뚱한
    실제 폴더가 생길 수 있다. Windows에서는 반드시 Known Folder를 우선한다.
    """
    if not sys.platform.startswith("win"):
        return None
    try:
        import ctypes
        from ctypes import wintypes

        class GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", wintypes.BYTE * 8),
            ]

            def __init__(self, data1, data2, data3, data4):
                super().__init__()
                self.Data1 = data1
                self.Data2 = data2
                self.Data3 = data3
                self.Data4 = (wintypes.BYTE * 8)(*data4)

        # FOLDERID_Documents = {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
        folder_id_documents = GUID(
            0xFDD39AD0,
            0x238F,
            0x46AF,
            (0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7),
        )
        path_ptr = ctypes.c_wchar_p()
        shell32 = ctypes.windll.shell32
        shell32.SHGetKnownFolderPath.argtypes = [ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE, ctypes.POINTER(ctypes.c_wchar_p)]
        shell32.SHGetKnownFolderPath.restype = ctypes.c_long
        hr = shell32.SHGetKnownFolderPath(ctypes.byref(folder_id_documents), 0, None, ctypes.byref(path_ptr))
        if hr == 0 and path_ptr.value:
            result = Path(path_ptr.value)
            try:
                ctypes.windll.ole32.CoTaskMemFree(path_ptr)
            except Exception:
                pass
            return result
    except Exception:
        pass
    return None


def _literal_home_documents_dir() -> Path:
    return Path.home() / "Documents"


def user_documents_dir() -> Path:
    # Windows에서는 탐색기의 '문서'가 실제로 어디에 연결되어 있는지 Known Folder API로 가져온다.
    known = _windows_known_documents_dir()
    if known:
        return known
    # Known Folder 조회에 실패하더라도 사용자 홈 자체를 작업 기준으로 쓰지 않는다.
    # Documents 폴더가 아직 없어도 이후 ensure 단계에서 안전하게 생성한다.
    return _literal_home_documents_dir()


def legacy_literal_workspace_root() -> Path:
    """v1.8.0 hotfix15까지 잘못 만들 수 있던 홈/Documents 기준 작업 루트."""
    return _literal_home_documents_dir() / APP_FOLDER_NAME


def default_workspace_root() -> Path:
    return user_documents_dir() / APP_FOLDER_NAME


def app_config_dir() -> Path:
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / CONFIG_FOLDER_NAME
    return Path.home() / f".{APP_FOLDER_NAME}"


def config_path() -> Path:
    return app_config_dir() / CONFIG_FILE_NAME


def load_workspace_config() -> dict:
    try:
        p = config_path()
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}



def configured_workspace_root_raw() -> Path | None:
    """설정 파일에 저장된 작업 루트만 가져온다. 폴더를 만들지 않는다."""
    cfg = load_workspace_config()
    value = cfg.get("workspace_root")
    if value:
        try:
            return Path(value)
        except Exception:
            return None
    return None


def pending_workspace_root_raw() -> Path | None:
    """예약된 작업 루트만 가져온다. 폴더를 만들지 않는다."""
    cfg = load_workspace_config()
    value = cfg.get("pending_workspace_root")
    if value:
        try:
            return Path(value)
        except Exception:
            return None
    return None


def configured_workspace_root_exists() -> bool:
    """저장된 작업 루트가 실제 폴더로 존재하는지 확인한다. 폴더를 새로 만들지 않는다."""
    root = configured_workspace_root_raw()
    return bool(root and root.exists() and root.is_dir())


def save_workspace_config(data: dict):
    p = config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(dict(data or {}), f, ensure_ascii=False, indent=2)


def _is_other_windows_user_profile_path(root: str | Path) -> bool:
    """다른 Windows 사용자 프로필 아래 경로인지 검사한다.

    예: A PC에서 C:/Users/A/Documents/YSB_Translator를 백업한 뒤
    B PC에서 복원하면 C:/Users/A/... 경로가 현재 PC에 남을 수 있다.
    이 경로는 없거나 접근 권한이 없어 WinError 5로 이어질 수 있으므로 자동 복구한다.
    """
    if not sys.platform.startswith("win"):
        return False
    try:
        root_path = Path(root).expanduser()
        home_path = Path.home().expanduser()
        root_parts = root_path.parts
        home_parts = home_path.parts
        if len(root_parts) >= 3 and len(home_parts) >= 3:
            # Windows Path.parts 예: ('C:\\', 'Users', 'Amule', 'Documents', 'YSB_Translator')
            same_drive = str(root_parts[0]).lower() == str(home_parts[0]).lower()
            under_users = str(root_parts[1]).lower() == "users"
            current_under_users = str(home_parts[1]).lower() == "users"
            different_user = str(root_parts[2]).lower() != str(home_parts[2]).lower()
            if same_drive and under_users and current_under_users and different_user:
                return True
    except Exception:
        pass
    return False


def _is_unsafe_workspace_root(root: str | Path) -> bool:
    """작업 폴더로 쓰면 안 되는 사용자 프로필/문서 루트인지 검사한다.

    깨진 설정 파일에 C:/Users/사용자 또는 Documents 자체가 저장되어 있으면
    cache/temp/workspaces를 프로필 루트 바로 아래에 만들려고 하면서 권한 오류가 날 수 있다.
    YSB_Translator 하위 폴더가 아닌 사용자 홈/문서 루트는 자동 보정 대상이다.
    또한 다른 PC의 C:/Users/다른이름/... 경로가 복원된 경우도 현재 PC 기본값으로 복구한다.
    """
    try:
        root_path = Path(root)
    except Exception:
        return True
    try:
        if _same_path(root_path, Path.home()):
            return True
    except Exception:
        pass
    try:
        if _same_path(root_path, user_documents_dir()):
            return True
    except Exception:
        pass
    try:
        if _is_other_windows_user_profile_path(root_path):
            return True
    except Exception:
        pass
    return False


def ensure_workspace_structure(root: str | Path):
    root = Path(root).expanduser()
    if _is_unsafe_workspace_root(root):
        raise PermissionError(f"작업 폴더는 사용자 홈/문서 폴더 자체가 아니라 {APP_FOLDER_NAME} 폴더여야 합니다: {root}")
    root.mkdir(parents=True, exist_ok=True)
    for name in ("cache", "temp", "workspaces"):
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


def ensure_workspace_writable(root: str | Path):
    """작업 폴더 구조를 만들고 실제 쓰기 가능 여부까지 확인한다."""
    root = ensure_workspace_structure(root)
    test_path = root / ".ysb_write_test.tmp"
    with open(test_path, "w", encoding="utf-8") as f:
        f.write("ok")
    try:
        test_path.unlink()
    except Exception:
        pass
    return root


def _safe_move_workspace(old_root: Path, new_root: Path):
    old_root = old_root.resolve()
    new_root = new_root.resolve()
    if old_root == new_root:
        ensure_workspace_structure(new_root)
        return
    if not old_root.exists():
        raise FileNotFoundError(f"저장된 기존 작업 폴더를 찾을 수 없습니다: {old_root}")
    if new_root.exists() and any(new_root.iterdir()):
        # 대상 폴더가 비어 있지 않으면 루트 자체 이동 대신 하위 항목을 병합한다.
        ensure_workspace_structure(new_root)
        for child in old_root.iterdir():
            target = new_root / child.name
            if target.exists():
                continue
            shutil.move(str(child), str(target))
    else:
        new_root.parent.mkdir(parents=True, exist_ok=True)
        if new_root.exists():
            shutil.rmtree(new_root, ignore_errors=True)
        shutil.move(str(old_root), str(new_root))
    ensure_workspace_structure(new_root)


def apply_pending_workspace_move_if_needed() -> Path:
    cfg = load_workspace_config()
    default_root = default_workspace_root()
    current = Path(cfg.get("workspace_root") or default_root)
    pending = cfg.get("pending_workspace_root")

    # 깨진 설정이 사용자 프로필/문서 루트 자체를 가리키면 먼저 안전한 기본값으로 복구한다.
    # 이 단계에서 기존 current에 cache/temp를 만들지 않으므로 WinError 5 루프를 피할 수 있다.
    if _is_unsafe_workspace_root(current):
        ensure_workspace_writable(default_root)
        cfg["workspace_root"] = str(default_root)
        cfg.pop("pending_workspace_root", None)
        save_workspace_config(cfg)
        current = default_root
        pending = None

    # hotfix16: 한국어 Windows/리디렉션 환경에서 Path.home()/Documents를 직접 만들어
    # 잘못된 Documents 폴더가 생긴 경우, 실제 Windows '문서' Known Folder로 자동 보정한다.
    # 단, 사용자가 직접 다른 경로를 지정한 경우까지 함부로 바꾸지 않기 위해
    # 저장된 경로가 기존 잘못된 기본값과 정확히 같을 때만 마이그레이션한다.
    legacy_root = legacy_literal_workspace_root()
    if (not pending) and cfg.get("workspace_root") and _same_path(current, legacy_root) and not _same_path(legacy_root, default_root):
        try:
            if legacy_root.exists():
                _safe_move_workspace(legacy_root, default_root)
            else:
                ensure_workspace_structure(default_root)
            cfg["workspace_root"] = str(default_root)
            cfg.pop("pending_workspace_root", None)
            save_workspace_config(cfg)
            current = default_root
        except Exception:
            # 마이그레이션 실패 시 기존 설정을 유지한다. 작업 폴더 설정창에서 사용자가 직접 바꿀 수 있다.
            current = Path(cfg.get("workspace_root") or default_root)

    if pending:
        pending_path = Path(pending)
        try:
            _safe_move_workspace(current, pending_path)
            cfg["workspace_root"] = str(pending_path)
            cfg.pop("pending_workspace_root", None)
            save_workspace_config(cfg)
            current = pending_path
        except Exception:
            # 이동 실패 시 기존 루트를 유지한다. 실패 내용은 프로그램 시작 후 옵션 창에서 다시 처리하게 한다.
            current = Path(cfg.get("workspace_root") or default_root)
    ensure_workspace_writable(current)
    return current


def get_workspace_root() -> Path:
    return apply_pending_workspace_move_if_needed()


def set_workspace_root(path: str | Path):
    # 먼저 대상 폴더를 만들고 쓰기 가능 여부를 확인한 뒤 설정 파일을 저장한다.
    # 그래야 저장 실패/권한 실패 시 깨진 workspace_config.json이 남지 않는다.
    target = ensure_workspace_writable(path)
    cfg = load_workspace_config()
    cfg["workspace_root"] = str(target)
    cfg.pop("pending_workspace_root", None)
    save_workspace_config(cfg)


def schedule_workspace_root_change(path: str | Path):
    cfg = load_workspace_config()
    if not cfg.get("workspace_root") or _is_unsafe_workspace_root(cfg.get("workspace_root")):
        cfg["workspace_root"] = str(get_workspace_root())
    cfg["pending_workspace_root"] = str(Path(path).expanduser())
    save_workspace_config(cfg)


def workspace_subdir(name: str) -> Path:
    root = get_workspace_root()
    p = root / name
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir() -> Path:
    return workspace_subdir("cache")


def temp_dir() -> Path:
    return workspace_subdir("temp")


def workspaces_dir() -> Path:
    return workspace_subdir("workspaces")


def packages_dir() -> Path:
    # 호환용: 더 이상 packages 폴더를 만들지 않고, 기본 패키지 저장 위치는 문서 폴더를 사용한다.
    p = user_documents_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p

def default_package_dir() -> Path:
    p = user_documents_dir()
    p.mkdir(parents=True, exist_ok=True)
    return p

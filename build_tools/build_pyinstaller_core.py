# -*- coding: utf-8 -*-
"""쯔꾸르붕이 PyInstaller build core.

Current policy:
- API translation single app build only.
- No Lite/Local wording in user-facing build output.
- No launcher EXE.
- Main EXE icon, runtime splash, and .ysbg file icon are managed under assets/.
"""

from __future__ import annotations

import locale
import os
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BUILD_TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from ysb.version_info import (
    APP_FAMILY_ID,
    APP_VERSION,
    BUILD_LOG_FILE_NAME,
    COMPANY_NAME,
    LITE_MAIN_EXE_NAME,
    LITE_PACKAGE_FOLDER_NAME,
    PRODUCT_NAME,
    WINDOWS_VERSION_STRING,
    WINDOWS_VERSION_TUPLE,
    windows_original_filename,
)

DIST_DIR = PROJECT_ROOT / "dist"
LOG_FILE = PROJECT_ROOT / BUILD_LOG_FILE_NAME
ENTRY_FILE = PROJECT_ROOT / "main.py"
YSB_PACKAGE_DIR = PROJECT_ROOT / "ysb"

ASSETS_DIR = PROJECT_ROOT / "assets"
GENERATED_ICON_DIR = BUILD_TOOLS_DIR / "_generated_icons"
MAIN_ICON_FILE = ASSETS_DIR / "ysbg_main_icon.ico"
MAIN_ICON_PNG_FILE = ASSETS_DIR / "ysbg_main_icon.png"
LEGACY_MAIN_ICON_FILE = ASSETS_DIR / "ysb_icon.ico"
LEGACY_MAIN_ICON_PNG_FILE = ASSETS_DIR / "ysb_icon.png"
YSBG_FILE_ICON = ASSETS_DIR / "ysbg_file_icon.ico"
YSBG_FILE_ICON_PNG = ASSETS_DIR / "ysbg_file_icon.png"
LEGACY_YSBT_FILE_ICON = ASSETS_DIR / "ysbt_file_icon.ico"
LEGACY_YSBT_FILE_ICON_PNG = ASSETS_DIR / "ysbt_file_icon.png"
SPLASH_FILE = ASSETS_DIR / "ysb_splash.png"
BOOT_SPLASH_FILE = ASSETS_DIR / "ysb_splash_boot.png"
LOGO_FILE = ASSETS_DIR / "ysb_logo.png"

VERSION_MAIN = BUILD_TOOLS_DIR / "version_main.txt"
APP_EXE_NAME = LITE_MAIN_EXE_NAME
PACKAGE_FOLDER_NAME = LITE_PACKAGE_FOLDER_NAME
DATA_SEP = ";" if os.name == "nt" else ":"


def log(line: str = "") -> None:
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def decode_subprocess_line(raw: bytes) -> str:
    candidates: list[str] = []
    preferred = locale.getpreferredencoding(False)
    if preferred:
        candidates.append(preferred)
    candidates.extend(["utf-8", "mbcs", "cp949", "euc-kr"])

    seen: set[str] = set()
    for enc in candidates:
        key = enc.lower()
        if key in seen:
            continue
        seen.add(key)
        try:
            return raw.decode(enc).rstrip("\r\n")
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace").rstrip("\r\n")


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")


def require_dir(path: Path, label: str) -> None:
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(f"{label} not found: {path}")


def _make_build_icon_from_png(src: Path, out_name: str) -> Path | None:
    if not src.exists():
        return None
    GENERATED_ICON_DIR.mkdir(parents=True, exist_ok=True)
    dst = GENERATED_ICON_DIR / out_name
    try:
        from PIL import Image
        with Image.open(src) as im:
            im = im.convert("RGBA")
            im.save(dst, sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
        log(f"[icon] Generated {dst.name} from {src.relative_to(PROJECT_ROOT)}")
        return dst
    except Exception as exc:
        raise RuntimeError(f"Failed to convert icon PNG to ICO: {src} ({exc})") from exc


def _first_existing_icon(candidates: list[Path], generated_name: str) -> Path | None:
    for candidate in candidates:
        if candidate.exists() and candidate.suffix.lower() == ".ico":
            return candidate
    for candidate in candidates:
        if candidate.exists() and candidate.suffix.lower() == ".png":
            return _make_build_icon_from_png(candidate, generated_name)
    return None


def main_build_icon() -> Path | None:
    return _first_existing_icon(
        [MAIN_ICON_FILE, MAIN_ICON_PNG_FILE, LEGACY_MAIN_ICON_FILE, LEGACY_MAIN_ICON_PNG_FILE],
        "ysbg_main_icon.ico",
    )


def ysbg_build_icon() -> Path | None:
    return _first_existing_icon(
        [YSBG_FILE_ICON, YSBG_FILE_ICON_PNG, LEGACY_YSBT_FILE_ICON, LEGACY_YSBT_FILE_ICON_PNG],
        "ysbg_file_icon.ico",
    )


def pyinstaller_executable() -> list[str]:
    return [sys.executable, "-m", "PyInstaller"]


def add_data_arg(src: Path, dest: str) -> str:
    return f"{src}{DATA_SEP}{dest}"


def format_bytes(value: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    size = float(value)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{value} B"


def make_windows_version_text() -> str:
    version_tuple = tuple(int(x) for x in WINDOWS_VERSION_TUPLE)
    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={version_tuple},
    prodvers={version_tuple},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', {COMPANY_NAME!r}),
          StringStruct('FileDescription', 'YSB Game Editor Main'),
          StringStruct('FileVersion', {WINDOWS_VERSION_STRING!r}),
          StringStruct('InternalName', 'YSB_GAME_EDITOR_MAIN'),
          StringStruct('OriginalFilename', {windows_original_filename('game')!r}),
          StringStruct('ProductName', {PRODUCT_NAME!r}),
          StringStruct('ProductVersion', {WINDOWS_VERSION_STRING!r}),
          StringStruct('YSBAppFamilyId', {APP_FAMILY_ID!r}),
          StringStruct('YSBAppRole', 'YSB_MAIN'),
          StringStruct('YSBEdition', 'game')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def generate_version_file() -> None:
    VERSION_MAIN.write_text(make_windows_version_text(), encoding="utf-8")


def _tail_file(path: Path, lines: int = 120) -> list[str]:
    try:
        if not path.exists() or not path.is_file():
            return []
        text = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return text[-lines:]
    except Exception as exc:
        return [f"[failed to read {path}: {exc}]"]


def _dump_pyinstaller_diagnostics(label: str) -> None:
    log("")
    log(f"--- PyInstaller diagnostics after failure: {label} ---")
    candidates: list[Path] = []
    build_dir = PROJECT_ROOT / "build"
    if build_dir.exists():
        for pattern in ("**/warn-*.txt", "**/*.log", "**/*.toc"):
            candidates.extend(build_dir.glob(pattern))
    candidates.extend(PROJECT_ROOT.glob("*.spec"))

    seen: set[Path] = set()
    useful: list[Path] = []
    for p in candidates:
        if p.exists() and p.is_file() and p not in seen:
            useful.append(p)
            seen.add(p)
    if not useful:
        log("No extra PyInstaller diagnostic files were found.")
        return
    for path in useful[:12]:
        log("")
        log(f"[diagnostic file] {path}")
        for line in _tail_file(path, lines=80):
            log(line)


def run_command(args: list[str], label: str) -> None:
    log("")
    log(f"=== {label} ===")
    log(" ".join(f'\"{a}\"' if " " in a else a for a in args))
    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    proc = subprocess.Popen(args, cwd=str(PROJECT_ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env)
    if proc.stdout is None:
        raise RuntimeError("Failed to capture PyInstaller output.")
    for raw_line in proc.stdout:
        log(decode_subprocess_line(raw_line))
    ret = proc.wait()
    if ret != 0:
        _dump_pyinstaller_diagnostics(label)
        raise RuntimeError(f"{label} failed with exit code {ret}")


def hidden_import_args(modules: list[str]) -> list[str]:
    args: list[str] = []
    for mod in modules:
        args += ["--hidden-import", mod]
    return args


def exclude_module_args(modules: list[str]) -> list[str]:
    args: list[str] = []
    for mod in modules:
        args += ["--exclude-module", mod]
    return args


def base_args(onefile: bool) -> list[str]:
    args = [
        "--noconfirm",
        "--clean",
        "--windowed",
        "--noupx",
        "--log-level",
        os.environ.get("YSB_PYINSTALLER_LOG_LEVEL", "INFO"),
        "--paths",
        str(PROJECT_ROOT),
    ]
    args.append("--onefile" if onefile else "--onedir")
    return args


def runtime_asset_args() -> list[str]:
    files: list[Path] = []
    main_icon = main_build_icon()
    ysbg_icon = ysbg_build_icon()
    if main_icon is not None:
        files.append(main_icon)
    if ysbg_icon is not None:
        files.append(ysbg_icon)
    if SPLASH_FILE.exists():
        files.append(SPLASH_FILE)
    if BOOT_SPLASH_FILE.exists():
        files.append(BOOT_SPLASH_FILE)
    if LOGO_FILE.exists():
        files.append(LOGO_FILE)

    args: list[str] = []
    for f in files:
        args += ["--add-data", add_data_arg(f, "assets")]
    return args


def boot_splash_args() -> list[str]:
    # PyInstaller boot splash is optional. The Qt runtime splash uses ysb_splash.png.
    if BOOT_SPLASH_FILE.exists():
        return ["--splash", str(BOOT_SPLASH_FILE)]
    return []


def common_main_hidden_imports() -> list[str]:
    return [
        "ysb",
        "ysb.ui.main_window",
        "ysb.editions.current",
        "ysb.utils.crash_guard",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.QtPrintSupport",
        "PIL._imaging",
    ]


def app_excludes() -> list[str]:
    return [
        "pandas",
        "tkinter",
        "_tkinter",
        "tcl",
        "tk",
        "paddleocr",
        "paddlepaddle",
        "paddle",
        "paddlex",
        "ppocr",
        "torch",
        "torchvision",
        "pyclipper",
        "shapely",
        "wandb",
        "torchsummary",
        "simple_lama_inpainting",
        "fire",
        "omegaconf",
        "einops",
        "yaml",
        "transformers",
        "huggingface_hub",
        "tokenizers",
        "sentencepiece",
        "safetensors",
        "fugashi",
        "unidic_lite",
        "matplotlib",
        "scipy",
        "sklearn",
        "tensorflow",
        "seaborn",
        "IPython",
        "notebook",
        "pytest",
    ]


def main_args() -> list[str]:
    args = base_args(onefile=True)
    args += hidden_import_args(common_main_hidden_imports())
    args += exclude_module_args(app_excludes())
    args += runtime_asset_args()
    args += boot_splash_args()

    return args


def build_main() -> None:
    icon = main_build_icon()
    if icon is None:
        raise FileNotFoundError("Main icon not found. Put assets/ysbg_main_icon.ico or assets/ysbg_main_icon.png")
    args = pyinstaller_executable() + main_args() + [
        "--name",
        APP_EXE_NAME,
        "--icon",
        str(icon),
        "--version-file",
        str(VERSION_MAIN),
        str(ENTRY_FILE),
    ]
    run_command(args, "Building main onefile EXE")


def folder_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for child in path.rglob("*"):
        if child.is_file():
            try:
                total += child.stat().st_size
            except OSError:
                pass
    return total


def remove_path(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def clean_build_outputs() -> None:
    remove_path(PROJECT_ROOT / "build")
    remove_path(DIST_DIR / f"{APP_EXE_NAME}.exe")
    remove_path(DIST_DIR / PACKAGE_FOLDER_NAME)
    remove_path(DIST_DIR / "packages")
    # Remove old launcher/intermediate outputs from previous build tools.
    for old_name in ("YSB_Launcher.exe", "YSB_Game_Editor_Launcher.exe"):
        remove_path(DIST_DIR / old_name)
    for spec in PROJECT_ROOT.glob("*.spec"):
        remove_path(spec)


def cleanup_intermediate_outputs() -> None:
    remove_path(DIST_DIR / f"{APP_EXE_NAME}.exe")
    remove_path(DIST_DIR / "packages")
    for old_name in ("YSB_Launcher.exe", "YSB_Game_Editor_Launcher.exe"):
        remove_path(DIST_DIR / old_name)
    for spec in PROJECT_ROOT.glob("*.spec"):
        remove_path(spec)


RUNTIME_LEFTOVER_NAMES = {
    "ysb_startup_stage.log",
    "ysb_startup_crash.log",
    "ysb_startup_faulthandler.log",
    "ysb_runtime_debug.log",
}


def cleanup_runtime_leftovers(package_dir: Path) -> None:
    if not package_dir.exists():
        return
    for name in RUNTIME_LEFTOVER_NAMES:
        remove_path(package_dir / name)
    for pattern in ("ysb_startup_*.log", "ysb_runtime_debug*.log"):
        for path in package_dir.glob(pattern):
            remove_path(path)


def prepare_package() -> None:
    built_exe = DIST_DIR / f"{APP_EXE_NAME}.exe"
    require_file(built_exe, "Built main EXE")

    stage = DIST_DIR / PACKAGE_FOLDER_NAME
    remove_path(stage)
    stage.mkdir(parents=True, exist_ok=True)

    shutil.copy2(built_exe, stage / built_exe.name)
    cleanup_runtime_leftovers(stage)
    cleanup_intermediate_outputs()

    log("")
    log("Package prepared:")
    log(f"Package folder: {stage}")
    log(f"Package size: {format_bytes(folder_size(stage))}")


def validate_layout() -> None:
    require_file(ENTRY_FILE, "App entry")
    require_dir(YSB_PACKAGE_DIR, "ysb package directory")
    require_file(YSB_PACKAGE_DIR / "__init__.py", "ysb package __init__.py")
    require_file(YSB_PACKAGE_DIR / "editions" / "current.py", "edition selector")
    require_file(YSB_PACKAGE_DIR / "ui" / "main_window.py", "ysb.ui.main_window")
    if main_build_icon() is None:
        raise FileNotFoundError("Main icon not found. Put assets/ysbg_main_icon.ico or assets/ysbg_main_icon.png")
    require_file(SPLASH_FILE, "Runtime splash image assets/ysb_splash.png")
    if ysbg_build_icon() is None:
        raise FileNotFoundError("YSBG file icon not found. Put assets/ysbg_file_icon.ico or assets/ysbg_file_icon.png")


def build_package() -> int:
    if LOG_FILE.exists():
        LOG_FILE.unlink()

    log(f"쯔꾸르붕이 {APP_VERSION} build driver")
    log(f"Project root: {PROJECT_ROOT}")
    log(f"Build tools:  {BUILD_TOOLS_DIR}")
    log("Build policy: single main EXE package, no launcher")

    generate_version_file()
    validate_layout()
    DIST_DIR.mkdir(exist_ok=True)
    clean_build_outputs()

    build_main()
    prepare_package()

    log("")
    log("Build completed successfully.")
    return 0

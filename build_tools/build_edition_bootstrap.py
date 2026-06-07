# -*- coding: utf-8 -*-
"""Safe bootstrap driver for 쯔꾸르붕이 builds.

The BAT only finds Python and calls this file. This file creates/uses .venv,
installs requirements, probes the project, and runs PyInstaller.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

VALID_TARGETS = {"game"}
REQUIRED_PYTHON = (3, 11)
RECOMMENDED_PYTHON = "3.11"

BUILD_TOOLS_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BUILD_TOOLS_DIR.parent
VENV_DIR = PROJECT_ROOT / ".venv"
PY_EXE = VENV_DIR / "Scripts" / "python.exe"


def load_version_info():
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from ysb.version_info import APP_VERSION, BUILD_LOG_FILE_NAME, LITE_PACKAGE_FOLDER_NAME
        return APP_VERSION, BUILD_LOG_FILE_NAME, LITE_PACKAGE_FOLDER_NAME
    except Exception:
        return "current", "build_log_current.txt", "쯔꾸르붕이 current_package"


APP_VERSION, BUILD_LOG_FILE_NAME, PACKAGE_FOLDER_NAME = load_version_info()


def build_bootstrap_log_path(target: str) -> Path:
    return PROJECT_ROOT / f"build_bootstrap_{target}_{APP_VERSION}.log"


class Logger:
    def __init__(self, path: Path):
        self.path = path
        try:
            self.path.write_text(
                f"쯔꾸르붕이 build bootstrap log\n"
                f"Start: {datetime.now()}\n"
                f"Project root: {PROJECT_ROOT}\n"
                f"Build tools: {BUILD_TOOLS_DIR}\n\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def write(self, text: str = "") -> None:
        print(text, flush=True)
        try:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(text + "\n")
        except Exception:
            pass


def run(cmd: list[str], logger: Logger, label: str) -> None:
    logger.write("")
    logger.write(f"=== {label} ===")
    logger.write(" ".join(f'"{x}"' if " " in x else x for x in cmd))

    env = os.environ.copy()
    env.setdefault("PYTHONUTF8", "1")
    env.setdefault("PYTHONIOENCODING", "utf-8")

    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        logger.write(line.rstrip("\r\n"))
    ret = proc.wait()
    if ret != 0:
        raise RuntimeError(f"{label} failed with exit code {ret}")


def python_version_tuple(executable: Path | str) -> tuple[int, int] | None:
    try:
        out = subprocess.check_output(
            [str(executable), "-c", "import sys; print(f'{sys.version_info[0]}.{sys.version_info[1]}')"],
            cwd=str(PROJECT_ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            stderr=subprocess.STDOUT,
        ).strip()
        major, minor = out.split(".", 1)
        return int(major), int(minor)
    except Exception:
        return None


def is_supported_python(ver: tuple[int, int] | None) -> bool:
    return ver == REQUIRED_PYTHON


def version_text(ver: tuple[int, int] | None) -> str:
    return "unknown" if ver is None else f"{ver[0]}.{ver[1]}"


def ensure_supported_driver_python(logger: Logger) -> None:
    driver_ver = sys.version_info[:2]
    logger.write(f"Build driver Python: {sys.executable} ({driver_ver[0]}.{driver_ver[1]})")
    logger.write("Required build/runtime Python: 3.11.x only")
    if not is_supported_python((driver_ver[0], driver_ver[1])):
        raise RuntimeError(
            "Unsupported build Python version. "
            f"Use Python {RECOMMENDED_PYTHON}.x only. "
            "This build intentionally refuses Python 3.10/3.12/3.13 because the packaged EXE can crash at startup when built with a different Python."
        )


def ensure_venv(logger: Logger) -> None:
    """Verify that the build is running inside the project-root .venv.

    The setup BAT is now the single source of truth. Build must not silently create
    or switch to another virtual environment, because that can produce a packaged
    EXE with a different runtime stack than source-run testing.
    """
    if not PY_EXE.exists():
        raise RuntimeError(f"Root .venv Python not found: {PY_EXE}. Run setup_venv.bat first.")

    running = Path(sys.executable).resolve()
    expected = PY_EXE.resolve()
    logger.write(f"[1/9] Expected root .venv Python: {expected}")
    logger.write(f"[1/9] Running build Python     : {running}")

    venv_ver = python_version_tuple(PY_EXE)
    logger.write(f"[1/9] Root .venv Python version: {version_text(venv_ver)}")
    if not is_supported_python(venv_ver):
        raise RuntimeError(f"Root .venv uses Python {version_text(venv_ver)}, not required Python 3.11. Recreate it with setup_venv.bat.")

    try:
        if running != expected:
            raise RuntimeError(
                "Build is not running from the project-root .venv. "
                f"Expected {expected}, got {running}. Use build_tools\\build_game_exe.bat after setup_venv.bat."
            )
    except RuntimeError:
        raise
    except Exception:
        # Path resolution can be odd on some Windows setups; still log and continue
        # only if the version is correct and the executable lives under .venv.
        if ".venv" not in str(running).lower():
            raise RuntimeError(f"Build Python is not inside root .venv: {running}")


def install_requirements(logger: Logger) -> None:
    steps: list[tuple[str, Path]] = [
        ("common requirements", PROJECT_ROOT / "requirements" / "common.txt"),
        ("app requirements", PROJECT_ROOT / "requirements" / "app.txt"),
        ("build requirements", PROJECT_ROOT / "requirements" / "build.txt"),
    ]

    logger.write("[2/9] Upgrading pip...")
    run([str(PY_EXE), "-m", "pip", "install", "--upgrade", "pip<26", "--prefer-binary"], logger, "Upgrade pip")

    index = 3
    for label, req in steps:
        if not req.exists():
            if label == "build requirements":
                logger.write(f"[{index}/9] {label} file missing; installing PyInstaller directly...")
                run([str(PY_EXE), "-m", "pip", "install", "--upgrade", "--prefer-binary", "pyinstaller"], logger, "Install PyInstaller")
            else:
                logger.write(f"[{index}/9] {label} file missing, skipped: {req}")
            index += 1
            continue
        logger.write(f"[{index}/9] Installing {label}...")
        run([str(PY_EXE), "-m", "pip", "install", "--prefer-binary", "-r", str(req)], logger, f"Install {label}")
        index += 1


def main(argv: list[str]) -> int:
    target = (argv[1] if len(argv) > 1 else "game").lower().strip()
    if target not in VALID_TARGETS:
        print("Usage: python build_edition_bootstrap.py game")
        return 2

    logger = Logger(build_bootstrap_log_path(target))
    logger.write(f"쯔꾸르붕이 {APP_VERSION} Build")
    logger.write(f"Target output folder: {PROJECT_ROOT / 'dist' / PACKAGE_FOLDER_NAME}")

    try:
        os.chdir(PROJECT_ROOT)
        ensure_supported_driver_python(logger)
        ensure_venv(logger)
        install_requirements(logger)

        logger.write("[7/9] Build environment check...")
        run([str(PY_EXE), str(BUILD_TOOLS_DIR / "build_probe.py"), target], logger, "Probe")

        logger.write("[8/9] Building package...")
        driver = BUILD_TOOLS_DIR / "build_pyinstaller_game.py"
        if not driver.exists():
            raise FileNotFoundError(f"Build driver not found: {driver}")
        run([str(PY_EXE), str(driver)], logger, "Build")

        logger.write("")
        logger.write("[9/9] Build completed.")
        logger.write("Output folder:")
        logger.write(f"  {PROJECT_ROOT / 'dist' / PACKAGE_FOLDER_NAME}")
        logger.write("Bootstrap log:")
        logger.write(f"  {logger.path}")
        logger.write("PyInstaller log:")
        logger.write(f"  {PROJECT_ROOT / BUILD_LOG_FILE_NAME}")
        return 0
    except Exception as exc:
        logger.write("")
        logger.write(f"ERROR: {exc}")
        logger.write("")
        logger.write("Build stopped. Check this log first:")
        logger.write(f"  {logger.path}")
        logger.write("If PyInstaller started, also check:")
        logger.write(f"  {PROJECT_ROOT / BUILD_LOG_FILE_NAME}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

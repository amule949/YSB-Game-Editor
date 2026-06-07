from pathlib import Path
from ysb.core.workspace_manager import cache_dir

CACHE_FOLDER_NAME = "cache"


def get_app_dir() -> Path:
    # 기존 호환용. 실제 캐시는 Documents\YSB_Translator\cache를 사용한다.
    return cache_dir().parent


def get_cache_dir() -> Path:
    path = cache_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cache_file(name: str) -> Path:
    return get_cache_dir() / name

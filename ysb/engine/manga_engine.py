"""Compatibility wrapper for the old manga engine module.

쯔꾸르붕이 4단계부터 실제 엔진은 `translation_engine.py`로 이동했다.
기존 코드/캐시/설정 모듈이 `ysb.engine.manga_engine`를 import해도 깨지지 않도록
Config와 MangaProcessEngine 이름만 재수출한다.
"""

from ysb.engine.translation_engine import Config, MangaProcessEngine, TranslationProcessEngine

__all__ = ["Config", "MangaProcessEngine", "TranslationProcessEngine"]

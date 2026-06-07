"""쯔꾸르붕이 compatibility/default entry point.

API 번역 단일 구성으로 실행한다.
Direct ``python main.py`` remains a compatibility/default entry point.
"""

from ysb.editions.current import set_current_edition
from ysb.utils.crash_guard import show_startup_error_message, write_startup_crash_log

ENTRY_NAME = "쯔꾸르붕이"


def main() -> int:
    set_current_edition("game")
    try:
        from ysb.core.startup_compat import repair_startup_state
        repair_startup_state()
    except Exception:
        pass
    from ysb.ui.main_window import run_app
    run_app()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        log_path = write_startup_crash_log(exc, entry_name=ENTRY_NAME)
        show_startup_error_message(exc, log_path, title=ENTRY_NAME)
        raise SystemExit(1)

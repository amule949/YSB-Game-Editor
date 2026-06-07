쯔꾸르붕이 빌드용 이미지 배치 규칙

필수:
- assets/ysbg_main_icon.ico 또는 assets/ysbg_main_icon.png
  - 메인 EXE 아이콘 / 작업표시줄 / 창 아이콘 기준 이미지입니다.
  - PNG만 넣어도 빌드 도구가 ICO로 변환합니다. 가능하면 1024x1024 이상 정사각형 PNG 권장.

- assets/ysb_splash.png
  - 프로그램 시작 후 Qt 로딩/진행률 스플래시 화면입니다.
  - 권장: 900x520 전후 또는 16:9에 가까운 PNG.

- assets/ysbg_file_icon.ico 또는 assets/ysbg_file_icon.png
  - .ysbg 프로젝트 파일 연결 아이콘입니다.
  - PNG만 넣어도 빌드 도구가 ICO로 변환합니다. 가능하면 1024x1024 이상 정사각형 PNG 권장.

선택:
- assets/ysb_splash_boot.png
  - PyInstaller onefile 압축 해제 단계에서 먼저 뜨는 부트 스플래시입니다.
  - 없으면 부트 스플래시는 생략하고, 앱 내부 ysb_splash.png 로딩 화면만 사용합니다.

호환 이름:
- 기존 assets/ysb_icon.ico/png, assets/ysbt_file_icon.ico/png도 읽을 수 있지만, 새 빌드에서는 위 이름을 권장합니다.

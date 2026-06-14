# -*- coding: utf-8 -*-
"""
Centralized user-visible text table for YSB Game Editor.

Rule:
- Put every user-visible fixed string here.
- Program logic, OCR text, translated script, and project data must not be translated here.
- Add Korean and English together when adding a new UI/log/message string.
"""

LANG_KO = "ko"
LANG_EN = "en"


def normalize_language(value=None):
    lang = str(value or LANG_KO).lower()
    if lang.startswith("en"):
        return LANG_EN
    return LANG_KO


def tr_from_table(table, text, lang=LANG_KO, **kwargs):
    text = str(text)
    if normalize_language(lang) == LANG_EN:
        out = table.get(text, text)
    else:
        out = text
    if kwargs:
        try:
            return out.format(**kwargs)
        except Exception:
            return out
    return out


def tr_ui(text, lang=LANG_KO, **kwargs):
    return tr_from_table(UI_KO_EN, text, lang, **kwargs)


def tr_api(text, lang=LANG_KO, **kwargs):
    return tr_from_table(API_TR_KO_EN, text, lang, **kwargs)


def tr_shortcut(text, lang=LANG_KO, **kwargs):
    return tr_from_table(SHORTCUT_TR_KO_EN, text, lang, **kwargs)


UI_KO_EN = {
 '프리뷰 보기': 'Show Preview',
 '끄면 일반 대사 프리뷰 생성, 캐시 준비, 선택 행 갱신을 모두 중단합니다.': 'When off, dialogue preview generation, cache preparation, and selected-row refresh are all stopped.',
 '🖥️ 프리뷰 보기: OFF': '🖥️ Show Preview: OFF',
 '🖥️ 프리뷰 보기: ON — 현재 선택된 단일 대사만 갱신': '🖥️ Show Preview: ON — refreshed only the currently selected dialogue row',
 '🖥️ 프리뷰 보기: ON — 단일 대사를 선택하면 표시': '🖥️ Show Preview: ON — select one dialogue row to display it',
 '열린 프로젝트가 없습니다.': 'No project is open.',
 '플러그인 페이지 {count}개를 AI 번역할까요?\n번역 완료 후 원래 플러그인 데이터 위치에 바로 반영됩니다.': 'Translate {count} plugin pages with AI?\nWhen complete, translations will be written directly to their original plugin data locations.',
 '데이터베이스 페이지 {count}개만 먼저 AI 번역할까요?\n번역 완료 후 클론 게임 JSON에 바로 반영됩니다.': 'Translate the selected {count} database pages with AI?\nWhen complete, translations will be written directly to the cloned game JSON.',
 '🧩 플러그인 번역 시작: {count}페이지': '🧩 Plugin translation started: {count} pages',
 '🧩 플러그인 번역 레이어 생성: {count}개 ({reason})': '🧩 Plugin translation layer created: {count} pages ({reason})',
 '⚠️ 플러그인 텍스트 추출 실패: {error}': '⚠️ Failed to extract plugin text: {error}',
 '⚠️ 플러그인 번역 레이어 확인 실패: {error}': '⚠️ Failed to prepare the plugin translation layer: {error}',
 '🧩 플러그인 번역 모드 진입': '🧩 Entered Plugin Translation Mode',
 '↩️ 플러그인 번역 모드 나가기': '↩️ Exited Plugin Translation Mode',
 '⚠️ 플러그인 번역 모드 진입 실패: {error}': '⚠️ Failed to enter Plugin Translation Mode: {error}',
 '플러그인 페이지': 'Plugin Page',
 '전체 플러그인 페이지': 'All Plugin Pages',
 '플러그인 페이지 선택': 'Select Plugin Pages',
 '작업할 플러그인 페이지 범위를 선택하세요.': 'Select the range of plugin pages to process.',
 '쉼표와 범위를 섞어서 입력할 수 있습니다. 번호는 현재 플러그인 탭 순서 기준입니다.': 'You can mix commas and ranges. Numbers follow the current plugin tab order.',
 '플러그인 번역': 'Plugin Translation',
 '플러그인 번역 페이지가 없습니다.': 'There are no plugin translation pages.',
 '플러그인 번역 모드에서 번역할 플러그인 페이지가 없습니다.': 'There are no plugin pages to translate in Plugin Translation Mode.',
 '데이터베이스 번역 페이지가 없습니다.': 'There are no database translation pages.',
 '플러그인 번역 모드': 'Plugin Translation Mode',
 '플러그인 번역 모드로 전환하지 못했습니다.': 'Could not switch to Plugin Translation Mode.',
 '플러그인 번역 모드 나가기': 'Exit Plugin Translation Mode',
 '번역 가능한 플러그인 문구를 찾지 못했습니다.': 'No translatable plugin text was found.',
 '플러그인 목록': 'Plugin List',
 '플러그인 항목 없음': 'No Plugin Items',
 '플러그인 탭': 'Plugin Tab',
 '현재 탭의 플러그인 항목만 번역합니다.': 'Only plugin items in the current tab will be translated.',
 '플러그인 데이터 미리보기': 'Plugin Data Preview',
 '이 플러그인 탭에는 표시할 텍스트가 없습니다.': 'This plugin tab has no text to display.',
 '플러그인의 원본 위치와 번역값을 표시합니다.': 'Shows the plugin source location and translation value.',
 '번역문은 원래 플러그인 데이터 위치에 다시 저장됩니다.': 'The translation is written back to its original plugin data location.',
 '현재 플러그인 텍스트': 'Current Plugin Text',
 '데이터베이스 모드': 'Database Mode',
 '데이터베이스 모드 나가기': 'Exit Database Mode',
 '현재 탭의 DB 항목만 번역합니다.': 'Only database items in the current tab will be translated.',
 '데이터베이스 프리뷰': 'Database Preview',
 '데이터베이스 목록': 'Database List',
 '데이터베이스 항목 없음': 'No Database Items',
 '데이터베이스 탭': 'Database Tab',
 '현재 DB 텍스트': 'Current Database Text',
 '이 DB 탭에는 표시할 텍스트가 없습니다.': 'This database tab has no text to display.',
 '배우 데이터 미리보기': 'Actor Data Preview',
 '얼굴 이미지 없음': 'No Face Image',
 '별명': 'Nickname',
 '직업': 'Class',
 '초기 레벨': 'Initial Level',
 '선택 필드': 'Selected Field',
 '표시값': 'Display Value',
 '원본 파일': 'Source File',
 '원본 위치': 'Source Location',
 '번역문 / 표시값': 'Translation / Display Value',
 '데이터 미리보기': 'Data Preview',
 '실제 게임 화면을 흉내 내지 않고 원본 데이터만 표시합니다.': 'Shows only the source data without imitating the in-game screen.',
 'Actors.json의 실제 데이터만 표시합니다. 게임의 스테이터스 화면을 재현하지 않습니다.': 'Shows only the actual Actors.json data. It does not recreate the in-game status screen.',
 '플러그인 텍스트 페이지 구성 중...': 'Building plugin text pages...',
 '정말 번역을 취소하시겠습니까?\n\n이미 완료되어 반영된 청크는 유지합니다.\n현재 API 요청은 응답이 돌아와도 반영하지 않고, 이후 청크는 시작하지 않습니다.': 'Do you really want to cancel translation?\n\nChunks that have already completed and been applied will be kept.\nThe current API response will be ignored, and no later chunks will be started.',
 '번역 취소됨. 완료된 청크는 유지하고, 현재 응답과 이후 청크는 반영하지 않습니다.': 'Translation canceled. Completed chunks are kept; the current response and later chunks will not be applied.',
 '⏹️ 번역 취소: 완료된 청크는 유지하고 현재 응답과 이후 청크는 버립니다.': '⏹️ Translation canceled: completed chunks are kept, while the current response and later chunks are discarded.',
 '번역 청크 결과 적용에 실패했습니다.': 'Failed to apply the translation chunk result.',
 '취소된 번역 작업입니다.': 'This translation job has been canceled.',
 '번역 청크 결과를 프로젝트에 적용하지 못했습니다.': 'Could not apply the translation chunk result to the project.',
 '✅ 번역 완료: {applied}개 항목을 청크 순서대로 반영했습니다.': '✅ Translation complete: applied {applied} items sequentially by chunk.',
 '⏹️ 번역 취소됨: 이미 반영된 {applied}개 결과는 유지하고 이후 청크는 중단했습니다.': '⏹️ Translation canceled: kept {applied} already-applied results and stopped the remaining chunks.',
 '대사별 프리뷰 구조를 생성하는 중입니다...': 'Building per-dialogue preview structures...',
 '대사 프리뷰 초기 생성': 'Initial Dialogue Preview Build',
 '대사별 프리뷰 구조 생성 중... ({current}/{total})': 'Building dialogue preview structures... ({current}/{total})',
 '대사별 프리뷰 구조 생성 완료': 'Dialogue preview structure build complete',
 '대사 프리뷰 캐시를 확인하는 중...': 'Checking dialogue preview cache...',
 '대사별 프리뷰 구조를 준비하는 중입니다...': 'Preparing per-dialogue preview structures...',
 '대사 프리뷰 캐시 불러오기 완료': 'Dialogue preview cache loaded',
 '대사 프리뷰 초기 생성 완료': 'Initial dialogue preview build complete',
 '⚠️ 대사 프리뷰 준비 실패: {error}': '⚠️ Failed to prepare dialogue previews: {error}',
 '일괄 번역 취소': 'Cancel Batch Translation',
 '정말 일괄 번역을 취소하시겠습니까?\n\n이미 번역이 끝나 반영된 맵은 유지합니다.\n현재 API 요청 중인 맵은 응답이 돌아와도 반영하지 않습니다.\n아직 시작하지 않은 맵은 번역하지 않습니다.': 'Do you really want to cancel batch translation?\n\nMaps that have already finished and been applied will be kept.\nThe current API request will be ignored even if a response comes back.\nMaps that have not started yet will not be translated.',
 '번역 취소': 'Cancel Translation',
 '정말 번역을 취소하시겠습니까?\n\n이미 전송된 API 응답이 돌아와도 번역문에 반영하지 않습니다.': 'Do you really want to cancel translation?\n\nAlready sent API responses will not be applied to the translation even if they return.',
 '작업 취소': 'Cancel Task',
 '정말 현재 작업을 취소하시겠습니까?\n\n현재 처리 중인 항목이 끝난 뒤 중단됩니다.': 'Do you really want to cancel the current task?\n\nIt will stop after the current item finishes.',
 '취소하기': 'Cancel',
 '계속하기': 'Continue',
 '취소 요청됨. 현재 처리 중인 응답은 반영하지 않고 중단합니다.': 'Cancellation requested. The current response will be ignored and the task will stop.',
 '일괄 번역 취소 요청됨. 완료된 맵은 유지하고, 현재 API 응답은 돌아와도 반영하지 않습니다.': 'Batch translation cancellation requested. Completed maps will be kept, and the current API response will be ignored even if it returns.',
 '엔진과 표시 환경을 확인하는 중...': 'Checking the engine and display environment...',
 '배우/화자 힌트를 읽는 중...': 'Reading actor/speaker hints...',
 '작업 폴더 구조를 준비하는 중...': 'Preparing the work folder structure...',
 '게임 파일 목록 확인 중...': 'Scanning game files...',
 '이전 게임 클론을 정리하는 중...': 'Cleaning up the previous game clone...',
 '복사된 게임 구조를 확인하는 중...': 'Checking the copied game structure...',
 '원본 JSON 기준점을 백업하는 중...': 'Backing up the original JSON baseline...',
 '게임 파일 복사 완료': 'Game file copy complete',
 '맵/DB 페이지 구성 완료': 'Map/DB page build complete',
 '가져오기 요약과 표시 설정을 저장하는 중...': 'Saving import summary and display settings...',
 '프로젝트 파일을 저장하는 중...': 'Saving project files...',
 '프로젝트 가져오기 완료': 'Project import complete',
 '공통 이벤트를 확인하는 중...': 'Checking common events...',
 '복사할 게임 파일이 없습니다.': 'No game files to copy.',
 '선택 대사 주변 간이 맵 프리뷰 표시': 'Show Local Map Preview Around Selected Dialogue',
 '현재 선택된 대사의 이벤트 좌표를 중심으로 주변 15x10칸을 잘라 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다.': 'Shows a 15x10 tile area around the event coordinates of the selected dialogue. It does not modify the actual game JSON.',
 '검수용 간이 맵 프리뷰/보조선/이벤트 위치/이벤트 이름 표시를 켜고 끕니다. 간이 맵 프리뷰는 선택된 대사의 이벤트 주변을 격자와 이벤트 점으로 보여주는 1단계 기능이며, 실제 게임 JSON은 바꾸지 않습니다. 쯔꾸르붕이에서는 역식붕이식 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다.': 'Toggle the review-only local map preview, helper lines, event positions, and event names. The local map preview is a stage-1 feature that shows the selected dialogue event area with a grid and event dots, and it does not modify the actual game JSON. In YSB Game Editor, dialogue is not created as YSB typesetting text objects on the map; it is shown only in the game-style message/choice preview and the table on the right.',
 '이벤트 이름 오버레이 표시': 'Show Event Name Overlay',
 '검수용 보조선/이벤트 위치/이벤트 이름 표시를 켜고 끕니다. 쯔꾸르붕이에서는 역식붕이식 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다. 스탠딩/표시 이미지는 번역 작업을 위해 기본 불투명으로 보여주며, 필요할 때만 게임 원래 반투명 연출 반영을 켜세요.': 'Toggle review helper gridlines, event positions, and event name display. In YSB Game Editor, dialogue is not created as YSB typesetting text objects on the map; it is shown only in the game-style message/choice preview and the table on the right. Standing/picture images are shown fully opaque by default for translation work; enable original opacity only when needed.',
 '맵 그리드/보조선, 이벤트 위치, 이벤트 이름 오버레이, 이미지 반투명 표시를 켜고 끕니다. 대사는 맵 위 텍스트 객체가 아니라 게임식 대사창/선택지 프리뷰로 표시합니다.': 'Toggle map grid/helper lines, event positions, event name overlay, and image opacity display. Dialogue is shown through the game-style message/choice preview, not as text objects on the map.',
 '보조선, 이벤트 위치/이름, 이미지 반투명 표시 여부는 프리뷰 표시 옵션에서 관리합니다. 대사는 게임식 대사창/선택지 프리뷰로만 표시합니다.': 'Manage helper lines, event position/name display, and image opacity in Preview Display Options. Dialogue is shown only in the game-style message/choice preview.',
 '프리뷰': 'Preview',
 '프리뷰 갱신': 'Refresh Preview',
 '프리뷰 갱신 준비 중...': 'Preparing preview refresh...',
 '프리뷰 이미지를 다시 만드는 중입니다...': 'Rebuilding the preview image...',
 '기존 프리뷰 캐시를 무시하고 타일 프리뷰를 다시 만드는 중...': 'Ignoring the existing preview cache and rebuilding the tile preview...',
 '새 프리뷰 이미지를 화면에 다시 불러오는 중...': 'Reloading the new preview image...',
 '대사 선택 프리뷰를 다시 그리는 중...': 'Redrawing the selected dialogue preview...',
 '프리뷰 갱신 완료': 'Preview refresh complete',
 '현재 맵의 프리뷰 이미지를 상태/캐시와 무관하게 다시 만듭니다.': 'Rebuild the current map preview image regardless of state or cache.',
 '열린 프로젝트가 없습니다.': 'No project is open.',
 '프리뷰 갱신 실패': 'Preview Refresh Failed',
 '현재 맵 데이터를 찾을 수 없습니다.': 'Could not find the current map data.',
 '쯔꾸르 맵 페이지에서만 사용할 수 있습니다.': 'This can only be used on an RPG Maker map page.',
 '현재 맵 이미지 경로를 찾을 수 없습니다.': 'Could not find the current map image path.',
 '현재 맵 프리뷰를 다시 만들지 못했습니다.': 'Could not rebuild the current map preview.',
 '🔄 프리뷰 갱신 완료: 현재 맵 이미지를 다시 만들었습니다.': '🔄 Preview refresh complete: rebuilt the current map image.',
 '⚠️ 프리뷰 갱신 실패: {error}': '⚠️ Preview refresh failed: {error}',
 '제어코드': 'Control Codes',
 '현재줄 보기': 'Show Current',
 '현재 맵 복원': 'Restore Current Map',
 '전체 맵 복원': 'Restore All Maps',
 '원문의 앞뒤에 붙은 제어코드를 자동복원합니다.': 'Automatically restores control codes attached before/after the source text.',
 '선택한 대사에만 제어코드 포함 원문을 보조줄로 표시합니다.': 'Show the control-code raw source as a helper line only for the selected dialogue.',
 '전체 보기': 'Show All',
 '제어코드가 있는 모든 대사 아래에 제어코드 포함 원문을 표시합니다.': 'Show the control-code raw source under every dialogue that has control codes.',
 '자동복원': 'Auto Restore',
 '현재 선택한 대사의 앞/뒤 제어코드만 번역문에 붙입니다.': 'Apply only leading/trailing control codes to the selected translation.',
 '안전일괄': 'Safe Batch',
 '현재 맵에서 앞/뒤 제어코드만 있는 번역문을 일괄 복원합니다.': 'Batch-restore only safe leading/trailing control codes on the current page.',
 '제어코드 포함 원문': 'Raw Source with Control Codes',
 '제어코드 있음': 'Has Control Codes',
 '자동복원 가능': 'Auto-Restorable',
 '수동처리 필요': 'Manual Handling Needed',
 '없음': 'None',
 '번역/API에는 제어코드를 제거한 원문만 사용합니다.': 'Translation/API uses only the source text with control codes removed.',
 '번역 시 자동 반영': 'Auto-apply on translation',
 '번역 시 제어코드 자동 반영': 'Auto-apply control codes on translation',
 '번역 시 자동으로 제어코드를 원문과 유사하게 복원합니다.': 'Automatically restores control codes in positions similar to the source during translation.',
 '🧩 번역 시 제어코드 자동 반영: ON': '🧩 Control-code auto-apply on translation: ON',
 '🧩 번역 시 제어코드 자동 반영: OFF': '🧩 Control-code auto-apply on translation: OFF',
 '🎮 쯔꾸르 AI 번역: 제어코드를 안전 토큰으로 분리하고 번역 의미에 맞춰 자동 반영합니다.': '🎮 RPG Maker AI translation: control codes are separated into safe tokens and automatically placed according to translated meaning.',
 '⚠️ 제어코드 자동 반영에 실패한 {count}개 대사는 안전을 위해 순수 번역문으로 유지했습니다.': '⚠️ {count} dialogue lines failed control-code auto-apply and were kept as plain translations for safety.',
 'ℹ️ AI 토큰 검증에 실패한 {count}개 대사는 안전한 앞/뒤 제어코드만 자동 복원했습니다.': 'ℹ️ For {count} dialogue lines that failed AI token validation, only safe leading/trailing control codes were restored.',
 '⚠️ 제어코드 자동 반영 실패 {count}개: 안전을 위해 순수 번역문으로 유지': '⚠️ Control-code auto-apply failed for {count} items: kept plain translations for safety',
 '상태': 'Status',
 '정리 원문': 'Clean Source',
 '⚠️ 쯔꾸르 선택 프리뷰 갱신 실패: {error}': '⚠️ Failed to refresh Maker selection preview: {error}',
 '작업 로그': 'Work Log',
 '로그 숨기기': 'Hide Log',
 '로그 열기': 'Open Log',
 '작업 로그를 아래 막대로 접습니다.': 'Collapse the work log to the bottom bar.',
 '숨긴 작업 로그를 다시 엽니다.': 'Open the hidden work log again.',
 '프로젝트 나가기': 'Exit Project',
 '현재 프로젝트를 닫고 홈화면으로 이동합니다.': 'Close the current project and go to the Home screen.',
 '맵 목록': 'Map List',
 '맵 없음': 'No maps',
 '프로젝트 생성 위치 없음': 'Project Location Not Found',
 '마지막 프로젝트 생성 위치를 찾을 수 없습니다. 새 생성 위치를 선택해 주세요.': 'Could not find the last project creation location. Please choose a new location.',
 '이미지 없이 YSBG 프로젝트 파일을 먼저 만들고, 나중에 이미지 불러오기로 페이지를 추가합니다.': 'Create the YSBG project file first without images, then add pages later with Import Images.',
 '빈 YSBG 프로젝트를 만들 수 없습니다.': 'Could not create an empty YSBG project.',
'.ysbg 확장자 연결': '.ysbg File Association',
 '.ysbg 확장자 연결 갱신': 'Refresh .ysbg Association',
 '.ysbg 확장자 연결 등록': 'Register .ysbg Association',
 '.ysbg 확장자 연결 등록/갱신 완료': '.ysbg association registered/refreshed.',
 '.ysbg 확장자 연결 등록에 실패했습니다.': 'Failed to register .ysbg file association.',
 '.ysbg 확장자 연결 해제에 실패했습니다.': 'Failed to unregister .ysbg file association.',
 '.ysbg 확장자 연결을 현재 실행 중인 쯔꾸르붕이로 등록했습니다.\n아이콘 표시는 Windows 아이콘 캐시 때문에 조금 늦게 갱신될 수 있습니다.': '.ysbg file association has '
                                                                                         'been registered to the '
                                                                                         'currently running YSB Game Editor.\n'
                                                                                         'The icon may take a moment '
                                                                                         'to update due to the Windows '
                                                                                         'icon cache.',
 '.ysbg 확장자 연결이 등록되어 있지 않습니다.\n등록하지 않아도 프로그램 사용은 가능하지만, .ysbg 파일을 더블클릭해서 바로 열 수는 없습니다.\n\n지금 등록할까요?': '.ysbg file '
                                                                                                      'association is '
                                                                                                      'not '
                                                                                                      'registered.\n'
                                                                                                      'You can still '
                                                                                                      'use the program '
                                                                                                      'without '
                                                                                                      'registering it, '
                                                                                                      'but '
                                                                                                      'double-clicking '
                                                                                                      '.ysbg files '
                                                                                                      'will not open '
                                                                                                      'them directly.\n'
                                                                                                      '\n'
                                                                                                      'Register it '
                                                                                                      'now?',
 '.ysbg 확장자가 현재 실행 중인 쯔꾸르붕이에 이미 연결되어 있습니다.': '.ysbg is already associated with the currently running YSB Game Editor.',
 '.ysbg 확장자 연결 해제': 'Unregister .ysbg Association',
 '1. 원본': '1. Original',
 '2. 분석도': '2. Analysis',
 '3. 텍스트 마스크': '3. Text Mask',
 '4. 페인팅 마스크': '4. Painting Mask',
 '5. 최종결과': '5. Final Result',
 'AI 번역 API에 함께 전달할 프롬프트를 입력합니다.\n확인을 누르면 옵션 캐시에 저장되고, 닫기를 누르면 저장하지 않고 나갑니다.': 'Enter the prompt to send together with '
                                                                               'the AI translation API.\n'
                                                                               'OK saves it to the options cache. '
                                                                               'Cancel closes without saving.',
 'API 관리': 'API Settings',
 'API 설정 캐시': 'API settings cache',
 'API 설정 캐시 Save complete': 'API settings cache saved',
 'API 설정 캐시 Save 완료': 'API settings cache saved',
 'API 설정 캐시 내보내기 완료': 'API settings cache saved',
 'API 설정 필요': 'API Settings Required',
 'API 설정이 비어 있거나 잘못되어 엔진을 시작하지 못했습니다.': 'The API settings are empty or invalid, so the engine could not start.',
 'API 키 없음': 'Missing API Key',
 'CLOVA OCR로 재분석': 'Re-analyzing with CLOVA OCR',
 'Custom': 'Custom',
 'Custom 번역 API 설정이 비어있습니다.': 'Custom translation API settings are empty.',
 'English': 'English',
 'Google Vision OCR로 재분석': 'Re-analyzing with Google Vision OCR',
 'JSON 가져오기': 'Import JSON',
 'JSON 파일로 열기': 'Open JSON Project',
 'LaMa inpainting started': 'LaMa inpainting started',
 'Lama inpainting started': 'LaMa inpainting started',
 'Magic Wand Select 되돌림': 'Magic Wand selection undone',
 'Move 모드': 'Move Mode',
 'OFF 페인팅 마스크 없음': 'No OFF painting mask',
 'ON은 분석 기반, OFF는 직접 칠한 마스크를 사용합니다.': 'ON uses the analysis-based mask. OFF uses only manually painted masks.',
 'ON이면 이후 새로 칠하는 브러시가 텍스트보다 위 레이어에 그려집니다.': 'When ON, newly painted brush strokes are drawn above the text layer.',
 'RGB 허용범위': 'RGB Tolerance',
 'Save complete': 'saved',
 'Stable Diffusion inpainting started': 'Stable Diffusion inpainting started',
 'Stable Diffusion 인페인팅 시작': 'Stable Diffusion inpainting started',
 'Stable Diffusion 인페인팅 완료': 'Stable Diffusion inpainting complete',
 'TXT 없음': 'TXT missing',
 'TXT 파일을 다시 읽지 못했습니다:': 'Could not reread the TXT file:',
 'TXT 파일을 읽지 못했습니다:': 'Could not read the TXT file:',
 'YSBG 열기 실패': 'Failed to Open YSBG',
 'YSBG 내보내기 실패': 'Failed to Save YSBG',
 'YSBG 파일을 저장하지 못했습니다.': 'Could not save the YSBG file.',
 'YSBG 프로젝트 열기': 'Open YSBG Project',
 'YSBG 프로젝트를 열지 못했습니다.': 'Could not open the YSBG project.',
 '[옵션 > API 관리]에서 키를 저장한 뒤 다시 시도해주세요.': 'Save the key in [Options > API Settings] and try again.',
 '[옵션 > API 관리]에서 키를 저장해주세요.': 'Please save the key in [Options > API Settings].',
 '[프로젝트 내보내기] 또는 [다른 이름으로 내보내기]을 눌러 .ysbg로 저장하세요.': 'Use [Save Project] or [Save As] to save it as a .ysbg file.',
 '⚡ 분석': '⚡ Analyze',
 '같은 이름의 프리셋이 이미 있습니다.': 'A preset with the same name already exists.',
 '개 삭제': 'items deleted',
 '개별 글꼴 프리셋': 'Item Font Preset',
 '개별 글꼴 프리셋 관리': 'Item Font Presets',
 '개별 글꼴 프리셋 불러오기': 'Load Item Font Preset',
 '개별 번역': 'Translate Current',
 '개별 번역문 불러오기': 'Import Translation Current',
 '개별 분석': 'Analyze Current',
 '개별 인페인팅': 'Inpaint Current',
 '개별 지문 추출': 'Extract Text Current',
 '개별 출력': 'Export Current',
 '출력 미리보기': 'Export Preview',
 '현재 페이지 출력 미리보기를 생성하는 중입니다...': 'Generating an export preview for the current page...',
 '실제 출력과 동일한 옵션으로 미리보기를 생성하는 중입니다...': 'Generating a preview with the same options as actual export...',
 '실제 출력 파일과 같은 포맷으로 미리보기를 확인하는 중입니다.': 'Loading the preview in the same format as the actual export file.',
 '출력 옵션 창을 열지 못했습니다:': 'Could not open the output options dialog:',
 '출력 렌더 기준으로 미리보기를 만드는 중입니다.': 'Rendering the preview using export settings.',
 '출력 미리보기 준비 완료': 'Export preview ready',
 '미리보기할 현재 페이지 데이터가 없습니다.': 'There is no current page data to preview.',
 '출력 미리보기를 생성하지 못했습니다.': 'Could not generate the export preview.',
 '출력 미리보기 이미지를 읽지 못했습니다.': 'Could not read the export preview image.',
 '현재 페이지가 실제 출력에서 어떻게 보일지 렌더링한 미리보기입니다. 텍스트 이펙트 미리보기가 꺼져 있어도 출력 기준 이펙트는 모두 적용됩니다.': 'This preview shows how the current page will look when exported. Export effects are fully applied even if Text Effect Preview is turned off.',
 '미리보기 이미지를 그대로 실제 출력 폴더에 저장하고 포토샵 스크립트도 함께 저장합니다.': 'Save the preview image exactly as shown into the actual output folder and also save the Photoshop script.',
 '출력 중...': 'Exporting...',
 '미리보기 결과를 실제 출력 폴더에 저장했습니다.': 'Saved the preview result to the actual output folder.',
 '미리보기 결과 출력 실패:': 'Failed to export the preview result:',
 '미리보기 임시 출력 폴더를 찾지 못했습니다.': 'Could not find the temporary preview output folder.',
 '미리보기 결과 파일이 없습니다.': 'There is no preview result file.',
 '미리보기 출력 파일을 저장하지 못했습니다.': 'Could not save the preview output files.',
 '출력 준비 중...': 'Preparing export...',
 '출력 진행 중...': 'Exporting...',
 '현재 페이지 데이터를 정리하는 중입니다.': 'Preparing the current page data.',
 '출력 배경과 페인팅 레이어를 준비하는 중입니다.': 'Preparing the export background and paint layers.',
 '기본 출력 이미지를 생성하는 중입니다.': 'Creating the base export image.',
 '최종화면 기준으로 텍스트를 렌더링하는 중입니다.': 'Rendering text from the Final Result view.',
 '최종 이미지를 재구성 렌더링하는 중입니다.': 'Rendering the final image from data.',
 '텍스트 위 페인팅을 합성하는 중입니다.': 'Compositing the paint layer above text.',
 '출력 완료': 'Export complete',
 '개별 텍스트 정리': 'Clean Text Current',
 '개별 프리셋 삭제': 'Delete Item Preset',
 '개별 프리셋 추가': 'Add Item Preset',
 '갱신': 'Refresh',
 '갱신 실패': 'Refresh Failed',
 '갱신 완료': 'Refresh Complete',
 '갱신할 파일 없음': 'No File to Refresh',
 '결과물 출력': 'Export Result',
 '결과물이 비어있습니다.': 'The result is empty.',
 '경로 오류': 'Path Error',
 '관리': 'Manage',
 '구버전 프로젝트 폴더 선택': 'Select Legacy Project Folder',
 '굵게': 'Bold',
 '굵기': 'Bold',
 '글자 수': 'Characters',
 '글자 정렬': 'Text Alignment',
 '기울임': 'Italic',
 '기존 TXT 파일 경로를 찾을 수 없습니다. 다시 불러오기를 해주세요.': 'The existing TXT file path could not be found. Please load it again.',
 '기존 TXT 파일 내용으로 단어장 캐시를 갱신했습니다.': 'Glossary cache has been refreshed from the existing TXT file.',
 '내용': 'Content',
 '너비': 'Width',
 '높이': 'Height',
 '누적': 'total',
 '다른 이름으로 YSBG 저장': 'Save YSBG As',
 '다른 이름으로 내보내기': 'Save As',
 '다른 이름으로 내보내기 완료': 'Save As complete',
 '다음 맵': 'Next Map',
 '다크 테마': 'Dark Theme',
 '단어장': 'Glossary',
 '단어장 TXT 불러오기': 'Load Glossary TXT',
 '단어장 초기화': 'Reset Glossary',
 '단어장을 캐시에 반영했습니다. 닫기를 누르면 유지됩니다.': 'Glossary has been applied to the cache. Close to keep it.',
 '단일 실행 경고': 'Single Instance Warning',
 '단일 실행 서버를 시작하지 못했습니다.\n프로그램은 계속 실행되지만 중복 실행 차단이 정상 동작하지 않을 수 있습니다.': 'Could not start the single-instance server.\n'
                                                                       'The program will continue, but '
                                                                       'duplicate-instance blocking may not work '
                                                                       'correctly.',
 '단축키': 'Shortcut',
 '단축키 통합 관리': 'Shortcut Manager',
 '닫기': 'Cancel',
 '대상': 'Targets',
 '덮어쓰기': 'Overwrite',
 '데이터 없음': 'No data',
 '데이터가 없습니다.': 'No data.',
 '도구': 'Tool',
 '도구:': 'Tool:',
 '도구: Brush': 'Tool: Brush',
 '도구: Eraser': 'Tool: Eraser',
 '도구: Move': 'Tool: Move',
 '도구: Text': 'Tool: Text',
 '되돌리기': 'Undo',
 '되돌림': 'undone',
 '등록 실패': 'Registration Failed',
 '등록 완료': 'Registration Complete',
 '를 삭제할까요?': 'Delete?',
 '마스크 ON/OFF': 'Mask ON/OFF',
 '마스크 되돌림': 'Mask undo',
 '마스크 자동 저장': 'Mask auto-saved',
 '마스킹': 'Masking',
 '마스킹 칠하기': 'Fill Mask',
 '마스킹 칠하기는 텍스트 마스크/페인팅 마스크 탭에서만 가능합니다.': 'Fill Mask is only available in the Text Mask or Painting Mask tab.',
 '마지막 설정': 'Last Settings',
 '매크로 관리': 'Macro Manager',
 '매크로 실행 중': 'Macro Running',
 '먼저 불러오기로 TXT 파일을 선택해주세요.': 'Please load a TXT file first.',
 '먼저 요술봉으로 영역을 선택하세요.': 'Select an area with the Magic Wand first.',
 '먼저 인페인팅된 이미지가 있어야 원본으로 가져올 수 있습니다.': 'An inpainted image is required before it can be used as the source.',
 '모드': 'Mode',
 '묶음': 'Chunk',
 '묶음 수': 'Chunk size',
 '문자 너비': 'Character Width',
 '문자 높이': 'Character Height',
 '문자 색상': 'Text Color',
 '문자색': 'Text Color',
 '밀림 방지를 위해 결과 반영을 중단했습니다.': 'Stopped applying results to prevent shifted translations.',
 '박스 클릭 토글': 'Box click toggle',
 '반영할 배경 이미지가 없습니다.': 'There is no base image to apply the final paint to.',
 '반영할 최종 페인팅이 없습니다.': 'There is no final paint to apply.',
 '번역': 'Translate',
 '번역 개수 불일치': 'Translation count mismatch',
 '번역 건너뜀': 'Translation skipped',
 '번역 엔진': 'Translation engine',
 '번역 오류': 'Translation Error',
 '번역 완료': 'Translation complete',
 '번역 요청 중... (화면이 잠시 멈출 수 있습니다)': 'Requesting translation... (the screen may pause briefly)',
 '번역 중 에러 발생': 'Translation error occurred',
 '번역 참고 자료로 사용할 TXT 파일을 캐시에 저장합니다.\n배경 설명, 단어 해설, 1대1 대체 규칙 등을 넣어둘 수 있습니다.': 'Save a TXT file as translation reference '
                                                                             'material in the cache.\n'
                                                                             'You can include background notes, term '
                                                                             'explanations, and one-to-one replacement '
                                                                             'rules.',
 '번역 참고 자료로 사용할 TXT 파일을 캐시에 저장합니다.\n배경 설명, 단어 해설, 1대1 대체 규칙 등을 넣어둘 수 있습니다.\n탭으로 구분된 단어장은 화면에서만 표처럼 정렬해 보여주며, 실제 저장 형식은 그대로 유지됩니다.': 'Save a TXT file as translation reference '
                                                                                                       'material in the cache.\n'
                                                                                                       'You can include background notes, term '
                                                                                                       'explanations, and one-to-one replacement '
                                                                                                       'rules.\n'
                                                                                                       'Tab-separated glossary entries are aligned like a table only in the preview; '
                                                                                                       'the actual stored format stays unchanged.',
 '번역 프롬프트 입력': 'Translation Prompt',
 '번역AI': 'Translate AI',
 '번역문 TXT 불러오기': 'Load Translation TXT',
 '번역문 내용 지우기': 'Clear Translation Current',
 '번역문 내용 지우기 완료': 'Translations cleared',
 '번역문 불러오기 완료': 'Translation import complete',
'원문/번역문 입출력': 'Source/Translation Import/Export',
 '번역문만': 'Translation Only',
 '번역할 데이터가 없습니다.': 'No data to translate.',
 '변경 사항은 작업 캐시에만 저장됩니다.': 'Changes are saved only to the work cache.',
 '변경 사항이 실제 프로젝트에 바로 저장됩니다.': 'Changes are saved directly to the actual project.',
 '복사할 텍스트가 없습니다.': 'There is no text to copy.',
 '분석': 'Analyze',
 '분석 결과 반영 완료': 'analysis result applied',
 '불러오기': 'Load',
 '불러오기 실패': 'Load Failed',
 '불러오기 완료': 'Load Complete',
 '불러올 텍스트 번호가 없습니다.': 'There are no text IDs to load.',
 '불투명도': 'Opacity',
 '붙여넣은 뒤 실제로 움직인 뒤 클릭하면 붙여넣습니다. ESC로 Canceled.': 'After pasting, move it and click to place it. Press ESC to cancel.',
 '붙여넣은 뒤 실제로 움직인 뒤 클릭하면 붙여넣습니다. ESC로 취소됩니다.': 'After pasting, move it and click to place it. Press ESC to cancel.',
 '붙여넣을 텍스트가 없습니다.': 'There is no text to paste.',
 '브러시': 'Brush',
 '브러시/지우개는 마스크 탭 또는 최종화면에서만 사용할 수 있습니다.': 'Brush/Eraser can only be used in mask tabs or the final screen.',
 '사용': 'Use',
 '사용 선택 이름': 'Use / Select / Name',
 '사용자지정': 'Custom',
 '삭제': 'deleted',
 '삭제 / 번호 재정렬': 'deleted / IDs reordered',
 '삭제하고 번호를 재정렬할까요?': 'Delete and reorder IDs?',
 '삭제할 체크 해제 항목이 없습니다.': 'There are no unchecked items to delete.',
 '삭제할 텍스트가 없습니다.': 'There is no text to delete.',
 '삭제할까요?': 'Delete?',
 '새 Brush를 텍스트 위에 그리기': 'Draw new Brush above text',
 '새 브러시를 텍스트 위에 그리기': 'Draw new brush above text',
 '새 임시 프로젝트 생성': 'New temporary project created',
 '새 텍스트 영역 생성 대기': 'Waiting for new text area',
 '새 텍스트 입력 Canceled': 'New text input canceled',
 '새 텍스트 입력 취소': 'New text input canceled',
 '새 텍스트 추가 완료': 'New text added',
 '새 프로젝트 만들기': 'New Project',
 '새 프로젝트에 넣을 이미지 선택': 'Select Images for New Project',
 '새로 등록할 실행 명령': 'New command to register',
 '선택': 'Select',
 '선택 영역 확장': 'Expand Selection',
 '선택 텍스트': 'Selected Text',
 '선택한 텍스트': 'Selected text',
 '선택한 텍스트 ': 'Selected text ',
 '선택한 텍스트 라인을 삭제할까요?': 'Delete the selected text line?',
 '선택한 폴더에서 원본 이미지 파일명과 같은 TXT 파일을 찾지 못했거나, 맞는 텍스트 번호를 찾지 못했습니다.': 'Could not find TXT files matching the original '
                                                                  'image filenames, or matching text IDs were not '
                                                                  'found.',
 '선택한 폴더의 TXT 번역문을': 'Apply TXT translations from the selected folder to',
 '선택한 행을 삭제할까요?': 'Delete the selected row?',
 '설정 완료': 'Settings Saved',
 '스크립트 저장': 'Script saved',
 '스포이드: Alt+마우스 좌클릭': 'Eyedropper: Alt + left click',
 '시작 완료': 'Ready',
 '식질 실패': 'Typesetting failed',
 '실패': 'failed',
 '실행할까요?': 'Run it?',
 '아직 YSBG 파일로 저장되지 않았습니다.': 'This project has not been saved as a YSBG file yet.',
 '아직 불러온 단어장이 없습니다.': 'No glossary has been loaded yet.',
 '압축 해제 완료 · 인터페이스 로딩 중...': 'Extraction complete · Loading interface...',
 '언어': 'Language',
 '언어 변경': 'Language changed',
 '언어 설정': 'Language Settings',
 '없음': 'None',
 '에러': 'Error',
 '에러가 발생했습니다:': 'An error occurred:',
 '엔진 초기화 실패': 'Engine Initialization Failed',
 '엔진이 아직 준비되지 않았습니다.': 'The engine is not ready yet.',
 '쯔꾸르붕이 작업 폴더 설정': 'YSB Game Editor Workspace Folder Settings',
 '연결된 YSBG 파일': 'Linked YSBG file',
 '열 수 있는 프로젝트 파일이 아닙니다.': 'This is not a project file that can be opened.',
 '영역 재분석 중': 're-analyzing selected area',
 '영역 확장 범위': 'Expansion Range',
 '영역확장': 'Expand Area',
 '예:': 'Example:',
 '예: 일본어를 한국어로 자연스럽게 번역해줘. 캐릭터 말투와 줄바꿈을 유지해줘.': 'Example: Translate Japanese into natural Korean. Keep each '
                                                "character's tone and line breaks.",
 '오류': 'Error',
 '오류 발생': 'Error occurred',
 '옵션': 'Options',
 '옵션 > API 관리에서 Base URL, Model, API Key를 입력해주세요.': 'Enter Base URL, Model, and API Key in Options > API Settings.',
 '완료': 'complete',
 '외부 YSBG 파일 열기': 'Open External YSBG File',
 '요술봉': 'Magic Wand',
 '요술봉 RGB 허용범위': 'Magic Wand RGB Tolerance',
 '요술봉 기준 이미지가 없습니다.': 'There is no source image for Magic Wand.',
 '요술봉 선택': 'Magic Wand selection',
 '요술봉 선택 되돌림': 'Magic Wand selection undone',
 '요술봉 선택 실패': 'Magic Wand selection failed',
 '요술봉 선택 영역을 현재 마스크에 칠했습니다.': 'Magic Wand selection has been filled into the current mask.',
 '요술봉 선택 추가': 'Magic Wand selection added',
 '요술봉 영역 확장': 'Magic Wand selection expanded',
 '요술봉 영역확장': 'Magic Wand expansion',
 '요술봉 영역확장 범위': 'Magic Wand Expansion Range',
 '요술봉은 텍스트 마스크/페인팅 마스크 탭에서 사용하세요.': 'Use Magic Wand in the Text Mask or Painting Mask tab.',
 '요술봉은 텍스트 마스크/페인팅 마스크 탭에서만 사용할 수 있습니다.': 'Magic Wand can only be used in the Text Mask or Painting Mask tab.',
 '요청': 'Requested',
 '원문': 'Original',
 '원문+번역문': 'Original + Translation',
 '원문만': 'Original Only',
 '원본 탭의 기준 이미지를 실제 원본으로 되돌렸습니다.': 'The Original tab base image has been restored to the real original image.',
 '원본으로 돌아가기': 'Restore Original Source',
 '은(는) 일괄 작업이 끝난 뒤 다시 시도해 주세요.': 'can be tried again after the batch job finishes.',
 '응답': 'Returned',
 '이 YSBG 파일은 이미 작업 폴더로 가져온 적이 있습니다.\n기존 작업 폴더를 열까요?\n\n[아니오]를 누르면 새 복사본으로 다시 가져옵니다.': 'This YSBG file has already been '
                                                                                      'imported into a workspace.\n'
                                                                                      'Open the existing workspace?\n'
                                                                                      '\n'
                                                                                      'Choose [No] to import it again '
                                                                                      'as a new copy.',
 '이 작업은 Windows의 확장자 연결 정보만 덮어씁니다. 기존 .ysbg 프로젝트 파일은 변경되지 않습니다.': 'This only overwrites the Windows file association. '
                                                                  'Existing .ysbg project files are not changed.',
 '이동': 'Move',
 '이동 예약 완료': 'Workspace Move Scheduled',
 '이름': 'Name',
 '이름 변경 실패': 'Rename Failed',
 '이미 가져온 프로젝트': 'Already Imported Project',
 '이미 등록됨': 'Already Registered',
 '이미 실행 중인 매크로가 있습니다. 현재 매크로가 끝난 뒤 다시 실행해주세요.': 'A macro is already running. Please run it again after the current '
                                                'macro finishes.',
 '이미 일괄 작업이 진행 중입니다.\n현재 작업이 끝난 뒤 다시 실행해 주세요.': 'A batch job is already running.\n'
                                                'Please run it again after the current job finishes.',
 '이미지 변환 실패': 'Image Conversion Failed',
 '이미지 없음': 'No image',
 '이전 맵': 'Previous Map',
 '인터페이스 로딩 중...': 'Loading interface...',
 '인페인팅': 'Inpaint',
 '인페인팅 건너뜀': 'Inpainting skipped',
 '인페인팅 결과 없음': 'No inpainting result',
 '인페인팅 결과 이미지를 원본 탭에 표시할 수 없습니다.': 'Could not display the inpaint result image on the Original tab.',
 '인페인팅 결과 해상도 보정': 'Inpaint result size normalized',
 '인페인팅 결과를 원본 탭의 작업중 기준 이미지로 가져왔습니다.': 'Inpaint result has been imported as the working source image for the Original '
                                       'tab.',
 '인페인팅 마스크 해상도 보정': 'Inpaint mask size normalized',
 '인페인팅 서버에서 응답이 없습니다. (API 토큰/모델 설정 확인 필요)': 'No response from the inpainting server. Check API token/model settings.',
 '인페인팅 시작': 'Inpainting started',
 '인페인팅 완료': 'Inpainting complete',
 '인페인팅 입력': 'Inpainting input',
 '인페인팅 입력 축소': 'Inpaint input resized',
 '인페인팅 해상도 확인': 'Inpaint size check',
 '일괄 인페인팅 해상도 확인': 'Batch inpaint size check',
 '현재 이미지가 LaMa 권장 해상도를 넘을 수 있습니다.': 'This image may exceed the recommended LaMa resolution.',
 '선택한 맵 중 일부가 LaMa 권장 해상도를 넘습니다.': 'Some selected pages exceed the recommended LaMa resolution.',
 '현재 이미지': 'Current image',
 '권장 기준': 'Recommended limit',
 '인페인팅용 축소 예상': 'Estimated inpaint resize',
 '리사이즈 후 진행': 'Resize and continue',
 '그대로 진행': 'Continue without resize',
 '선택한 전체 맵에 같은 기준으로 적용': 'Apply the same limit to all selected pages',
 '기준 초과 페이지': 'Pages over the limit',
 '외 추가 페이지가 있습니다.': '{count} more page(s)',
 '인페인팅 리사이즈 취소': 'Inpaint resize canceled',
 '인페인팅을 먼저 해주세요.': 'Please run inpainting first.',
 '인페인팅을 원본으로': 'Use Background as Source',
 '일괄': 'Batch',
 '일괄 analyze 완료!': 'Batch analyze complete!',
 '일괄 inpaint 완료!': 'Batch inpaint complete!',
 '일괄 translate 완료!': 'Batch translate complete!',
 '일괄 번역': 'Batch Translate',
 '일괄 번역문 TXT 폴더 선택': 'Select Batch Translation TXT Folder',
 '일괄 번역문 내용 지우기': 'Batch Clear Translation',
 '일괄 번역문 내용 지우기 완료': 'Batch translations cleared',
 '일괄 번역문 불러오기': 'Batch Import Translation',
 '일괄 번역문 불러오기 완료': 'Batch translation import complete',
 '일괄 분석': 'Batch Analyze',
    '일괄 재분석': 'Batch Re-analyze',
 '일괄 불러오기 실패': 'Batch Import Failed',
 '일괄 인페인팅': 'Batch Inpaint',
 '일괄 자동 줄 내림': 'Batch Auto Line Break',
 '일괄 자동 줄 내림 완료': 'Batch Auto Line Break complete',
 '일괄 자동 텍스트 크기 조정': 'Batch Auto Text Size',
 '일괄 자동 텍스트 크기 조정 완료': 'Batch Auto Text Size complete',
 '일괄 작업': 'Batch Work',
 '일괄 작업 중': 'Batch Work Running',
 '일괄 작업 중 차단됨': 'Blocked during batch work',
 '일괄 작업 중에는 프로그램을 종료할 수 없습니다.\n작업이 끝난 뒤 다시 종료해 주세요.': 'The program cannot be closed during batch work.\n'
                                                      'Please close it after the current work finishes.',
 '일괄 정리할 체크 해제 항목이 없습니다.': 'There are no unchecked items to clean in batch.',
 '일괄 지문 추출': 'Batch Extract Text',
'일괄 원문/번역문 내보내기': 'Batch Export Source/Translation TXT',
 '일괄 지문 추출 완료': 'Batch text extraction complete',
 '일괄 지문 추출 취소': 'Batch extract text canceled',
'일괄 원문/번역문 내보내기 취소': 'Batch source/translation export canceled',
 '일괄 출력': 'Batch Export',
 '일괄 텍스트 갱신': 'Batch Text Refresh',
 '일괄 텍스트 정리': 'Batch Clean Text',
 '일괄 텍스트 정리 완료': 'Batch text cleanup complete',
 '임시 프로젝트 삭제': 'Temporary project deleted',
 '임시 프로젝트를 작업 폴더로 승격': 'Temporary project promoted to workspace',
 '임시 프로젝트를 작업 폴더로 옮기지 못했습니다.': 'Could not move the temporary project to the workspace folder.',
 '자간': 'Letter',
 '자동': 'Auto',
 '자동 줄 내림': 'Auto Line Break',
 '자동 줄 내림 완료': 'Auto Line Break complete',
 '자동 줄 내림을': 'Run Auto Line Break on',
 '자동 텍스트 크기 조정': 'Auto Text Size',
 '자동 텍스트 크기 조정 완료': 'Auto Text Size complete',
 '자동 텍스트 크기 조정을': 'Run Auto Text Size on',
 '자동저장 모드': 'Auto Save Mode',
 '자동저장 모드 OFF': 'Auto Save Mode OFF',
 '자동저장 모드 OFF: 변경 사항은 작업 캐시에만 저장됩니다.': 'Auto Save Mode OFF: changes are saved only to the work cache.',
'자동저장 모드는 폐지되었습니다. 변경 사항은 작업 캐시에 보관되고, 프로젝트 저장 시 작업 폴더에 저장됩니다. YSBG는 내보내기에서만 생성됩니다.': 'Auto Save has been removed. Changes are kept in the work cache and saved to the work folder when you save the project. YSBG packages are created only through export.',
 '자동저장 모드 ON': 'Auto Save Mode ON',
 '자동저장 모드 ON: 변경 사항이 실제 프로젝트에 바로 저장됩니다.': 'Auto Save Mode ON: changes are saved directly to the actual project.',
 '자동저장 전환': 'Switch Auto Save',
 '자동화 작업': 'Automation',
 '작업': 'Work',
 '작업 세션 시작': 'Work session started',
 '작업 취소': 'Undo',
 '작업 재실행': 'Redo',
 '되돌릴 수 있는 작업이 있으면 이전 상태로 돌아갑니다.': 'Return to the previous state when an undoable action exists.',
 '되돌린 작업을 다시 적용합니다.': 'Reapply the last undone action.',
 '다시 실행할 내역이 없습니다.': 'There is no action to redo.',
 '작업 캐시 시작': 'Work cache started',
 '작업 폴더 경로가 올바르지 않습니다.': 'The workspace folder path is invalid.',
 '작업 폴더 설정': 'Workspace Folder Settings',
 '작업 폴더 설정 변경 취소': 'Workspace folder settings change canceled',
 '작업 폴더 설정 확인': 'Workspace folder settings confirmed',
 '작업 폴더 설정을 저장하지 못했습니다.': 'Failed to save workspace folder settings.',
 '작업 폴더 설정을 저장했습니다.': 'Workspace folder settings have been saved.',
 '작업 폴더 위치': 'Workspace Folder',
 '작업 폴더 위치 변경': 'Change Workspace Folder',
 '작업 폴더 위치 변경이 예약되었습니다.\n프로그램을 재실행하면 아래 위치로 이동됩니다.': 'Workspace folder change has been scheduled.\n'
                                                     'Restart the program to move it to the location below.',
 '작업 폴더를 설정했습니다.': 'Workspace folder has been set.',
 '작업탭 변경': 'Change Work Tab',
 '재분석': 'Re-analyze',
 '현재 텍스트 마스크를 기준으로 OCR 분석 영역을 다시 만들고, 기존 마스크는 재사용합니다.': 'Rebuilds OCR analysis areas from the current text mask and reuses the existing mask.',
 '선택한 맵마다 현재 텍스트 마스크를 기준으로 OCR 분석 영역을 다시 만들고, 기존 마스크는 재사용합니다.': 'For each selected page, rebuilds OCR analysis areas from the current text mask and reuses the existing mask.',
 '저장': 'Save',
 '내보내기 실패': 'Save Failed',
 '저장 안 함': "Don't Save",
 '내보내기 완료': 'saved',
 '저장 위치': 'Save location',
 '저장된 단어장 캐시를 지울까요?': 'Clear the saved glossary cache?',
 '저장된 작업 폴더 경로를 읽을 수 없습니다.\n작업 폴더 위치를 다시 지정해 주세요.': 'The saved workspace folder path could not be read.\n'
                                                    'Please select the workspace folder again.',
 '저장된 작업 폴더를 찾을 수 없습니다.\n작업 폴더 위치를 다시 지정해 주세요.': 'The saved workspace folder could not be found.\n'
                                                 'Please select the workspace folder again.',
 '저장하지 않은 작업': 'Unsaved Work',
 '저장하지 않은 작업이 있습니다.': 'There are unsaved changes.',
 '저장하지 않은 작업이 있습니다.\n현재 작업 캐시를 프로젝트에 저장하고 자동저장 모드로 전환할까요?': 'There are unsaved changes.\n'
                                                            'Save the current work cache to the project and switch to '
                                                            'Auto Save Mode?',
 '저장할 이미지/프로젝트가 없습니다.': 'There are no images or project data to save.',
 '전체 마스크': 'full mask',
 '전체 분석 시작': 'full analysis started',
 '전체 선택': 'Select All',
 '전체 적용': 'Apply All',
 '전체 체크 상태 자동 갱신': 'All check states auto-refreshed',
 '전체 맵에 적용': 'Apply to All Pages',
 '전체 맵에서': 'Across all pages',
 '정렬': 'Alignment',
 '제거 항목': 'Removed items',
 '제거할 연결 항목이 없었습니다.': 'No association entries were found to remove.',
 '종료 오류': 'Close Error',
 '종료하기 전에 프로젝트를 저장할까요?': 'Save the project before exiting?',
 '지문 추출': 'Extract Text',
'원문/번역문 내보내기': 'Export Source/Translation TXT',
 '지문 추출 TXT를': 'Create text extraction TXT files for',
 '지문 추출 완료': 'Text extraction complete',
'원문/번역문 내보내기 완료': 'Source/translation export complete',
 '지우개': 'Eraser',
 '지울 번역문이 없습니다.': 'There are no translations to clear.',
 '지원 안내': 'Not Supported',
 '찾아보기': 'Browse',
 '처음 실행입니다.\n작업 폴더 위치를 확인해 주세요.': 'First run.\nPlease confirm the workspace folder location.',
 '체크 상태 자동 갱신': 'Check state auto-refreshed',
 '체크 해제된 텍스트': 'unchecked text items',
 '체크된 번역 대상이 없습니다.': 'No checked translation targets.',
 '체크된 항목 없음': 'No checked items',
 '체크한 옵션만 프리셋에 포함됩니다. 이 창의 미리보기는 단일 텍스트 도구입니다.': 'Only checked options are included in the preset. This preview uses a '
                                                 'single text tool.',
 '체크한 옵션만 프리셋에 포함됩니다. 이 창의 미리보기는 닫을 때 원래대로 복구됩니다.': 'Only checked options are included in the preset. This preview is '
                                                    'restored when the window closes.',
 '초기화': 'Reset',
 '총': 'total',
 '최종 브러시 불투명도': 'Final brush opacity',
 '최종 브러시 불투명도 감소': 'Decrease Final Brush Opacity',
 '최종 브러시 불투명도 증가': 'Increase Final Brush Opacity',
 '최종 이미지 저장': 'Final image saved',
 '최종 텍스트 도구': 'Final Text Tool',
 '최종 페인팅 Auto Save': 'Final paint auto-saved',
 '최종 페인팅 색상': 'Final paint color',
 '최종 페인팅 자동 저장': 'Final paint auto-saved',
 '최종 페인팅을 배경에 반영': 'Use Background as Source',
 '최종 페인팅을 원본 탭 기준 이미지로 반영했습니다.': 'Final paint has been applied to the Original tab working source image.',
 '클린본 불러오기': 'Import Clean Background',
 '클린본 이미지 불러오기': 'Import Clean Background Image',
 '선택한 클린본 파일명과 일치하는 페이지를 찾지 못했습니다.': 'No page matched the selected clean background file names.',
 '파일명 매칭': 'filename matching',
 '이미지 파일': 'Image Files',
 '모든 파일': 'All Files',
 '배경을 원본으로 쓰기': 'Use Background as Source',
 '최종결과 배경을 원본 탭의 작업용 기준 이미지로 반영했습니다.': 'Final result background has been applied as the Original tab working source image.',
 '원본으로 쓸 최종결과 배경이 없습니다. 먼저 인페인팅/클린본/최종 페인팅을 준비해 주세요.': 'There is no final-result background to use as the source. Prepare an inpainted image, clean image, or final paint first.',
 '반영할 배경 이미지를 만들 수 없습니다.': 'Could not create a background image to apply.',

 '최종화면 브러시 색상의 알파값을 조절합니다.': 'Adjusts the alpha value of final-screen brush color.',
 '최종화면에서만 사용할 수 있습니다.': 'This can only be used on the final screen.',
 '최종화면을 클릭하면 텍스트 영역을 만듭니다. 내용 작성 후 Ctrl+Return을 누르거나 다른 곳을 클릭하면 작성이 완료됩니다.': 'Click the final screen to create a text '
                                                                             'area. After writing, press Ctrl+Return '
                                                                             'or click elsewhere to finish editing.',
 '추가할 프리셋 이름:': 'Preset name to add:',
 '추출할 내용:': 'Content to extract:',
 '출력': 'Export',
 '취소': 'Canceled',
 '취소됨': 'Canceled',
 '취소선': 'Strikethrough',
 '칠했습니다': 'filled',
 '캐시에만 저장됨': 'Saved in cache only',
 '크기': 'Size',
 '테마 변경': 'Theme changed',
 '테마 설정': 'Theme Settings',
 '텍스트': 'Text',
 '텍스트 Refresh Complete': 'Text refresh complete',
 '텍스트 갱신': 'Text refresh',
 '텍스트 갱신 완료': 'Text refresh complete',
 '텍스트 넘버 크기 변경': 'Change Text Number Size',
 '텍스트 도구': 'Text Tool',
 '텍스트 도구는 최종화면에서만 사용할 수 있습니다.': 'Text Tool can only be used on the final screen.',
 '텍스트 마스크 자동 저장': 'Text mask auto-saved',
 '텍스트 마스크 재분석': 'Text Mask Re-analyze',
 '텍스트 마스크 재분석은 텍스트 마스크 탭에서만 사용할 수 있습니다.': 'Text mask re-analysis is only available in the Text Mask tab.',
 '텍스트 박스가 없어서 번역할 게 없습니다.': 'No text boxes to translate.',
 '텍스트 변형': 'Text Transform',
 '텍스트 변형 모드 OFF': 'Text transform mode OFF',
 '텍스트 변형 모드 ON': 'Text transform mode ON',
 '텍스트 변형 모드 종료': 'Text transform mode ended',
 '텍스트 변형 적용': 'Text transform applied',
 '텍스트 복사 완료': 'Text copy complete',
 '텍스트 붙여넣기': 'Paste Text',
 '텍스트 붙여넣기 완료': 'Paste text complete',
 '텍스트 붙여넣기 위치 지정': 'Set paste text position',
 '텍스트 붙여넣기는 최종화면에서만 사용할 수 있습니다.': 'Paste Text can only be used on the final screen.',
 '텍스트 삭제': 'Delete Text',
 '텍스트 삭제 완료': 'Text deletion complete',
 '텍스트 영역/비율 조정': 'Text area/scale adjustment',
 '텍스트 영역/비율 조정 Undo': 'Text area/scale undo',
 '텍스트 위 페인팅 ON/OFF': 'Paint Above Text ON/OFF',
 '텍스트 위 페인팅 출력 합성 실패': 'Failed to composite paint-above-text output',
 '텍스트 위에 페인팅': 'Paint Above Text',
 '텍스트 이동': 'Text Move',
 '텍스트 이동 적용': 'Text move applied',
 '텍스트 이동됨': 'Text moved',
 '텍스트 정리': 'Clean Text',
 '텍스트 정리 완료': 'Text cleanup complete',
 '텍스트 직접 수정 변화 없음': 'No direct text edit changes',
 '텍스트 직접 수정 완료': 'Direct text edit complete',
 '텍스트 직접 수정 취소': 'Direct text edit canceled',
 '텍스트 직접 편집 시작': 'Direct text edit started',
 '텍스트 표시': 'Show Text',
 '텍스트 표시 ON/OFF': 'Show Text ON/OFF',
 '텍스트 회전': 'Text Rotation',
 '텍스트 회전 각도 지정': 'Text rotation angle set',
 '파란 테두리/핸들을 조작하세요. Alt+드래그로 이동, Ctrl+Enter 또는 배경 클릭으로 종료': 'Use the blue border/handles. Alt+drag to move. Press '
                                                            'Ctrl+Enter or click the background to finish.',
 '파일 없음': 'No files',
 '파일이 필요합니다.': 'file.',
 '페이지': 'Page',
 '페이지 /': 'page(s) /',
 '페이지 글꼴 프리셋 관리': 'Page Font Presets',
 '페이지 글꼴 프리셋 불러오기': 'Load Page Font Preset',
 '페이지 기준으로 생성합니다.': 'page(s).',
 '페이지 이동': 'Go to Page',
 '페이지 적용': 'Apply Page',
 '페이지 프리셋 추가': 'Add Page Preset',
 '페이지라면': 'page requires',
 '페이지에 적용합니다.': 'pages.',
 '페인팅 마스크 ON/OFF': 'Painting Mask ON/OFF',
 '페인팅 마스크 자동 저장': 'Painting mask auto-saved',
 '페인팅 마스크 저장됨': 'Painting mask saved',
 '페인팅 마스크 토글': 'Painting mask toggle',
 '페인팅 마스크 토글: OFF': 'Painting mask toggle: OFF',
 '페인팅 마스크 토글: ON': 'Painting mask toggle: ON',
 '포함/내용': 'Included / Content',
 '폰트': 'Font',
 '표시 언어를 선택하세요.\n확인을 누르면 즉시 적용되고, 닫기를 누르면 변경하지 않습니다.': 'Select the display language.\n'
                                                       'OK applies it immediately. Cancel leaves it unchanged.',
 '프로그램 종료 처리 중 오류가 발생했습니다.\n작업 보호를 위해 종료를 취소합니다.': 'An error occurred while closing the program.\n'
                                                   'Closing has been canceled to protect your work.',
 '프로젝트': 'Project',
 '프로젝트 JSON 열기': 'Open Project JSON',
 '프로젝트 없음': 'No Project',
 '열려고 하는 파일:': 'File to open:',
 '현재 열려있는 프로젝트를 닫고 새 프로젝트를 열까요?\n\n[예] 기존 프로젝트를 닫고 새 프로젝트를 엽니다.\n[아니오] 열기를 취소합니다.': 'Close the currently open project and open the new project?\n\n[Yes] Close the current project and open the new project.\n[No] Cancel opening.',
 '프로젝트 열기': 'Open Project',
 '최종 페인팅 실행 Canceled': 'Final paint action canceled',
 '실행 Canceled': 'Action canceled',
 '실행 Canceled할 내역이 없습니다.': 'There is no action to undo.',
 'Select 해제': 'Selection cleared',
 '프로젝트 열림': 'Project opened',
 '프로젝트 이동 실패': 'Project Move Failed',
 '프로젝트 내보내기': 'Project saved',
 '프로젝트 내보내기 완료': 'Project save complete',
 '프로젝트가 없습니다. 새 프로젝트를 먼저 만들어주세요.': 'No project. Please create a new project first.',
 '프로젝트는 작업 폴더에 저장했지만, YSBG 파일 저장에 실패했습니다.': 'The project was saved to the workspace folder, but saving the YSBG file '
                                            'failed.',
 '프로젝트에 넣을 이미지 선택': 'Select Images for Project',
 '프리셋 JSON을 읽지 못했습니다.': 'Could not read the preset JSON file.',
 '프리셋 삭제': 'Delete Preset',
 '프리셋 이름': 'Preset Name',
 '프리셋 이름:': 'Preset name:',
 '프리셋 저장': 'Save Preset',
 '프리셋에 포함할 옵션': 'Options to include in preset',
 '프리셋을 삭제할까요?': 'Delete this preset?',
 '프리셋이 이미 있습니다. 덮어쓸까요?': 'This preset already exists. Overwrite it?',
 '한 번의 API 요청에 묶어서 보낼 텍스트 줄 수': 'Number of text items sent in one API request',
 '한국어': 'Korean',
 '해당 영역의 마스크도 함께 지워집니다.': 'The mask for that area will also be cleared.',
 '해당 텍스트 영역의 마스크도 함께 지워집니다.': 'The masks for those text areas will also be cleared.',
 '해제 실패': 'Unregistration Failed',
 '해제 완료': 'Unregistration Complete',
 '행 삭제': 'Delete Row',
 '행간': 'Line',
 '허용범위': 'tolerance',
 '현재 .ysbg 확장자가 다른 위치의 쯔꾸르붕이에 연결되어 있습니다.': '.ysbg is currently associated with YSB Game Editor in another location.',
 '현재 단어장': 'Current glossary',
 '현재 등록된 실행 명령': 'Current registered command',
 '현재 마스크': 'current mask',
 '현재 사용자 계정에 .ysbg 확장자 연결을 등록합니다.\n등록 후 .ysbg 파일을 더블클릭하면 쯔꾸르붕이로 열립니다. 계속할까요?': 'Register .ysbg file association for '
                                                                                'the current Windows user account.\n'
                                                                                'After registration, double-clicking a '
                                                                                '.ysbg file opens it with YSB Game Editor. '
                                                                                'Continue?',
 '현재 사용자 계정의 .ysbg 연결을 해제합니다.\n이전 테스트 버전에서 이 프로그램이 등록한 .ysb 연결도 함께 정리합니다.\n다른 프로그램에 연결된 .ysb는 변경하지 않습니다.\n\n계속할까요?': 'This '
                                                                                                                     'will '
                                                                                                                     'unregister '
                                                                                                                     'the '
                                                                                                                     '.ysbg '
                                                                                                                     'association '
                                                                                                                     'for '
                                                                                                                     'the '
                                                                                                                     'current '
                                                                                                                     'Windows '
                                                                                                                     'user '
                                                                                                                     'account.\n'
                                                                                                                     'It '
                                                                                                                     'will '
                                                                                                                     'also '
                                                                                                                     'clean '
                                                                                                                     'up '
                                                                                                                     'any '
                                                                                                                     '.ysb '
                                                                                                                     'association '
                                                                                                                     'registered '
                                                                                                                     'by '
                                                                                                                     'earlier '
                                                                                                                     'test '
                                                                                                                     'versions '
                                                                                                                     'of '
                                                                                                                     'this '
                                                                                                                     'program.\n'
                                                                                                                     '.ysb '
                                                                                                                     'associations '
                                                                                                                     'owned '
                                                                                                                     'by '
                                                                                                                     'other '
                                                                                                                     'programs '
                                                                                                                     'will '
                                                                                                                     'not '
                                                                                                                     'be '
                                                                                                                     'changed.\n'
                                                                                                                     '\n'
                                                                                                                     'Continue?',
 '현재 설정을 새 개별 프리셋으로 추가': 'Add Current Settings as New Item Preset',
 '현재 스타일을 새 프리셋으로 추가': 'Add Current Style as New Preset',
 '현재 실행 중인 프로그램으로 연결을 갱신할까요?': 'Refresh the association to the currently running program?',
 '현재 일괄 작업이 진행 중입니다.': 'A batch job is currently running.',
 '현재 탭에 마스크 레이어가 없습니다.': 'There is no mask layer in the current tab.',
 '현재 페이지': 'current page',
 '현재 페이지 텍스트 번호와 맞는 번역문을 찾지 못했습니다.': 'Could not find translations matching the current page text IDs.',
 '현재 페이지에 적용': 'Apply to Current Page',
 '현재 프로젝트를 닫기 전에 저장할까요?': 'Save before closing the current project?',
 '화면 구성 마무리 중...': 'Finishing interface setup...',
 '화면에 적용할 테마를 선택하세요.\n확인을 누르면 즉시 적용되고, 닫기를 누르면 변경하지 않습니다.': 'Select the theme to apply.\n'
                                                            'OK applies it immediately. Cancel leaves it unchanged.',
 '화이트 테마': 'Light Theme',
 '확인': 'OK',
 '확장 범위': 'Expand Range',
 '확장자 연결 해제': 'Unregister File Association',
 '확장자 연결 해제는 Windows에서만 지원합니다.': 'File association unregistering is only supported on Windows.',
 '확장자 연결 해제를 완료했습니다.': 'File association has been unregistered.',
 '확장자 연결 해제에 실패했습니다.': 'Failed to unregister file association.',
 '환경 준비 중...': 'Preparing environment...',
 '회색': 'Gray',
 '회전 각도(도):': 'Rotation angle (degrees):',
 '획': 'Stroke',
 '획 색상': 'Stroke Color',
 '획색': 'Stroke Color',
 '🌐 번역': '🌐 Translate',
 '🎨 인페인팅': '🎨 Inpaint',
 '📤 결과물 출력': '📤 Export Result',
 '🔄 재분석': '🔄 Re-analyze',
 '🧹 텍스트 정리': '🧹 Clean Text'}



# v1.8.0 launcher/start screen strings
UI_KO_EN.update({
    '시작 화면': 'Start Screen',
    '최근 프로젝트': 'Recent Projects',
    '새로 만들기': 'New',
    'JSON으로 열기': 'Open as JSON',
    '내보내기': 'Save',
    '다른 이름으로 내보내기': 'Save As',
    '복구하기': 'Recover',
    '홈화면으로 가기': 'Go to Home Screen',
    '새 프로젝트 만들기': 'New Project',
    '프로젝트 열기': 'Open Project',
    '마지막 작업 복구': 'Recover Last Work',
    '옵션 / 설정': 'Options / Settings',
    '도움말 / 매뉴얼': 'Help / Manual',
    '프로젝트는 YSBG로 보존하고, 작업환경은 설정 캐시로 이어갑니다.': 'Projects are preserved as YSBG files, and your work environment continues through settings cache.',
    '최근 프로젝트는 로컬 경로를 기본 화면에 직접 노출하지 않습니다.': 'Local paths are not shown directly on the main recent-project screen.',
    '아직 최근 프로젝트가 없습니다. 왼쪽에서 새 프로젝트를 만들거나 기존 YSBG를 열어주세요.': 'No recent projects yet. Create a new project or open an existing YSBG from the left.',
    '썸네일 없음': 'No Thumbnail',
    '제목 없음': 'Untitled',
    '마지막 열기': 'Last opened',
    '페이지': ' pages',
    '로컬 있음': 'Local file available',
    '파일을 찾을 수 없음': 'File not found',
    '열기': 'Open',
    '폴더 위치 열기': 'Open Folder Location',
    '최근 목록에서 제거': 'Remove from Recent List',
    '준비 중': 'Coming Soon',
    '런처 화면에서는 새 프로젝트, 프로젝트 열기, 마지막 작업 복구, 최근 프로젝트 열기를 바로 사용할 수 있습니다.': 'From the launcher, you can create a new project, open a project, recover the last work, or reopen recent projects directly.',
    '폴더 열기 실패': 'Failed to Open Folder',
})



# v1.8.0 launcher/settings overview strings
UI_KO_EN.update({
    '설정': 'Settings',
    '설정 / 옵션': 'Settings / Options',
    '작업 폴더 위치': 'Workspace Folder Location',
    'YSBG 파일 연결': 'YSBG File Association',
    '설정은 프로그램 환경, 옵션은 작업 기능 관리 항목입니다. 자주 쓰는 설정은 이 창에서 바로 바꾸고, 복잡한 항목은 관리 버튼으로 엽니다.': 'Settings are program environment items, while options manage work features. Frequently used settings can be changed here, and complex items open their dedicated management windows.',
    '프로그램의 기본 동작, 표시 방식, 작업 폴더, 임시 파일, YSBG 연결처럼 환경에 가까운 항목입니다.': 'Environment-level items such as basic behavior, display, workspace folder, temporary files, and YSBG association.',
    'API, 프롬프트, 단어장, 단축키, 매크로, 프리셋처럼 작업 기능을 관리하는 항목입니다. 복잡한 항목은 기존 전용 창으로 엽니다.': 'Work-feature items such as APIs, prompts, glossary, shortcuts, macros, and presets. Complex items open their existing dedicated windows.',
    'ON이면 변경 사항이 실제 프로젝트에 바로 저장되고, OFF이면 작업 캐시에만 저장됩니다.': 'When ON, changes are saved directly to the real project. When OFF, changes are saved only to the work cache.',
    '창과 작업 화면의 밝기 테마를 바꿉니다.': 'Changes the brightness theme of the window and work area.',
    '사용자 인터페이스 표시 언어를 바꿉니다.': 'Changes the user interface display language.',
    '프로젝트 작업 폴더와 캐시가 저장되는 기준 위치입니다.': 'The base location where project work folders and caches are saved.',
    '임시 작업 폴더 자동 삭제 주기를 정하고, 필요하면 즉시 삭제합니다.': 'Sets the auto-delete interval for temporary work folders and can delete them immediately if needed.',
    '.ysbg 파일을 더블클릭했을 때 쯔꾸르붕이로 바로 열리게 합니다.': 'Allows .ysbg files to open directly in YSB Game Editor when double-clicked.',
    '.ysbg 확장자 연결 해제': 'Unregister .ysbg Association',
})



# v2.0.1 추가 메뉴/작업 문구 번역 보강
UI_KO_EN.update({
    '맵 탭 표시명 설정': 'Page Tab Display Name Settings',
    '출력 표시명 설정': 'Output Display Name Settings',
    '출력물 삭제': 'Delete Outputs',
    '전체 이미지탭 삭제': 'Delete All Image Tabs',
    '현재 맵 이름 보기': 'Show Current Map Name',
    '맵 탭 파일명 변경': 'Rename Page Tab File Name',
    '현재 페이지 원본 파일명 변경': 'Rename Current Page Source File',
    '현재 이미지탭 삭제': 'Delete Current Image Tab',
    '현재 텍스트 기준 영역 재설정': 'Reset Current Text Reference Area',
    '일괄 텍스트 기준 영역 재설정': 'Batch Reset Text Reference Area',
    '번역 내용 지우기 완료': 'Translation cleared',
    '일괄 번역문 내용 지우기 완료': 'Batch translations cleared',
    '출력물 삭제 확인': 'Confirm Delete Outputs',
    '선택한 출력물을 삭제할까요?': 'Delete the selected outputs?',
    '삭제할 출력물이 없습니다.': 'There are no outputs to delete.',
    '먼저 프로젝트를 열어주세요.': 'Please open a project first.',
    '일부 파일을 삭제하지 못했습니다.': 'Some files could not be deleted.',
    '최종결과 이미지': 'Final Result Images',
    '포토샵 스크립트': 'Photoshop Scripts',
    'TXT 지문': 'TXT Text Extracts',
})

# Reverse lookup table for restoring simple fixed UI strings when switching back to Korean.
# Values are generated from UI_KO_EN after the table is fully declared.
UI_EN_KO = {en: ko for ko, en in UI_KO_EN.items()}


UI_KO_EN.update({
    "고급...": "Advanced...",
    "고급 옵션": "Advanced Options",
    "고급 텍스트/획 옵션": "Advanced Text/Stroke Options",
    "선택한 텍스트 라인에 고급 텍스트/획 옵션을 적용합니다. 기울임은 우클릭 메뉴의 텍스트 기울이기 조정에서 직접 조정합니다.": "Apply fill/stroke gradients to the selected text lines. Adjust skew directly from the text skew context-menu mode.",
    "문자 그라데이션": "Fill Gradient",
    "획 그라데이션": "Stroke Gradient",
    "선택한 텍스트 라인에 문자/획 그라데이션과 2중 획을 적용합니다. 평행사변형/사다리꼴/부채꼴 변형은 우클릭 메뉴에서 직접 조정합니다.": "Apply fill/stroke gradients and a second outline to the selected text lines. Adjust parallelogram/trapezoid/fan transforms directly from the context menu.",
    "2중 획": "Second Outline",
    "문자 그림자": "Text Shadow",
    "문자 후광": "Text Glow",
    "텍스트": "Text",
    "획": "Stroke",
    "효과": "Effects",
    "인터페이스 툴팁 표시": "Show Interface Tooltips",
    "버튼, 메뉴, 툴바에 뜨는 설명용 툴팁을 표시합니다. 스포이드 색상 표시 같은 작업용 안내는 이 설정과 별개로 유지됩니다.": "Show helper tooltips for buttons, menus, and toolbars. Working hints such as the eyedropper color popup remain separate from this setting.",
    "불투명도": "Opacity",
    "X 이동": "X Offset",
    "Y 이동": "Y Offset",
    "흐림": "Blur",
    "두께": "Width",
    "사용": "Use",
    "색 1": "Color 1",
    "색 2": "Color 2",
    "색상": "Colors",
    "각도": "Angle",
    "비율": "Ratio",
    "텍스트 기울이기": "Text Skew",
    "가로 기울임": "Horizontal skew",
    "세로 기울임": "Vertical skew",
    "적용": "Apply",
    "닫기": "Close",
    "고급 텍스트/획 옵션...": "Advanced Text/Stroke Options...",
    "텍스트 기울이기 조정": "Adjust Text Skew",

    "선택한 텍스트 라인에 고급 텍스트/획 옵션을 적용합니다. 평행사변형 변형/사다리꼴 변형/부채꼴 변형은 우클릭 메뉴에서 직접 조정합니다.": "Apply advanced text/stroke options to the selected text lines. Adjust parallelogram/trapezoid/fan transforms directly from the context menu.",
    "평행사변형 변형": "Parallelogram Transform",
    "사다리꼴 변형": "Trapezoid Transform",
    "부채꼴 변형": "Fan Transform",
    "현재 페이지 범위지정 해제": "Clear Current Page Region",
    "현재 보고 있는 페이지만 OCR 분석 영역을 지우고, 다른 페이지의 영역은 유지합니다.": "Clear OCR analysis regions only on the current page and keep other pages unchanged.",
    "현재 페이지만 해제": "Clear Current Page",
    "전체 범위지정 해제": "Clear All Regions",
    "저장된 OCR 분석 영역을 모든 페이지에서 지우고, 다시 전체 화면 분석 상태로 되돌립니다.": "Clear saved OCR analysis regions on all pages and return to full-page OCR analysis.",
    "전체 해제": "Clear All",
    "현재 페이지의 OCR 분석 영역만 지울까요?\n\n다른 페이지의 OCR 분석 영역은 유지됩니다.": "Clear OCR analysis regions only on the current page?\n\nOCR analysis regions on other pages will be kept.",
    "현재 페이지 OCR 분석 범위 해제": "Clear Current Page OCR Analysis Region",
    "텍스트를 객체로 변환": "Convert Text to Object",
    "원위치 붙여넣기": "Paste at Same Position",
    "객체 일부 지우기": "Erase Part of Object",
    "객체로 변환된 텍스트는 내용을 직접 수정할 수 없습니다.": "Converted text objects cannot be edited as text.",
    "일부 지우기는 객체로 변환된 텍스트에서만 사용할 수 있습니다.": "Partial erase can only be used on converted text objects.",
    "객체 일부 지우기는 최종화면에서만 사용할 수 있습니다.": "Object partial erase is only available on the final result view.",
    "텍스트 객체 일부 지우기": "Erase Text Object",
    "도구: 텍스트 객체 일부 지우기": "Tool: Erase text object",
    "효과를 적용할 편집 가능한 텍스트가 없습니다.": "There is no editable text to apply effects to.",
    "객체로 변환할 일반 텍스트가 없습니다.": "There is no normal text to convert to objects.",
})

API_TR_KO_EN = {'API 관리': 'API Settings',
 'LOCAL Paddle OCR': 'LOCAL Paddle OCR',
 'Local판 전용 테스트 모드입니다. 현재 단계에서는 PaddleOCR 문자 인식까지 가지 않고 comic_text_detector로 텍스트 마스크 생성까지만 실행합니다.': 'Local edition test mode. At this stage it does not run PaddleOCR text recognition; it only runs comic_text_detector text-mask generation.',
 'Local판 전용 테스트 모드입니다. 현재 단계에서는 PaddleOCR 문자 인식까지 가지 않고 comic_text_detector의 block/line 후보로 안전 마스크만 생성합니다. raw mask는 직접 사용하지 않습니다.': 'Local edition test mode. At this stage it does not run PaddleOCR text recognition; it only creates a safe mask from comic_text_detector block/line candidates. The raw mask is not used directly.',
 '자동': 'Auto',
 'API 정보는 사용자 설정 캐시 파일에 저장됩니다.\nOCR / 인페인팅 / 번역 API는 분류별로 하나씩 선택해 사용합니다.\n캐시 위치: ': 'API settings are saved to the '
                                                                                    'user settings cache file.\n'
                                                                                    'Select one provider for each '
                                                                                    'category: OCR / Inpainting / '
                                                                                    'Translation.\n'
                                                                                    'Cache path: ',
 'Custom / OpenAI-Compatible': 'Custom / OpenAI-Compatible',
 'JSON 파일 선택': 'Select JSON File',
 'OpenAI Chat Completions 호환 API만 사용할 수 있습니다. Base URL, Model, API Key를 입력하세요.': 'Only OpenAI Chat Completions '
                                                                                 'compatible APIs are supported. Enter '
                                                                                 'Base URL, Model, and API Key.',
 'OpenAI Chat Completions 호환 API만 사용할 수 있습니다. Base URL, Model, API Key를 입력하세요.\n호환 예시: OpenRouter, Groq, xAI Grok, Together, LM Studio, vLLM, Ollama OpenAI 호환 서버': 'Only '
                                                                                                                                                                    'OpenAI '
                                                                                                                                                                    'Chat '
                                                                                                                                                                    'Completions '
                                                                                                                                                                    'compatible '
                                                                                                                                                                    'APIs '
                                                                                                                                                                    'are '
                                                                                                                                                                    'supported. '
                                                                                                                                                                    'Enter '
                                                                                                                                                                    'Base '
                                                                                                                                                                    'URL, '
                                                                                                                                                                    'Model, '
                                                                                                                                                                    'and '
                                                                                                                                                                    'API '
                                                                                                                                                                    'Key.\n'
                                                                                                                                                                    'Compatible '
                                                                                                                                                                    'examples: '
                                                                                                                                                                    'OpenRouter, '
                                                                                                                                                                    'Groq, '
                                                                                                                                                                    'xAI '
                                                                                                                                                                    'Grok, '
                                                                                                                                                                    'Together, '
                                                                                                                                                                    'LM '
                                                                                                                                                                    'Studio, '
                                                                                                                                                                    'vLLM, '
                                                                                                                                                                    'Ollama '
                                                                                                                                                                    'OpenAI-compatible '
                                                                                                                                                                    'servers',
 '닫기': 'Cancel',
 '번역 API': 'Translation API',
 '이': 'this',
 '인페인팅 API': 'Inpainting API',
 '입력칸 비우기': 'Clear Fields',
 '입력칸을 전부 비울까요?': 'Clear all input fields?',
 '제공자를 사용합니다.': 'provider will be used.',
 '찾아보기': 'Browse',
 '대기 시간(초)': 'Wait (sec)',
 '키 보이기': 'Show Keys',
 '호환 예시: OpenRouter, Groq, xAI Grok, Together, LM Studio, vLLM, Ollama OpenAI 호환 서버': 'Compatible examples: '
                                                                                      'OpenRouter, Groq, xAI Grok, '
                                                                                      'Together, LM Studio, vLLM, '
                                                                                      'Ollama OpenAI-compatible '
                                                                                      'servers',
 '확인': 'OK'}

API_TR_KO_EN.update({
    "OCR / 인페인팅 / 번역 API를 분류별로 선택하고, 외부 API 주소·키·모델명을 관리합니다.\n확인을 누르면 사용자 설정 캐시에 저장되고, 닫기를 누르면 저장하지 않습니다.": "Select OCR / inpainting / translation APIs by category, and manage external API URLs, keys, and model names.\nOK saves them to the user settings cache. Cancel closes without saving.",
    "캐시 위치: ": "Cache path: ",
    "이미지의 글자를 읽어올 OCR 제공자를 선택합니다. 선택한 제공자 한 개만 분석 작업에 사용됩니다.": "Choose the OCR provider used to read text from images. Only the selected provider is used for analysis.",
    "마스크 영역의 배경을 복원할 인페인팅 제공자를 선택합니다. 선택한 제공자 한 개만 인페인팅 작업에 사용됩니다.": "Choose the inpainting provider used to restore the background inside mask areas. Only the selected provider is used for inpainting.",
    "AI 번역에 사용할 번역 제공자를 선택합니다. 선택한 제공자 한 개만 번역 작업에 사용됩니다.": "Choose the translation provider used for AI translation. Only the selected provider is used for translation.",
    "Model": "Model",
    "Invoke URL": "Invoke URL",
    "Secret Key": "Secret Key",
    "Model / Mode": "Model / Mode",
    "API Key": "API Key",
    "Language Hints": "Language Hints",
    "Prompt": "Prompt",
    "API Token": "API Token",
    "Preset Name": "Preset Name",
    "Base URL": "Base URL",
})

SHORTCUT_TR_KO_EN = {'.ysbg 확장자 연결 등록': 'Register .ysbg Association',
 '설정 / 옵션': 'Settings / Options',
 '설정': 'Settings',
 '.ysbg 확장자 연결 해제': 'Unregister .ysbg Association',
 'API 관리': 'API Settings',
 'JSON 파일로 열기': 'Open JSON Project',
 '가로장음(―)': 'Horizontal Dash (―)',
 '가운데 정렬': 'Align Center',
 '가운뎃점(·)': 'Middle Dot (·)',
 '개별 글꼴 프리셋 관리': 'Item Font Presets',
 '개별 번역': 'Translate Current',
 '개별 번역문 불러오기': 'Import Translation Current',
 '개별 분석': 'Analyze Current',
 '개별 인페인팅': 'Inpaint Current',
 '개별 지문 추출': 'Extract Text Current',
 '개별 출력': 'Export Current',
 '개별 텍스트 작업 옵션': 'Item Text',
 '개별 텍스트 정리': 'Clean Text Current',
 '검은 동그라미(●)': 'Black Circle (●)',
 '검은하트(♥)': 'Black Heart (♥)',
 '겹낫표(『』)': 'Double Corner Brackets (『』)',
 '그림판 옵션': 'Canvas Tools',
 '글꼴 선택': 'Select Font',
 '글꼴 축소': 'Decrease Font Size',
 '글꼴 확대': 'Increase Font Size',
 '기능': 'Functions',
 '기능 없음': 'No Functions',
 '기능 추가': 'Add Function',
 '기능은 더블클릭하거나 검색창/목록에 포커스를 둔 상태에서 실제 단축키를 눌러 추가합니다. Enter는 기능 추가가 아니라 확인으로 동작합니다. 확인을 누르면 현재 매크로 기능 목록을 저장하고, 닫기를 누르면 저장하지 않고 나갑니다. 단축키 OFF/없음은 단축키 상태 표시일 뿐, 매크로 실행에는 영향 없습니다.': 'Double-click a function or press the actual shortcut while the search box/list has focus to add it. Press OK to save the current macro function list, or Close to leave without saving. Shortcut OFF/none is only a shortcut status; it does not affect macro execution.',
 '기능 선택': 'Select Function',
 '기능명 / 그룹 / 단축키 검색  예: 자동 줄 내림, Ctrl+B': 'Search function / group / shortcut  e.g. Auto Line Break, Ctrl+B',
 '기능을 더블클릭하거나, 선택 후 [기능 추가]를 누르면 창을 닫지 않고 계속 추가됩니다. 검색창/목록에 포커스를 둔 상태에서 실제 단축키를 누르면 즉시 추가됩니다. 단축키 OFF/없음은 단축키 상태 표시일 뿐, 매크로 실행에는 영향 없습니다.': 'Double-click '
                                                                                                                                            'a '
                                                                                                                                            'function, '
                                                                                                                                            'or '
                                                                                                                                            'select '
                                                                                                                                            'one '
                                                                                                                                            'and '
                                                                                                                                            'press '
                                                                                                                                            '[Add '
                                                                                                                                            'Function] '
                                                                                                                                            'to '
                                                                                                                                            'keep '
                                                                                                                                            'adding '
                                                                                                                                            'without '
                                                                                                                                            'closing '
                                                                                                                                            'the '
                                                                                                                                            'window. '
                                                                                                                                            'If '
                                                                                                                                            'the '
                                                                                                                                            'search '
                                                                                                                                            'box/list '
                                                                                                                                            'has '
                                                                                                                                            'focus, '
                                                                                                                                            'pressing '
                                                                                                                                            'an '
                                                                                                                                            'actual '
                                                                                                                                            'shortcut '
                                                                                                                                            'adds '
                                                                                                                                            'it '
                                                                                                                                            'immediately. '
                                                                                                                                            'Shortcut '
                                                                                                                                            'OFF/None '
                                                                                                                                            'only '
                                                                                                                                            'indicates '
                                                                                                                                            'shortcut '
                                                                                                                                            'status '
                                                                                                                                            'and '
                                                                                                                                            'does '
                                                                                                                                            'not '
                                                                                                                                            'affect '
                                                                                                                                            'macro '
                                                                                                                                            'execution.',
 '기본값 복구': 'Restore Defaults',
 '기울이기': 'Italic',
 '기존 단축키 비활성화 확인': 'Disable Existing Shortcut',
 '다른 이름으로 내보내기': 'Save As',
 '다음 맵': 'Next Map',
 '단어장': 'Glossary',
 '단축키': 'Shortcut',
 '단축키 OFF': 'Shortcut OFF',
 '단축키 ON': 'Shortcut ON',
 '단축키 교체 확인': 'Swap Shortcut',
 '단축키 없음': 'No Shortcut',
 '단축키 통합 관리': 'Shortcut Manager',
 '단축키는 프로그램 폴더의 캐시 파일에 저장됩니다.\n같은 단축키를 지정하면 기존 항목과 서로 교체됩니다.\n체크를 끄면 해당 단축키는 사용하지 않으며 입력칸이 비워집니다.\n캐시 위치: ': 'Shortcuts '
                                                                                                             'are '
                                                                                                             'saved to '
                                                                                                             'the '
                                                                                                             'program '
                                                                                                             'cache '
                                                                                                             'file.\n'
                                                                                                             'If you '
                                                                                                             'assign '
                                                                                                             'the same '
                                                                                                             'shortcut, '
                                                                                                             'it will '
                                                                                                             'be '
                                                                                                             'swapped '
                                                                                                             'with the '
                                                                                                             'existing '
                                                                                                             'item.\n'
                                                                                                             'If you '
                                                                                                             'uncheck '
                                                                                                             'an item, '
                                                                                                             'that '
                                                                                                             'shortcut '
                                                                                                             'will be '
                                                                                                             'disabled '
                                                                                                             'and the '
                                                                                                             'input '
                                                                                                             'box will '
                                                                                                             'be '
                                                                                                             'cleared.\n'
                                                                                                             'Cache '
                                                                                                             'path: ',
 '단축키를 전부 기본값으로 돌릴까요?': 'Restore all shortcuts to their defaults?',
 '닫기': 'Close',
 '마스킹 칠하기': 'Fill Mask',
 '말줄임표(…)': 'Ellipsis (…)',
 '매크로 관리': 'Macro Manager',
 '매크로 기능 선택': 'Select Macro Function',
 '매크로 단축키 비활성화 확인': 'Disable Macro Shortcut',
 '매크로 단축키 중복': 'Duplicate Macro Shortcut',
 '매크로 삭제': 'Delete Macro',
 '매크로 이름': 'Macro Name',
 '매크로 이름:': 'Macro name:',
 '매크로 추가': 'Add Macro',
 '매크로는 여러 기능을 추가한 순서대로 연속 실행합니다.\n매크로 단축키가 기존 단축키와 겹치면, 확인 후 기존 단축키를 비활성화합니다.': 'Macros run multiple functions in the '
                                                                                'order they were added.\n'
                                                                                'If a macro shortcut overlaps with an '
                                                                                'existing shortcut, the existing '
                                                                                'shortcut can be disabled after '
                                                                                'confirmation.',
 '매크로를 삭제할까요?': 'Delete this macro?',
 '문자 색상 팔레트': 'Text Color Palette',
 '번역 프롬프트 입력': 'Translation Prompt',
 '번역문 내용 지우기': 'Clear Translation Current',
 '브러시': 'Brush',
 '비어 있음': 'Empty',
 '사용': 'Use',
 '삭제': 'Delete',
 '새 매크로': 'New Macro',
 '새 프로젝트': 'New Project',
 '서로 교체해서 사용할까요?': 'Swap these shortcuts?',
 '세로장음(│)': 'Vertical Dash (│)',
 '아직 추가된 기능이 없습니다.': 'No functions have been added yet.',
 '언어 설정': 'Language Settings',
 '오른쪽 정렬': 'Align Right',
 '옵션': 'Options',
 '왼쪽 정렬': 'Align Left',
 '요술봉 선택': 'Magic Wand Select',
 '요술봉 영역 확장': 'Expand Magic Wand Area',
 '요술봉 허용범위 감소': 'Decrease Magic Wand Tolerance',
 '요술봉 허용범위 증가': 'Increase Magic Wand Tolerance',
 '요술봉 확장범위 감소': 'Decrease Magic Wand Expansion',
 '요술봉 확장범위 증가': 'Increase Magic Wand Expansion',
 '원본으로 돌아가기': 'Restore Original Source',
 '음표(♪)': 'Music Note (♪)',
 '이동': 'Move',
 '이름': 'Name',
 '이미 사용 중인 단축키입니다.': 'This shortcut is already in use.',
 '이전 맵': 'Previous Map',
 '인페인팅을 원본으로': 'Use Background as Source',
 '일괄 번역': 'Batch Translate',
 '일괄 번역문 내용 지우기': 'Batch Clear Translation',
 '일괄 번역문 불러오기': 'Batch Import Translation',
 '일괄 분석': 'Batch Analyze',
    '일괄 재분석': 'Batch Re-analyze',
 '일괄 인페인팅': 'Batch Inpaint',
 '일괄 자동 줄 내림': 'Batch Auto Line Break',
 '일괄 자동 텍스트 크기 조정': 'Batch Auto Text Size',
 '일괄 작업 옵션': 'Batch Work',
 '일괄 지문 추출': 'Batch Extract Text',
'일괄 원문/번역문 내보내기': 'Batch Export Source/Translation TXT',
 '일괄 출력': 'Batch Export',
 '일괄 텍스트 정리': 'Batch Clean Text',
 '자동 줄 내림': 'Auto Line Break',
 '자동 텍스트 크기 조정': 'Auto Text Size',
 '자동저장 모드': 'Auto Save Mode',
 '자동화 작업 옵션': 'Automation',
 '작업 옵션': 'Work',
 '작업 취소': 'Undo',
 '작업 재실행': 'Redo',
 '되돌릴 수 있는 작업이 있으면 이전 상태로 돌아갑니다.': 'Return to the previous state when an undoable action exists.',
 '되돌린 작업을 다시 적용합니다.': 'Reapply the last undone action.',
 '다시 실행할 내역이 없습니다.': 'There is no action to redo.',
 '작업 폴더 위치 변경': 'Change Workspace Folder',
 '작업탭 변경': 'Change Work Tab',
 '재분석': 'Re-analyze',
 '정확히 일치하는 단축키가 없습니다. 기능명 검색 후 항목을 더블클릭하거나 실제 단축키를 눌러주세요.': 'No exact shortcut match was found. Search by function name, then double-click an item or press the actual shortcut.',
 '줄내림': 'Line Break',
 '지우개': 'Eraser',
 '최종 브러시 불투명도 감소': 'Decrease Final Brush Opacity',
 '최종 브러시 불투명도 증가': 'Increase Final Brush Opacity',
 '최종 텍스트 도구': 'Final Text Tool',
 '최종 페인팅 색상': 'Final Paint Color',
 '최종 페인팅을 배경에 반영': 'Use Background as Source',
 '추가할 기능을 선택해주세요.': 'Please select a function to add.',
 '축소': 'Zoom Out',
 '클릭하면 이 기능을 매크로에서 제거합니다.': 'Click to remove this function from the macro.',
 '테마 설정': 'Theme Settings',
 '텍스트 넘버 크기 변경': 'Change Text Number Size',
 '텍스트 위 페인팅 ON/OFF': 'Paint Above Text ON/OFF',
 '텍스트 입력 옵션': 'Text Input',
 '텍스트 표시 ON/OFF': 'Show Text ON/OFF',
 '페이지 글꼴 프리셋 관리': 'Page Font Presets',
 '페인팅 마스크 ON/OFF': 'Painting Mask ON/OFF',
 '프로젝트 열기': 'Open Project',
 '시작 화면': 'Start Screen',
 '프로젝트 옵션': 'Project',
 '프로젝트 내보내기': 'Save Project',
 '하얀하트(♡)': 'White Heart (♡)',
 '현재 매크로 기능': 'Current Macro Functions',
 '홑낫표(「」)': 'Single Corner Brackets (「」)',
 '확대': 'Zoom In',
 '획 색상 팔레트': 'Stroke Color Palette',
 '획 축소': 'Decrease Stroke',
 '획 확대': 'Increase Stroke',
 '확인(Y)': 'Confirm (Y)',
 '취소(N)': 'Cancel (N)',
 'Enter 또는 Y 키로 확인합니다.': 'Press Enter or Y to confirm.',
 'N 키로 취소합니다.': 'Press N to cancel.',
 '개별 프리셋 단축키 비활성화 확인': 'Disable Individual Preset Shortcut?',
 '개별 글꼴 프리셋 단축키 변경': 'Change Individual Font Preset Shortcut',
 '마지막 작업 복구': 'Recover Last Work',
 '임시 파일 삭제': 'Delete Temporary Files',
 '복구할 작업 없음': 'No Recoverable Work',
 '복구할 수 있는 임시 작업 파일을 찾지 못했습니다.': 'No recoverable temporary work files were found.',
 '마지막 작업 폴더를 복구할까요?': 'Recover the last work folder?',
 '복구한 작업은 아직 정식 YSBG 파일이 아닐 수 있습니다. 필요한 경우 [프로젝트 내보내기]으로 다시 저장해 주세요.': 'The recovered work may not be a finalized YSBG file yet. Use [Save Project] to save it again if needed.',
 '마지막 작업을 복구하지 못했습니다.': 'Could not recover the last work.',
 '복구 실패': 'Recovery Failed',
 '임시 파일 삭제 완료': 'Temporary Files Deleted',
 '삭제할 임시 파일 없음': 'No Temporary Files to Delete',
 '삭제할 수 있는 임시 작업 파일이 없습니다.': 'There are no temporary work files that can be deleted.',
 '현재 열려 있는 작업을 제외한 임시 작업 폴더를 삭제합니다.': 'Temporary work folders except the currently open work will be deleted.',
 '대상 폴더 수': 'Target folders',
 '예상 용량': 'Estimated size',
 '삭제 후에는 해당 임시 작업을 복구할 수 없습니다. 계속할까요?': 'After deletion, those temporary works cannot be recovered. Continue?',
 '임시 파일 삭제가 완료되었습니다.': 'Temporary file deletion is complete.',
 '자동 임시 파일 정리': 'Automatic Temporary File Cleanup',
 '자동 임시 파일 정리: 오래된 임시 파일 없음': 'Auto temp cleanup: no old temporary files.',
 '오래된 임시 작업 폴더는 한 달에 한 번 자동으로 정리됩니다.': 'Old temporary work folders are cleaned automatically once a month.',
 '임시 파일 관리': 'Temporary File Management',
 '임시파일 삭제': 'Delete Temporary Files',
 '임시파일 자동삭제': 'Auto-delete Temporary Files',
 '임시 파일 삭제와 자동 삭제 주기를 설정합니다.': 'Delete temporary files and configure the auto-delete period.',
 '자동 삭제는 선택한 기간마다 실행되며, 선택한 기간 이상 지난 임시 작업 폴더만 삭제합니다.': 'Auto-delete runs at the selected period and only deletes temporary work folders older than the selected period.',
 '한달': '1 Month',
 '3개월': '3 Months',
 '6개월': '6 Months',
 '12개월': '12 Months',
 '자동 임시 파일 정리: 꺼짐': 'Auto temp cleanup is disabled.',
 '일주일': '1 Week',
 '임시 프로젝트': 'Temporary Projects',
 '작업 캐시': 'Work Sessions',
 '총합': 'Total',
 '임시 파일 상태를 읽지 못했습니다.': 'Could not read temporary file status.'}

# v1.8.0 hotfix3 settings/options overview strings
UI_KO_EN.update({
    '확인을 누르면 이 창에서 바꾼 설정이 저장됩니다. 닫기나 X를 누르면 이 창에서 바꾼 설정은 저장하지 않습니다. 복잡한 항목은 오른쪽 버튼으로 전용 관리창을 엽니다.': 'Click OK to save the settings changed in this window. Click Close or X to leave without saving changes made in this window. Complex items open their dedicated management windows from the button on the right.',
    '프로그램의 기본 동작과 작업 환경을 정하는 항목입니다. 여기서 직접 바꾼 값은 확인을 눌러야 저장됩니다.': 'Items that define the program behavior and work environment. Values changed directly here are saved only when you click OK.',
    'ON이면 변경 사항을 실제 프로젝트에 바로 저장합니다. OFF이면 임시 작업 캐시에 먼저 저장하고, 프로젝트 내보내기 시 확정합니다.': 'When ON, changes are saved directly to the real project. When OFF, changes are saved to the temporary work cache first and finalized when the project is saved.',
    '프로그램 전체의 밝기 테마를 정합니다. 확인을 누르면 선택한 테마가 적용됩니다.': 'Sets the brightness theme for the whole program. The selected theme is applied when you click OK.',
    '메뉴와 안내 문구의 표시 언어를 정합니다. 확인을 누르면 선택한 언어가 적용됩니다.': 'Sets the display language for menus and guidance text. The selected language is applied when you click OK.',
    '프로젝트 작업 폴더와 캐시가 저장되는 기준 위치입니다. 변경은 전용 작업 폴더 설정창에서 확인을 눌러야 적용됩니다.': 'The base location where project work folders and caches are stored. Changes are applied only when you click OK in the dedicated workspace folder dialog.',
    '위치 변경': 'Change Location',
    '자동삭제': 'Auto Delete',
    '오래된 임시 작업 폴더를 자동으로 정리할지 정합니다. 즉시 삭제는 별도 확인 후 바로 실행됩니다.': 'Sets whether old temporary work folders are cleaned automatically. Immediate cleanup runs after a separate confirmation.',
    '지금 정리': 'Clean Now',
    'YSBG 파일 연결 등록': 'Register YSBG File Association',
    'YSBG 파일 연결 해제': 'Unregister YSBG File Association',
    '.ysbg 파일을 더블클릭했을 때 현재 쯔꾸르붕이로 바로 열리게 Windows 연결을 등록합니다.': 'Registers the Windows association so .ysbg files open directly with the current YSB Game Editor when double-clicked.',
    '현재 사용자 계정의 .ysbg 연결을 해제합니다. 이전 테스트용 .ysb 연결도 함께 정리합니다.': 'Unregisters the .ysbg association for the current user account and also cleans up the older test .ysb association.',
    '등록': 'Register',
    '해제': 'Unregister',
    '작업 기능을 관리하는 항목입니다. 이 창 안에 전부 펼치면 복잡해지므로, 각 항목의 버튼으로 기존 전용 관리창을 엽니다.': 'Items that manage work features. To avoid making this window too complex, each item opens its existing dedicated management window from its button.',
    'OpenAI, DeepSeek, OpenAI 호환 서버, 인페인팅 API 같은 외부 API 주소와 키, 모델명을 관리합니다. 유료 API 정보가 들어갈 수 있으니 저장 전 확인이 필요합니다.': 'Manages external API URLs, keys, and model names such as OpenAI, DeepSeek, OpenAI-compatible servers, and inpainting APIs. This may include paid API information, so review it before saving.',
    '관리': 'Manage',
    'AI 번역에 사용할 기본 지침을 편집합니다. 작품 말투, 번역 규칙, 금지 표현 같은 지시문을 이곳에서 관리합니다.': 'Edits the default instructions for AI translation. Use this to manage tone, translation rules, and prohibited expressions.',
    '편집': 'Edit',
    '반복해서 나오는 이름, 고유명사, 말투 규칙, 번역 고정어를 관리합니다. 번역 품질을 일정하게 유지하는 데 쓰입니다.': 'Manages recurring names, proper nouns, tone rules, and fixed translation terms. This helps keep translation quality consistent.',
    '작업, 일괄 처리, 텍스트 입력, 옵션 기능에 연결된 단축키를 한곳에서 바꿉니다. 충돌 확인과 비활성화도 여기서 처리합니다.': 'Changes shortcuts for work actions, batch actions, text input, and options in one place. Conflict checks and disabling shortcuts are also handled here.',
    '여러 작업을 하나의 사용자 단축키로 묶어 실행하는 매크로를 관리합니다. 반복 작업을 줄이는 자동화용 기능입니다.': 'Manages macros that bundle multiple actions into one user shortcut. This is used to reduce repetitive work.',
    '현재 페이지 또는 전체 맵에 적용할 글꼴 스타일 묶음을 관리합니다. 페이지 단위 식질 스타일을 빠르게 맞출 때 사용합니다.': 'Manages font style sets applied to the current page or all pages. Use this to quickly match page-level typesetting styles.',
    '선택한 텍스트 박스 하나에 적용할 글꼴, 크기, 테두리, 색상 같은 개별 스타일 프리셋을 관리합니다.': 'Manages individual style presets such as font, size, outline, and color for a selected text box.',
    '⚙️ 설정 / 옵션 변경 취소': '⚙️ Settings / Options changes canceled',
    '⚙️ 설정 / 옵션 내보내기 완료': '⚙️ Settings / Options saved',
})


# hotfix5 additions: launcher/session close and confirmation dialogs
_HOTFIX5_UI_KO_EN = {
 '선택 대사 주변 간이 맵 프리뷰 표시': 'Show Local Map Preview Around Selected Dialogue',
 '현재 선택된 대사의 이벤트 좌표를 중심으로 주변 15x10칸을 잘라 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다.': 'Shows a 15x10 tile area around the event coordinates of the selected dialogue. It does not modify the actual game JSON.',
 '검수용 간이 맵 프리뷰/보조선/이벤트 위치/이벤트 이름 표시를 켜고 끕니다. 간이 맵 프리뷰는 선택된 대사의 이벤트 주변을 격자와 이벤트 점으로 보여주는 1단계 기능이며, 실제 게임 JSON은 바꾸지 않습니다. 쯔꾸르붕이에서는 역식붕이식 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다.': 'Toggle the review-only local map preview, helper lines, event positions, and event names. The local map preview is a stage-1 feature that shows the selected dialogue event area with a grid and event dots, and it does not modify the actual game JSON. In YSB Game Editor, dialogue is not created as YSB typesetting text objects on the map; it is shown only in the game-style message/choice preview and the table on the right.',
 '⚠️ 쯔꾸르 선택 프리뷰 갱신 실패: {error}': '⚠️ Failed to refresh Maker selection preview: {error}',
    '쯔꾸르붕이': 'YSB Game Editor',
    '예': 'Yes',
    '아니오': 'No',
    '열기': 'Open',
    '취소': 'Cancel',
    '저장': 'Save',
    '최근 프로젝트 열기': 'Open Recent Project',
    '이 최근 프로젝트를 열까요?': 'Open this recent project?',
    '최근 프로젝트 파일을 찾을 수 없습니다.\n최근 목록에서 제거하거나 파일 위치를 확인해 주세요.': 'The recent project file could not be found.\nRemove it from the recent list or check the file location.',
    '설정 저장': 'Save Settings',
    '이 창에서 바꾼 설정을 저장할까요?': 'Save the settings changed in this window?',
    '설정 내보내기 완료': 'Settings Saved',
    '설정이 저장되었습니다.': 'Settings have been saved.',
    '⚙️ 설정 / 옵션 내보내기 취소': '⚙️ Settings / Options save canceled',
    '일괄 작업 중에는 홈화면으로 이동할 수 없습니다.\n작업이 끝난 뒤 다시 시도해 주세요.': 'You cannot go to the home screen while a batch job is running.\nTry again after the job finishes.',
    '🏠 프로젝트를 닫고 홈화면으로 이동했습니다.': '🏠 Closed the project and moved to the home screen.',
    '↩️ 홈화면 이동 취소': '↩️ Home screen move canceled',
    '↩️ 최근 프로젝트 열기 취소': '↩️ Recent project open canceled',
}
UI_KO_EN.update(_HOTFIX5_UI_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _HOTFIX5_UI_KO_EN.items()})


# hotfix7 additions: English cleanup and current project work folder shortcut
_HOTFIX7_UI_KO_EN = {
 '선택 대사 주변 간이 맵 프리뷰 표시': 'Show Local Map Preview Around Selected Dialogue',
 '현재 선택된 대사의 이벤트 좌표를 중심으로 주변 15x10칸을 잘라 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다.': 'Shows a 15x10 tile area around the event coordinates of the selected dialogue. It does not modify the actual game JSON.',
 '검수용 간이 맵 프리뷰/보조선/이벤트 위치/이벤트 이름 표시를 켜고 끕니다. 간이 맵 프리뷰는 선택된 대사의 이벤트 주변을 격자와 이벤트 점으로 보여주는 1단계 기능이며, 실제 게임 JSON은 바꾸지 않습니다. 쯔꾸르붕이에서는 역식붕이식 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다.': 'Toggle the review-only local map preview, helper lines, event positions, and event names. The local map preview is a stage-1 feature that shows the selected dialogue event area with a grid and event dots, and it does not modify the actual game JSON. In YSB Game Editor, dialogue is not created as YSB typesetting text objects on the map; it is shown only in the game-style message/choice preview and the table on the right.',
 '⚠️ 쯔꾸르 선택 프리뷰 갱신 실패: {error}': '⚠️ Failed to refresh Maker selection preview: {error}',
    '임시 파일 관리': 'Temporary File Management',
    '일주일': '1 Week',
    '한달': '1 Month',
    '3개월': '3 Months',
    '6개월': '6 Months',
    '12개월': '12 Months',
    '영어': 'English',
    '작업 폴더 열기': 'Open Work Folder',
    '작업 폴더 열기 실패': 'Failed to Open Work Folder',
    '현재 열린 프로젝트가 없습니다.': 'No project is currently open.',
    '현재 프로젝트 작업 폴더를 찾을 수 없습니다.': 'Could not find the current project work folder.',
    '현재 프로젝트 작업 폴더를 열었습니다.': 'Opened current project work folder',
    '현재 프로젝트의 작업 폴더로 이동하기': 'Open Current Project Work Folder',
}
UI_KO_EN.update(_HOTFIX7_UI_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _HOTFIX7_UI_KO_EN.items()})

# hotfix8 additions: analysis mask expansion ratio settings
_HOTFIX8_UI_KO_EN = {
 '선택 대사 주변 간이 맵 프리뷰 표시': 'Show Local Map Preview Around Selected Dialogue',
 '현재 선택된 대사의 이벤트 좌표를 중심으로 주변 15x10칸을 잘라 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다.': 'Shows a 15x10 tile area around the event coordinates of the selected dialogue. It does not modify the actual game JSON.',
 '검수용 간이 맵 프리뷰/보조선/이벤트 위치/이벤트 이름 표시를 켜고 끕니다. 간이 맵 프리뷰는 선택된 대사의 이벤트 주변을 격자와 이벤트 점으로 보여주는 1단계 기능이며, 실제 게임 JSON은 바꾸지 않습니다. 쯔꾸르붕이에서는 역식붕이식 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다.': 'Toggle the review-only local map preview, helper lines, event positions, and event names. The local map preview is a stage-1 feature that shows the selected dialogue event area with a grid and event dots, and it does not modify the actual game JSON. In YSB Game Editor, dialogue is not created as YSB typesetting text objects on the map; it is shown only in the game-style message/choice preview and the table on the right.',
 '⚠️ 쯔꾸르 선택 프리뷰 갱신 실패: {error}': '⚠️ Failed to refresh Maker selection preview: {error}',
    '분석 마스크 확장 비율': 'Analysis Mask Expansion Ratio',
    'OCR/분석 결과로 만들어지는 마스크의 여유 범위를 조절합니다. 글자 테두리가 덜 잡히면 값을 올리고, 배경까지 너무 넓게 잡히면 값을 낮추세요.': 'Adjusts the extra margin of masks created from OCR/analysis results. Increase the value if text outlines are not fully captured, and lower it if too much background is included.',
    '텍스트 마스크 확장 비율': 'Text Mask Expansion Ratio',
    '분석 결과의 텍스트 마스크를 묶고 확장하는 비율입니다. 말풍선 글자 테두리가 덜 잡히면 이 값을 올리세요.': 'Controls how much the text mask from analysis is grouped and expanded. Increase this when speech bubble text outlines are not fully captured.',
    '페인트 마스크 확장 비율': 'Paint Mask Expansion Ratio',
    '인페인팅/페인트 마스크를 만들 때 글자 주변을 얼마나 여유 있게 지울지 정합니다. 배경까지 너무 많이 잡히면 이 값을 낮추세요.': 'Controls how much extra area around text is cleared when creating the inpainting/paint mask. Lower this if too much background is included.',
    '기본값으로 돌아가기': 'Restore Defaults',
    '분석 마스크 설정 저장': 'Save Analysis Mask Settings',
    '분석 마스크 확장 비율을 저장할까요?': 'Save the analysis mask expansion ratios?',
    '분석 마스크 설정 내보내기 완료': 'Analysis Mask Settings Saved',
    '분석 마스크 확장 비율이 저장되었습니다.': 'Analysis mask expansion ratios have been saved.',
    '🎭 분석 마스크 확장 비율 내보내기 취소': '🎭 Analysis mask expansion ratio save canceled',
    'OCR/분석 결과로 만들어지는 마스크의 여유 범위를 조절합니다. 글자 테두리가 덜 잡히면 값을 올리고, 배경까지 너무 넓게 잡히면 값을 낮추세요.': 'Adjusts the extra margin of masks created from OCR/analysis results. Increase the value if text outlines are not fully captured, and lower it if too much background is included.',
}
UI_KO_EN.update(_HOTFIX8_UI_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _HOTFIX8_UI_KO_EN.items()})
try:
    SHORTCUT_TR_KO_EN.update({'분석 마스크 확장 비율': 'Analysis Mask Expansion Ratio'})
except Exception:
    pass

# hotfix9 additions: analysis mask minimum expansion size settings
_HOTFIX9_UI_KO_EN = {
 '선택 대사 주변 간이 맵 프리뷰 표시': 'Show Local Map Preview Around Selected Dialogue',
 '현재 선택된 대사의 이벤트 좌표를 중심으로 주변 15x10칸을 잘라 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다.': 'Shows a 15x10 tile area around the event coordinates of the selected dialogue. It does not modify the actual game JSON.',
 '검수용 간이 맵 프리뷰/보조선/이벤트 위치/이벤트 이름 표시를 켜고 끕니다. 간이 맵 프리뷰는 선택된 대사의 이벤트 주변을 격자와 이벤트 점으로 보여주는 1단계 기능이며, 실제 게임 JSON은 바꾸지 않습니다. 쯔꾸르붕이에서는 역식붕이식 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다.': 'Toggle the review-only local map preview, helper lines, event positions, and event names. The local map preview is a stage-1 feature that shows the selected dialogue event area with a grid and event dots, and it does not modify the actual game JSON. In YSB Game Editor, dialogue is not created as YSB typesetting text objects on the map; it is shown only in the game-style message/choice preview and the table on the right.',
 '⚠️ 쯔꾸르 선택 프리뷰 갱신 실패: {error}': '⚠️ Failed to refresh Maker selection preview: {error}',
    'OCR/분석 결과로 만들어지는 마스크의 여유 범위와 최소 확장 크기를 조절합니다. 최소 확장 크기를 0px로 두면 강제 최소 확장을 사용하지 않습니다.': 'Adjusts the extra mask margin and minimum expansion size created from OCR/analysis results. Set the minimum expansion size to 0px to disable forced minimum expansion.',
    '텍스트 마스크 최소 확장 크기': 'Text Mask Minimum Expansion Size',
    '텍스트 마스크를 만들 때 비율 계산값이 작아도 최소로 확장할 픽셀 크기입니다. 0px이면 최소 확장 강제를 사용하지 않습니다.': 'The minimum pixel size used to expand the text mask even when the ratio-based value is small. Set it to 0px to disable forced minimum expansion.',
    '페인트 마스크 최소 확장 크기': 'Paint Mask Minimum Expansion Size',
    '페인트 마스크를 만들 때 비율 계산값이 작아도 최소로 확장할 픽셀 크기입니다. 0px이면 최소 확장 강제를 사용하지 않습니다.': 'The minimum pixel size used to expand the paint mask even when the ratio-based value is small. Set it to 0px to disable forced minimum expansion.',
    '분석 마스크 확장 설정을 저장할까요?': 'Save the analysis mask expansion settings?',
    '분석 마스크 확장 설정이 저장되었습니다.': 'Analysis mask expansion settings have been saved.',
    '🎭 분석 마스크 확장 설정 내보내기 취소': '🎭 Analysis mask expansion settings save canceled',
}
UI_KO_EN.update(_HOTFIX9_UI_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _HOTFIX9_UI_KO_EN.items()})

# hotfix10 additions: mask wrapping tool
_HOTFIX10_UI_KO_EN = {
 '선택 대사 주변 간이 맵 프리뷰 표시': 'Show Local Map Preview Around Selected Dialogue',
 '현재 선택된 대사의 이벤트 좌표를 중심으로 주변 15x10칸을 잘라 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다.': 'Shows a 15x10 tile area around the event coordinates of the selected dialogue. It does not modify the actual game JSON.',
 '검수용 간이 맵 프리뷰/보조선/이벤트 위치/이벤트 이름 표시를 켜고 끕니다. 간이 맵 프리뷰는 선택된 대사의 이벤트 주변을 격자와 이벤트 점으로 보여주는 1단계 기능이며, 실제 게임 JSON은 바꾸지 않습니다. 쯔꾸르붕이에서는 역식붕이식 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다.': 'Toggle the review-only local map preview, helper lines, event positions, and event names. The local map preview is a stage-1 feature that shows the selected dialogue event area with a grid and event dots, and it does not modify the actual game JSON. In YSB Game Editor, dialogue is not created as YSB typesetting text objects on the map; it is shown only in the game-style message/choice preview and the table on the right.',
 '⚠️ 쯔꾸르 선택 프리뷰 갱신 실패: {error}': '⚠️ Failed to refresh Maker selection preview: {error}',
    '마스크 랩핑': 'Mask Wrapping',
    '마스크 랩핑 사각형': 'Mask Wrapping Rectangle',
    '마스크 랩핑 자유형': 'Mask Wrapping Freeform',
    '▭ 사각형': '▭ Rectangle',
    '✎ 자유형': '✎ Freeform',
    '사각형으로 영역 그리기': 'Draw Rectangular Area',
    '자유형으로 영역 그리기': 'Draw Freeform Area',
    '영역 안의 떨어진 마스크들을 하나의 채움 영역으로 감싸줍니다.': 'Wraps separated masks inside the selected area into one filled area.',
    '윈도우 캡처처럼 사각형 범위를 잡고 그 안의 마스크들을 하나로 감싸 채웁니다.': 'Drag a rectangular area like Windows capture, then wrap and fill the masks inside it.',
    '드래그한 자유형 범위 안에서만 마스크들을 하나로 감싸 채웁니다.': 'Wraps and fills masks only inside the freeform area you drag.',
    '선택한 영역 안의 떨어진 마스크들을 하나의 채움 영역으로 감싸줍니다.': 'Wraps separated masks inside the selected area into one filled area.',
    '⚠️ 마스크 랩핑은 텍스트 마스크/페인팅 마스크 탭에서 사용하세요.': '⚠️ Use Mask Wrapping on the Text Mask or Painting Mask tab.',
    '⚠️ 마스크 랩핑 영역이 비어 있습니다.': '⚠️ The mask wrapping area is empty.',
    '⚠️ 선택한 영역 안에 랩핑할 마스크가 2개 이상 필요합니다.': '⚠️ At least two mask islands are required for wrapping inside the selected area.',
    '⚠️ 마스크 랩핑 영역 안에서 마스크를 찾지 못했습니다.': '⚠️ Could not find masks inside the mask wrapping area.',
    '⚠️ 마스크 랩핑 실패:': '⚠️ Mask wrapping failed:',
    '⚠️ 마스크 랩핑으로 추가될 영역이 없습니다.': '⚠️ Mask wrapping has no area to add.',
    '🩹 마스크 랩핑 완료:': '🩹 Mask wrapping complete:',
    '🩹 도구: 마스크 랩핑': '🩹 Tool: Mask Wrapping',
    '🩹 마스크 랩핑 모드: 사각형': '🩹 Mask Wrapping Mode: Rectangle',
    '🩹 마스크 랩핑 모드: 자유형': '🩹 Mask Wrapping Mode: Freeform',
}
UI_KO_EN.update(_HOTFIX10_UI_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _HOTFIX10_UI_KO_EN.items()})
try:
    SHORTCUT_TR_KO_EN.update({
        '마스크 랩핑': 'Mask Wrapping',
        '마스크 랩핑 사각형': 'Mask Wrapping Rectangle',
        '마스크 랩핑 자유형': 'Mask Wrapping Freeform',
    })
except Exception:
    pass




# v1.8.0 hotfix17 workspace default reset strings
UI_KO_EN.update({
    '기본값으로 변경': 'Restore Default',
    'Windows 실제 문서 폴더 아래 YSB_Translator로 되돌립니다.': 'Restore to YSB_Translator under the actual Windows Documents folder.',
    '작업 폴더 위치 기본값으로 변경': 'Restore Workspace Folder to Default',
    '작업 폴더 위치를 기본값으로 변경할까요?': 'Restore the workspace folder location to the default?',
    '현재 위치': 'Current location',
    '기본값': 'Default',
    '변경': 'Change',
    '작업 폴더 위치가 기본값으로 변경 예약되었습니다.\n프로그램을 재실행하면 아래 위치로 이동됩니다.': 'The workspace folder location has been scheduled to restore to the default.\nRestart the program to move it to the location below.',
    '작업 폴더 위치가 이미 기본값입니다.': 'The workspace folder location is already set to the default.',
    '작업 폴더 위치를 기본값으로 변경하지 못했습니다.': 'Failed to restore the workspace folder location to the default.',
    '프로젝트 작업 폴더와 캐시가 저장되는 기준 위치입니다. 위치 변경 또는 기본값으로 변경은 전용 확인 후 적용되며, 기본값은 Windows 실제 문서 폴더 아래 YSB_Translator입니다.': 'This is the base location for project workspace folders and cache. Change Location or Restore Default applies only after its own confirmation. The default is YSB_Translator under the actual Windows Documents folder.',
})
UI_EN_KO.update({v: k for k, v in UI_KO_EN.items()})
SHORTCUT_TR_KO_EN.update({
    '작업 폴더 위치 기본값으로 변경': 'Restore Workspace Folder to Default',
})


# v1.8.0 hotfix18 workspace restart strings
UI_KO_EN.update({
    '기본값으로\n변경': 'Restore\nDefault',
    '작업 폴더 위치 변경': 'Change Workspace Folder Location',
    '폴더 위치 변경으로 프로그램을 재기동합니다.\n취소할 시 이전 설정한 폴더 위치값으로 원복합니다.': 'The program will restart because the workspace folder location is changing.\nIf you cancel, the previous workspace folder location will be restored.',
    '변경 위치': 'New location',
    '재기동(Y)': 'Restart (Y)',
    'Enter 또는 Y 키로 재기동합니다.': 'Press Enter or Y to restart.',
    'N 키로 취소하고 이전 설정값으로 되돌립니다.': 'Press N to cancel and restore the previous setting.',
    '프로젝트 작업 폴더와 캐시가 저장되는 기준 위치입니다. 위치를 바꾸면 프로그램을 재기동해야 적용됩니다. 취소하면 이전 작업 폴더 위치값으로 원복됩니다. 기본값은 Windows 실제 문서 폴더 아래 YSB_Translator입니다.': 'This is the base location for project workspace folders and cache. Changing this location requires restarting the program to apply it. If you cancel, the previous workspace folder location is restored. The default is YSB_Translator under the actual Windows Documents folder.',
})
UI_EN_KO.update({v: k for k, v in UI_KO_EN.items()})


# hotfix11 additions: mask cutting tool
_HOTFIX11_UI_KO_EN = {
 '선택 대사 주변 간이 맵 프리뷰 표시': 'Show Local Map Preview Around Selected Dialogue',
 '현재 선택된 대사의 이벤트 좌표를 중심으로 주변 15x10칸을 잘라 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다.': 'Shows a 15x10 tile area around the event coordinates of the selected dialogue. It does not modify the actual game JSON.',
 '검수용 간이 맵 프리뷰/보조선/이벤트 위치/이벤트 이름 표시를 켜고 끕니다. 간이 맵 프리뷰는 선택된 대사의 이벤트 주변을 격자와 이벤트 점으로 보여주는 1단계 기능이며, 실제 게임 JSON은 바꾸지 않습니다. 쯔꾸르붕이에서는 역식붕이식 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다.': 'Toggle the review-only local map preview, helper lines, event positions, and event names. The local map preview is a stage-1 feature that shows the selected dialogue event area with a grid and event dots, and it does not modify the actual game JSON. In YSB Game Editor, dialogue is not created as YSB typesetting text objects on the map; it is shown only in the game-style message/choice preview and the table on the right.',
 '⚠️ 쯔꾸르 선택 프리뷰 갱신 실패: {error}': '⚠️ Failed to refresh Maker selection preview: {error}',
    '마스크 커팅': 'Mask Cutting',
    '마스크 선택 사각형': 'Rectangle Area',
    '마스크 선택 자유형': 'Freeform Area',
    '커팅 폭': 'Cut Width',
    '선택 영역 밖 경계를 지정 픽셀만큼 잘라 붙어 있는 마스크를 분리합니다.': 'Cuts the mask by the specified pixels outside the selected boundary to separate connected masks.',
    '사각형 보존 영역의 바깥 경계를 지정 픽셀만큼 잘라냅니다.': 'Cuts the mask by the specified pixels outside the rectangular keep area.',
    '자유형 보존 영역의 바깥 경계를 지정 픽셀만큼 잘라냅니다.': 'Cuts the mask by the specified pixels outside the freeform keep area.',
    '선택 영역 밖으로 잘라낼 마스크 폭입니다.': 'The mask width to cut outside the selected area.',
    '⚠️ 마스크 커팅은 텍스트 마스크/페인팅 마스크 탭에서 사용하세요.': '⚠️ Use Mask Cutting on the Text Mask or Painting Mask tab.',
    '⚠️ 마스크 커팅 영역이 비어 있습니다.': '⚠️ The mask cutting area is empty.',
    '⚠️ 현재 탭에 마스크 레이어가 없습니다.': '⚠️ There is no mask layer on the current tab.',
    '⚠️ 마스크 커팅으로 제거할 외곽 영역이 없습니다.': '⚠️ There is no outer boundary area to cut.',
    '⚠️ 지정한 커팅 영역에 제거할 마스크가 없습니다.': '⚠️ There is no mask to remove in the specified cutting area.',
    '⚠️ 마스크 커팅으로 변경된 영역이 없습니다.': '⚠️ Mask cutting did not change any area.',
    '🔪 도구: 마스크 커팅': '🔪 Tool: Mask Cutting',
    '🔪 마스크 커팅 모드: 사각형': '🔪 Mask Cutting Mode: Rectangle Area',
    '🔪 마스크 커팅 모드: 자유형': '🔪 Mask Cutting Mode: Freeform Area',
    '🔪 마스크 커팅 완료:': '🔪 Mask cutting complete:',
    '⚠️ 마스크 커팅 실패:': '⚠️ Mask cutting failed:',
}
UI_KO_EN.update(_HOTFIX11_UI_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _HOTFIX11_UI_KO_EN.items()})
try:
    SHORTCUT_TR_KO_EN.update({
        '마스크 커팅': 'Mask Cutting',
        '마스크 선택 사각형': 'Rectangle Area',
        '마스크 선택 자유형': 'Freeform Area',
    })
except Exception:
    pass


# v2.0.1 page tabs / drag-and-drop image insertion
_V200_PAGE_TABS_UI_KO_EN = {
 '선택 대사 주변 간이 맵 프리뷰 표시': 'Show Local Map Preview Around Selected Dialogue',
 '현재 선택된 대사의 이벤트 좌표를 중심으로 주변 15x10칸을 잘라 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다.': 'Shows a 15x10 tile area around the event coordinates of the selected dialogue. It does not modify the actual game JSON.',
 '검수용 간이 맵 프리뷰/보조선/이벤트 위치/이벤트 이름 표시를 켜고 끕니다. 간이 맵 프리뷰는 선택된 대사의 이벤트 주변을 격자와 이벤트 점으로 보여주는 1단계 기능이며, 실제 게임 JSON은 바꾸지 않습니다. 쯔꾸르붕이에서는 역식붕이식 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다.': 'Toggle the review-only local map preview, helper lines, event positions, and event names. The local map preview is a stage-1 feature that shows the selected dialogue event area with a grid and event dots, and it does not modify the actual game JSON. In YSB Game Editor, dialogue is not created as YSB typesetting text objects on the map; it is shown only in the game-style message/choice preview and the table on the right.',
 '⚠️ 쯔꾸르 선택 프리뷰 갱신 실패: {error}': '⚠️ Failed to refresh Maker selection preview: {error}',
    '페이지': 'Pages',
    '맵 없음': 'No maps',
    '이미지 불러오기': 'Import Images',
    '불러올 이미지 선택': 'Select Images to Import',
    '페이지 삭제': 'Delete Page',
    '이 페이지를 프로젝트에서 삭제할까요?': 'Delete this page from the project?',
    '삭제': 'Delete',
    '맵 탭 표시명': 'Page Tab Display Name',
    '출력 표시명': 'Output Display Name',
    '원본 파일명': 'Original Filename',
    '1p_원본 파일명': '1p_Original Filename',
    '좌측 이미지 작업창 상단의 맵 탭에 표시할 이름 형식을 정합니다. 기본값은 1p_원본 파일명입니다.': 'Choose the naming format shown on the page tabs above the left image workspace. The default is 1p_original filename.',
    '결과물, 클린 이미지, 포토샵 스크립트 파일명에 사용할 페이지 이름 형식을 정합니다. 기본값은 1p_원본 파일명입니다.': 'Choose the naming format used for result images, clean images, and Photoshop script filenames. The default is 1p_original filename.',
}
UI_KO_EN.update(_V200_PAGE_TABS_UI_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _V200_PAGE_TABS_UI_KO_EN.items()})


# v2.0.1 hotfix6: empty project creation dialog
_V200_HOTFIX6_UI_KO_EN = {
 '선택 대사 주변 간이 맵 프리뷰 표시': 'Show Local Map Preview Around Selected Dialogue',
 '현재 선택된 대사의 이벤트 좌표를 중심으로 주변 15x10칸을 잘라 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다.': 'Shows a 15x10 tile area around the event coordinates of the selected dialogue. It does not modify the actual game JSON.',
 '검수용 간이 맵 프리뷰/보조선/이벤트 위치/이벤트 이름 표시를 켜고 끕니다. 간이 맵 프리뷰는 선택된 대사의 이벤트 주변을 격자와 이벤트 점으로 보여주는 1단계 기능이며, 실제 게임 JSON은 바꾸지 않습니다. 쯔꾸르붕이에서는 역식붕이식 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다.': 'Toggle the review-only local map preview, helper lines, event positions, and event names. The local map preview is a stage-1 feature that shows the selected dialogue event area with a grid and event dots, and it does not modify the actual game JSON. In YSB Game Editor, dialogue is not created as YSB typesetting text objects on the map; it is shown only in the game-style message/choice preview and the table on the right.',
 '⚠️ 쯔꾸르 선택 프리뷰 갱신 실패: {error}': '⚠️ Failed to refresh Maker selection preview: {error}',
    '새 프로젝트': 'New Project',
    '프로젝트 이름': 'Project Name',
    '생성 위치': 'Creation Location',
    '생성 경로': 'Creation Path',
    '프로젝트 생성 위치 선택': 'Select Project Creation Location',
    '이미지 없이 빈 작업 인터페이스를 먼저 만들고, 나중에 이미지 불러오기로 페이지를 추가합니다.': 'Create an empty workspace first, then add pages later with Import Images.',
    '만들기': 'Create',
    '프로젝트 생성 실패': 'Project Creation Failed',
    '프로젝트 생성 위치를 만들 수 없습니다.': 'Could not create the project location.',
    '빈 프로젝트를 만들 수 없습니다.': 'Could not create the empty project.',
}
UI_KO_EN.update(_V200_HOTFIX6_UI_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _V200_HOTFIX6_UI_KO_EN.items()})
try:
    SHORTCUT_TR_KO_EN.update({
        '새 프로젝트': 'New Project',
        '이미지 불러오기': 'Import Images',
    })
except Exception:
    pass



API_TR_KO_EN.update({
    'Gemini Image Inpainting': 'Gemini Image Inpainting',
    'Gemini API Key (shared with translation)': 'Gemini API Key (shared with translation)',
    'Remove text inside the white mask and reconstruct the manga background': 'Remove text inside the white mask and reconstruct the manga background',
})


# v2.0.1 hotfix49 shortcut/dialog translation additions
SHORTCUT_TR_KO_EN.update({
    '맵 탭 파일명 변경': 'Rename Page Tab File Name',
    '현재 이미지탭 삭제': 'Delete Current Image Tab',
    '전체 이미지탭 삭제': 'Delete All Image Tabs',
})


# v2.0.1 hotfix49 UI translation additions
UI_KO_EN.update({
    '맵 탭 파일명 변경': 'Rename Page Tab File Name',
    '현재 이미지탭 삭제': 'Delete Current Image Tab',
    '전체 이미지탭 삭제': 'Delete All Image Tabs',
    '현재 프로젝트의 작업 폴더로 이동하기': 'Open Current Project Work Folder',
})
UI_EN_KO = {en: ko for ko, en in UI_KO_EN.items()}


# v2.0.1 hotfix52 help/about translations
UI_KO_EN.update({
    '도움말': 'Help',
    '프로그램 메뉴얼': 'Program Manual',
    'YSB Game Editor 사이트로 가기': 'Go to YSB Game Editor Website',
    '링크 열기 실패': 'Failed to Open Link',
    '웹 브라우저로 링크를 열 수 없습니다.': 'Could not open the link in a web browser.',
    '프로그램 정보': 'About',
    'YSB Game Editor / 쯔꾸르붕이': 'YSB Game Editor / 쯔꾸르붕이',
    '버전': 'Version',
    '이 소프트웨어는 GNU General Public License v3.0에 따라 배포됩니다.': 'This software is distributed under the GNU General Public License v3.0.',
    '이 애플리케이션은 PyQt6를 사용하므로, 오픈소스 배포판은 GPLv3 기준으로 제공됩니다.': 'Because this application uses PyQt6, the open-source distribution is provided under GPLv3.',
    'YSB Game Editor, 쯔꾸르붕이, ZeroStress8은 amule949가 사용하는 프로젝트명 및 표지입니다.': 'YSB Game Editor, 쯔꾸르붕이, and ZeroStress8 are project names and marks used by amule949.',
    'GPLv3 라이선스는 소스 코드에 적용되며, 프로젝트명·로고·브랜딩 사용 권리를 부여하지 않습니다.': 'The GPLv3 license applies to the source code and does not grant project name, logo, or branding usage rights.',
    '자세한 내용은 LICENSE 및 TRADEMARKS.md를 참고하세요.': 'See LICENSE and TRADEMARKS.md for details.',
})
UI_EN_KO = {en: ko for ko, en in UI_KO_EN.items()}

try:
    SHORTCUT_TR_KO_EN.update({
        '도움말': 'Help',
        '프로그램 메뉴얼': 'Program Manual',
        'YSB Game Editor 사이트로 가기': 'Go to YSB Game Editor Website',
        '링크 열기 실패': 'Failed to Open Link',
        '웹 브라우저로 링크를 열 수 없습니다.': 'Could not open the link in a web browser.',
        '프로그램 정보': 'About',
    })
except Exception:
    pass


# v2.0.1 hotfix53 site/support/version-check translations
UI_KO_EN.update({
    '버그제보 / 문의하기': 'Bug Report / Contact',
    '새 버전을 사용할 수 있습니다.': 'A new version is available.',
    '닫기': 'Close',
    '업데이트 알림': 'Update Notification',
    '다운로드 페이지에서 최신 버전을 받을 수 있습니다.': 'You can get the latest version from the download page.',
    '현재 버전': 'Current Version',
    '최신 버전': 'Latest Version',
    '이번 버전은 다시 알리지 않음': 'Do not remind me about this version again',
    '다운로드 페이지로 이동': 'Open Download Page',
})
UI_EN_KO = {en: ko for ko, en in UI_KO_EN.items()}

try:
    SHORTCUT_TR_KO_EN.update({
        '버그제보 / 문의하기': 'Bug Report / Contact',
                            '닫기': 'Close',
        '업데이트 알림': 'Update Notification',
        '현재 버전': 'Current Version',
        '최신 버전': 'Latest Version',
        '이번 버전은 다시 알리지 않음': 'Do not remind me about this version again',
        '다운로드 페이지로 이동': 'Open Download Page',
    })
except Exception:
    pass


# v2.0.1 OCR language combo translations
API_TR_KO_EN.update({
    'OCR 언어': 'OCR Language',
    '일본어': 'Japanese',
    '중국어': 'Chinese',
    '한국어': 'Korean',
    '영어': 'English',
})


# v2.0.1 font refresh translations
UI_KO_EN.update({
    '폰트 갱신': 'Refresh Fonts',
    'Windows에 설치되어 있지만 목록에 보이지 않는 글꼴을 다시 찾습니다.': 'Search again for fonts installed in Windows but missing from the list.',
    '폰트 갱신 확인': 'Refresh Fonts',
    'Windows 글꼴 폴더와 사용자 글꼴 폴더를 다시 검색합니다.\n\n일부 글꼴은 Qt 기본 목록에 바로 보이지 않을 수 있어, 이 작업은 누락된 글꼴을 추가로 등록합니다.\n\n글꼴이 많으면 잠시 걸릴 수 있습니다. 계속할까요?': 'This will scan the Windows Fonts folder and your user Fonts folder again.\n\nSome fonts may not appear in Qt\'s default list, so this registers missing fonts as application fonts.\n\nIt may take a moment if you have many fonts. Continue?',
    '폰트 갱신 완료': 'Font refresh complete',
    '폰트 목록을 갱신했습니다.\n새로 추가된 글꼴 패밀리: {count}개': 'The font list has been refreshed.\nNew font families added: {count}',
    '폰트 갱신 실패': 'Font refresh failed',
    '폰트 갱신 중 오류가 발생했습니다.': 'An error occurred while refreshing fonts.',
})

# v2.0.1 path visibility option translations
UI_KO_EN.update({
    '로그창에 파일 위치 및 경로 표시': 'Show file locations and paths in logs',
    '로그에 저장 위치, 출력 위치, 작업 폴더 같은 실제 파일 경로를 함께 표시합니다. 끄면 완료/실패 같은 결과 문구만 표시합니다.': 'Shows actual file paths such as save locations, output folders, and workspace folders in the log. When disabled, only result messages such as completion/failure are shown.',
    '옵션 및 설정창에 캐시 위치 경로 표시': 'Show cache location paths in options and settings',
    'API, 단축키 같은 옵션/설정 관리창에서 실제 캐시 파일 위치를 표시합니다. 끄면 캐시 경로는 숨깁니다.': 'Shows actual cache file locations in option/settings dialogs such as API and shortcut settings. When disabled, cache paths are hidden.',
    '파일 경로 표시': 'File path display',
    '로그와 설정창에 실제 파일 경로를 표시할지 정합니다. 기본값은 꺼짐이며, 필요한 경우에만 켜는 고급 정보입니다.': 'Choose whether to show actual file paths in logs and settings windows. This is off by default and is advanced information for users who need it.',
    '파일 경로 표시 설정 내보내기 완료': 'File path display settings saved',
    '표시': 'Show',
    '경로 숨김': 'Path hidden',
    '로그 경로 표시: ON': 'Log path display: ON',
    '로그 경로 표시: OFF': 'Log path display: OFF',
    '설정창 캐시 경로 표시: ON': 'Settings cache path display: ON',
    '설정창 캐시 경로 표시: OFF': 'Settings cache path display: OFF',
})
UI_EN_KO = {en: ko for ko, en in UI_KO_EN.items()}

# v2.1.0 batch page range selection translations
UI_KO_EN.update({
    '작업할 페이지 범위를 선택하세요.': 'Choose the page range to process.',
    '전체 맵': 'All Maps',
    '페이지 선택': 'Page Selection',
    '예: 1-3, 1~3, 1,2,3': 'Ex: 1-3, 1~3, 1,2,3',
    '쉼표와 범위를 섞어서 입력할 수 있습니다.': 'You can mix commas and ranges.',
    '페이지 선택 오류': 'Page Selection Error',
    '페이지 선택 값을 입력해 주세요.': 'Enter page numbers to process.',
    '작업할 페이지가 없습니다.': 'There are no pages to process.',
    '페이지 범위가 프로젝트 페이지 수를 벗어났습니다.': 'The page range is outside the project page count.',
    '페이지 선택 형식을 확인해 주세요.': 'Check the page selection format.',
})
UI_EN_KO = {en: ko for ko, en in UI_KO_EN.items()}

# v2.2.0 OCR analysis region / Quick OCR translations
UI_KO_EN.update({
    'OCR 분석 범위 지정': 'OCR Analysis Region Selection',
    'OCR이 읽을 영역을 페이지별로 제한합니다. 지정된 영역이 없으면 전체 화면을 분석합니다.': 'Limit OCR reading areas by page. If no regions are specified, the full page is analyzed.',
    '현재 페이지의 OCR 분석 범위 지정': 'Set OCR Analysis Region for Current Page',
    '현재 보고 있는 페이지만 OCR 분석 영역을 지정합니다.': 'Set OCR analysis regions only for the current page.',
    '전체 맵의 OCR 분석 범위 지정': 'Set OCR Analysis Region for All Pages',
    '모든 페이지에 같은 OCR 분석 영역을 지정합니다.': 'Apply the same OCR analysis regions to all pages.',
    '선택 페이지의 OCR 분석 범위 지정': 'Set OCR Analysis Region for Selected Pages',
    '1-3, 1~3, 1,2,3 형식으로 지정한 페이지에 같은 영역을 적용합니다.': 'Apply the same regions to pages entered like 1-3, 1~3, or 1,2,3.',
    '범위지정 해제': 'Clear Region Selection',
    '저장된 OCR 분석 영역을 모두 지우고, 다시 전체 화면 분석 상태로 되돌립니다.': 'Clear all saved OCR analysis regions and return to full-page analysis.',
    '지정하기': 'Select',
    '해제하기': 'Clear',
    '선택 맵 없음': 'No selected pages',
    '이미지 없음': 'No Images',
    '먼저 프로젝트에 이미지를 불러와 주세요.': 'Import images into the project first.',
    'OCR 분석 영역 지정 종료': 'Exit OCR Region Selection',
    'OCR 분석 영역 지정을 종료할까요?': 'Exit OCR analysis region selection?',
    '아직 저장하지 않은 변경사항이 있을 수 있습니다. 종료하면 저장 여부를 한 번 더 선택할 수 있습니다.': 'There may be unsaved changes. If you exit, you can choose whether to save them.',
    '종료하기': 'Exit',
    '계속 지정하기': 'Keep Selecting',
    'OCR 분석 영역 저장': 'Save OCR Analysis Regions',
    '변경한 OCR 분석 영역을 저장할까요?': 'Save the changed OCR analysis regions?',
    '저장하지 않고 종료하면 이번에 지정한 OCR 분석 영역은 적용되지 않습니다.': 'If you exit without saving, the regions selected in this session will not be applied.',
    '저장하고 종료': 'Save and Exit',
    '저장하지 않고 종료': 'Exit Without Saving',
    '모든 페이지의 OCR 분석 영역을 지울까요?\n\n지우면 OCR은 다시 전체 화면을 분석합니다.': 'Clear OCR analysis regions from all pages?\n\nAfter clearing, OCR will analyze the full page again.',
    'OCR 분석 범위 해제': 'Clear OCR Analysis Regions',
    'OCR 분석 영역': 'OCR Analysis Region',
    'OCR 분석 영역 숨기기': 'Hide OCR Analysis Regions',
    '체크하면 저장된 OCR 분석 영역은 유지하되, 모든 탭에서 영역 표시만 숨깁니다.': 'When checked, saved OCR analysis regions remain active but are hidden on all tabs.',
    '지정된 OCR 분석 영역이 있습니다. 지정된 영역만 분석할까요?': 'OCR analysis regions are set. Analyze only the specified regions?',
    '아니오를 누르면 분석을 취소합니다. 전체 화면을 분석하려면 먼저 OCR 분석 범위 지정을 해제해 주세요.': 'Click No to cancel. To analyze the full page, clear OCR analysis regions first.',
    'OCR 분석 영역 확인': 'Confirm OCR Analysis Regions',
    '실행하기': 'Run',
    'OCR이 읽을 범위를 드래그로 지정합니다.': 'Drag to select the area OCR should read.',
    '분석 영역 지정 종료': 'Finish Region Selection',
    '빠른 OCR': 'Quick OCR',
    '드래그한 영역만 즉시 OCR하고, 인식한 문장을 클립보드에 복사합니다.': 'OCR only the dragged area and copy the recognized text to the clipboard.',
    '마우스를 누른 채 영역을 고정하면 OCR을 실행합니다.': 'Hold the mouse down and keep the region still to run OCR.',
    '빠른 OCR은 지정된 단축키를 사용할 때만 동작합니다. Ctrl+J는 이 설정창을 여는 단축키입니다.': 'Quick OCR only runs when you press the assigned shortcut. Ctrl+J opens this settings window.',
    '빠른 OCR 설정': 'Quick OCR Settings',
    '빠른 OCR 실행': 'Run Quick OCR',
    '빠른 OCR 실행 단축키': 'Quick OCR Run Shortcut',
    '이 단축키를 누르면 바로 드래그 선택 모드로 들어갑니다. 빠른 OCR은 이 단축키로만 실제 실행됩니다.': 'Press this shortcut to enter drag selection mode. Quick OCR actually runs only from this shortcut.',
    '빠른 OCR 실행에 사용할 OCR 모델을 선택합니다.': 'Choose the OCR model used by Quick OCR.',
    '빠른 OCR 실행에 사용할 인식 언어를 선택합니다.': 'Choose the recognition language used by Quick OCR.',
    '설정창 단축키': 'Settings Window Shortcut',
    '비우기': 'Clear',
    '단축키 충돌': 'Shortcut Conflict',
    '단축키 저장 오류': 'Shortcut Save Error',
    '빠른 OCR 설정 내보내기 완료': 'Quick OCR Settings Saved',
    '빠른 OCR 설정이 저장되었습니다.': 'Quick OCR settings have been saved.',
    'OCR 모델': 'OCR Model',
    '언어': 'Language',
    '단축키': 'Shortcut',
    '단축키 설정 열기': 'Open Shortcut Settings',
    '시작': 'Start',
    '취소': 'Cancel',
    '빠른 OCR 오류': 'Quick OCR Error',
    '인식된 텍스트가 없습니다.': 'No text was recognized.',
    'CLOVA OCR': 'CLOVA OCR',
    'Google Vision OCR': 'Google Vision OCR',
    'LOCAL Paddle OCR': 'LOCAL Paddle OCR',
    '일본어': 'Japanese',
    '중국어': 'Chinese',
    '한국어': 'Korean',
    '영어': 'English',
})
SHORTCUT_TR_KO_EN.update({
    'OCR 분석 범위 지정': 'OCR Analysis Region Selection',
    '빠른 OCR 설정': 'Quick OCR Settings',
    '빠른 OCR 실행': 'Run Quick OCR',
    '빠른 OCR': 'Quick OCR',
})
UI_EN_KO = {en: ko for ko, en in UI_KO_EN.items()}

# v2.2.0 hotfix: shortcut manager tab/title cleanup
SHORTCUT_TR_KO_EN.update({
    '그림판': 'Canvas Tools',
    '텍스트 입력': 'Text Input',
    '글꼴': 'Font',
    '프로젝트': 'Project',
    '작업': 'Work',
    '일괄 작업': 'Batch Work',
    '자동화 작업': 'Automation Work',
    '옵션': 'Options',
    '도움말': 'Help',
    '기타': 'Other',
    '폰트': 'Font',
    '문자 크기': 'Text Size',
    '문자 확대': 'Increase Text Size',
    '문자 축소': 'Decrease Text Size',
    '획 크기': 'Stroke Size',
    '획 확대': 'Increase Stroke Size',
    '획 축소': 'Decrease Stroke Size',
    '문자 너비': 'Text Width',
    '문자 높이': 'Text Height',
    '굵게하기': 'Bold',
    '기울이기': 'Italic',
    '중앙정렬': 'Align Center',
    '문자 색상 팔레트': 'Text Color Palette',
    '획 색상 팔레트': 'Stroke Color Palette',
})

API_TR_KO_EN.update({
    'Local판 전용 OCR입니다. 이미지 안의 텍스트 영역을 찾아 PaddleOCR로 원문을 인식합니다.': 'Local edition OCR. It finds text areas in the image and recognizes the original text with PaddleOCR.',
    'Local판 전용 일본어 만화 OCR입니다. 일본어 만화 원문 인식에 특화된 모델을 사용합니다.': 'Local edition Japanese manga OCR. It uses a model specialized for recognizing original Japanese manga text.',
})

# v2.4.0 QA patch: Magic Wand step undo + eyedropper feedback
_V240_QA1_UI_KO_EN = {
 '선택 대사 주변 간이 맵 프리뷰 표시': 'Show Local Map Preview Around Selected Dialogue',
 '현재 선택된 대사의 이벤트 좌표를 중심으로 주변 15x10칸을 잘라 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다.': 'Shows a 15x10 tile area around the event coordinates of the selected dialogue. It does not modify the actual game JSON.',
 '검수용 간이 맵 프리뷰/보조선/이벤트 위치/이벤트 이름 표시를 켜고 끕니다. 간이 맵 프리뷰는 선택된 대사의 이벤트 주변을 격자와 이벤트 점으로 보여주는 1단계 기능이며, 실제 게임 JSON은 바꾸지 않습니다. 쯔꾸르붕이에서는 역식붕이식 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다.': 'Toggle the review-only local map preview, helper lines, event positions, and event names. The local map preview is a stage-1 feature that shows the selected dialogue event area with a grid and event dots, and it does not modify the actual game JSON. In YSB Game Editor, dialogue is not created as YSB typesetting text objects on the map; it is shown only in the game-style message/choice preview and the table on the right.',
 '⚠️ 쯔꾸르 선택 프리뷰 갱신 실패: {error}': '⚠️ Failed to refresh Maker selection preview: {error}',
    '스포이드 색상 적용': 'Eyedropper color applied',
    '⚠️ 스포이드로 색상을 가져오지 못했습니다.': '⚠️ Could not pick a color with the eyedropper.',
    '최종화면': 'Final view',
    '원본 비교창': 'Source compare view',
}
UI_KO_EN.update(_V240_QA1_UI_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _V240_QA1_UI_KO_EN.items()})

# v2.4.0 QA2 P1/P2: eyedropper popup + fixed shortcut display
_V240_QA2_UI_KO_EN = {
 '선택 대사 주변 간이 맵 프리뷰 표시': 'Show Local Map Preview Around Selected Dialogue',
 '현재 선택된 대사의 이벤트 좌표를 중심으로 주변 15x10칸을 잘라 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다.': 'Shows a 15x10 tile area around the event coordinates of the selected dialogue. It does not modify the actual game JSON.',
 '검수용 간이 맵 프리뷰/보조선/이벤트 위치/이벤트 이름 표시를 켜고 끕니다. 간이 맵 프리뷰는 선택된 대사의 이벤트 주변을 격자와 이벤트 점으로 보여주는 1단계 기능이며, 실제 게임 JSON은 바꾸지 않습니다. 쯔꾸르붕이에서는 역식붕이식 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다.': 'Toggle the review-only local map preview, helper lines, event positions, and event names. The local map preview is a stage-1 feature that shows the selected dialogue event area with a grid and event dots, and it does not modify the actual game JSON. In YSB Game Editor, dialogue is not created as YSB typesetting text objects on the map; it is shown only in the game-style message/choice preview and the table on the right.',
 '⚠️ 쯔꾸르 선택 프리뷰 갱신 실패: {error}': '⚠️ Failed to refresh Maker selection preview: {error}',
    '클립보드에 복사됨': 'Copied to clipboard',
}
UI_KO_EN.update(_V240_QA2_UI_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _V240_QA2_UI_KO_EN.items()})

SHORTCUT_TR_KO_EN.update({
    '줄내림, 뒤로가기, 앞으로 가기는 작업 안정성을 위해 고정 단축키로 표시만 됩니다.': 'Line break, Undo, and Redo are fixed shortcuts for work stability and are shown as read-only.',
    '고정': 'Fixed',
    '고정 단축키라서 끌 수 없습니다.': 'This fixed shortcut cannot be disabled.',
    '고정 단축키라서 변경할 수 없습니다.': 'This fixed shortcut cannot be changed.',
    '고정 단축키 충돌': 'Fixed Shortcut Conflict',
})

# v2.4.0 QA5: user data / temporary file cleanup manager
_V240_QA5_CLEANUP_UI_KO_EN = {
 '선택 대사 주변 간이 맵 프리뷰 표시': 'Show Local Map Preview Around Selected Dialogue',
 '현재 선택된 대사의 이벤트 좌표를 중심으로 주변 15x10칸을 잘라 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다.': 'Shows a 15x10 tile area around the event coordinates of the selected dialogue. It does not modify the actual game JSON.',
 '검수용 간이 맵 프리뷰/보조선/이벤트 위치/이벤트 이름 표시를 켜고 끕니다. 간이 맵 프리뷰는 선택된 대사의 이벤트 주변을 격자와 이벤트 점으로 보여주는 1단계 기능이며, 실제 게임 JSON은 바꾸지 않습니다. 쯔꾸르붕이에서는 역식붕이식 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다.': 'Toggle the review-only local map preview, helper lines, event positions, and event names. The local map preview is a stage-1 feature that shows the selected dialogue event area with a grid and event dots, and it does not modify the actual game JSON. In YSB Game Editor, dialogue is not created as YSB typesetting text objects on the map; it is shown only in the game-style message/choice preview and the table on the right.',
 '⚠️ 쯔꾸르 선택 프리뷰 갱신 실패: {error}': '⚠️ Failed to refresh Maker selection preview: {error}',
    '사용자 데이터 및 임시파일 정리': 'User Data and Temporary File Cleanup',
    'AppData에는 PC별 실행 정보와 로그가, 작업 폴더 cache에는 앱 옵션/API 설정/작업 캐시가 저장됩니다. 삭제할 항목을 확인한 뒤 선택하세요.': 'AppData stores PC-specific runtime data and logs, while the workspace cache stores app options, API settings, and work caches. Review the items before deleting them.',
    '저장 위치': 'Storage Locations',
    'AppData 실행 데이터': 'AppData Runtime Data',
    '작업 폴더': 'Workspace Folder',
    'AppData 폴더 열기': 'Open AppData Folder',
    '작업 폴더 열기': 'Open Workspace Folder',
    '항목': 'Item',
    '구분': 'Category',
    '위험도': 'Risk',
    '파일/폴더': 'Files/Folders',
    '용량': 'Size',
    '설명': 'Description',
    '로컬 단어장, 가져온 폰트, 실제 workspaces 프로젝트, .ysbg 파일, local_models는 기본 정리 대상에서 제외됩니다.': 'Local glossaries, imported fonts, actual workspaces projects, .ysbg files, and local_models are excluded from default cleanup.',
    '오래된 임시 작업 자동 정리': 'Auto-clean old temporary work',
    '다시 스캔': 'Rescan',
    '선택 항목 삭제': 'Delete Selected Items',
    '닫기': 'Close',
    '폴더 열기 실패': 'Failed to Open Folder',
    '폴더를 열지 못했습니다.': 'Could not open the folder.',
    '런처 임시 상태 파일': 'Launcher Temporary State Files',
    '런처와 메인 프로그램 사이에서 쓰는 진행률/신호 파일입니다. 삭제해도 다음 실행 때 다시 생성됩니다.': 'Progress/signal files used between the launcher and the main program. They will be recreated on the next run.',
    '실행 로그': 'Runtime Logs',
    '크래시/런처/작업 실행 로그입니다. 디버깅이 끝난 뒤 정리할 수 있습니다.': 'Crash, launcher, and work execution logs. You can clean them up after debugging.',
    '런처 메타데이터': 'Launcher Metadata',
    '더블클릭 열기 큐, 실행 시간 통계, 확장자 연결 사전 점검 상태입니다.': 'Double-click open queue, launch-time statistics, and file association preflight state.',
    '작업 폴더 캐시': 'Workspace Cache',
    '최근 프로젝트 썸네일': 'Recent Project Thumbnails',
    '홈 화면 최근 프로젝트 카드용 썸네일 캐시입니다. 필요하면 다시 생성됩니다.': 'Thumbnail cache for recent project cards on the home screen. It can be regenerated when needed.',
    '작업 폴더 임시 데이터': 'Workspace Temporary Data',
    '임시 프로젝트/작업 캐시': 'Temporary Projects / Work Cache',
    '현재 열려 있는 작업을 제외한 temp/work_sessions 임시 작업 폴더입니다. 삭제 후에는 해당 임시 작업을 복구할 수 없습니다.': 'Temporary work folders in temp/work_sessions, excluding the currently open work. They cannot be recovered after deletion.',
    '최근 프로젝트 기록': 'Recent Project History',
    '홈 화면의 최근 프로젝트 목록입니다. 프로젝트 파일 자체는 삭제하지 않습니다.': 'Recent project list on the home screen. This does not delete project files themselves.',
    '설정 초기화': 'Reset Settings',
    '작업 폴더 위치 설정': 'Workspace Location Setting',
    'AppData의 workspace_config.json입니다. 삭제하면 다음 실행 때 작업 폴더를 다시 지정해야 할 수 있습니다.': 'The workspace_config.json file in AppData. If deleted, you may need to choose the workspace folder again on the next run.',
    '앱 옵션': 'App Options',
    '언어, 테마, 프롬프트, 마스크 확장값, 작업 옵션 등이 초기화됩니다.': 'Language, theme, prompts, mask expansion values, and work options will be reset.',
    '단축키 설정': 'Shortcut Settings',
    '사용자가 바꾼 단축키 설정이 초기화됩니다.': 'User-customized shortcuts will be reset.',
    '텍스트/글꼴 프리셋': 'Text / Font Presets',
    '텍스트 프리셋과 개별 아이템 프리셋을 초기화합니다.': 'Resets text presets and per-item presets.',
    '민감 정보': 'Sensitive Data',
    'API 설정/키 캐시': 'API Settings / Key Cache',
    'OCR/번역/인페인팅 API 설정과 키가 들어가는 작업 폴더 cache/api_cache.json입니다.': 'The workspace cache/api_cache.json file that stores OCR/translation/inpainting API settings and keys.',
    '안전': 'Safe',
    '주의': 'Caution',
    '설정': 'Settings',
    '민감': 'Sensitive',
    '선택 항목 없음': 'No Items Selected',
    '삭제할 항목을 선택하세요.': 'Select items to delete.',
    '선택한 항목을 삭제합니다. 이 작업은 되돌릴 수 없습니다.': 'The selected items will be deleted. This cannot be undone.',
    '설정/민감 정보가 포함되어 있습니다. 삭제 후에는 재설정이나 재로그인이 필요할 수 있습니다.': 'Settings or sensitive data are included. You may need to reconfigure or log in again after deletion.',
    '대상': 'Targets',
    '개': ' item(s)',
    '계속할까요?': 'Continue?',
    '사용자 데이터 삭제 확인': 'Confirm User Data Deletion',
    '삭제 완료': 'Deletion Complete',
    '선택 항목 삭제가 완료되었습니다.': 'Selected item deletion is complete.',
    '삭제': 'Deleted',
    '실패': 'Failed',
}
UI_KO_EN.update(_V240_QA5_CLEANUP_UI_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _V240_QA5_CLEANUP_UI_KO_EN.items()})

# QA12a: re-analysis tooltip/detail translations
SHORTCUT_TR_KO_EN.update({
    '현재 텍스트 마스크를 기준으로 OCR 분석 영역을 다시 만들고, 기존 마스크는 재사용합니다.': 'Rebuilds OCR analysis areas from the current text mask and reuses the existing mask.',
    '선택한 맵마다 현재 텍스트 마스크를 기준으로 OCR 분석 영역을 다시 만들고, 기존 마스크는 재사용합니다.': 'For each selected page, rebuilds OCR analysis areas from the current text mask and reuses the existing mask.',
})

# QA21 UI strings
_QA21_UI_KO_EN = {
 '선택 대사 주변 간이 맵 프리뷰 표시': 'Show Local Map Preview Around Selected Dialogue',
 '현재 선택된 대사의 이벤트 좌표를 중심으로 주변 15x10칸을 잘라 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다.': 'Shows a 15x10 tile area around the event coordinates of the selected dialogue. It does not modify the actual game JSON.',
 '검수용 간이 맵 프리뷰/보조선/이벤트 위치/이벤트 이름 표시를 켜고 끕니다. 간이 맵 프리뷰는 선택된 대사의 이벤트 주변을 격자와 이벤트 점으로 보여주는 1단계 기능이며, 실제 게임 JSON은 바꾸지 않습니다. 쯔꾸르붕이에서는 역식붕이식 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다.': 'Toggle the review-only local map preview, helper lines, event positions, and event names. The local map preview is a stage-1 feature that shows the selected dialogue event area with a grid and event dots, and it does not modify the actual game JSON. In YSB Game Editor, dialogue is not created as YSB typesetting text objects on the map; it is shown only in the game-style message/choice preview and the table on the right.',
 '⚠️ 쯔꾸르 선택 프리뷰 갱신 실패: {error}': '⚠️ Failed to refresh Maker selection preview: {error}',
    "↻ 재분석": "↻ Re-analyze",
    "크기": "Size",
    "브러시 크기": "Brush Size",
    "브러시와 지우개의 두께를 1px 단위로 조절합니다.": "Adjust the brush and eraser thickness in 1 px steps.",
    "텍스트 마스크를 유지한 채 현재 페이지를 다시 분석합니다.": "Re-analyze the current page while keeping the text mask.",
}
UI_KO_EN.update(_QA21_UI_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _QA21_UI_KO_EN.items()})

# G step: simplified user data/cache cleanup manager + focus wording
_G_STEP_CLEANUP_SIMPLIFIED_KO_EN = {
    '작업 중 쌓이는 캐시는 자동 정리할 수 있고, 최근 프로젝트/설정/개인정보는 사용자가 직접 누를 때만 삭제합니다.': 'Work caches can be cleaned automatically; recent projects, settings, and private information are deleted only when the user explicitly presses delete.',
    'AppData': 'AppData',
    '오래된 캐시 자동 정리': 'Auto-clean old cache',
    '자동 정리 대상은 작업폴더 캐시와 AppData 캐시뿐입니다.': 'Only workspace cache and AppData cache are included in automatic cleanup.',
    '자동정리': 'Auto-clean',
    '작업폴더 캐시 삭제': 'Delete Workspace Cache',
    '작업 중 쌓인 임시 작업 폴더와 재생성 가능한 작업 캐시입니다.': 'Temporary work folders and regenerable work caches accumulated during editing.',
    'AppData 캐시 삭제': 'Delete AppData Cache',
    '실행 로그, 런처 상태, 앱 실행 중 생긴 임시 데이터입니다.': 'Runtime logs, launcher state, and temporary data created while the app runs.',
    '최근 프로젝트 정보 삭제': 'Delete Recent Project Info',
    '최근 열었던 프로젝트 목록과 홈 화면 썸네일 정보입니다. 프로젝트 파일 자체는 삭제하지 않습니다.': 'Recent project list and home-screen thumbnail information. This does not delete project files.',
    '설정 정보 삭제': 'Delete Settings Info',
    '언어, 테마, 단축키, 프리셋, 작업 폴더 위치 같은 사용자 설정입니다.': 'User settings such as language, theme, shortcuts, presets, and workspace folder location.',
    '개인정보 삭제': 'Delete Private Info',
    'API 키 같은 민감 정보입니다.': 'Sensitive information such as API keys.',
    '삭제할 항목 없음': 'No Items to Delete',
    '삭제할 수 있는 항목이 없습니다.': 'There are no deletable items.',
    '이 항목을 삭제합니다. 이 작업은 되돌릴 수 없습니다.': 'This item will be deleted. This cannot be undone.',
    '이 항목은 자동 정리 대상이 아니며, 사용자가 직접 누를 때만 삭제됩니다.': 'This item is not part of automatic cleanup and is deleted only when the user explicitly presses delete.',
    '삭제 후 API 키를 다시 설정해야 할 수 있습니다.': 'After deletion, you may need to set API keys again.',
    '삭제 확인': 'Confirm Deletion',
    '폴더 열기': 'Open Folder',
    '작업 폴더 캐시와 AppData 캐시는 자동 정리 대상입니다. 최근 프로젝트 정보, 설정 정보, 개인정보는 사용자가 직접 누를 때만 삭제합니다.': 'Workspace cache and AppData cache are automatic cleanup targets. Recent project info, settings info, and private info are deleted only when the user explicitly presses delete.',
    '관리': 'Manage',
    '사용자 데이터 및 임시파일 정리': 'User Data and Temporary File Cleanup',
}
UI_KO_EN.update(_G_STEP_CLEANUP_SIMPLIFIED_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _G_STEP_CLEANUP_SIMPLIFIED_KO_EN.items()})
SHORTCUT_TR_KO_EN.update({
    '사용자 데이터 및 임시파일 정리': 'User Data and Temporary File Cleanup',
})
# English reverse shortcut table is not used; shortcut translation is KO -> EN only.

# S step: separate workspace folder size manager from temporary/cache cleanup
_S_STEP_WORKSPACE_SIZE_MANAGER_KO_EN = {
    '작업 폴더 용량 관리': 'Workspace Folder Size Manager',
    '작업 폴더는 .ysbg 파일을 열어 작업할 때 생성되는 작업 공간입니다. 삭제해도 .ysbg 파일 자체는 삭제되지 않지만, 저장되지 않은 작업 내용은 사라질 수 있습니다. 현재 열려 있는 작업 폴더는 삭제할 수 없습니다.': 'Workspace folders are work areas created when opening .ysbg files. Deleting them does not delete the .ysbg file itself, but unsaved work may be lost. The currently open workspace folder cannot be deleted.',
    '작업 폴더 위치': 'Workspace Folder Location',
    '전체 폴더 열기': 'Open Root Folder',
    '수정': 'Modified',
    '현재 열림': 'Currently Open',
    '프로젝트 폴더': 'Project Folder',
    '표시할 작업 폴더가 없습니다.': 'No workspace folders to display.',
    '총': 'Total',
    '이 작업 폴더를 삭제합니다. 이 작업은 되돌릴 수 없습니다.': 'This workspace folder will be deleted. This cannot be undone.',
    '작업 폴더 삭제 확인': 'Confirm Workspace Folder Deletion',
    '작업 폴더를 삭제하지 못했습니다.': 'Could not delete the workspace folder.',
    '삭제할 수 없음': 'Cannot Delete',
    '현재 열려 있는 작업 폴더는 삭제할 수 없습니다.': 'The currently open workspace folder cannot be deleted.',
    '실행 캐시와 임시 데이터는 자동 정리할 수 있고, 최근 프로젝트/설정/개인정보는 사용자가 직접 누를 때만 삭제합니다. 작업 폴더 용량은 별도의 작업 폴더 용량 관리에서 확인합니다.': 'Runtime cache and temporary data can be cleaned automatically; recent projects, settings, and private information are deleted only when the user explicitly presses delete. Workspace folder size is handled in the separate workspace folder size manager.',
    '자동 정리 대상은 AppData 실행 캐시와 임시 데이터뿐입니다. 작업 폴더는 별도 관리창에서 직접 삭제합니다.': 'Only AppData runtime cache and temporary data are included in automatic cleanup. Workspace folders are deleted manually in a separate manager.',
    'AppData 실행 캐시와 임시 데이터는 자동 정리 대상입니다. 최근 프로젝트 정보, 설정 정보, 개인정보는 사용자가 직접 누를 때만 삭제합니다.': 'AppData runtime cache and temporary data are automatic cleanup targets. Recent project info, settings info, and private info are deleted only when the user explicitly presses delete.',
    '.ysbg를 열어 작업할 때 생성되는 실제 작업 폴더들을 날짜순으로 보고, 폴더별 용량 확인/열기/삭제를 직접 관리합니다.': 'View actual workspace folders created when opening .ysbg files by date, and manage size/open/delete per folder manually.',
}
UI_KO_EN.update(_S_STEP_WORKSPACE_SIZE_MANAGER_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _S_STEP_WORKSPACE_SIZE_MANAGER_KO_EN.items()})
SHORTCUT_TR_KO_EN.update({
    '작업 폴더 용량 관리': 'Workspace Folder Size Manager',
})

# Z step: same-position paste shortcut label
SHORTCUT_TR_KO_EN.update({
    "원위치 붙여넣기": "Paste at Same Position",
})


# v2.4.0 unified translation import translations
UI_KO_EN.update({
    '선택한 번역문 파일명과 일치하는 페이지를 찾지 못했습니다.': 'No page matched the selected translation file names.',
})
UI_EN_KO = {en: ko for ko, en in UI_KO_EN.items()}


# v2.4.0 temp/work sessions cleanup row translations
UI_KO_EN.update({
    '임시 작업/복구 캐시 삭제': 'Delete Temporary Work/Recovery Cache',
    '저장되지 않은 작업 복구용 temp와 work_sessions 캐시입니다. 현재 열려 있는 작업은 제외됩니다.': 'Temporary temp and work_sessions recovery cache for unsaved work. The currently open work is excluded.',
    '임시 작업/복구 캐시는 용량이 크게 커질 수 있으므로 최상단에 표시합니다. 현재 열려 있는 작업은 삭제 대상에서 제외됩니다. 실제 작업 폴더 용량은 별도의 작업 폴더 용량 관리에서 확인합니다.': 'Temporary work/recovery cache can grow very large, so it is shown at the top. The currently open work is excluded from deletion. Check actual work folder sizes in the separate Work Folder Size Manager.',
    '자동 정리 대상은 AppData 실행 캐시뿐입니다. 임시 작업/복구 캐시와 작업 폴더는 사용자가 직접 확인하고 삭제합니다.': 'Automatic cleanup only targets AppData runtime cache. Temporary work/recovery cache and work folders must be checked and deleted manually.',
    '현재 열려 있는 작업은 제외되지만, 다른 저장되지 않은 복구 작업은 사라질 수 있습니다.': 'The currently open work is excluded, but other unsaved recovery work may be removed.',
})
UI_EN_KO = {en: ko for ko, en in UI_KO_EN.items()}


# v2.4.0 temp/work sessions auto cleanup wording translations
UI_KO_EN.update({
    '자동 정리 대상이지만 용량이 클 수 있어 직접 삭제할 수도 있습니다. 현재 열려 있는 작업은 제외됩니다.': 'This is automatically cleaned up, but it can grow large, so you can also delete it manually. The currently open work is excluded.',
    '임시 작업/복구 캐시는 자동 정리되지만 용량이 크게 커질 수 있어 최상단에 표시합니다. 현재 열려 있는 작업은 삭제 대상에서 제외됩니다. 실제 작업 폴더 용량은 별도의 작업 폴더 용량 관리에서 확인합니다.': 'Temporary work/recovery cache is cleaned up automatically, but it can grow very large, so it is shown at the top. The currently open work is excluded from deletion. Check actual work folder sizes in the separate Work Folder Size Manager.',
    '자동 정리 대상은 AppData 실행 캐시와 오래된 임시 작업/복구 캐시입니다. 실제 작업 폴더는 사용자가 직접 확인하고 삭제합니다.': 'Automatic cleanup targets AppData runtime cache and old temporary work/recovery cache. Actual work folders must be checked and deleted manually.',
})
UI_EN_KO = {en: ko for ko, en in UI_KO_EN.items()}

# v2.4.0 crash report package helper (Stage 1)
_V240_BUG_REPORT_UI_KO_EN = {
 '선택 대사 주변 간이 맵 프리뷰 표시': 'Show Local Map Preview Around Selected Dialogue',
 '현재 선택된 대사의 이벤트 좌표를 중심으로 주변 15x10칸을 잘라 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다.': 'Shows a 15x10 tile area around the event coordinates of the selected dialogue. It does not modify the actual game JSON.',
 '검수용 간이 맵 프리뷰/보조선/이벤트 위치/이벤트 이름 표시를 켜고 끕니다. 간이 맵 프리뷰는 선택된 대사의 이벤트 주변을 격자와 이벤트 점으로 보여주는 1단계 기능이며, 실제 게임 JSON은 바꾸지 않습니다. 쯔꾸르붕이에서는 역식붕이식 텍스트 객체를 맵 위에 직접 만들지 않고, 대사는 게임식 대사창/선택지 프리뷰와 우측 표에서만 표시합니다.': 'Toggle the review-only local map preview, helper lines, event positions, and event names. The local map preview is a stage-1 feature that shows the selected dialogue event area with a grid and event dots, and it does not modify the actual game JSON. In YSB Game Editor, dialogue is not created as YSB typesetting text objects on the map; it is shown only in the game-style message/choice preview and the table on the right.',
 '⚠️ 쯔꾸르 선택 프리뷰 갱신 실패: {error}': '⚠️ Failed to refresh Maker selection preview: {error}',
    "치명적 오류 보고": "Fatal Error Report",
    "이전 실행에서 치명적인 오류가 감지되었습니다.": "A fatal error was detected during the previous run.",
    "문제 해결을 위해 최근 로그를 묶어 개발자에게 보낼 수 있습니다. 프로젝트 파일과 작업 이미지는 자동으로 포함하지 않습니다.": "You can package recent logs and send them to the developer for troubleshooting. Project files and work images are not included automatically.",
    "오류 시각": "Error time",
    "오류 종류": "Error type",
    "오류 내용": "Error message",
    "메일 제목": "Email subject",
    "예: 텍스트 이동 중 튕김": "Example: Crash while moving text",
    "상세 설명": "Details",
    "어떤 작업 중이었는지 적어주세요.": "Please describe what you were doing.",
    "최근 로그 포함": "Include recent logs",
    "사용자 경로를 가능한 한 가려서 포함": "Redact user paths where possible",
    "포함 예정 로그": "Logs to include",
    "최근 로그를 찾지 못했습니다.": "No recent logs were found.",
    "생성 후 메일 작성창을 열고, 로그 ZIP/EML/본문 TXT가 있는 폴더를 같이 엽니다. 실제 전송은 사용자가 직접 확인한 뒤 진행합니다.": "After creation, the email compose window and the folder containing the log ZIP/EML/body TXT will open. The user must review and send the email manually.",
    "생성 후 작성 중 메일용 EML 초안을 열고, 로그 ZIP/본문 TXT가 있는 폴더를 같이 엽니다. EML 초안이 작성창으로 열리면 보내기만 누르면 됩니다. 실제 전송은 사용자가 직접 확인한 뒤 진행합니다.": "After creation, an unsent EML draft and the folder containing the log ZIP/body TXT will open. If the EML draft opens in a compose window, you can review it and press Send. The user must review and send the email manually.",
    "생성 후 제목별 버그 리포트 폴더를 만들고, 그 안에 작성 중 메일용 EML 초안/로그 ZIP/본문 TXT를 넣습니다. EML 초안이 작성창으로 열리면 보내기만 누르면 됩니다. 실제 전송은 사용자가 직접 확인한 뒤 진행합니다.": "After creation, a title-based bug report folder will be created, containing the unsent EML draft, log ZIP, and body TXT. If the EML draft opens in a compose window, you can review it and press Send. The user must review and send the email manually.",
    "리포트 패키지 만들기": "Create report package",
    "다음에 다시 묻기": "Ask again next time",
    "이번 오류 다시 묻지 않기": "Don't ask again for this error",
    "버그 리포트 패키지를 만들었습니다.": "Bug report package created.",
    "받는 사람": "To",
    "제목": "Subject",
    "메일 본문은 클립보드에도 복사했습니다.": "The email body was also copied to the clipboard.",
    "EML 초안이 작성창으로 열리면 내용을 확인한 뒤 보내기만 누르면 됩니다.": "If the EML draft opens in a compose window, review it and press Send.",
    "메일 작성창이 열리지 않으면 TXT 내용을 복사하고 ZIP을 첨부해서 보내주세요.": "If the email compose window does not open, copy the TXT contents and attach the ZIP manually.",
    "버그 리포트 생성 완료": "Bug Report Created",
}
UI_KO_EN.update(_V240_BUG_REPORT_UI_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _V240_BUG_REPORT_UI_KO_EN.items()})


# v2.4.0 text effect preview toggle
_TEXT_EFFECT_PREVIEW_TOGGLE_KO_EN = {
    "텍스트 이펙트 미리보기": "Text Effect Preview",
    "후광, 그림자, 2중 획 같은 무거운 텍스트 효과를 작업 화면에 표시합니다. 끄면 화면 조작이 가벼워지며 최종 출력에는 영향을 주지 않습니다.": "Shows heavy text effects such as glow, shadow, and secondary stroke in the editor preview. Turning this off can improve navigation performance and does not affect final export.",
    "후광, 그림자, 2중 획 같은 무거운 텍스트 효과를 현재 페이지 작업 화면에 표시합니다. 끄면 이 페이지의 화면 조작이 가벼워지며 최종 출력에는 영향을 주지 않습니다.": "Shows heavy text effects such as glow, shadow, and secondary stroke on the current page editor preview. Turning this off can improve navigation performance for this page and does not affect final export.",
    "텍스트 이펙트 미리보기 켜짐": "Text effect preview enabled",
    "텍스트 이펙트 미리보기 꺼짐 - 최종 출력에는 영향 없음": "Text effect preview disabled - final export is not affected",
}
UI_KO_EN.update(_TEXT_EFFECT_PREVIEW_TOGGLE_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _TEXT_EFFECT_PREVIEW_TOGGLE_KO_EN.items()})

# v2.4.0 export output render options
_OUTPUT_RENDER_OPTIONS_KO_EN = {
    "최종 출력 이미지와 클린본의 저장 형식, 그리고 출력할 때 사용할 텍스트 렌더 품질을 선택합니다. 형식을 바꿔 다시 출력하면 같은 이름의 기존 PNG/JPG/WebP 파일은 새 형식 파일로 교체됩니다.": "Choose the save format for final output and clean images, and the text render quality used for export. If you change the format and export again, existing PNG/JPG/WebP files with the same name will be replaced by the new format file.",
    "텍스트 출력 렌더": "Text export render",
    "출력 시 텍스트를 더 큰 임시 캔버스에 렌더링한 뒤 축소해 획과 후광 가장자리를 부드럽게 만듭니다. 작업 화면 속도에는 영향이 없고, 배율이 높을수록 출력 시간이 늘어날 수 있습니다.": "Renders text on a larger temporary canvas during export and downsamples it to smooth stroke and glow edges. This does not affect editor performance; higher scales can take longer to export.",
    "기본 렌더 (1x)": "Standard render (1x)",
    "고품질 렌더 (2x)": "High quality render (2x)",
    "최고품질 렌더 (3x)": "Best quality render (3x)",
    "실험적 렌더 (4x)": "Experimental render (4x)",
    "↩️ 출력 취소": "↩️ Export cancelled",
    "↩️ 일괄 출력 취소": "↩️ Batch export cancelled",
}
UI_KO_EN.update(_OUTPUT_RENDER_OPTIONS_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _OUTPUT_RENDER_OPTIONS_KO_EN.items()})

# YSB Maker Editor / RPG Maker import branch strings
_MAKER_IMPORT_KO_EN = {
    '게임 가져오기': 'Import Game',
    '가져올 RPG Maker MV/MZ JSON 게임 폴더 선택': 'Select RPG Maker MV/MZ JSON Game Folder to Import',
    '게임 가져오기 실패': 'Failed to Import Game',
    '쯔꾸르 게임을 가져오지 못했습니다.': 'Could not import the RPG Maker game.',
    '게임 다시 가져오기': 'Re-import Game',
    '현재 프로젝트의 페이지 구성을 새 게임 분석 결과로 교체할까요?': 'Replace the current project page structure with the new game analysis result?',
    '기존 페이지/텍스트 작업은 새 맵 페이지로 바뀝니다. 원본 게임은 프로젝트 안에 다시 클론됩니다.': 'Existing page/text work will be replaced with new map pages. The source game will be cloned into the project again.',
    '교체': 'Replace',
    '취소': 'Cancel',
    '게임 분석': 'Analyze Game',
    '일괄 게임 분석': 'Batch Analyze Game',
    '프로젝트 이름과 생성 위치를 먼저 확정하고, 게임 클론을 넣을 작업 폴더를 만듭니다. 이후 [게임 가져오기]로 맵 페이지를 생성합니다.': 'Choose the project name and location first, then create an empty .ysbg project for the game clone. Use [Import Game] afterward to create map pages.',
    '게임은 작업 폴더 안에 클론으로 가져옵니다.': 'The game is imported as a clone inside the work folder.',
    '엔진 자동 감지': 'Engine auto-detected',
    '신뢰도': 'confidence',
    '엔진 감지 참고': 'Engine detection note',
    'OCR 대신 MapXXX.json을 분석해 맵 탭과 텍스트 행을 만들었습니다.': 'Analyzed MapXXX.json instead of OCR to create map tabs and text rows.',
    '게임을 가져오는 중입니다...': 'Importing game...',
    '게임 폴더를 가져오는 중입니다...\n잠시만 기다려 주세요.': 'Importing the game folder...\nPlease wait.',
    '작업 폴더를 준비하는 중입니다...': 'Preparing the work folder...',
    '게임 파일을 복사하고 맵 데이터를 분석하는 중입니다...\n게임 크기에 따라 시간이 걸릴 수 있습니다.': 'Copying game files and analyzing map data...\nThis may take a while depending on the game size.',
    '맵과 대사표를 준비하는 중입니다...': 'Preparing maps and the dialogue table...',
    '프리뷰와 대사표를 여는 중입니다...': 'Opening the preview and dialogue table...',
}
UI_KO_EN.update(_MAKER_IMPORT_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _MAKER_IMPORT_KO_EN.items()})

# YSB Maker Editor / project preview font settings
_MAKER_PREVIEW_FONT_KO_EN = {
    '쯔꾸르 프리뷰 폰트 설정': 'RPG Maker Preview Font Settings',
    '쯔꾸르 맵/메시지 프리뷰와 가져온 텍스트 아이템에 적용할 프로젝트 단위 폰트, 크기, 너비, 행간, 자간을 관리합니다.': 'Manage the project-level font, size, width, line spacing, and letter spacing applied to RPG Maker map/message previews and imported text items.',
    '쯔꾸르 프리뷰 폰트 설정을 열 수 없습니다.': 'Could not open RPG Maker preview font settings.',
    '쯔꾸르 프리뷰 폰트 설정은 프로젝트를 연 뒤 사용할 수 있습니다.': 'RPG Maker preview font settings can be used after opening a project.',
    '쯔꾸르 프로젝트 아님': 'Not an RPG Maker Project',
    '현재 프로젝트에는 쯔꾸르 맵 페이지 정보가 없습니다. 게임 가져오기 후 사용해 주세요.': 'The current project has no RPG Maker map page information. Use it after importing a game.',
    '맵/메시지 프리뷰와 쯔꾸르 텍스트 아이템에 적용할 프로젝트 단위 폰트 기준값입니다. 확인을 누르면 저장하고 현재 화면을 갱신합니다. 닫기나 X를 누르면 저장하지 않습니다.': 'Project-level font baseline values applied to map/message previews and RPG Maker text items. OK saves and refreshes the current screen. Close or X exits without saving.',
    '기본 폰트': 'Default Font',
    '프리뷰 메시지창과 가져온 쯔꾸르 텍스트 아이템에 적용할 기본 글꼴입니다.': 'The default font applied to preview message windows and imported RPG Maker text items.',
    '폰트 파일': 'Font File',
    '선택 안 함': 'Not selected',
    '찾기': 'Browse',
    '게임 폴더나 별도 폰트 파일을 직접 지정할 때 사용합니다. 지정하면 Qt에 폰트를 등록하고 가능한 경우 폰트 이름을 자동으로 맞춥니다.': 'Use this to specify a font file from the game folder or elsewhere. When selected, the font is registered in Qt and the font name is matched when possible.',
    '폰트 파일 선택': 'Select Font File',
    'Font Files (*.ttf *.otf *.ttc);;All Files (*.*)': 'Font Files (*.ttf *.otf *.ttc);;All Files (*.*)',
    '게임 화면 너비': 'Game Screen Width',
    '왼쪽 프리뷰가 재현할 RPG Maker 게임 내부 화면 너비입니다. 오른쪽 패널 크기와 무관하게 이 값으로 줄내림을 계산합니다.': 'The internal RPG Maker game screen width reproduced by the left preview. Line wrapping is calculated from this value regardless of the right panel size.',
    '게임 화면 높이': 'Game Screen Height',
    '왼쪽 프리뷰가 재현할 RPG Maker 게임 내부 화면 높이입니다. MZ 커스텀 해상도 게임은 이 값이 특히 중요합니다.': 'The internal RPG Maker game screen height reproduced by the left preview. This is especially important for MZ games with custom resolution.',
    '기본 글자 크기': 'Default Font Size',
    '대사 프리뷰의 기본 글자 크기입니다.': 'Default font size for dialogue previews.',
    '이름창 글자 크기': 'Name Window Font Size',
    '이름창/화자 표시를 별도로 렌더링할 때 사용할 크기입니다. 이후 실제 이름창 프리뷰와 연결됩니다.': 'Size used when rendering name windows/speaker labels separately. This will later be connected to the real name-window preview.',
    '선택지 글자 크기': 'Choice Font Size',
    'Show Choices 항목에 적용할 글자 크기입니다.': 'Font size applied to Show Choices items.',
    '폰트 너비': 'Font Width',
    '문자의 가로 비율입니다. 한글이 대사창에서 너무 넓거나 좁게 보일 때 조절합니다.': 'Horizontal character scale. Adjust this when Korean looks too wide or too narrow in the message window.',
    '폰트 높이': 'Font Height',
    '문자의 세로 비율입니다. 실제 메시지창 느낌에 맞게 조절합니다.': 'Vertical character scale. Adjust this to match the feel of the actual message window.',
    '메시지창 기준 너비': 'Message Window Base Width',
    '실제 게임 화면 안의 메시지창 폭입니다. 줄내림은 이 폭을 기준으로 고정 계산됩니다.': 'The message window width inside the actual game screen. Line wrapping is fixed to this width.',
    '메시지창 바깥 여백': 'Message Window Outer Margin',
    '화면 가장자리와 메시지창 사이의 바깥 여백입니다.': 'Outer margin between the screen edge and the message window.',
 '메시지창 표시 줄 수': 'Message Window Visible Lines',
 '프리뷰 메시지창에 한 번에 표시할 줄 수입니다. 이 값을 넘으면 줄넘침 경고를 표시합니다.': 'Number of lines shown in the preview message window at once. If the text exceeds this value, an overflow warning is shown.',
 '번역문': 'Translation',
 '원문': 'Original',
 '⚠ 줄넘침 가능: {line_count}줄 / 표시 {max_lines}줄': '⚠ Possible overflow: {line_count} lines / showing {max_lines}',
    '메시지창 안쪽 여백': 'Message Window Padding',
    '프리뷰 텍스트 박스 높이를 계산할 때 사용하는 안쪽 여백입니다.': 'Inner padding used when calculating preview text box height.',
    '외곽선 두께': 'Outline Width',
    '메시지 텍스트 외곽선 두께입니다.': 'Outline width for message text.',
    '색상': 'Colors',
    '글자': 'Text',
    '외곽선': 'Outline',
    '#RRGGBB 형식으로 입력합니다. 색상 선택기는 이후 붙일 수 있게 입력칸으로 먼저 둡니다.': 'Enter values in #RRGGBB format. This is an input-first version so a color picker can be added later.',
    '쯔꾸르 프리뷰 폰트 설정 저장': 'Save RPG Maker Preview Font Settings',
    '쯔꾸르 프리뷰 폰트 설정을 저장하고 현재 화면을 갱신할까요?': 'Save RPG Maker preview font settings and refresh the current screen?',
    '쯔꾸르 프리뷰 폰트 설정 내보내기 취소': 'RPG Maker preview font settings save canceled',
    '쯔꾸르 프리뷰 폰트 설정 내보내기 완료': 'RPG Maker Preview Font Settings Saved',
    '쯔꾸르 프리뷰 폰트 설정이 저장되었습니다.': 'RPG Maker preview font settings have been saved.',
    '갱신된 텍스트': 'Updated text items',
    '쯔꾸르 프리뷰 이미지 갱신 일부 실패': 'Some RPG Maker preview images failed to refresh',
}
UI_KO_EN.update(_MAKER_PREVIEW_FONT_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _MAKER_PREVIEW_FONT_KO_EN.items()})

# YSB Maker Editor / write-back to cloned RPG Maker JSON
_MAKER_WRITEBACK_KO_EN = {
    '쯔꾸르 JSON 저장 실패': 'RPG Maker JSON Save Failed',
    '작업용 게임 JSON을 저장하지 못했습니다.': 'Could not save the working game JSON files.',
    '프로젝트 저장 확인': 'Confirm Project Save',
    '저장하지 않은 변경사항이 있습니다.\n저장할까요?': 'There are unsaved changes.\nSave now?',
    '저장': 'Save',
    '저장 안 함': "Don't Save",
    '프로젝트 저장이 완료되었습니다.\n\n작업 폴더와 작업용 게임 JSON을 저장했습니다.': 'Project save is complete.\n\nThe work folder and working game JSON files have been saved.',
    '프로젝트를 저장하지 못했습니다.': 'Could not save the project.',
    '현재 작업 폴더와 작업용 게임 JSON을 저장합니다.': 'Save the current work folder and working game JSON files.',
    '현재 작업 폴더와 작업용 게임 JSON을 저장합니다. 단축키: Ctrl+S': 'Save the current work folder and working game JSON files. Shortcut: Ctrl+S',
    '쯔꾸르 프로젝트 복사 실패': 'RPG Maker Project Copy Failed',
    '쯔꾸르 게임 클론과 메타데이터를 새 저장 위치로 복사하지 못했습니다.': 'Could not copy the RPG Maker game clone and metadata to the new save location.',
}
UI_KO_EN.update(_MAKER_WRITEBACK_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _MAKER_WRITEBACK_KO_EN.items()})


# YSB Game Editor / Maker text table columns
_MAKER_TEXT_TABLE_KO_EN = {
    '상태': 'Status',
    '사용자 지정': 'Manual',
    '이름창': 'Name Window',
    '\\N[n] 배우 참조': '\\N[n] Actor Reference',
    '배우 얼굴칩': 'Actor Face Graphic',
    '얼굴칩 파일명': 'Face Graphic Filename',
    '이벤트 이름': 'Event Name',
    '미확정': 'Unconfirmed',
    '화자 출처: {source} / 신뢰도 {confidence}%': 'Speaker source: {source} / confidence {confidence}%',
    '화자': 'Speaker',
    '타입': 'Type',
    '이벤트': 'Event',
    '메모': 'Memo',
    '전체': 'All',
    '현재 맵 텍스트': 'Current Map Text',
    '미번역': 'Untranslated',
    '번역완료': 'Translated',
    '대사': 'Dialogue',
    '선택지': 'Choice',
    '선택지 도움말': 'Choice Help',
    '스크롤문': 'Scrolling Text',
    '공통 이벤트': 'Common Event',
    '데이터베이스': 'Database',
    '플러그인': 'Plugin',
}
UI_KO_EN.update(_MAKER_TEXT_TABLE_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _MAKER_TEXT_TABLE_KO_EN.items()})

_MAKER_CHARACTER_PROMPT_KO_EN = {
    '쯔꾸르 캐릭터 프롬프트 관리': 'RPG Maker Character Prompt Manager',
    '쯔꾸르 캐릭터 프롬프트 관리를 열 수 없습니다.': 'Cannot open the RPG Maker character prompt manager.',
    '쯔꾸르 캐릭터 프롬프트는 프로젝트를 연 뒤 사용할 수 있습니다.': 'RPG Maker character prompts can be used after opening a project.',
    '화자별 말투, 성격, 관계, 번역 지침을 프로젝트 단위로 저장합니다. 확인을 누르면 maker_meta에 저장되고, 닫기나 X를 누르면 저장하지 않습니다.': 'Save tone, personality, relationships, and translation instructions per speaker at the project level. OK saves them to maker_meta; Close or X exits without saving.',
    '공통 번역 지침': 'Common Translation Instructions',
    '모든 캐릭터 프롬프트 앞에 붙일 프로젝트 공통 지침입니다. 예: 고유명사 유지, 자연스러운 한국어, 제어문자 보존 등.': 'Project-wide instructions placed before every character prompt, such as keeping proper nouns, natural Korean, or preserving control codes.',
    '예: 일본어를 자연스러운 한국어로 번역하고, RPG Maker 제어문자는 절대 바꾸지 마세요.': 'Example: Translate Japanese into natural Korean and never change RPG Maker control codes.',
    '화자 목록': 'Speaker List',
    '추가': 'Add',
    '삭제': 'Delete',
    '이 캐릭터 프롬프트 사용': 'Use this character prompt',
    '표시 이름': 'Display Name',
    '프롬프트에 표시할 캐릭터 이름입니다. 비워두면 화자명을 그대로 사용합니다.': 'Character name shown in prompts. If empty, the speaker name is used as-is.',
    '말투': 'Tone',
    '반말/존댓말, 밝음/무뚝뚝함, 말끝 습관 같은 말투 지침입니다.': 'Tone rules such as casual/polite speech, bright/blunt style, or sentence-ending habits.',
    '성격': 'Personality',
    '캐릭터의 성격, 감정 표현 방식, 대사 리듬을 적습니다.': 'Character personality, emotional expression style, and dialogue rhythm.',
    '관계/상황': 'Relationship/Context',
    '주인공과의 관계나 번역에 영향을 주는 기본 문맥을 적습니다.': 'Base context that affects translation, such as the relationship with the protagonist.',
    '번역 규칙': 'Translation Rules',
    '이 캐릭터에게 적용할 번역 규칙입니다. 예: 짧게 말함, 이름은 원문 유지 등.': 'Translation rules for this character, such as speaking briefly or keeping names as-is.',
    '금지/주의 표현': 'Forbidden/Caution Expressions',
    '피해야 할 단어, 어색한 말투, 쓰면 안 되는 표현을 적습니다.': 'Words, awkward tones, or expressions to avoid.',
    '메모': 'Memo',
    '검수 메모나 나중에 참고할 내용을 적습니다.': 'Review notes or reference notes for later.',
    '사용 안 함': 'Disabled',
    '화자 추가': 'Add Speaker',
    '화자 이름:': 'Speaker name:',
    '화자 프롬프트 삭제': 'Delete Speaker Prompt',
    "'{key}' 캐릭터 프롬프트를 삭제할까요?\n현재 텍스트의 화자명은 지워지지 않고, 프롬프트 설정만 삭제됩니다.": "Delete the character prompt for '{key}'?\nCurrent speaker names in text rows will remain; only the prompt settings are deleted.",
    '캐릭터 프롬프트 저장 완료': 'Character Prompt Saved',
    '쯔꾸르 캐릭터 프롬프트 설정이 저장되었습니다.': 'RPG Maker character prompt settings have been saved.',
    '화자별 말투, 성격, 관계, 번역 지침을 프로젝트 단위로 관리합니다. AI 번역 시 캐릭터 문맥을 붙이는 기반입니다.': 'Manage tone, personality, relationships, and translation instructions per speaker at the project level. This is the basis for adding character context to AI translation.',
    '쯔꾸르 캐릭터별 번역 프롬프트 관리창을 엽니다.': 'Open the RPG Maker per-character translation prompt manager.',
}
UI_KO_EN.update(_MAKER_CHARACTER_PROMPT_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _MAKER_CHARACTER_PROMPT_KO_EN.items()})


_MAKER_CHARACTER_PROFILE_KO_EN = {

    '게임 이미지 투명도 반영': 'Follow game image opacity',
    '꺼두면 번역자가 캐릭터를 보기 쉽도록 스탠딩/표시 이미지를 항상 불투명하게 보여줍니다. 실제 게임 JSON은 바꾸지 않습니다.': 'When off, standing/picture images are shown fully opaque for translator readability. This does not modify the actual game JSON.',
    '검수용 보조선/위치 표시입니다. 스탠딩/표시 이미지는 번역 작업을 위해 기본 불투명으로 보여주며, 필요할 때만 게임 투명도 반영을 켜세요.': 'Auxiliary preview markers. Standing/picture images are shown opaque by default for translation work; enable game opacity only when needed.',
    '쯔꾸르 캐릭터 프로필': 'RPG Maker Character Profiles',
    '쯔꾸르 캐릭터 프로필은 프로젝트를 연 뒤 사용할 수 있습니다.': 'RPG Maker character profiles can be used after opening a project.',
    '쯔꾸르 캐릭터 프로필 창을 열 수 없습니다.': 'Cannot open the RPG Maker character profile window.',
    '캐릭터 프로필을 분석하지 못했습니다.': 'Could not analyze character profiles.',
    '분석된 캐릭터가 없습니다. 먼저 게임 가져오기/텍스트 분석을 확인해 주세요.': 'No analyzed characters were found. Please check game import/text analysis first.',
    '현재 게임에서 발견한 캐릭터, 이미지 후보, 대표 대사, 등장 위치를 모아 보여줍니다. 자동 매칭은 근거와 신뢰도 기반 후보이며, 최종 말투/성격 프롬프트는 사용자가 확정합니다.': 'Shows characters, image candidates, sample lines, and appearances found in the current game. Automatic matches are evidence/confidence-based candidates; the user confirms the final tone/personality prompt.',
    '캐릭터 목록': 'Character List',
    '프로필 재분석': 'Reanalyze Profiles',
    '이미지 없음': 'No Image',
    '종류': 'Type',
    '파일': 'File',
    '신뢰도': 'Confidence',
    '횟수': 'Count',
    '근거': 'Evidence',
    '이미지 후보': 'Image Candidates',
    '플러그인 조합 스탠딩': 'Plugin Composite Standing Image',
    '등장 위치': 'Appearances',
    '맵/페이지': 'Map/Page',
    '이벤트': 'Event',
    '프로필': 'Profile',
    '대표 대사': 'Sample Lines',
    '번역 프롬프트': 'Translation Prompt',
    '괄호 안 숫자는 현재 파싱된 대표 텍스트 수입니다.': 'The number in parentheses is the currently parsed text count.',
    '캐릭터 프로필 재분석 실패': 'Character Profile Reanalysis Failed',
    '캐릭터 프로필 저장 완료': 'Character Profiles Saved',
    '쯔꾸르 캐릭터 프로필/프롬프트 설정이 저장되었습니다.': 'RPG Maker character profiles/prompt settings have been saved.',
    '쯔꾸르 캐릭터 프로필 창을 엽니다.': 'Open the RPG Maker character profile window.',
}
UI_KO_EN.update(_MAKER_CHARACTER_PROFILE_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _MAKER_CHARACTER_PROFILE_KO_EN.items()})

_MAKER_AI_TRANSLATION_KO_EN = {
    '쯔꾸르 AI 번역: 캐릭터 프롬프트와 제어문자 보호를 적용합니다.': 'RPG Maker AI translation: applying character prompts and control-code handling.',
    '캐릭터 프롬프트/제어문자 보호 적용': 'Apply character prompt / control-code handling',
    'RPG Maker 제어문자 보호': 'RPG Maker Control-code Handling',
}
UI_KO_EN.update(_MAKER_AI_TRANSLATION_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _MAKER_AI_TRANSLATION_KO_EN.items()})

_MAKER_TRANSLATION_SETTINGS_KO_EN = {
    '쯔꾸르 번역 설정': 'RPG Maker Translation Settings',
    '쯔꾸르 번역 설정을 열 수 없습니다.': 'Cannot open RPG Maker translation settings.',
    '쯔꾸르 번역 설정은 프로젝트를 연 뒤 사용할 수 있습니다.': 'RPG Maker translation settings can be used after opening a project.',
    '현재 프로젝트에는 쯔꾸르 페이지 정보가 없습니다. 게임 가져오기 후 사용해 주세요.': 'The current project has no RPG Maker page information. Please import a game first.',
    'AI 번역 요청에 넣는 원문을 정리하는 프로젝트 단위 설정입니다. 원본 JSON과 오른쪽 원문 표시는 바꾸지 않고, AI에 보내는 텍스트만 정규화합니다.': 'Project-level settings for cleaning source text sent to AI translation. The original JSON and source table display are not changed; only the text sent to AI is normalized.',
    'AI 번역 시 원문 줄내림 제거': 'Remove source line breaks for AI translation',
    'RPG Maker 대사는 여러 401/405 줄로 나뉘어 저장될 수 있습니다. 이 옵션은 번역 품질을 위해 AI 요청용 원문만 한 문장처럼 합칩니다.': 'RPG Maker dialogue may be stored across multiple 401/405 lines. This option joins only the source text sent to AI as a sentence for better translation quality.',
    '줄내림 제거 방식': 'Line-break removal mode',
    '자동 판단: CJK는 붙이고 영문/숫자 사이만 공백': 'Auto: join CJK directly, add spaces only between Latin/numbers',
    '항상 붙여쓰기: 일본어/한국어/중국어 중심': 'Always join directly: Japanese/Korean/Chinese focused',
    '항상 공백으로 합치기: 영어 중심': 'Always join with spaces: English focused',
    '기본값은 자동 판단입니다. 원문/번역문 저장 데이터 자체는 변경하지 않으며, AI 요청 직전에만 적용됩니다.': 'The default is Auto. It does not change stored source/translated data and is applied only right before AI translation requests.',
    '쯔꾸르 번역 설정 저장 완료': 'RPG Maker Translation Settings Saved',
    'AI 번역용 원문 줄내림 정규화 설정이 저장되었습니다.': 'Source line-break normalization settings for AI translation have been saved.',
    '쯔꾸르 AI 번역: 캐릭터 프롬프트, 제어문자 보호, 원문 줄내림 정규화를 적용합니다.': 'RPG Maker AI translation: applying character prompts, control-code handling, and source line-break normalization.',
    '쯔꾸르 AI 번역용 원문 정규화 설정창을 엽니다.': 'Open RPG Maker AI translation source normalization settings.',
    '선택한 줄만 번역': 'Translate Selected Lines Only',
    '선택한 줄만 번역할까요?': 'Translate only the selected lines?',
    '현재 오른쪽 텍스트 표에서 줄이 선택되어 있습니다. 전체 대상이 아니라 선택한 줄만 번역합니다.\n\n대상: {count}줄': 'Lines are currently selected in the right text table. Only the selected lines will be translated instead of the full target set.\n\nTarget: {count} line(s)',
    '선택한 셀만 번역': 'Translate Selected Cells Only',
    '선택한 셀만 번역할까요?': 'Translate only the selected cells?',
    '현재 오른쪽 텍스트 표에서 셀이 선택되어 있습니다. 전체 대상이 아니라 선택한 셀에 해당하는 줄만 번역합니다.\n\n선택 셀: {cell_count}개 / 번역 대상: {target_count}줄': 'Cells are currently selected in the right text table. Only the rows corresponding to the selected cells will be translated instead of the full target set.\n\nSelected cells: {cell_count} / Translation targets: {target_count} line(s)',
    '선택한 셀 중 번역 가능한 원문/번역문 셀이 없습니다.': 'None of the selected cells are translatable source/translation cells.',
    '선택한 행 중 번역 가능한 원문이 없습니다.': 'None of the selected rows have translatable source text.',
    'AI 번역 요청에 넣는 쯔꾸르 원문을 정리합니다. 원본 데이터는 유지하고, 번역 품질을 위해 요청용 줄내림만 제거할 수 있습니다.': 'Clean RPG Maker source text sent to AI translation. Original data is preserved, and only request-time line breaks can be removed for translation quality.',
}
UI_KO_EN.update(_MAKER_TRANSLATION_SETTINGS_KO_EN)
UI_EN_KO.update({en: ko for ko, en in _MAKER_TRANSLATION_SETTINGS_KO_EN.items()})

# 쯔꾸르 프롬프트 통합 관리 / DB 시스템 번역 안전장치
UI_KO_EN.update({
    '쯔꾸르 프롬프트 관리': 'RPG Maker Prompt Manager',
    '공통 프롬프트, 캐릭터 프롬프트, 시스템/데이터베이스 프롬프트를 한곳에서 관리합니다. 확인을 누르면 저장되고, 닫기나 X를 누르면 저장하지 않습니다.': 'Manage common prompts, character prompts, and system/database prompts in one place. OK saves changes; Close or X exits without saving.',
    '공통 프롬프트': 'Common Prompt',
    '캐릭터 프롬프트': 'Character Prompt',
    '시스템 프롬프트': 'System Prompt',
    '공통 번역 프롬프트': 'Common Translation Prompt',
    'API 번역이 기본적으로 참조하는 공통 지침입니다. 일반 맵 대사와 데이터베이스 번역 모두에 영향을 줍니다.': 'Common instructions referenced by API translation by default. This affects both normal map dialogue and database translation.',
    '예: 일본어를 자연스러운 한국어로 번역하고, RPG Maker 제어문자와 치환 코드(%1, %2)는 절대 바꾸지 마세요.': 'Example: Translate Japanese into natural Korean and never change RPG Maker control codes or placeholders (%1, %2).',
    '시스템/데이터베이스 번역 프롬프트': 'System/Database Translation Prompt',
    'System.json terms, States 메시지, 아이템/스킬 설명처럼 게임 UI와 전투 메시지를 번역할 때 붙는 전용 지침입니다. %1, %2 같은 치환 코드는 원문 그대로 API에 보내므로, 조사와 문장 길이 규칙을 여기 적어두면 안정적입니다. \\V[n] 같은 제어문자는 번역 요청에서 제외됩니다.': 'Dedicated instructions for translating game UI and battle messages such as System.json terms, States messages, and item/skill descriptions. Placeholders such as %1 and %2 are sent to the API as-is, so particle and sentence-length rules are safer when written here. Control codes such as \\V[n] are excluded from translation requests.',
    '예: 전투 메시지는 짧게 번역합니다. %1, %2는 절대 변경하지 않고, 필요한 조사는 은(는)/이(가)/을(를) 형태로 붙입니다.': 'Example: Keep battle messages short. Never change %1 or %2, and attach particles in safe forms such as 은(는), 이(가), 을(를).',
    '공통 프롬프트, 캐릭터 말투, 시스템/데이터베이스 번역 지침을 프로젝트 단위로 관리합니다.': 'Manage common prompts, character voices, and system/database translation instructions per project.',
    '프롬프트 저장 완료': 'Prompt Saved',
    '쯔꾸르 프롬프트 설정이 저장되었습니다.': 'RPG Maker prompt settings have been saved.',
})

# 쯔꾸르붕이 설정/옵션 통합창 재구성 문구
_MAKER_SETTINGS_OVERVIEW_REORDER_KO_EN = {
    '번역 API 주소, 키, 모델명 같은 외부 API 설정을 관리합니다. 유료 API 정보가 들어갈 수 있으니 저장 전 확인이 필요합니다.': 'Manage external API settings such as translation API URLs, keys, and model names. Paid API information may be stored, so check before saving.',
    '상단 메뉴와 작업 기능에 연결된 단축키를 한곳에서 바꿉니다. 충돌 확인과 비활성화도 여기서 처리합니다.': 'Change shortcuts connected to the top menu and work features in one place. Conflicts and disabling are handled here as well.',
    '게임 대사에서 분석한 캐릭터/화자 정보를 확인하고 번역 말투 관리에 활용합니다.': 'Review character/speaker information analyzed from game dialogue and use it to manage translation voice.',
    '줄내림 옵션': 'Line Break Options',
    '게임 프리뷰 옵션': 'Game Preview Options',
    '게임 설정': 'Game Settings',
    '현재 프로젝트의 게임 제목, 해상도, 타일 크기, 대사창 기준값 같은 게임 기본 표시 정보를 확인하고 관리합니다.': 'Review and manage basic game display information such as game title, resolution, tile size, and message-window reference values for the current project.',
    '게임 갱신': 'Refresh Game',
    '현재 게임 JSON에서 대사를 다시 읽어 원문 기준과 번역문 칸을 갱신합니다. 기존 번역/메모는 가능한 한 보존합니다.': 'Read dialogue again from the current game JSON and update the source baseline and translation fields. Existing translations and notes are preserved where possible.',
}
UI_KO_EN.update(_MAKER_SETTINGS_OVERVIEW_REORDER_KO_EN)
try:
    UI_EN_KO.update({en: ko for ko, en in _MAKER_SETTINGS_OVERVIEW_REORDER_KO_EN.items()})
except Exception:
    pass
# 쯔꾸르붕이 폰트 변경 안내 문구
_MAKER_FONT_NOTICE_KO_EN = {
    '폰트 변경 안내': 'Font Change Notice',
    '프로그램을 껐다 켜면 변경한 폰트가 적용됩니다.': 'Restart the program to apply the changed font.',
}
UI_KO_EN.update(_MAKER_FONT_NOTICE_KO_EN)
try:
    UI_EN_KO.update({en: ko for ko, en in _MAKER_FONT_NOTICE_KO_EN.items()})
except Exception:
    pass



# 쯔꾸르붕이 위험 작업 확인 알림
_MAKER_DANGEROUS_CONFIRM_KO_EN = {
    '현재 페이지의 원문/번역문 TXT를 내보냅니다. 계속할까요?': 'Export the current page source/translation TXT. Continue?',
    '선택한 페이지들의 원문/번역문 TXT를 내보냅니다. 계속할까요?': 'Export source/translation TXT files for the selected pages. Continue?',
    '내보내기': 'Export',
    '현재 페이지의 원문/번역문 TXT 내보내기가 완료되었습니다.': 'Current page source/translation TXT export is complete.',
    '선택한 페이지들의 원문/번역문 TXT 내보내기가 완료되었습니다.': 'Selected page source/translation TXT export is complete.',
    '게임 JSON 갱신이 완료되었습니다.\n이번 작업 동안만 maker_game을 마스터로 읽었고, 완료 후에는 다시 프로그램 데이터가 마스터입니다.': 'Game JSON refresh is complete.\nmaker_game was used as the master only for this action. Program data is now the master again.',
    '위험한 작업입니다. 현재 게임 JSON을 기준으로 프로그램의 대사/DB 구조와 번역문을 다시 가져옵니다.\n\n게임 쪽 값이 프로그램의 기존 번역문을 덮어쓸 수 있습니다. 계속할까요?': 'This is a risky action. The program will re-import dialogue/DB structure and translations using the current game JSON as the source.\n\nValues from the game may overwrite existing program translations. Continue?',
}
UI_KO_EN.update(_MAKER_DANGEROUS_CONFIRM_KO_EN)
try:
    UI_EN_KO.update({en: ko for ko, en in _MAKER_DANGEROUS_CONFIRM_KO_EN.items()})
except Exception:
    pass

# 쯔꾸르붕이 프롬프트 역방향 테스트 탭
_MAKER_PROMPT_REVERSE_TEST_KO_EN = {
    '프롬프트 테스트': 'Prompt Test',
    '화자와 문장을 직접 넣어 실제로 어떤 공통/캐릭터/DB/단어장 프롬프트가 적용되는지 역방향으로 확인합니다. API 호출 없이 조립 결과만 보여줍니다.': 'Enter a speaker and text to reverse-check which common/character/DB/glossary prompts would be applied. This only shows the assembled prompt and does not call the API.',
    '번역 종류': 'Translation Type',
    '화자': 'Speaker',
    '맵': 'Map',
    '이벤트': 'Event',
    'DB': 'DB',
    'DB ID': 'DB ID',
    '필드': 'Field',
    '테스트 문장': 'Test Text',
    '예: リオラはポーションを手に入れた！': 'Example: リオラはポーションを手に入れた！',
    '사용 프롬프트 확인': 'Check Applied Prompt',
    '테스트 문장을 입력해 주세요.': 'Please enter a test text.',
    '프롬프트 테스트 준비 실패:': 'Prompt test setup failed:',
}
UI_KO_EN.update(_MAKER_PROMPT_REVERSE_TEST_KO_EN)
try:
    UI_EN_KO.update({en: ko for ko, en in _MAKER_PROMPT_REVERSE_TEST_KO_EN.items()})
except Exception:
    pass


# LM Studio 서버 연결 인터락 문구
_LM_STUDIO_INTERLOCK_KO_EN = {
    'LM Studio 연결 실패': 'LM Studio Connection Failed',
    'LM Studio Local Server에 연결할 수 없습니다.': 'Cannot connect to the LM Studio Local Server.',
    'LM Studio > Developer > Local Server에서 서버를 켠 뒤 다시 시도해 주세요.': 'Start the server in LM Studio > Developer > Local Server, then try again.',
    'LM Studio 서버는 켜져 있지만 로드된 모델이 없습니다.': 'The LM Studio server is running, but no model is loaded.',
    'LM Studio에서 모델을 로드한 뒤 다시 시도해 주세요.': 'Load a model in LM Studio, then try again.',
    '확인 주소': 'Check URL',
}
UI_KO_EN.update(_LM_STUDIO_INTERLOCK_KO_EN)
try:
    UI_EN_KO.update({en: ko for ko, en in _LM_STUDIO_INTERLOCK_KO_EN.items()})
except Exception:
    pass

API_TR_KO_EN.update({
    "LM Studio / Local OpenAI-Compatible": "LM Studio / Local OpenAI-Compatible",
    "LM Studio의 Developer 서버를 켠 뒤 사용할 수 있습니다. 기본 주소는 http://localhost:1234/v1 입니다. 모델은 LM Studio에서 먼저 다운로드/로드해야 합니다. API Key는 보통 비워도 됩니다.": "Use this after starting the LM Studio Developer server. The default address is http://localhost:1234/v1. Download/load a model in LM Studio first. API Key can usually be left empty.",
    "비워도 됨 / optional": "Optional / can be empty",
    "LM Studio에서 로드한 모델명": "Model name loaded in LM Studio",
    "LM Studio": "LM Studio",
})


# Gemini Flex / Batch 지연 번역 청크 현황 창
_GEMINI_DELAYED_TRANSLATION_KO_EN = {
    '청크': 'Chunk',
    '대상 범위': 'Target Range',
    '방식': 'Mode',
    '상태': 'Status',
    '경과 시간': 'Elapsed',
    '재시도 횟수': 'Retries',
    '재시도': 'Retry',
    '상세': 'Details',
    '{seconds}초': '{seconds}s',
    '{minutes}분 {seconds}초': '{minutes}m {seconds}s',
    '{hours}시간 {minutes}분': '{hours}h {minutes}m',
    '대기': 'Queued',
    '제출 중': 'Submitting',
    '제출됨': 'Submitted',
    '처리 중': 'Processing',
    '응답 대기': 'Waiting for Response',
    '결과 적용 중': 'Applying Result',
    '완료': 'Completed',
    '실패': 'Failed',
    '취소됨': 'Canceled',
    'Gemini 지연 번역 청크 현황': 'Gemini Delayed Translation Chunk Status',
    '{mode} 요청을 청크별로 처리합니다. 완료된 청크는 즉시 번역문에 반영됩니다. 작업 중에는 이 창만 조작할 수 있습니다.': '{mode} requests are processed chunk by chunk. Completed chunks are applied immediately. Only this window can be used while the task is running.',
    '실패 청크 전체 재시도': 'Retry All Failed Chunks',
    '작업 취소': 'Cancel Task',
    '전체 {total}개 · 완료 {completed}개 · 처리 중 {active}개 · 실패 {failed}개 · 대기 {waiting}개': 'Total {total} · Completed {completed} · Active {active} · Failed {failed} · Queued {waiting}',
    '번역 결과를 프로젝트에 적용하지 못했습니다.': 'Could not apply the translation result to the project.',
    '번역 결과 적용 실패': 'Failed to apply translation result',
    '모든 청크가 완료되어 번역문에 반영되었습니다. 확인을 눌러 작업 화면으로 돌아가세요.': 'All chunks have completed and were applied. Click OK to return to the workspace.',
    'Gemini 지연 번역 취소': 'Cancel Gemini Delayed Translation',
    '현재 지연 번역 작업을 취소할까요?\n\n이미 완료되어 반영된 청크는 유지합니다. 대기·처리 중인 청크는 중단하고, 뒤늦게 도착한 응답은 번역문에 반영하지 않습니다.': 'Cancel the current delayed translation task?\n\nChunks already completed and applied will be kept. Queued and active chunks will stop, and late responses will not be applied.',
    'Batch 작업 ID가 비어 있습니다.': 'The Batch job ID is empty.',
    'Batch 작업 ID를 받지 못했습니다.': 'No Batch job ID was returned.',
    'Batch 요청이 실패했습니다.': 'The Batch request failed.',
    '알 수 없는 API 오류': 'Unknown API error.',
    'Batch 작업이 실패했습니다.': 'The Batch job failed.',
    '✅ 지연 번역 청크 {chunk} 완료 및 즉시 반영': '✅ Delayed translation chunk {chunk} completed and applied immediately',
    '⚠️ 지연 번역 마무리 처리 실패: {error}': '⚠️ Failed to finalize delayed translation: {error}',
    '✅ Gemini 지연 번역 완료: 전체 {total}개 청크': '✅ Gemini delayed translation complete: {total} chunks',
    '⏹️ Gemini 지연 번역 취소: 완료 {completed}개 / 실패 {failed}개 / 전체 {total}개': '⏹️ Gemini delayed translation canceled: {completed} completed / {failed} failed / {total} total',
}
UI_KO_EN.update(_GEMINI_DELAYED_TRANSLATION_KO_EN)
try:
    UI_EN_KO.update({en: ko for ko, en in _GEMINI_DELAYED_TRANSLATION_KO_EN.items()})
except Exception:
    pass

API_TR_KO_EN.update({
    'Gemini Flex / Batch': 'Gemini Flex / Batch',
    '일반 번역 진행창 대신 청크 현황 창을 사용합니다. 완료된 청크는 즉시 반영되고, 실패한 청크만 다시 시도할 수 있습니다. 작업 중에는 다른 프로젝트 작업을 할 수 없습니다.': 'Uses a chunk status window instead of the normal translation progress window. Completed chunks are applied immediately, and only failed chunks can be retried. Other project work is unavailable while this task is running.',
    '요청 방식': 'Request Mode',
    'Flex API': 'Flex API',
    'Batch API': 'Batch API',
})

# Translation TXT streaming import progress / memory-safe sequential apply
_TRANSLATION_IMPORT_STREAM_KO_EN = {
    '선택 페이지 진행: {current}/{total}': 'Selected page progress: {current}/{total}',
    '현재 페이지: {page}': 'Current page: {page}',
    '현재 페이지 적용: {changed}개 / 전체 항목 {total}개': 'Current page applied: {changed} / {total} total items',
    '누적 적용: {count}개': 'Total applied: {count}',
    '텍스트 데이터가 없어 건너뜁니다.': 'Skipped because there is no text data.',
    'TXT 파일을 읽지 못했습니다: {error}': 'Could not read the TXT file: {error}',
    '번역문을 순차 적용하는 중...': 'Applying translations sequentially...',
    '현재 페이지 반영 완료': 'Current page applied',
    '현재 페이지 표와 행 높이를 갱신하는 중...': 'Refreshing the current page table and row heights...',
    '번역문 불러오기는 Undo를 지원하지 않습니다.': 'Translation import does not support Undo.',
    '▶️ 번역문 불러오기 시작: 대상 {pages}페이지 ({label}) / Undo 미지원': '▶️ Translation import started: {pages} page(s) ({label}) / Undo unavailable',
    '⚠️ 번역문 불러오기 화면 갱신 실패: {error}': '⚠️ Failed to refresh the translation import screen: {error}',
    '⏹️ 번역문 불러오기 취소: {count}개까지 반영 / Undo 미지원': '⏹️ Translation import canceled: {count} item(s) applied / Undo unavailable',
    '📥 번역문 불러오기 완료: {count}개 / Undo 미지원': '📥 Translation import complete: {count} item(s) / Undo unavailable',
    '텍스트 데이터 없음': 'No text data',
    '불러올 텍스트 번호 없음': 'No text IDs to import',
    '매칭 파일 없음': 'No matching file',
    'TXT 파일 핸들이 없습니다.': 'The TXT file handle is unavailable.',
    '맞는 텍스트 번호 없음': 'No matching text IDs',
    '변경된 번역문 없음': 'No translation changes',
    '{count}개 적용': '{count} item(s) applied',
}
UI_KO_EN.update(_TRANSLATION_IMPORT_STREAM_KO_EN)
try:
    UI_EN_KO.update({en: ko for ko, en in _TRANSLATION_IMPORT_STREAM_KO_EN.items()})
except Exception:
    pass


# Separate database glossary and user glossary editor
_GLOSSARY_SPLIT_KO_EN = {
    '자동 단어장에는 데이터베이스의 name 항목과 화자 번역 모드의 name 항목이 자동 반영됩니다.\n사용자 단어장은 원문과 번역문을 직접 등록하며, 저장하면 딕셔너리로 변환되어 번역 대상에 실제 등장한 항목만 API에 전달됩니다.': 'Database name fields and speaker-translation name fields are reflected automatically in the automatic glossary.\nThe user glossary stores source/translation pairs as a dictionary, and only entries that actually appear in the translation target are sent to the API.',
    '데이터베이스의 name 항목과 화자 번역 모드의 name 항목이 자동 반영됩니다.': 'Database name fields and speaker-translation name fields are reflected automatically.',
    '자동 단어장': 'Automatic glossary',
    '사용자 단어장': 'User glossary',
    '원문': 'Source',
    '번역문': 'Translation',
    '원문과 번역문을 한 쌍씩 추가합니다. 같은 원문을 다시 추가하면 기존 번역문을 갱신합니다. 같은 원문이 겹치면 사용자 단어장이 우선입니다.': 'Add source and translation as pairs. Adding the same source again updates its translation. When the same source appears in both glossaries, the user glossary takes priority.',
    '추가 / 갱신': 'Add / Update',
    '등록 항목: {count}개': 'Entries: {count}',
    'TXT 불러오기': 'Load TXT',
    '선택 삭제': 'Delete selected',
    '전체 초기화': 'Clear all',
    '추가 번역 메모 / 규칙': 'Additional translation notes / rules',
    '단어 쌍이 아닌 배경 설명이나 말투 규칙이 필요할 때만 적습니다.': 'Use this only for background notes or voice rules that are not term pairs.',
    '입력 필요': 'Input required',
    '원문과 번역문을 모두 입력해주세요.': 'Enter both the source and translation.',
    '입력 확인': 'Check input',
    '원문과 번역문이 같습니다.': 'The source and translation are identical.',
    '사용자 단어장 초기화': 'Clear user glossary',
    '사용자 단어장의 모든 항목을 지울까요?': 'Clear all entries in the user glossary?',
    '사용자 단어장 TXT 불러오기': 'Load user glossary TXT',
    '사용자 단어장 {imported}개를 불러왔습니다. 인식하지 못한 줄: {skipped}개': 'Imported {imported} user glossary entries. Unrecognized lines: {skipped}',
    '↩️ 단어장 저장 취소': '↩️ Glossary save canceled',
    '📚 사용자 단어장 저장 완료: {count}개': '📚 User glossary saved: {count} entries',
    ' / 메모 {count}자': ' / notes {count} characters',
    '📚 자동 단어장 갱신: {count}개 / DB name·화자 name 자동 반영 / 현재 번역 청크에 등장한 항목만 사용': '📚 Automatic glossary refreshed: {count} entries / DB names and speaker names included / only terms appearing in the current translation chunk are used',
    '⚠️ 자동 단어장 갱신 실패: {error}': '⚠️ Failed to refresh the automatic glossary: {error}',
}
UI_KO_EN.update(_GLOSSARY_SPLIT_KO_EN)
try:
    UI_EN_KO.update({en: ko for ko, en in _GLOSSARY_SPLIT_KO_EN.items()})
except Exception:
    pass

# Independent RPG Maker speaker translation layer
_MAKER_SPEAKER_LAYER_KO_EN = {
    '화자 번역 모드': 'Speaker Translation Mode',
    '화자 번역 모드 나가기': 'Exit Speaker Translation Mode',
    '화자 번역 모드로 전환하지 못했습니다.': 'Could not switch to Speaker Translation Mode.',
    '⚠️ 화자 번역 모드 진입 실패: {error}': '⚠️ Failed to enter Speaker Translation Mode: {error}',
    '👤 화자 번역 모드 진입': '👤 Entered Speaker Translation Mode',
    '↩️ 화자 번역 모드 나가기': '↩️ Exited Speaker Translation Mode',
    '👤 화자 번역 레이어 생성: {count}개 ({reason})': '👤 Speaker translation layer created: {count} names ({reason})',
    '⚠️ 화자 번역 레이어 확인 실패: {error}': '⚠️ Failed to prepare the speaker translation layer: {error}',
    '👤 화자 번역 적용: {count}개 대사 갱신': '👤 Applied speaker translations: updated {count} dialogue rows',
    '👤 화자 번역 시작: {count}페이지': '👤 Speaker translation started: {count} pages',
    '화자 데이터가 없습니다.': 'There is no speaker data.',
    '화자 번역 페이지가 없습니다.': 'There are no speaker translation pages.',
    '화자 번역 모드에서 번역할 화자 페이지가 없습니다.': 'There are no speaker pages to translate in Speaker Translation Mode.',
    '화자명 {count}개를 AI 번역할까요?\n번역 결과는 연결된 실제 대사의 화자명에 반영됩니다.': 'Translate {count} speaker names with AI?\nThe results will be applied to the speaker names of linked dialogue rows.',
    '화자 목록': 'Speaker List',
    '화자 탭': 'Speaker Tab',
    '화자 페이지': 'Speaker Page',
    '전체 화자 페이지': 'All Speaker Pages',
    '화자 페이지 선택': 'Select Speaker Pages',
    '작업할 화자 페이지 범위를 선택하세요.': 'Select the range of speaker pages to process.',
    '쉼표와 범위를 섞어서 입력할 수 있습니다. 번호는 현재 화자 탭 순서 기준입니다.': 'You can mix commas and ranges. Numbers follow the current speaker tab order.',
    '현재 화자명만 번역합니다.': 'Only the current speaker names are translated.',
    '화자 번역 미리보기': 'Speaker Translation Preview',
    '현재 화자명': 'Current Speaker Names',
    '화자명': 'Speaker Name',
    '이름': 'Name',
    '사용 {count}회': 'Used {count} times',
    '이 화자 탭에는 표시할 화자명이 없습니다.': 'This speaker tab has no speaker names to display.',
    '대사에서 수집한 화자명을 독립 레이어에서 관리합니다.': 'Manages speaker names collected from dialogue in an independent layer.',
    '원래 화자': 'Original Speaker',
    '제어코드 포함 원본': 'Original with Control Codes',
    '번역/표시 이름': 'Translated / Display Name',
    '수정한 화자명은 연결된 실제 대사에만 반영됩니다.': 'Edited speaker names are applied only to linked dialogue rows.',
    '플러그인 번역 모드': 'Plugin Translation Mode',
}
UI_KO_EN.update(_MAKER_SPEAKER_LAYER_KO_EN)
try:
    UI_EN_KO.update({en: ko for ko, en in _MAKER_SPEAKER_LAYER_KO_EN.items()})
except Exception:
    pass
SHORTCUT_TR_KO_EN.update({
    '플러그인 번역 모드': 'Plugin Translation Mode',
    '화자 번역 모드': 'Speaker Translation Mode',
})

_TRANSLATION_PROMPT_PRESET_KO_EN = {
    '프리셋': 'Preset',
    '새 프리셋': 'New Preset',
    '이름 변경': 'Rename',
    '이름 중복': 'Duplicate Name',
    '프롬프트 변수 누락': 'Missing Prompt Variables',
    '↩️ 번역 프롬프트 저장 취소': '↩️ Translation prompt save cancelled',
}
UI_KO_EN.update(_TRANSLATION_PROMPT_PRESET_KO_EN)
try:
    UI_EN_KO.update({en: ko for ko, en in _TRANSLATION_PROMPT_PRESET_KO_EN.items()})
except Exception:
    pass

_TRANSLATION_PROMPT_EDITOR_KO_EN = {
    '공통 번역 지시': 'Common translation instructions',
    '모든 AI 번역 요청에 공통으로 들어가는 사용자 지시입니다.': 'User instructions included in every AI translation request.',
    '사용자 단어장 안내': 'Manual glossary instructions',
    '사용자 메모/단어장을 AI에 전달할 때 감싸는 안내문입니다.': "Instructions wrapping the user's glossary notes.",
    '자동 단어장 항목 형식': 'Matched glossary entry format',
    '현재 문장에 매칭된 자동/사용자 단어장 한 항목의 형식입니다.': 'Format for one matched automatic/user glossary entry.',
    '자동 단어장 안내': 'Matched glossary instructions',
    '현재 번역 묶음에 실제 등장한 단어장 항목을 감싸는 안내문입니다.': 'Instructions wrapping glossary entries matched to the current chunk.',
    '캐릭터 프롬프트 머리말': 'Character prompt header',
    '캐릭터별 프롬프트의 이름 머리말입니다.': 'Name header for a character-specific prompt.',
    '캐릭터 말투 항목': 'Character tone line',
    '캐릭터 말투 값이 있을 때 추가되는 한 줄입니다.': 'Line added when a character tone is present.',
    '캐릭터 성격 항목': 'Character personality line',
    '캐릭터 성격 값이 있을 때 추가되는 한 줄입니다.': 'Line added when a character personality is present.',
    '캐릭터 관계·문맥 항목': 'Character relationship/context line',
    '캐릭터 관계·문맥 값이 있을 때 추가되는 한 줄입니다.': 'Line added when relationship/context is present.',
    '캐릭터 번역 규칙 항목': 'Character translation-rules line',
    '캐릭터별 번역 규칙 값이 있을 때 추가되는 한 줄입니다.': 'Line added when character-specific translation rules are present.',
    '캐릭터 금지 표현 항목': 'Character forbidden-words line',
    '캐릭터 금지 표현 값이 있을 때 추가되는 한 줄입니다.': 'Line added when forbidden/avoid words are present.',
    '캐릭터 메모 항목': 'Character notes line',
    '캐릭터 메모 값이 있을 때 추가되는 한 줄입니다.': 'Line added when character notes are present.',
    '화자 이름 번역 지시': 'Speaker-name translation instructions',
    '화자 번역 독립 레이어에서 이름을 번역할 때 사용하는 지시입니다.': 'Instructions used by the independent speaker-name layer.',
    '데이터베이스 번역 지시': 'Database translation instructions',
    'DB 번역 레이어에서 사용하는 지시입니다. 프로젝트별 DB 프롬프트를 원하는 위치에 넣을 수 있습니다.': 'Instructions used by the database layer. The project-level DB prompt can be placed anywhere.',
    '전투 이벤트 번역 지시': 'Battle-event translation instructions',
    'Troops.json 전투 이벤트 문장을 번역할 때 사용하는 지시입니다.': 'Instructions used for Troops.json battle-event text.',
    '청크 프롬프트 항목 형식': 'Chunk-prompt item format',
    '한 번의 API 묶음에 포함되는 캐릭터/모드 프롬프트 한 항목의 형식입니다.': 'Format for one character/mode prompt inside an API chunk.',
    '청크 프롬프트 묶음 지시': 'Chunk-prompt wrapper',
    '캐릭터·DB·화자·전투 프롬프트 묶음을 감싸는 지시입니다.': 'Instructions wrapping character/database/speaker/battle prompt blocks.',
    '제어코드 매핑 항목 형식': 'Control-code mapping entry format',
    '개별 대사의 제어코드 토큰과 실제 코드를 보여주는 한 항목의 형식입니다.': 'Format for one opaque-token to raw-control-code mapping entry.',
    '개별 대사 제어코드 배치 문맥': 'Per-item control-code placement context',
    '제어코드 자동 반영 시 각 대사의 원문·토큰 원문·매핑표와 함께 전달되는 전체 지시입니다.': 'Full per-item instructions sent with raw source, tokenized source, and token mapping.',
    '제어코드 자동 반영 지시': 'Control-token placement instructions',
    '‘번역 시 자동 반영’이 켜져 제어코드 토큰이 포함됐을 때 사용하는 지시입니다.': 'Instructions used when automatic control-code token placement is enabled.',
    '제어코드 제거 상태 지시': 'Control-code-removed instructions',
    '제어코드 자동 반영을 사용하지 않을 때 새 제어코드를 만들지 않도록 안내하는 지시입니다.': 'Instructions used when raw control codes were removed before translation.',
    '출력 형식·행 유지 지시': 'Output-format and line-preservation rules',
    'JSON 응답 형식, ID 유지, 줄 수 보존 등을 AI에 요구하는 전체 지시입니다.': 'Full instructions for JSON output, id preservation, and physical-line preservation.',
    '개별 행 줄 수 지시': 'Per-item line-count rule',
    '여러 줄 원문 항목에 별도로 붙는 줄 수 유지 지시입니다.': 'Per-item rule attached to source text containing multiple physical lines.',
    'Gemini 입력 묶음 형식': 'Gemini input wrapper',
    'Gemini REST 요청에서 시스템 프롬프트와 입력 JSON을 합치는 형식입니다.': 'Format joining the system prompt and input JSON for Gemini REST requests.',
}
UI_KO_EN.update(_TRANSLATION_PROMPT_EDITOR_KO_EN)
try:
    UI_EN_KO.update({en: ko for ko, en in _TRANSLATION_PROMPT_EDITOR_KO_EN.items()})
except Exception:
    pass

_TRANSLATION_PROMPT_PRESET_DIALOG_KO_EN = {
    'AI 번역에 전달되는 모든 자연어 프롬프트를 직접 수정합니다. 프리셋 1에는 프로그램 기본값이 들어 있습니다. 확인을 눌러야 저장됩니다.': "Every natural-language instruction sent to the AI translator is editable here. Preset 1 contains the program's built-in defaults. Changes are saved only when you press OK.",
    'AI 번역에 전달되는 모든 자연어 프롬프트를 직접 수정합니다. Default Set에는 프로그램 기본값이 들어 있습니다. 확인을 눌러야 저장됩니다.': "Every natural-language instruction sent to the AI translator is editable here. Default Set contains the program's built-in defaults. Changes are saved only when you press OK.",
    '프리셋 1 원본 복원': 'Restore Preset 1 Defaults',
    'Default Set 원본 복원': 'Restore Default Set',
    '필수 변수를 지워도 저장할 수 있지만, 해당 데이터가 AI에 전달되지 않을 수 있습니다. 프로그램은 숨겨진 프롬프트를 몰래 다시 붙이지 않습니다.': 'Missing placeholders are allowed, but related data may not be sent to the AI. The program will not silently reinsert hidden prompts.',
    '사용 가능한 변수: ': 'Available variables: ',
    '프리셋 1은 기본 복구 이름을 유지합니다. 내용은 전부 수정할 수 있습니다.': 'Preset 1 keeps its fixed fallback name. Its contents are fully editable.',
    'Default Set은 기본 복구 이름을 유지합니다. 내용은 전부 수정할 수 있습니다.': 'Default Set keeps its fixed recovery name. All of its contents remain editable.',
    '프리셋 1은 기본 복구용이라 삭제할 수 없습니다. 내용은 수정하거나 원본으로 복원할 수 있습니다.': 'Preset 1 is the built-in fallback and cannot be deleted. It can still be edited or restored.',
    'Default Set은 기본 복구용이라 삭제할 수 없습니다. 내용은 수정하거나 원본으로 복원할 수 있습니다.': 'Default Set is the built-in recovery preset and cannot be deleted. It can still be edited or restored.',
    "'{name}' 프리셋을 삭제할까요?": "Delete the '{name}' preset?",
    '일부 프롬프트에서 변수가 빠져 있습니다. 해당 데이터가 AI에 전달되지 않을 수 있습니다.': 'Some prompt variables are missing. Related data may not be sent to the AI.',
    '그래도 저장할까요?': 'Save anyway?',
    '프리셋 1': 'Preset 1',
    '기존 프롬프트': 'Legacy Prompt',
}
UI_KO_EN.update(_TRANSLATION_PROMPT_PRESET_DIALOG_KO_EN)
try:
    UI_EN_KO.update({en: ko for ko, en in _TRANSLATION_PROMPT_PRESET_DIALOG_KO_EN.items()})
except Exception:
    pass

_UNIFIED_GAME_PROMPT_MANAGER_KO_EN = {
    '전체 번역 프롬프트 세트, 프로젝트 DB 지침, 캐릭터별 말투와 프롬프트 테스트를 이 창 하나에서 관리합니다. 확인을 눌러야 저장되고, 닫기나 X는 저장하지 않습니다.': 'Manage the full translation prompt set, project DB instructions, character voices, and prompt tests in this single window. Changes are saved only with OK; Close or X discards them.',
    '전체 번역 프롬프트': 'All Translation Prompts',
    '프로젝트 DB 프롬프트': 'Project DB Prompt',
    '현재 프로젝트에만 적용되는 DB 번역 지침입니다. 전체 프롬프트 세트의 데이터베이스 번역 지시에서 {PROJECT_DB_PROMPT} 위치에 들어갑니다.': 'Project-specific DB translation instructions. They are inserted at {PROJECT_DB_PROMPT} in the Database Translation Instructions field of the full prompt set.',
    '예: 이 게임의 아이템명은 짧게, 스킬 설명은 명령형으로 통일합니다.': 'Example: Keep item names short and use imperative phrasing for skill descriptions in this game.',
    '현재 창에서 편집 중인 프롬프트로 실제 요청 구조를 조립합니다. 확인을 누르기 전에도 결과를 볼 수 있습니다.': 'Build the actual request structure from the prompts currently being edited in this window. You can inspect the result before pressing OK.',
    '현재 창에서 편집 중인 전체 프롬프트와 프로젝트/캐릭터 프롬프트를 기준으로 대표 요청을 확인합니다.': 'Inspect representative requests using the full prompt set and project/character prompts currently being edited in this window.',
    '게임 프롬프트 관리를 열 수 없습니다.': 'Could not open Game Prompt Manager.',
    '게임 프롬프트 관리는 쯔꾸르 프로젝트를 연 뒤 사용할 수 있습니다.': 'Game Prompt Manager is available after opening an RPG Maker project.',
    'Default Set': 'Default Set',
}
UI_KO_EN.update(_UNIFIED_GAME_PROMPT_MANAGER_KO_EN)
try:
    UI_EN_KO.update({en: ko for ko, en in _UNIFIED_GAME_PROMPT_MANAGER_KO_EN.items()})
except Exception:
    pass

_MAKER_NESTED_CONTENT_ROOT_KO_EN = {
    '데이터 폴더를 찾지 못했습니다. 선택한 게임 폴더 아래에 RPG Maker MV/MZ의 data/MapInfos.json이 있는지 확인해 주세요.': 'Could not find the data folder. Check that data/MapInfos.json for RPG Maker MV/MZ exists somewhere under the selected game folder.',
}
UI_KO_EN.update(_MAKER_NESTED_CONTENT_ROOT_KO_EN)
try:
    UI_EN_KO.update({en: ko for ko, en in _MAKER_NESTED_CONTENT_ROOT_KO_EN.items()})
except Exception:
    pass

from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from typing import Any, Dict, Iterable, Mapping, MutableMapping, Tuple

PROMPT_PRESET_SCHEMA_VERSION = 1
BUILTIN_PROMPT_PRESET_NAME = "Default Set"
LEGACY_BUILTIN_PROMPT_PRESET_NAMES = ("프리셋 1", "Preset 1")
LEGACY_PROMPT_PRESET_NAME = "기존 프롬프트"
PROMPT_BLOCK_BEGIN = "__YSB_PROMPT_BLOCK_BEGIN__"
PROMPT_BLOCK_END = "__YSB_PROMPT_BLOCK_END__"

# Every actual instruction string sent to an AI translation provider lives here.
# Program data/protocol (JSON keys, ids, source text, contexts) stays code-driven,
# while all natural-language instructions remain editable through the preset UI.
DEFAULT_TRANSLATION_PROMPT_PRESET: "OrderedDict[str, str]" = OrderedDict([
    (
        "common_prompt",
        "",
    ),
    (
        "manual_glossary_prompt",
        "번역 참고 자료/단어장입니다. 아래 내용을 우선 참고해서 번역하세요.\n"
        "배경 설명, 단어 해설, 1대1 대체 규칙이 섞여 있을 수 있습니다.\n\n"
        "{GLOSSARY}",
    ),
    (
        "matched_glossary_entry",
        "- {SOURCE} = {TARGET} ({ORIGIN})",
    ),
    (
        "matched_glossary_prompt",
        "이번 번역 대상 원문/문맥에 실제 등장한 단어장 항목입니다. 아래 용어는 반드시 우선 적용하세요.\n"
        "전체 단어장을 보내지 않고 현재 문장에 매칭된 항목만 추렸습니다. 긴 용어에 포함된 짧은 용어는 제외했습니다.\n"
        "{ENTRIES}",
    ),
    (
        "character_profile_header",
        "[Character: {DISPLAY_NAME}]",
    ),
    (
        "character_profile_tone",
        "Tone: {TONE}",
    ),
    (
        "character_profile_personality",
        "Personality: {PERSONALITY}",
    ),
    (
        "character_profile_relationship",
        "Relationship/Context: {RELATIONSHIP}",
    ),
    (
        "character_profile_translation_rules",
        "Translation rules: {TRANSLATION_RULES}",
    ),
    (
        "character_profile_forbidden_words",
        "Forbidden/avoid: {FORBIDDEN_WORDS}",
    ),
    (
        "character_profile_notes",
        "Notes: {NOTES}",
    ),
    (
        "speaker_name_prompt",
        "This is an RPG Maker speaker/character name. Translate only the name naturally. "
        "Return only the translated name with no explanation, punctuation wrapper, or extra text.",
    ),
    (
        "database_prompt",
        "{PROJECT_DB_PROMPT}\n"
        "Database text is game UI/system text, not free dialogue. Translate it briefly and consistently. "
        "RPG Maker message placeholders such as %1, %2, %3 are real game codes. Copy them exactly; do not translate, delete, reorder, or add spaces inside them. "
        "If a Korean particle must follow a placeholder, use safe forms such as 은(는), 이(가), 을(를) or rewrite the sentence to avoid ambiguity.",
    ),
    (
        "battle_event_prompt",
        "This is text from a Troops.json battle event. It can appear during combat, so translate it as visible in-game text. "
        "Keep RPG Maker message placeholders such as %1, %2, and %3 exactly unchanged.",
    ),
    (
        "chunk_prompt_item",
        "[{INDEX}]\n{PROMPT}",
    ),
    (
        "chunk_prompt_wrapper",
        "Once-per-chunk prompts for this translation request. Apply character prompts only to rows whose Speaker tag matches that character.\n"
        "{BLOCKS}",
    ),
    (
        "control_code_mapping_entry",
        "- {TOKEN} = {CODE}",
    ),
    (
        "control_code_item_context",
        "RPG Maker control codes auto placement is enabled for this item.\n"
        "The input text contains opaque tokens that stand for control codes removed from the source.\n"
        "Preserve every token exactly once, never translate or edit a token, and keep token order unchanged.\n"
        "A token before visible text on a source line must stay at the start of the corresponding translated line.\n"
        "Inline/range tokens must move with the translated word or phrase that the original code affected.\n"
        "Do not output raw backslash/yen-sign control codes; output only the opaque tokens.\n"
        "Original source with control codes:\n{RAW_TEXT}\n"
        "Tokenized source:\n{TOKENIZED_TEXT}\n"
        "Token mapping (reference only; output the token, not the code):\n{TOKEN_MAPPING}",
    ),
    (
        "control_token_prompt",
        "6. Some input texts contain opaque tokens such as ⟦YSB_CC_0001⟧. "
        "Each token represents an RPG Maker control code removed by the program. "
        "Copy every token exactly once, never edit/translate/delete/duplicate it, keep token order unchanged, "
        "and place it with the corresponding translated word or at the corresponding translated line start. "
        "Do not output raw backslash or yen-sign control codes; output only the opaque tokens.",
    ),
    (
        "control_code_absent_prompt",
        r"6. RPG Maker control codes such as \V[n], \N[n], \C[n], and \I[n] are not expected in the input "
        "because the Maker preprocessor removes them from API requests. Do not invent or add control codes.",
    ),
    (
        "output_format_prompt",
        "OUTPUT FORMAT RULES FOR THIS PROGRAM:\n"
        "1. Input is a JSON list of objects.\n"
        "2. Each object has \"id\" and \"text\". Some objects may also have a short \"context\" with Map/Event/Type/Speaker metadata.\n"
        "3. Use \"context\" only to improve translation tone, speaker voice, RPG Maker scene nuance, and explicit token-placement instructions.\n"
        "4. RPG Maker variable placeholders such as %1, %2, %3, %4 MUST be copied exactly unchanged. Do not translate, delete, reorder, or add spaces inside them.\n"
        "5. When a Korean particle would attach to a placeholder like %1, prefer a safe wording that avoids batchim ambiguity, e.g. \"%1은(는)\", \"%1이(가)\", or \"%1의\" rather than changing the placeholder.\n"
        "{CONTROL_CODE_RULE}\n"
        "7. Return ONLY a valid JSON object.\n"
        "8. The JSON object MUST have one key: \"items\".\n"
        "9. \"items\" MUST be a list of objects.\n"
        "10. Each output object MUST have the same \"id\" and a \"translation\".\n"
        "11. NEVER skip any id.\n"
        "12. NEVER merge two ids into one translation.\n"
        "13. NEVER create a new id.\n"
        "14. If an input object's \"text\" contains line breaks, the output \"translation\" MUST keep exactly the same number of lines.\n"
        "15. Treat each source line as an independent RPG Maker message line: translate line 1 into line 1, line 2 into line 2, and so on.\n"
        "16. NEVER merge multiple source lines into one line, and NEVER split one source line into extra lines unless the source already has those lines.\n"
        "17. This line-count rule is mandatory because the editor restores RPG Maker control codes and preview layout per physical line.\n"
        "18. Do not add explanations, notes, comments, markdown, or extra text.\n"
        "19. Example output:\n"
        "{{\"items\":[{{\"id\":0,\"translation\":\"번역문\"}},{{\"id\":1,\"translation\":\"번역문\"}}]}}",
    ),
    (
        "line_rule_prompt",
        "Return the translation with exactly {LINE_COUNT} lines. Do not merge or split physical lines.",
    ),
    (
        "gemini_input_wrapper",
        "{SYSTEM_PROMPT}\n\nINPUT JSON:\n{INPUT_JSON}",
    ),
])

PROMPT_FIELD_SPECS = [
    {
        "key": 'common_prompt',
        "label": '공통 번역 지시',
        "description": '모든 AI 번역 요청에 공통으로 들어가는 사용자 지시입니다.',
        "placeholders": '',
    },
    {
        "key": 'manual_glossary_prompt',
        "label": '사용자 단어장 안내',
        "description": '사용자 메모/단어장을 AI에 전달할 때 감싸는 안내문입니다.',
        "placeholders": '{GLOSSARY}',
    },
    {
        "key": 'matched_glossary_entry',
        "label": '자동 단어장 항목 형식',
        "description": '현재 문장에 매칭된 자동/사용자 단어장 한 항목의 형식입니다.',
        "placeholders": '{SOURCE} {TARGET} {ORIGIN}',
    },
    {
        "key": 'matched_glossary_prompt',
        "label": '자동 단어장 안내',
        "description": '현재 번역 묶음에 실제 등장한 단어장 항목을 감싸는 안내문입니다.',
        "placeholders": '{ENTRIES}',
    },
    {
        "key": 'character_profile_header',
        "label": '캐릭터 프롬프트 머리말',
        "description": '캐릭터별 프롬프트의 이름 머리말입니다.',
        "placeholders": '{DISPLAY_NAME}',
    },
    {
        "key": 'character_profile_tone',
        "label": '캐릭터 말투 항목',
        "description": '캐릭터 말투 값이 있을 때 추가되는 한 줄입니다.',
        "placeholders": '{TONE}',
    },
    {
        "key": 'character_profile_personality',
        "label": '캐릭터 성격 항목',
        "description": '캐릭터 성격 값이 있을 때 추가되는 한 줄입니다.',
        "placeholders": '{PERSONALITY}',
    },
    {
        "key": 'character_profile_relationship',
        "label": '캐릭터 관계·문맥 항목',
        "description": '캐릭터 관계·문맥 값이 있을 때 추가되는 한 줄입니다.',
        "placeholders": '{RELATIONSHIP}',
    },
    {
        "key": 'character_profile_translation_rules',
        "label": '캐릭터 번역 규칙 항목',
        "description": '캐릭터별 번역 규칙 값이 있을 때 추가되는 한 줄입니다.',
        "placeholders": '{TRANSLATION_RULES}',
    },
    {
        "key": 'character_profile_forbidden_words',
        "label": '캐릭터 금지 표현 항목',
        "description": '캐릭터 금지 표현 값이 있을 때 추가되는 한 줄입니다.',
        "placeholders": '{FORBIDDEN_WORDS}',
    },
    {
        "key": 'character_profile_notes',
        "label": '캐릭터 메모 항목',
        "description": '캐릭터 메모 값이 있을 때 추가되는 한 줄입니다.',
        "placeholders": '{NOTES}',
    },
    {
        "key": 'speaker_name_prompt',
        "label": '화자 이름 번역 지시',
        "description": '화자 번역 독립 레이어에서 이름을 번역할 때 사용하는 지시입니다.',
        "placeholders": '',
    },
    {
        "key": 'database_prompt',
        "label": '데이터베이스 번역 지시',
        "description": 'DB 번역 레이어에서 사용하는 지시입니다. 프로젝트별 DB 프롬프트를 원하는 위치에 넣을 수 있습니다.',
        "placeholders": '{PROJECT_DB_PROMPT}',
    },
    {
        "key": 'battle_event_prompt',
        "label": '전투 이벤트 번역 지시',
        "description": 'Troops.json 전투 이벤트 문장을 번역할 때 사용하는 지시입니다.',
        "placeholders": '',
    },
    {
        "key": 'chunk_prompt_item',
        "label": '청크 프롬프트 항목 형식',
        "description": '한 번의 API 묶음에 포함되는 캐릭터/모드 프롬프트 한 항목의 형식입니다.',
        "placeholders": '{INDEX} {PROMPT}',
    },
    {
        "key": 'chunk_prompt_wrapper',
        "label": '청크 프롬프트 묶음 지시',
        "description": '캐릭터·DB·화자·전투 프롬프트 묶음을 감싸는 지시입니다.',
        "placeholders": '{BLOCKS}',
    },
    {
        "key": 'control_code_mapping_entry',
        "label": '제어코드 매핑 항목 형식',
        "description": '개별 대사의 제어코드 토큰과 실제 코드를 보여주는 한 항목의 형식입니다.',
        "placeholders": '{TOKEN} {CODE}',
    },
    {
        "key": 'control_code_item_context',
        "label": '개별 대사 제어코드 배치 문맥',
        "description": '제어코드 자동 반영 시 각 대사의 원문·토큰 원문·매핑표와 함께 전달되는 전체 지시입니다.',
        "placeholders": '{RAW_TEXT} {TOKENIZED_TEXT} {TOKEN_MAPPING}',
    },
    {
        "key": 'control_token_prompt',
        "label": '제어코드 자동 반영 지시',
        "description": '‘번역 시 자동 반영’이 켜져 제어코드 토큰이 포함됐을 때 사용하는 지시입니다.',
        "placeholders": '',
    },
    {
        "key": 'control_code_absent_prompt',
        "label": '제어코드 제거 상태 지시',
        "description": '제어코드 자동 반영을 사용하지 않을 때 새 제어코드를 만들지 않도록 안내하는 지시입니다.',
        "placeholders": '',
    },
    {
        "key": 'output_format_prompt',
        "label": '출력 형식·행 유지 지시',
        "description": 'JSON 응답 형식, ID 유지, 줄 수 보존 등을 AI에 요구하는 전체 지시입니다.',
        "placeholders": '{CONTROL_CODE_RULE}',
    },
    {
        "key": 'line_rule_prompt',
        "label": '개별 행 줄 수 지시',
        "description": '여러 줄 원문 항목에 별도로 붙는 줄 수 유지 지시입니다.',
        "placeholders": '{LINE_COUNT}',
    },
    {
        "key": 'gemini_input_wrapper',
        "label": 'Gemini 입력 묶음 형식',
        "description": 'Gemini REST 요청에서 시스템 프롬프트와 입력 JSON을 합치는 형식입니다.',
        "placeholders": '{SYSTEM_PROMPT} {INPUT_JSON}',
    },
]

_FIELD_KEYS = tuple(DEFAULT_TRANSLATION_PROMPT_PRESET.keys())
_RUNTIME_PROMPT_TEMPLATES: Dict[str, str] = deepcopy(dict(DEFAULT_TRANSLATION_PROMPT_PRESET))


def builtin_prompt_preset() -> Dict[str, str]:
    return deepcopy(dict(DEFAULT_TRANSLATION_PROMPT_PRESET))


def normalize_prompt_preset(raw: Mapping[str, Any] | None = None) -> Dict[str, str]:
    out = builtin_prompt_preset()
    if isinstance(raw, Mapping):
        for key in _FIELD_KEYS:
            if key in raw:
                out[key] = str(raw.get(key) or "")
    return out


def normalize_prompt_preset_store(raw: Mapping[str, Any] | None = None) -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    explicit_builtin = None
    migrated_builtin = None
    if isinstance(raw, Mapping):
        for raw_name, raw_preset in raw.items():
            name = str(raw_name or "").strip()
            if not name or not isinstance(raw_preset, Mapping):
                continue
            if name == BUILTIN_PROMPT_PRESET_NAME:
                explicit_builtin = normalize_prompt_preset(raw_preset)
                continue
            if name in LEGACY_BUILTIN_PROMPT_PRESET_NAMES:
                if migrated_builtin is None:
                    migrated_builtin = normalize_prompt_preset(raw_preset)
                continue
            out[name] = normalize_prompt_preset(raw_preset)
    # The built-in recovery preset is always first and always present.
    if explicit_builtin is not None:
        built = normalize_prompt_preset(explicit_builtin)
    elif migrated_builtin is not None:
        built = normalize_prompt_preset(migrated_builtin)
    else:
        built = builtin_prompt_preset()
    ordered: Dict[str, Dict[str, str]] = {BUILTIN_PROMPT_PRESET_NAME: built}
    for name, preset in out.items():
        if name != BUILTIN_PROMPT_PRESET_NAME:
            ordered[name] = preset
    return ordered


def normalize_prompt_options(
    presets_raw: Mapping[str, Any] | None,
    active_raw: Any = "",
    legacy_common_prompt: Any = "",
) -> Tuple[Dict[str, Dict[str, str]], str]:
    had_presets = isinstance(presets_raw, Mapping) and bool(presets_raw)
    presets = normalize_prompt_preset_store(presets_raw)
    active = str(active_raw or "").strip()
    if active in LEGACY_BUILTIN_PROMPT_PRESET_NAMES:
        active = BUILTIN_PROMPT_PRESET_NAME
    legacy = str(legacy_common_prompt or "")

    # Preserve an existing installation's old one-box prompt without silently
    # replacing the built-in Default Set. Fresh installations start on Default Set.
    if not had_presets and legacy.strip():
        legacy_name = LEGACY_PROMPT_PRESET_NAME
        suffix = 2
        while legacy_name in presets:
            legacy_name = f"{LEGACY_PROMPT_PRESET_NAME} {suffix}"
            suffix += 1
        migrated = builtin_prompt_preset()
        migrated["common_prompt"] = legacy
        presets[legacy_name] = migrated
        active = legacy_name

    if active not in presets:
        active = BUILTIN_PROMPT_PRESET_NAME
    return presets, active


def set_runtime_prompt_templates(raw: Mapping[str, Any] | None) -> Dict[str, str]:
    global _RUNTIME_PROMPT_TEMPLATES
    _RUNTIME_PROMPT_TEMPLATES = normalize_prompt_preset(raw)
    return deepcopy(_RUNTIME_PROMPT_TEMPLATES)


def get_runtime_prompt_templates() -> Dict[str, str]:
    return deepcopy(_RUNTIME_PROMPT_TEMPLATES)


def render_prompt_template(template: Any, **values: Any) -> str:
    """Replace known {PLACEHOLDER} tokens without interpreting JSON braces."""
    text = str(template or "")
    for key, value in values.items():
        text = text.replace("{" + str(key) + "}", str(value if value is not None else ""))
    return text.strip()


def prompt_field_spec(key: str) -> Dict[str, str]:
    for spec in PROMPT_FIELD_SPECS:
        if spec.get("key") == key:
            return dict(spec)
    return {"key": key, "label": key, "description": "", "placeholders": ""}


def prompt_field_keys() -> Tuple[str, ...]:
    return _FIELD_KEYS

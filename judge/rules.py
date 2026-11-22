"""규칙 층: LLM 없이 판정하는 항목.

숫자의 출처
- CHARS_PER_SEC: 쇼더스 2단계 화면의 예상 발화 시간을 섹션 59개에서 쟀다.
  59개 모두 "공백 포함 글자 수 / 7.0 을 0.1초로 반올림한 값"과 같았다 (Aria, 1.1배속).
- TARGET_MIN_SEC, TARGET_MAX_SEC: 과제 메일의 "30~45초".
- SECTION_MIN_CHARS, SECTION_MAX_CHARS, 첫 섹션 훅: 쇼더스 "확정 준비" 조건.
"""
import re

CHARS_PER_SEC = 7.0
TARGET_MIN_SEC = 30.0
TARGET_MAX_SEC = 45.0
SECTION_MIN_CHARS = 5
SECTION_MAX_CHARS = 300
HOOK_ROLE = "훅"

_NUM_RE = re.compile(r"\d[\d,]*(?:\.\d+)?")


def estimate_sec(text: str) -> float:
    """쇼더스와 같은 방식으로 예상 발화 시간을 낸다."""
    return round(len(text) / CHARS_PER_SEC, 1)


def numbers_in(text: str) -> set:
    """글 안의 아라비아 숫자를 쉼표 없이 모은다. '1만 7,500명'은 {'1', '7500'}이 된다."""
    return {m.replace(",", "") for m in _NUM_RE.findall(text)}


def check_structure(sections: list) -> list:
    """분량과 형식을 본다. 문제마다 {code, message}를 돌려준다. 하나라도 있으면 재생성이다."""
    problems = []
    if not sections:
        return [{"code": "EMPTY", "message": "섹션이 없다"}]

    if sections[0].get("role") != HOOK_ROLE:
        problems.append({"code": "FIRST_NOT_HOOK", "message": "첫 섹션의 역할이 훅이 아니다"})

    for i, s in enumerate(sections):
        n = len(s.get("text", ""))
        if not SECTION_MIN_CHARS <= n <= SECTION_MAX_CHARS:
            problems.append({
                "code": "SECTION_LENGTH",
                "section": i,
                "message": f"섹션 {i + 1}이 {n}자다 (허용 {SECTION_MIN_CHARS}~{SECTION_MAX_CHARS}자)",
            })

    total_chars = sum(len(s.get("text", "")) for s in sections)
    est = round(total_chars / CHARS_PER_SEC, 1)
    if est < TARGET_MIN_SEC:
        short = round(TARGET_MIN_SEC * CHARS_PER_SEC) - total_chars
        problems.append({
            "code": "LENGTH_UNDER",
            "message": f"예상 {est}초로 {TARGET_MIN_SEC:.0f}초에 못 미친다 (약 {short}자 부족)",
        })
    elif est > TARGET_MAX_SEC:
        over = total_chars - round(TARGET_MAX_SEC * CHARS_PER_SEC)
        problems.append({
            "code": "LENGTH_OVER",
            "message": f"예상 {est}초로 {TARGET_MAX_SEC:.0f}초를 넘는다 (약 {over}자 초과)",
        })
    return problems


def numbers_not_in_source(source: str, sections: list) -> list:
    """대본에는 있고 원문에는 없는 숫자를 섹션별로 찾는다. 안전망이다.

    한글로 쓴 수(세 번, 두 대)와 원문 숫자로 계산한 값(차이, 합)은 다루지 못한다.
    """
    src = numbers_in(source)
    found = []
    for i, s in enumerate(sections):
        missing = sorted(numbers_in(s.get("text", "")) - src)
        if missing:
            found.append({"section": i, "numbers": missing})
    return found

"""규칙 층과 LLM 층의 결과를 하나의 행동으로 합친다.

행동은 셋 중 하나다.
- render: 그대로 승인해도 된다.
- regenerate: 대본을 다시 뽑는다. 사유를 함께 낸다.
- human_review: 판정기가 확신하지 못한다. 사람이 본다. 판정 불가는 통과가 아니다.
"""
from . import llm, rules

RENDER, REGENERATE, HUMAN_REVIEW = "render", "regenerate", "human_review"


def judge(source: str, sections: list, model: str = llm.DEFAULT_MODEL,
          short_circuit: bool = True, ask=None) -> dict:
    """대본 하나를 판정한다.

    short_circuit이 True면 규칙에서 탈락한 대본은 LLM을 부르지 않는다.
    ask는 시험용으로 LLM 층을 바꿔 끼울 때 쓴다.
    """
    ask = ask or llm.ask
    total_chars = sum(len(s.get("text", "")) for s in sections)
    result = {
        "action": RENDER,
        "est_sec": round(total_chars / rules.CHARS_PER_SEC, 1),
        "regenerate_reasons": [],
        "review_reasons": [],
        "warnings": [],
        "llm_called": False,
        "llm_answer": None,
    }

    structure = rules.check_structure(sections)
    for p in structure:
        result["regenerate_reasons"].append({"layer": "rule", **p})
    if structure and short_circuit:
        result["action"] = REGENERATE
        return result

    answer, raw = ask(source, sections, model)
    result["llm_called"] = True
    result["llm_answer"] = answer if answer is not None else {"unparsed": raw[:2000]}

    if answer is None:
        result["review_reasons"].append({"code": "LLM_UNPARSED", "message": "LLM의 답을 읽지 못했다"})
    else:
        flagged = set()
        for s in answer["sections"]:
            i = s["idx"]
            if not s["facts_in_source"] or not s["same_meaning"]:
                flagged.add(i)
                code = "NOT_IN_SOURCE" if not s["facts_in_source"] else "MEANING_CHANGED"
                result["regenerate_reasons"].append({
                    "layer": "llm", "code": code, "section": i,
                    "message": s.get("issue", ""), "source_quote": s.get("source_quote", ""),
                })
            elif not llm.quote_in_source(s.get("source_quote", ""), source):
                # 문제없다고 했지만 근거로 댄 구절이 원문에 없다. 믿지 않는다.
                result["review_reasons"].append({
                    "code": "QUOTE_NOT_FOUND", "section": i,
                    "message": f"섹션 {i + 1}의 근거 인용이 원문에 없다",
                })

        if answer["omission_misleads"]:
            result["regenerate_reasons"].append({
                "layer": "llm", "code": "OMISSION_MISLEADS", "message": answer.get("omission_note", ""),
            })
        if answer["injection_suspected"]:
            result["review_reasons"].append({
                "code": "INJECTION_SUSPECTED", "message": "원문이나 대본에 검수자를 향한 지시문이 있다",
            })
        if not answer["ends_complete"]:
            result["warnings"].append({"code": "ENDS_ABRUPTLY", "message": "마지막 섹션에서 이야기가 마무리되지 않는다"})
        for i in answer.get("role_mismatch", []):
            result["warnings"].append({"code": "ROLE_MISMATCH", "section": i, "message": f"섹션 {i + 1}의 역할과 내용이 맞지 않는다"})

        # 숫자 안전망: 원문에 없는 숫자가 있는데 LLM이 그 섹션을 문제 삼지 않았으면 사람이 본다.
        for m in rules.numbers_not_in_source(source, sections):
            if m["section"] not in flagged:
                result["review_reasons"].append({
                    "code": "NUMBER_NOT_IN_SOURCE", "section": m["section"],
                    "message": f"섹션 {m['section'] + 1}의 숫자 {', '.join(m['numbers'])}가 원문에 없다",
                })

    if result["regenerate_reasons"]:
        result["action"] = REGENERATE
    elif result["review_reasons"]:
        result["action"] = HUMAN_REVIEW
    return result

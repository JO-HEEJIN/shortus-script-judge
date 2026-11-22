"""eval/results 의 결과 파일에서 문서에 쓰는 숫자를 다시 계산해 출력한다.

사용: python3 eval/summarize.py
문서의 숫자는 모두 이 출력에서 옮겼다.
"""
import glob
import json
import pathlib
import sys
from collections import Counter, defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from judge import rules  # noqa: E402

with open(ROOT / "data/sources/sources.json", encoding="utf-8") as f:
    SOURCES = {s["id"]: s["body"] for s in json.load(f)["sources"]}
with open(ROOT / "data/mutants/mutants.json", encoding="utf-8") as f:
    MUTANTS = {m["id"]: m for m in json.load(f)}
PAIRS = {}
for path in sorted(glob.glob(str(ROOT / "data/pairs/pair_*.json"))):
    with open(path, encoding="utf-8") as f:
        p = json.load(f)
    PAIRS[p["id"]] = p


def planted_section(mid):
    """변형본에서 결함을 심은 섹션 번호. 바탕 대본과 글이 다른 섹션이다. 섹션 수가 다르면 None."""
    m = MUTANTS[mid]
    base_id = {"d0": "pair_01_library", "d1": None}.get(mid[:2])
    candidates = [PAIRS[k] for k in PAIRS if PAIRS[k]["source_id"] == m["source_id"]]
    base = [s["text"] for s in candidates[0]["sections"]]
    cur = [s["text"] for s in m["sections"]]
    if len(base) != len(cur):
        return None
    diff = [i for i, (a, b) in enumerate(zip(base, cur)) if a != b]
    if m["source_id"] == "src_01_library":
        diff = [i for i in diff if i != 0] or ([0] if "텅 비었어요" in cur[0] else [])
    return diff[0] if len(diff) == 1 else None


def load(tag):
    with open(ROOT / "eval/results" / f"{tag}.json", encoding="utf-8") as f:
        return json.load(f)


def flagged_sections(r):
    return {x["section"] for x in r["regenerate_reasons"] if x.get("layer") == "llm" and "section" in x}


print("== 1. 규칙 층만 (LLM 없음)")
under = [k for k, p in PAIRS.items() if rules.check_structure(p["sections"])]
print("원본 12편 중 분량/형식 탈락:", len(under), [k[5:7] for k in under])
fp = [k for k, p in PAIRS.items() if rules.numbers_not_in_source(SOURCES[p["source_id"]], p["sections"])]
print("원본 12편 중 숫자 안전망이 걸린 것(오탐 후보):", len(fp), fp)
hit = [k for k, m in MUTANTS.items()
       if rules.numbers_not_in_source(SOURCES[m["source_id"]] + m.get("source_append", ""), m["sections"])]
print("변형본 중 숫자 안전망이 잡은 것:", hit)
print("변형본 중 분량 규칙이 잡은 것:", [k for k, m in MUTANTS.items() if rules.check_structure(m["sections"])])

for tag in ["dev_v1_haiku", "dev_v1_sonnet", "dev_v2_haiku", "dev_v2_sonnet",
            "dev_v3_haiku_x3", "dev_v3_sonnet_x3", "dev_v3_sonnet_final_check",
            "test_final_sonnet", "test_final_haiku"]:
    try:
        d = load(tag)
    except FileNotFoundError:
        continue
    res = d["results"]
    print(f"\n== {tag}  (모델 {d['model']}, 프롬프트 {d.get('prompt_version', 'v1')}, 반복 {d['repeat']})")
    if d.get("usage"):
        print("  사용량:", d["usage"])
    muts = [r for r in res if r["kind"] == "mutant" and r["expect_pass"] is False]
    ctrl = [r for r in res if r["kind"] == "mutant" and r["expect_pass"] is True]
    orig = [r for r in res if r["kind"] == "original"]
    print("  결함 변형본 실행 수:", len(muts), " render 아님:", sum(r["action"] != "render" for r in muts),
          " 행동:", dict(Counter(r["action"] for r in muts)))
    loc_total = loc_hit = 0
    for r in muts:
        ps = planted_section(r["id"])
        if ps is None:
            continue
        loc_total += 1
        loc_hit += ps in flagged_sections(r)
    print("  결함을 심은 섹션을 LLM이 짚은 실행:", loc_hit, "/", loc_total)
    extra = sum(len(flagged_sections(r) - {planted_section(r["id"])}) for r in muts if planted_section(r["id"]) is not None)
    print("  심지 않은 섹션을 추가로 짚은 횟수:", extra)
    if ctrl:
        print("  대조군(결함 없음) 실행 수:", len(ctrl), " render:", sum(r["action"] == "render" for r in ctrl))
    print("  원본 행동:", {r["id"][5:7] + (f".{r['run']}" if d["repeat"] > 1 else ""): r["action"] for r in orig})
    unparsed = sum(1 for r in res if any(x.get("code") == "LLM_UNPARSED" for x in r["review_reasons"]))
    qnf = sum(1 for r in res for x in r["review_reasons"] if x.get("code") == "QUOTE_NOT_FOUND")
    print("  답을 읽지 못한 실행:", unparsed, " 근거 인용이 원문에 없던 횟수:", qnf)
    inj = [r for r in res if "injection" in r["id"]]
    if inj:
        ok = sum(1 for r in inj if any(x.get("code") == "INJECTION_SUSPECTED" for x in r["review_reasons"]))
        other = sum(1 for r in res if "injection" not in r["id"] and any(x.get("code") == "INJECTION_SUSPECTED" for x in r["review_reasons"]))
        print("  지시문 변형본 실행 수:", len(inj), " 지시문을 알아챈 실행:", ok, " render 아님:", sum(r["action"] != "render" for r in inj),
              " 지시문이 없는데 알아챘다고 한 실행:", other)
    if d["repeat"] > 1:
        by = defaultdict(list)
        for r in res:
            codes = tuple(sorted(x.get("code", "") + str(x.get("section", "")) for x in r["regenerate_reasons"] + r["review_reasons"]))
            by[r["id"]].append((r["action"], codes))
        same_a = sum(len({a for a, _ in v}) == 1 for v in by.values())
        same_r = sum(len(set(v)) == 1 for v in by.values())
        print(f"  반복 일관성: 행동이 {d['repeat']}회 모두 같은 대본 {same_a}/{len(by)}, 사유까지 같은 대본 {same_r}/{len(by)}")
        print("  행동이 갈린 대본:", {k: [a for a, _ in v] for k, v in by.items() if len({a for a, _ in v}) > 1})

labels_path = ROOT / "labeling/labels_heejin.json"
if labels_path.exists():
    with open(labels_path, encoding="utf-8") as f:
        labels = json.load(f)["labels"]
    print("\n== 사람 라벨과 판정기 비교 (원본)")
    KO = {"렌더": "render", "재생성": "regenerate", "사람 확인": "human_review"}
    for tag, split in [("dev_v3_sonnet_final_check", "dev"), ("test_final_sonnet", "test")]:
        d = load(tag)
        rows = [(r["id"], KO[labels[r["id"]]["verdict"]], r["action"], r["rule_fail"], r["llm_flag_count"], bool(r["review_reasons"]))
                for r in d["results"] if r["kind"] == "original" and r["id"] in labels]
        same3 = sum(h == j for _, h, j, *_ in rows)
        same2 = sum((h == "render") == (j == "render") for _, h, j, *_ in rows)
        print(f"  {split}: 세 갈래 일치 {same3}/{len(rows)}, 통과/비통과 일치 {same2}/{len(rows)}")
        # 분량 규칙을 빼고 내용 층(LLM)만으로 본 통과 여부
        content = sum((h == "render") == (n == 0 and not rv) for _, h, _, _, n, rv in rows)
        print(f"  {split}: 내용만 본 통과/비통과 일치(분량 규칙 제외) {content}/{len(rows)}")
        for i, h, j, rf, n, rv in rows:
            print(f"    {i[5:]:22s} 사람={h:13s} 판정기={j:13s} 분량탈락={rf} LLM지적={n} 사람확인사유={rv}")

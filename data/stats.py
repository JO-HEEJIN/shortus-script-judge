"""수집한 초안의 구조 통계를 낸다. 내용 판단은 하지 않는다.
사용: python3 stats.py
"""
import glob
import json
import pathlib
import statistics
from collections import Counter

base = pathlib.Path(__file__).parent
TARGET_MIN, TARGET_MAX = 30.0, 45.0  # 과제 메일의 목표 구간(초)

pairs = [json.load(open(f)) for f in sorted(glob.glob(str(base / "pairs/pair_*.json")))]

rows = []
for p in pairs:
    secs = p["sections"]
    chars = sum(len(s["text"]) for s in secs)
    est = p["shortus"]["est_total_sec"]
    rows.append({
        "id": p["id"],
        "split": p["split"],
        "type": p["type"],
        "src": p["source_chars"],
        "n": len(secs),
        "chars": chars,
        "est": est,
        "cps": chars / est,
        "ratio": chars / p["source_chars"],
        "zone": "미달" if est < TARGET_MIN else ("초과" if est > TARGET_MAX else "범위 안"),
        "roles": " > ".join(s["role"] for s in secs),
        "max_sec": max(s["est_sec"] for s in secs),
        "min_sec": min(s["est_sec"] for s in secs),
        "flags": p["shortus"]["existing_review_flags_on_draft_screen"],
    })

print("| 대본 | 묶음 | 유형 | 원문 자 | 섹션 | 대본 자 | 예상 초 | 초당 자 | 30~45초 | 역할 순서 |")
print("|---|---|---|---|---|---|---|---|---|---|")
for r in rows:
    print(f"| {r['id'][5:]} | {r['split']} | {r['type']} | {r['src']} | {r['n']} | {r['chars']} | "
          f"{r['est']} | {r['cps']:.2f} | {r['zone']} | {r['roles']} |")

n = len(rows)
est = [r["est"] for r in rows]
print()
print("대본 수:", n)
print("예상 길이(초): 최소", min(est), "중앙값", statistics.median(est), "평균", round(statistics.mean(est), 1), "최대", max(est))
print("30~45초 구간:", dict(Counter(r["zone"] for r in rows)))
print("섹션 수 분포:", dict(sorted(Counter(r["n"] for r in rows).items())))
print("초당 글자 수: 최소", round(min(r["cps"] for r in rows), 2), "최대", round(max(r["cps"] for r in rows), 2))
print("섹션 하나의 예상 길이(초): 최소", min(r["min_sec"] for r in rows), "최대", max(r["max_sec"] for r in rows))
print("원문 대비 대본 길이: 최소", round(min(r["ratio"] for r in rows), 2), "최대", round(max(r["ratio"] for r in rows), 2))
print("첫 섹션 역할:", dict(Counter(p["sections"][0]["role"] for p in pairs)))
print("마지막 섹션 역할:", dict(Counter(p["sections"][-1]["role"] for p in pairs)))
print("역할별 섹션 수:", dict(Counter(s["role"] for p in pairs for s in p["sections"])))
print("초안 화면의 기존 검수 표시 합계:", sum(r["flags"] for r in rows))

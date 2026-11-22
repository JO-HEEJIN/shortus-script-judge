"""원문과 대본을 나란히 둔 라벨 시트를 만든다.
사용: python3 make_label_sheet.py  (label_sheet.md를 새로 쓴다. 이미 적은 라벨이 있으면 덮어쓰지 않도록 파일을 먼저 옮겨 둔다)
"""
import glob
import json
import pathlib

base = pathlib.Path(__file__).parent
data = base.parent / "data"
sources = {s["id"]: s for s in json.load(open(data / "sources/sources.json"))["sources"]}
pairs = [json.load(open(f)) for f in sorted(glob.glob(str(data / "pairs/pair_*.json")))]

out = []
out.append("# 라벨 시트: 희진이 직접 매긴다\n")
out.append("판정기를 만들기 전에 사람이 먼저 매기는 라벨이다. Claude의 관찰 파일(pair_*_notes_claude.md, dev_notes_claude.md)은 이 시트를 다 채운 뒤에 연다.\n")
out.append("적는 법\n")
out.append("- 판정: 렌더(그대로 만들어도 된다), 재생성(대본을 다시 뽑아야 한다), 사람 확인(사람이 보고 고쳐야 한다) 가운데 하나.")
out.append("- 문제: 섹션 번호와 한 줄 이유. 없으면 \"없음\".")
out.append("- 유형: 원문과 다름, 과장, 빠져서 오해, 구조, 분량, 읽기 어색, 없음 가운데 고른다. 여러 개 가능.")
out.append("- 분량은 예상 초를 보고 판단하되, 30~45초를 벗어났다는 이유만으로 탈락시킬지는 희진이 정한다.\n")
out.append("---\n")

for p in pairs:
    src = sources[p["source_id"]]
    out.append(f"## {p['id']} ({p['type']}, {p['hard_feature']})\n")
    out.append(f"원문 {p['source_chars']}자, 대본 {len(p['sections'])}섹션, 예상 {p['shortus']['est_total_sec']}초\n")
    out.append("원문\n")
    for line in src["body"].split("\n"):
        out.append("> " + line if line else ">")
    out.append("")
    out.append("대본\n")
    out.append("| # | 역할 | 예상 초 | 문장 |")
    out.append("|---|---|---|---|")
    for s in p["sections"]:
        out.append(f"| {s['idx'] + 1} | {s['role']} | {s['est_sec']} | {s['text']} |")
    out.append("")
    out.append("희진의 라벨\n")
    out.append("- 판정:")
    out.append("- 문제:")
    out.append("- 유형:")
    out.append("- 메모:\n")
    out.append("---\n")

(base / "label_sheet.md").write_text("\n".join(out), encoding="utf-8")
print("label_sheet.md", len(pairs), "편")

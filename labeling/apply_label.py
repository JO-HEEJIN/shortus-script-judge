"""희진이 매긴 라벨을 기록한다. labels_heejin.json 과 라벨 시트 두 곳에 같이 적는다.

사용: python3 apply_label.py 03 렌더 ["문제"] ["유형"] ["메모"]
"""
import datetime
import json
import pathlib
import re
import sys

here = pathlib.Path(__file__).resolve().parent
SHEETS = [here / "label_sheet.md", here.parent.parent / "labeling" / "label_sheet.md"]
VERDICTS = {"렌더", "재생성", "사람 확인"}


def main():
    num, verdict = sys.argv[1], sys.argv[2]
    problem, types, memo = (sys.argv[3:6] + ["", "", ""])[:3]
    assert verdict in VERDICTS, verdict

    path = here / "labels_heejin.json"
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"labeled_by": "조희진", "labels": {}}

    sheet = SHEETS[0].read_text(encoding="utf-8")
    ids = re.findall(r"^## (pair_%s_\S+)" % re.escape(num), sheet, flags=re.M)
    assert len(ids) == 1, ids
    pid = ids[0]
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="minutes")
    data["labels"][pid] = {"verdict": verdict, "problem": problem, "types": types, "memo": memo, "labeled_at": now}
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    for sp in SHEETS:
        if not sp.exists():
            continue
        text = sp.read_text(encoding="utf-8")
        start = text.index(f"## {pid}")
        end = text.find("\n## ", start + 1)
        end = len(text) if end < 0 else end
        block = text[start:end]
        for key, val in (("판정", verdict), ("문제", problem), ("유형", types), ("메모", memo)):
            block = re.sub(r"^- %s:.*$" % key, f"- {key}: {val}".rstrip(), block, count=1, flags=re.M)
        sp.write_text(text[:start] + block + text[end:], encoding="utf-8")
    print(pid, "->", verdict, "| 지금까지", len(data["labels"]), "편")


if __name__ == "__main__":
    main()

"""쇼더스 2단계 화면에서 읽은 초안을 pairs/ 아래 JSON으로 저장한다.
사용: python3 save_pair.py <source_id> '<화면에서 읽은 JSON>'
"""
import json, sys, datetime, pathlib

base = pathlib.Path(__file__).parent
src_id, raw = sys.argv[1], sys.argv[2]
got = json.loads(raw)
sources = {s["id"]: s for s in json.load(open(base / "sources/sources.json"))["sources"]}
src = sources[src_id]
num = src_id.split("_")[1]
pair = {
    "id": "pair_" + src_id[4:],
    "split": src["split"],
    "type": src["type"],
    "hard_feature": src["hard_feature"],
    "collected_at": datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).isoformat(timespec="minutes"),
    "source_id": src_id,
    "source_chars": len(src["body"]),
    "shortus": {
        "job_id": got["id"],
        "script_status": "draft",
        "write_mode": "AI 재작성",
        "script_format": "자동(추천)",
        "voice": "Aria",
        "speed": 1.1,
        "est_total_sec": float(got["total"]),
        "ready": got["ready"],
        "existing_review_flags_on_draft_screen": got["flags"],
    },
    "sections": [
        {"idx": i, "role": s["role"], "est_sec": s["est"], "text": s["text"]}
        for i, s in enumerate(got["out"])
    ],
}
out = base / "pairs" / f"pair_{src_id[4:]}.json"
json.dump(pair, open(out, "w"), ensure_ascii=False, indent=2)
chars = sum(len(s["text"]) for s in pair["sections"])
print(out.name, "sections", len(pair["sections"]), "chars", chars, "est", pair["shortus"]["est_total_sec"],
      "chars/sec", round(chars / pair["shortus"]["est_total_sec"], 2))

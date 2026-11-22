"""판정기를 대본 묶음에 돌리고 결과를 저장한다.

사용: python3 eval/run_eval.py --split dev --tag dev_v1 [--model haiku] [--repeat 1]

- 원본 대본(data/pairs)과 변형본(data/mutants/mutants.json) 가운데 --split 에 해당하는 것을 돌린다.
- 평가에서는 규칙에서 탈락해도 LLM 층까지 돌린다. LLM 층이 무엇을 보는지 따로 보기 위해서다.
  실제 사용(judge.cli)에서는 규칙에서 탈락하면 LLM을 부르지 않는다.
- 결과는 eval/results/<tag>.json 에 모델의 원래 답과 함께 저장한다.
"""
import argparse
import glob
import json
import pathlib
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from judge import core, llm  # noqa: E402


def load_items(split):
    with open(ROOT / "data/sources/sources.json", encoding="utf-8") as f:
        sources = {s["id"]: s["body"] for s in json.load(f)["sources"]}
    items = []
    for path in sorted(glob.glob(str(ROOT / "data/pairs/pair_*.json"))):
        with open(path, encoding="utf-8") as f:
            p = json.load(f)
        if split in ("all", p["split"]):
            items.append({
                "id": p["id"], "kind": "original", "split": p["split"], "defect": "", "expect_pass": None,
                "source": sources[p["source_id"]],
                "sections": [{"role": s["role"], "text": s["text"]} for s in p["sections"]],
            })
    with open(ROOT / "data/mutants/mutants.json", encoding="utf-8") as f:
        for m in json.load(f):
            if split in ("all", m["split"]):
                items.append({
                    "id": m["id"], "kind": "mutant", "split": m["split"], "defect": m["defect"],
                    "expect_pass": m["expect_pass"],
                    "source": sources[m["source_id"]] + m.get("source_append", ""),
                    "sections": m["sections"],
                })
    return items


def run_one(args):
    item, model, run = args
    r = core.judge(item["source"], item["sections"], model=model, short_circuit=False)
    rule_fail = any(x["layer"] == "rule" for x in r["regenerate_reasons"])
    llm_flags = [x for x in r["regenerate_reasons"] if x["layer"] == "llm"]
    return {
        "id": item["id"], "kind": item["kind"], "split": item["split"], "defect": item["defect"],
        "expect_pass": item["expect_pass"], "run": run,
        "action": r["action"], "est_sec": r["est_sec"],
        "rule_fail": rule_fail, "llm_flag_count": len(llm_flags),
        "regenerate_reasons": r["regenerate_reasons"], "review_reasons": r["review_reasons"],
        "warnings": r["warnings"], "llm_answer": r["llm_answer"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", choices=["dev", "test", "all"], required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--model", default=llm.DEFAULT_MODEL)
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--only", default="", help="쉼표로 나눈 id 접두어. 일부만 돌릴 때 쓴다")
    a = ap.parse_args()

    items = load_items(a.split)
    if a.only:
        keys = tuple(a.only.split(","))
        items = [i for i in items if i["id"].startswith(keys)]
    jobs = [(i, a.model, run) for i in items for run in range(a.repeat)]
    started = time.time()
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(run_one, jobs))
    elapsed = round(time.time() - started, 1)

    costs = [u["cost_usd"] for u in llm.USAGE if u["cost_usd"] is not None]
    lat = sorted(u["api_ms"] for u in llm.USAGE if u["api_ms"] is not None)
    usage = {"calls": len(llm.USAGE), "cost_usd_total": round(sum(costs), 4),
             "cost_usd_per_call": round(sum(costs) / len(costs), 5) if costs else None,
             "api_ms_median": lat[len(lat) // 2] if lat else None, "api_ms_max": lat[-1] if lat else None}
    out = {"tag": a.tag, "model": a.model, "split": a.split, "repeat": a.repeat, "usage": usage,
           "elapsed_sec": elapsed, "prompt_version": llm.PROMPT_VERSION, "system_prompt": llm.SYSTEM_PROMPT, "questions": llm.QUESTIONS,
           "results": results}
    path = ROOT / "eval/results" / f"{a.tag}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    for r in results:
        why = [x.get("code", "") + (f"@{x['section'] + 1}" if "section" in x else "") for x in r["regenerate_reasons"] + r["review_reasons"]]
        warn = [w["code"] + (f"@{w['section'] + 1}" if "section" in w else "") for w in r["warnings"]]
        print(f"{r['id']:26s} run{r['run']} {r['action']:13s} {r['est_sec']:5.1f}초  {' '.join(why)}  | {' '.join(warn)}")
    print(f"\n{len(results)}건, {elapsed}초, 호출 {usage['calls']}회, 호출당 {usage['cost_usd_per_call']}달러, "
          f"응답 중앙값 {usage['api_ms_median']}ms, 저장: {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

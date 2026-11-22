"""대본 하나를 판정한다.

사용: python3 -m judge.cli 입력.json [--model haiku] [--rules-only]

입력.json 형식: {"source": "원문", "sections": [{"role": "훅", "text": "..."}, ...]}
"""
import argparse
import json
import sys

from . import core, llm


def main() -> int:
    ap = argparse.ArgumentParser(description="쇼더스 대본 품질 판정기")
    ap.add_argument("input", help="원문과 대본이 든 JSON 파일")
    ap.add_argument("--model", default=llm.DEFAULT_MODEL, help="claude -p 에 넘길 모델 이름")
    ap.add_argument("--rules-only", action="store_true", help="LLM을 부르지 않고 규칙 층만 본다")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8") as f:
        data = json.load(f)
    source, sections = data["source"], data["sections"]

    if args.rules_only:
        from . import rules
        out = {
            "structure": rules.check_structure(sections),
            "numbers_not_in_source": rules.numbers_not_in_source(source, sections),
        }
    else:
        out = core.judge(source, sections, model=args.model)
    json.dump(out, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

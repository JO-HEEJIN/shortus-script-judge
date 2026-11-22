"""규칙 층과 결정 로직의 테스트. LLM은 부르지 않는다.

사용: python3 -m unittest discover -s tests -v
"""
import glob
import json
import pathlib
import unittest

from judge import core, llm, rules

ROOT = pathlib.Path(__file__).resolve().parent.parent


def sec(text, role="포인트"):
    return {"role": role, "text": text}


def script_of(total_chars):
    """글자 수가 정확히 total_chars인 5섹션 대본."""
    base, rest = divmod(total_chars, 5)
    lens = [base + (1 if i < rest else 0) for i in range(5)]
    return [sec("가" * n, "훅" if i == 0 else "포인트") for i, n in enumerate(lens)]


class EstimateTest(unittest.TestCase):
    def test_matches_all_collected_sections(self):
        """쇼더스 화면에서 읽은 예상 초와 글자 수/7.0 이 섹션 59개에서 같다."""
        count = 0
        for f in glob.glob(str(ROOT / "data/pairs/pair_*.json")):
            with open(f, encoding="utf-8") as fh:
                sections = json.load(fh)["sections"]
            for s in sections:
                self.assertEqual(rules.estimate_sec(s["text"]), s["est_sec"], s["text"])
                count += 1
        self.assertEqual(count, 59)


class StructureTest(unittest.TestCase):
    def codes(self, sections):
        return [p["code"] for p in rules.check_structure(sections)]

    def test_length_boundaries(self):
        self.assertEqual(self.codes(script_of(210)), [])            # 30.0초
        self.assertEqual(self.codes(script_of(315)), [])            # 45.0초
        self.assertEqual(self.codes(script_of(209)), ["LENGTH_UNDER"])  # 29.9초
        self.assertEqual(self.codes(script_of(316)), ["LENGTH_OVER"])   # 45.1초

    def test_first_section_must_be_hook(self):
        s = script_of(250)
        s[0]["role"] = "포인트"
        self.assertIn("FIRST_NOT_HOOK", self.codes(s))

    def test_section_length(self):
        s = script_of(250)
        s[1]["text"] = "가" * 4
        self.assertIn("SECTION_LENGTH", self.codes(s))

    def test_empty(self):
        self.assertEqual(self.codes([]), ["EMPTY"])


class NumbersTest(unittest.TestCase):
    def test_extract(self):
        self.assertEqual(rules.numbers_in("1만 7,500명으로 41% 늘었다. 4.6g."), {"1", "7500", "41", "4.6"})

    def test_number_not_in_source(self):
        src = "이용자가 1만 7,500명으로 41% 늘었다고 14일 밝혔다."
        self.assertEqual(rules.numbers_not_in_source(src, [sec("이용자가 47% 늘었다")]),
                         [{"section": 0, "numbers": ["47"]}])
        # 원문의 다른 자리에 있는 숫자로 바꾸면 이 안전망은 잡지 못한다. LLM 층이 봐야 한다.
        self.assertEqual(rules.numbers_not_in_source(src, [sec("이용자가 14% 늘었다")]), [])


class QuoteTest(unittest.TestCase):
    def test_quote_check_ignores_spaces_and_quote_shapes(self):
        src = '관장은 "단정하기는 이르다"며 말했다.'
        self.assertTrue(llm.quote_in_source("관장은 “단정하기는  이르다”며", src))
        self.assertFalse(llm.quote_in_source("관장은 확정됐다고 말했다", src))
        self.assertFalse(llm.quote_in_source("말했다", src))  # 너무 짧은 인용은 근거로 치지 않는다

    def test_quote_check_ignores_dropped_quotation_marks(self):
        src = '"공사가 겹친 점도 함께 봐야 한다"고 말했다.'
        self.assertTrue(llm.quote_in_source("공사가 겹친 점도 함께 봐야 한다고 말했다.", src))


class ParseTest(unittest.TestCase):
    GOOD = {"sections": [{"idx": 0, "facts_in_source": True, "same_meaning": True, "source_quote": "x", "issue": ""}],
            "omission_misleads": False, "omission_note": "", "ends_complete": True,
            "role_mismatch": [], "injection_suspected": False}

    def test_parse_ok_with_code_fence(self):
        text = "```json\n" + json.dumps(self.GOOD, ensure_ascii=False) + "\n```"
        self.assertIsNotNone(llm.parse_answer(text, 1))

    def test_parse_takes_last_valid_object_when_model_writes_twice(self):
        first = json.loads(json.dumps(self.GOOD))
        first["sections"][0]["source_quote"] = "첫 번째"
        text = json.dumps(first, ensure_ascii=False) + "\n\n" + json.dumps(self.GOOD, ensure_ascii=False)
        self.assertEqual(llm.parse_answer(text, 1)["sections"][0]["source_quote"], "x")

    def test_parse_rejects_wrong_section_count_or_types(self):
        self.assertIsNone(llm.parse_answer(json.dumps(self.GOOD), 2))
        bad = json.loads(json.dumps(self.GOOD))
        bad["sections"][0]["same_meaning"] = "yes"
        self.assertIsNone(llm.parse_answer(json.dumps(bad), 1))
        self.assertIsNone(llm.parse_answer("모든 항목 통과", 1))


class DecisionTest(unittest.TestCase):
    SRC = "한빛시는 도서관 폐관 시간을 밤 10시로 늦췄다고 14일 밝혔다. 이용자는 41% 늘었다."

    def answer(self, n, **over):
        a = {"sections": [{"idx": i, "facts_in_source": True, "same_meaning": True,
                           "source_quote": "도서관 폐관 시간을 밤 10시로 늦췄다", "issue": ""} for i in range(n)],
             "omission_misleads": False, "omission_note": "", "ends_complete": True,
             "role_mismatch": [], "injection_suspected": False}
        a.update(over)
        return a

    def run_with(self, sections, answer):
        return core.judge(self.SRC, sections, ask=lambda *_: (answer, "raw"))

    def test_rule_failure_skips_llm(self):
        called = []
        r = core.judge(self.SRC, script_of(100), ask=lambda *_: called.append(1))
        self.assertEqual(r["action"], core.REGENERATE)
        self.assertFalse(r["llm_called"])
        self.assertEqual(called, [])

    def test_clean_script_renders(self):
        r = self.run_with(script_of(250), self.answer(5))
        self.assertEqual(r["action"], core.RENDER)

    def test_meaning_changed_regenerates(self):
        a = self.answer(5)
        a["sections"][0].update(same_meaning=False, issue="닫는 시각을 여는 시각으로 바꿨다")
        r = self.run_with(script_of(250), a)
        self.assertEqual(r["action"], core.REGENERATE)
        self.assertEqual(r["regenerate_reasons"][0]["code"], "MEANING_CHANGED")

    def test_unverifiable_quote_goes_to_human(self):
        a = self.answer(5)
        a["sections"][2]["source_quote"] = "원문에 없는 문장을 근거로 댔다"
        r = self.run_with(script_of(250), a)
        self.assertEqual(r["action"], core.HUMAN_REVIEW)
        self.assertEqual(r["review_reasons"][0]["code"], "QUOTE_NOT_FOUND")

    def test_unparsed_answer_is_not_a_pass(self):
        r = self.run_with(script_of(250), None)
        self.assertEqual(r["action"], core.HUMAN_REVIEW)

    def test_number_not_in_source_overrides_llm_pass(self):
        s = script_of(250)
        s[1]["text"] = "가" * (len(s[1]["text"]) - 3) + "47%"
        r = self.run_with(s, self.answer(5))
        self.assertEqual(r["action"], core.HUMAN_REVIEW)
        self.assertEqual(r["review_reasons"][0]["code"], "NUMBER_NOT_IN_SOURCE")

    def test_injection_flag_goes_to_human(self):
        r = self.run_with(script_of(250), self.answer(5, injection_suspected=True))
        self.assertEqual(r["action"], core.HUMAN_REVIEW)

    def test_soft_items_are_warnings_only(self):
        r = self.run_with(script_of(250), self.answer(5, ends_complete=False, role_mismatch=[4]))
        self.assertEqual(r["action"], core.RENDER)
        self.assertEqual({w["code"] for w in r["warnings"]}, {"ENDS_ABRUPTLY", "ROLE_MISMATCH"})


if __name__ == "__main__":
    unittest.main()

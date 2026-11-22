# 쇼더스 대본 품질 판정기

패스트뷰 AI Engineer 사전 과제 제출물이다. 쇼더스(ShortUs)가 만든 대본 초안을 원문과 함께 받아, 영상으로 넘기기 전에 세 가지 행동 가운데 하나를 낸다.

| 행동 | 뜻 |
|---|---|
| `render` | 그대로 승인해도 된다 |
| `regenerate` | 대본을 다시 뽑는다. 어느 섹션이 왜 문제인지 사유를 붙인다 |
| `human_review` | 판정기가 확신하지 못한다. 사람이 본다 |

문서는 두 개다.

- [docs/quality_judge_validation.md](docs/quality_judge_validation.md): 좋은 대본의 기준, 판정 방식, 검증 방법과 결과
- [docs/decision_log.md](docs/decision_log.md): 시간순 결정 기록, 뒤집은 결정, 쓴 시간

## 실행 방법

준비물은 Python 3.10 이상과, 로그인된 [Claude Code](https://claude.com/claude-code) 명령줄 도구(`claude`)다. 따로 설치할 패키지는 없다. API 키를 코드나 설정에 두지 않는다. LLM 호출은 `claude -p`(비대화 모드)로 한다.

```bash
# 1. 테스트 (LLM을 부르지 않는다. 1초 안에 끝난다)
python3 -m unittest discover -s tests -v

# 2. 대본 하나 판정
python3 -m judge.cli examples/pair_01_library.json

# 3. 규칙 층만 (LLM 없이, Claude Code가 없어도 된다)
python3 -m judge.cli examples/pair_02_earnings_recall.json --rules-only

# 4. 검증 다시 돌리기
python3 eval/run_eval.py --split dev --tag my_dev_run
python3 eval/summarize.py
```

입력 형식은 이렇다. 역할 이름은 쇼더스 화면의 것을 그대로 쓴다.

```json
{
  "source": "원문 전체",
  "sections": [
    {"role": "훅", "text": "첫 섹션 문장"},
    {"role": "포인트", "text": "둘째 섹션 문장"}
  ]
}
```

`examples/` 에 입력 세 개와 그 출력이 들어 있다.

## MCP 도구로 쓰기 (선택)

쇼더스는 Claude에 MCP로 붙는다. 판정기도 같은 방식으로 붙일 수 있게 얇은 서버를 뒀다. 도구는 `check_rules`(LLM 없음)와 `judge_script` 두 개다.

```bash
pip install "mcp>=2"
claude mcp add shortus-judge -- python3 /절대/경로/mcp_server.py
```

stdio 클라이언트로 두 도구를 호출해 응답을 확인했다. 쇼더스의 MCP와 실제로 이어 붙여 "초안 읽기, 판정, 승인"을 한 번에 돌려 보지는 못했다. 판정기 본체는 이 파일과 `mcp` 패키지 없이 돌아간다.

## 폴더

| 경로 | 내용 |
|---|---|
| `judge/rules.py` | 규칙 층. 분량, 형식, 숫자 안전망 |
| `judge/llm.py` | LLM 층. 질문, 모델 호출, 답 형식 확인, 근거 인용 대조 |
| `judge/core.py` | 두 층의 결과를 행동 하나로 합친다 |
| `judge/cli.py` | 명령줄 진입점 |
| `tests/` | 규칙 층과 결정 로직 테스트 20개 |
| `data/sources/` | 시험용 원문 12개 (모두 새로 쓴 가상의 글) |
| `data/pairs/` | 쇼더스에서 받은 대본 초안 12편 |
| `data/mutants/` | 결함을 하나씩 심은 변형본 18개와 만드는 스크립트 |
| `labeling/` | 사람이 매긴 라벨 |
| `eval/` | 검증 실행 스크립트, 결과 파일(모델의 원래 답 포함), 고정 기록 |
| `mcp_server.py` | 판정기를 MCP 도구로 내는 얇은 서버 (선택) |
| `examples/` | 입력 예 3개와 실제 출력 |

## 알아 둘 점

- 모델을 바꾸려면 `--model haiku` 처럼 넘긴다. 기본은 `sonnet`이다. 다른 회사의 모델로 바꾸려면 `judge/llm.py`의 `call_model` 함수 하나만 바꾸면 된다.
- 판정기는 쇼더스에 접속하지 않는다. 대본은 쇼더스 2단계 화면에서 읽어 JSON으로 옮겼다.
- 예상 발화 시간은 쇼더스 화면의 값과 같은 식(공백 포함 글자 수 ÷ 7.0)으로 계산한다. Aria 목소리 1.1배속에서 잰 값이다.

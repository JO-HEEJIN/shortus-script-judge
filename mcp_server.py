"""판정기를 MCP 도구로 낸다 (선택 사항).

쇼더스는 이미 Claude에 MCP로 붙는다. 이 서버를 함께 붙이면 Claude가
"초안 읽기(t2s_get_script) -> judge_script -> 승인(t2s_produce)" 순서로 쓸 수 있다.

준비: pip install "mcp>=2"
실행: python3 mcp_server.py        (stdio)
등록: claude mcp add shortus-judge -- python3 /절대/경로/mcp_server.py

판정기 본체(judge/)는 이 파일 없이도 돌아가고, mcp 패키지에 기대지 않는다.
"""
import re

from mcp.server.mcpserver import MCPServer

from judge import core, rules

server = MCPServer("shortus-script-judge")
_MODEL_NAME = re.compile(r"^[A-Za-z0-9._-]{1,64}$")  # 모델 이름은 명령 인자로 넘어가므로 형식을 확인한다


@server.tool()
def check_rules(source: str, sections: list[dict]) -> dict:
    """LLM 없이 분량, 형식, 숫자만 본다. sections 는 [{"role": "훅", "text": "..."}] 형식이다."""
    return {
        "est_sec": round(sum(len(s.get("text", "")) for s in sections) / rules.CHARS_PER_SEC, 1),
        "structure": rules.check_structure(sections),
        "numbers_not_in_source": rules.numbers_not_in_source(source, sections),
    }


@server.tool()
def judge_script(source: str, sections: list[dict], model: str = "sonnet") -> dict:
    """대본 초안을 원문과 함께 판정한다. action 은 render, regenerate, human_review 가운데 하나다.

    regenerate 면 regenerate_reasons 에 섹션 번호와 사유가 들어 있다. 승인 전에 부른다.
    """
    if not _MODEL_NAME.match(model):
        raise ValueError("model 이름에 쓸 수 없는 문자가 있다")
    return core.judge(source, sections, model=model)


if __name__ == "__main__":
    server.run()

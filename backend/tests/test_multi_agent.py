"""多智能体协作（multi_agent.py）单测：专家分组 / 子图执行 / 主管路由 / 回退。"""
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from app.agent.multi_agent import make_agent, SQL_TOOL_NAMES, VIZ_TOOL_NAMES, FILE_TOOL_NAMES
from app.agent.prompts import SUPERVISOR_PROMPT
from app.tools.agent_tools import make_tools


# ── fake LLM：按顺序消费 responses（主管与专家共享同一实例，调用顺序即消费顺序）──
class FakeLLM(BaseChatModel):
    responses: list = []
    last_bound_tools: list = []
    _i: int = 0

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools, **kwargs):
        self.last_bound_tools = list(tools)
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        r = self.responses[min(self._i, len(self.responses) - 1)]
        self._i += 1
        return ChatResult(generations=[ChatGeneration(message=r)])

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        from langchain_core.messages import AIMessageChunk
        from langchain_core.outputs import ChatGenerationChunk
        r = self.responses[min(self._i, len(self.responses) - 1)]
        self._i += 1
        yield ChatGenerationChunk(message=AIMessageChunk(content=r.content, tool_calls=r.tool_calls or []))


def _tool_call(name, args, cid="c1"):
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid}])


def _all_tools():
    import pandas as pd
    return make_tools(None, files={"成绩.csv": pd.DataFrame({"a": [1, 2]})})


# ── 专家分组 ──────────────────────────────────────────────────────────────────
def test_tool_name_groups_cover_all():
    names = {t.name for t in _all_tools()}
    grouped = set(SQL_TOOL_NAMES) | set(VIZ_TOOL_NAMES) | set(FILE_TOOL_NAMES)
    assert names == grouped  # 所有工具都归属某个专家，无遗漏


def test_make_agent_registers_three_experts():
    llm = FakeLLM(responses=[AIMessage(content="ok")])
    graph, prompt = make_agent(llm, _all_tools())
    assert prompt == SUPERVISOR_PROMPT
    expert_names = [t.name for t in llm.last_bound_tools]
    assert expert_names == ["sql_expert", "viz_expert", "file_expert"]


def test_make_agent_no_files_drops_file_expert():
    llm = FakeLLM(responses=[AIMessage(content="ok")])
    # 无上传文件 → 无 file 工具 → 只有 2 个专家
    graph, prompt = make_agent(llm, make_tools(None, files={}))
    expert_names = [t.name for t in llm.last_bound_tools]
    assert "file_expert" not in expert_names
    assert "sql_expert" in expert_names and "viz_expert" in expert_names


# ── 主管路由 + 专家执行（顺序消费 FakeLLM responses）─────────────────────────
def test_supervisor_routes_sql_then_final_answer():
    llm = FakeLLM(responses=[
        _tool_call("sql_expert", {"request": "查询订单数量"}, "c1"),   # 主管 → 调 SQL 专家
        _tool_call("query_mysql", {"sql": "SELECT COUNT(*) FROM t"}, "c2"),  # 专家 → 调查询工具
        AIMessage(content="查询完成：共 120 单"),                          # 专家 → 总结
        AIMessage(content="上月共 **120** 单。"),                          # 主管 → 最终回答
    ])
    graph, _ = make_agent(llm, _all_tools())
    result = graph.invoke({"messages": [HumanMessage(content="上月订单数？")]})
    msgs = result["messages"]
    assert msgs[-1].content == "上月共 **120** 单。"
    # 专家子图执行过（存在 query_mysql 的 ToolMessage）
    assert any("120" in m.content for m in msgs if m.type == "tool")


def test_supervisor_routes_viz_expert():
    llm = FakeLLM(responses=[
        _tool_call("viz_expert", {"request": "画柱状图，数据 A:10 B:20"}, "c1"),
        _tool_call("make_chart", {"chart_type": "bar", "title": "对比", "x_labels": ["A", "B"],
                                  "series": [{"name": "s", "data": [10, 20]}]}, "c2"),
        AIMessage(content="已生成柱状图"),
        AIMessage(content="已为您生成柱状图。"),
    ])
    graph, _ = make_agent(llm, _all_tools())
    result = graph.invoke({"messages": [HumanMessage(content="画个柱状图")]})
    assert result["messages"][-1].content == "已为您生成柱状图。"


def test_supervisor_chitchat_no_expert_call():
    llm = FakeLLM(responses=[
        AIMessage(content="你好！有什么可以帮你？"),  # 主管直接回答，不调专家
    ])
    graph, _ = make_agent(llm, _all_tools())
    result = graph.invoke({"messages": [HumanMessage(content="你好")]})
    msgs = result["messages"]
    assert len(msgs) == 2  # 只有输入 + 回答，没有专家调用
    assert msgs[-1].content == "你好！有什么可以帮你？"


# ── 回退：专家太少 → 单 Agent ────────────────────────────────────────────────
def test_fallback_when_no_tools():
    llm = FakeLLM(responses=[AIMessage(content="hi")])
    graph, prompt = make_agent(llm, [])  # 空工具 → 单 agent
    assert prompt == SUPERVISOR_PROMPT  # prompt 仍返回（调用方统一使用）
    result = graph.invoke({"messages": [HumanMessage(content="hi")]})
    assert result["messages"][-1].content == "hi"


# ── 图表标记回传（前端渲染的关键）────────────────────────────────────────────
def test_viz_expert_forwards_chart_markup():
    """专家最终回复没带 CHART 标记时，标记也必须从子图 ToolMessage 带回主管层。"""
    llm = FakeLLM(responses=[
        _tool_call("viz_expert", {"request": "画柱状图"}, "c1"),          # 主管 → 专家
        _tool_call("make_chart", {"chart_type": "bar", "title": "对比",
                                  "x_labels": ["A"], "series": [{"name": "s", "data": [1]}]}, "c2"),  # 专家 → 图表工具
        AIMessage(content="已生成柱状图"),                                   # 专家回复（无标记）
        AIMessage(content="已为您生成柱状图。"),                             # 主管最终回复
    ])
    graph, _ = make_agent(llm, _all_tools())
    result = graph.invoke({"messages": [HumanMessage(content="画个图")]})
    # 主管图里应存在含 CHART 标记的 ToolMessage（viz_expert 返回值）
    chart_found = any("<!--CHART:" in (m.content or "") for m in result["messages"])
    assert chart_found, "专家子图的 CHART 标记必须回传到主管层，否则前端无图"
    assert result["messages"][-1].content == "已为您生成柱状图。"

"""chat 主流程纯逻辑（api/chat_api.py 的 _extract）单测。"""
import json

from langchain_core.messages import ToolMessage, AIMessage

from app.api.chat_api import _extract


def _tool(content: str, tool_call_id="t1"):
    return ToolMessage(content=content, tool_call_id=tool_call_id, name="query_mysql")


def test_extract_chart_and_table():
    msg = _tool('图表已生成<!--CHART:{"type":"bar"}-->数据见<!--TABLE:{"columns":["a"],"rows":[[1]]}-->')
    visuals, tables, sql = _extract([msg])
    assert visuals[0]["chart"] == {"type": "bar"}
    assert tables[0]["columns"] == ["a"]


def test_extract_image():
    msg = _tool("<!--IMAGE_BASE64:abc123-->")
    visuals, tables, sql = _extract([msg])
    assert visuals[0]["image"] == "abc123"


def test_extract_multiple_tables_in_one_message():
    content = '<!--TABLE:{"columns":["a"]}--><!--TABLE:{"columns":["b"]}-->'
    visuals, tables, sql = _extract([_tool(content)])
    assert len(tables) == 2


def test_extract_sql_from_ai_tool_call():
    ai = AIMessage(content="", tool_calls=[
        {"name": "query_mysql", "args": {"sql": "SELECT 1"}, "id": "c1"},
    ])
    visuals, tables, sql = _extract([ai])
    assert sql == "SELECT 1"


def test_extract_ignores_unrelated_tools():
    ai = AIMessage(content="", tool_calls=[
        {"name": "make_chart", "args": {"chart_type": "bar"}, "id": "c1"},
    ])
    visuals, tables, sql = _extract([ai])
    assert sql is None


def test_extract_empty_message():
    visuals, tables, sql = _extract([_tool("没有标记的普通文本")])
    assert visuals == [] and tables == [] and sql is None


def test_extract_bad_json_ignored():
    msg = _tool("<!--CHART:{bad json}-->")
    visuals, tables, sql = _extract([msg])
    assert visuals == []

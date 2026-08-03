"""多智能体协作（Supervisor 模式）：主管 + 三专家，复用显式图。

架构（面试可画图讲解）：
                 ┌──────────────┐
                 │  supervisor  │  主管 Agent：分派任务 + 汇总回答
                 └──────┬───────┘
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
  [sql_expert]    [viz_expert]    [file_expert]
  list_schemas    make_chart      list_files
  get_schema      generate_chart  query_file
  query_mysql     auto_analyze    file_stats

实现方式：
- 主管是一个显式图（make_graph），其工具是 3 个"专家入口工具"
- 每个专家入口工具内部：用专家自己的显式子图（make_graph(llm, expert_tools)）
  + 专家专用 system prompt 执行任务，返回结果字符串给主管
- 主管基于用户问题通过工具调用路由；可串联多个专家（如 先查库再画图）
- 子图共享同一个 llm 实例（bind_tools 各自绑定自己的工具集）
"""
from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from app.agent.graph import make_graph
from app.agent.prompts import (
    SUPERVISOR_PROMPT, SQL_EXPERT_PROMPT, VIZ_EXPERT_PROMPT, FILE_EXPERT_PROMPT,
)

# 工具 → 专家分组（按现有工具名划分）
SQL_TOOL_NAMES = ("list_schemas", "get_schema", "query_mysql")
VIZ_TOOL_NAMES = ("make_chart", "generate_chart", "auto_analyze_and_visualize")
FILE_TOOL_NAMES = ("list_files", "query_file", "file_stats")

# 专家子图内可能生成的前端标记（图表/表格/图片）：必须原样带回主管层，
# 否则标记只留在专家子图内部，_extract 提取不到 → 前端无图/无表。
_MARK_RE = re.compile(r"<!--(?:CHART|TABLE|IMAGE_BASE64):.*?-->", re.S)


def _make_expert_tool(name: str, description: str, llm, tools: list, system_prompt: str,
                      trace=None):
    """构造专家入口工具：内部用专家的显式子图执行任务，返回结果字符串。"""
    # 与主管共享同一个 trace 采集器，专家内部工具调用也进入全链路轨迹
    subgraph = make_graph(llm, tools, trace=trace, agent_name=name)

    @tool
    def expert(request: str) -> str:
        """(description 由外层注入)"""
        msgs = [SystemMessage(content=system_prompt), HumanMessage(content=request)]
        result = subgraph.invoke({"messages": msgs})
        sub_msgs = result["messages"]
        last = sub_msgs[-1]
        reply = str(getattr(last, "content", None) or "")
        # 把子图内生成的图表/表格/图片标记全部带回（去重保序），
        # 供主管层 _extract 提取、前端渲染。
        marks: list = []
        for m in sub_msgs:
            c = str(getattr(m, "content", None) or "")
            for mk in _MARK_RE.findall(c):
                if mk not in marks:
                    marks.append(mk)
        if marks:
            reply = (reply.rstrip() + "\n" + "\n".join(marks)).strip()
        return reply

    expert.name = name
    return expert


def make_agent(llm, all_tools: list, trace=None):
    """构建多智能体主管图。

    - all_tools：全量工具列表（make_tools 产物），按名称分给三个专家
    - 返回 (graph, supervisor_prompt)：graph 供 chat 调用；prompt 用于构造输入
    - 若可用专家 ≤1 个（如无上传文件），回退为单 Agent（多智能体无意义）
    """
    by_name = {t.name: t for t in all_tools}
    sql_tools = [by_name[n] for n in SQL_TOOL_NAMES if n in by_name]
    viz_tools = [by_name[n] for n in VIZ_TOOL_NAMES if n in by_name]
    file_tools = [by_name[n] for n in FILE_TOOL_NAMES if n in by_name]

    supervisor_tools: list = []
    if sql_tools:
        supervisor_tools.append(_make_expert_tool(
            "sql_expert", "处理所有需要查询 MySQL 数据库的任务（列库、看表结构、执行 SQL 统计/分析）。"
                          "入参 request 为给专家的完整任务描述。", llm, sql_tools,
                          SQL_EXPERT_PROMPT, trace))
    if viz_tools:
        supervisor_tools.append(_make_expert_tool(
            "viz_expert", "生成图表/可视化（柱状、折线、饼图等）。数据需先由 sql_expert/file_expert 或用户提供。"
                          "入参 request 为给专家的完整任务描述（含数据）。", llm, viz_tools,
                          VIZ_EXPERT_PROMPT, trace))
    if file_tools:
        supervisor_tools.append(_make_expert_tool(
            "file_expert", "分析用户上传的 CSV/Excel 文件（列、统计、SQL 查询）。"
                           "入参 request 为给专家的完整任务描述。", llm, file_tools,
                           FILE_EXPERT_PROMPT, trace))

    if len(supervisor_tools) <= 1:
        # 专家太少：多智能体没有分派价值，回退单 Agent（全量工具 + 原 system prompt 由调用方决定）
        return make_graph(llm, all_tools, trace=trace, agent_name="agent"), SUPERVISOR_PROMPT

    return make_graph(llm, supervisor_tools, trace=trace, agent_name="supervisor"), SUPERVISOR_PROMPT

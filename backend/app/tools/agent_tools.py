import json, re
import pandas as pd
from langchain_core.tools import tool
from app.db.schema import list_business_schemas, get_schema_text
from app.tools.chart_tool import get_chart_tools
from app.tools.file_tool import make_file_tools

_FORBIDDEN = re.compile(r"\b(drop|delete|update|insert|alter|truncate|create|grant|revoke)\b", re.I)
_BARE_DASH = re.compile(r"(?<!`)(share-[A-Za-z0-9_]+)(?!`)")

def _to_md(df):
    cols = list(df.columns)
    esc = lambda v: "" if pd.isna(v) else str(v).replace("|", "\\|")
    head = "| " + " | ".join(esc(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    if len(df) == 0:
        return head + "\n" + sep + "\n| (空结果) |"
    body = "\n".join("| " + " | ".join(esc(v) for v in row) + " |" for row in df.values.tolist())
    return "\n".join([head, sep, body])

def make_tools(engine, default_schema=None, files=None):
    """构造工具集。files: {文件名: DataFrame}，有上传文件时注册文件分析工具。"""
    @tool
    def list_schemas() -> str:
        """列出所有业务库名。写 SQL 前必须先调用，判断问题涉及哪些库。"""
        names = list_business_schemas(engine)
        return ", ".join(names) or "(无业务库)"

    @tool
    def get_schema(schema: str) -> str:
        """查看指定库的表结构。schema 必填，如 share-order。先 list_schemas 再针对相关库调用，禁止一次看全部。"""
        if not schema:
            return "错误：请指定库名 schema（如 share-order）。先用 list_schemas 看库列表。"
        return get_schema_text(engine, schema)

    @tool
    def query_mysql(sql: str) -> str:
        """执行只读 SELECT。横杠库名必须反引号全限定，如 `share-order`.`表名`。报错时据错误信息修正后重试。"""
        if _FORBIDDEN.search(sql):
            return "错误：仅允许 SELECT，检测到写操作关键字。"
        if not sql.strip().lower().startswith("select"):
            return "错误：SQL 必须以 SELECT 开头。"
        bare = _BARE_DASH.findall(sql)
        if bare:
            return f"错误：{bare} 含横杠但未加反引号，请用反引号全限定，如 `share-order`.`表名`。"
        if "limit" not in sql.lower():
            sql = sql.rstrip(";") + " LIMIT 500"
        try:
            df = pd.read_sql(sql, engine)
            d2 = df.head(200)
            machine = {"columns": list(df.columns),
                       "rows": d2.where(d2.notna(), None).values.tolist()}
            return _to_md(df) + f"\n<!--TABLE:{json.dumps(machine, ensure_ascii=False, default=str)}-->"
        except Exception as e:
            return f"SQL 执行错误：{e}  请根据此错误修正 SQL 后重试（最多 3 次）。"

    # 基础图表工具（保留兼容性）
    @tool
    def make_chart(chart_type: str, title: str, x_labels: list, series: list) -> str:
        """生成 ECharts 图表。chart_type∈bar/line/pie。bar/line：series=[{name,data:[...]}]；pie：series=[{name,value}]。"""
        ct = (chart_type or "bar").lower()
        if ct == "pie":
            option = {"title": {"text": title}, "tooltip": {"trigger": "item"}, "legend": {},
                      "series": [{"type": "pie", "radius": "60%", "data": series or []}]}
        else:
            option = {"title": {"text": title}, "tooltip": {"trigger": "axis"}, "legend": {},
                      "xAxis": {"type": "category", "data": x_labels or []}, "yAxis": {"type": "value"},
                      "series": [{"type": ct, "name": s.get("name", ""), "data": s.get("data", [])} for s in (series or [])]}
        return f"<!--CHART:{json.dumps(option, ensure_ascii=False)}-->图表已生成：{title}（前端会渲染，回复里不要重复罗列数据）"

    # 高级可视化工具
    chart_tools = get_chart_tools()

    # 上传文件分析工具（有文件时才注册）
    file_tools = make_file_tools(files or {})

    return [list_schemas, get_schema, query_mysql, make_chart] + chart_tools + file_tools

"""库/表结构读取（db/schema.py）单测：用 fake engine 模拟 INFORMATION_SCHEMA，不连真实数据库。"""
from app.db.schema import _q, list_business_schemas, list_tables, get_schema_text


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, mapping):
        self._mapping = mapping

    def execute(self, stmt, params=None):
        # schema.py 传的是 sqlalchemy text(...) 对象，取 .text 作为匹配键
        key = getattr(stmt, "text", stmt)
        return _Result(self._mapping.get(key, []))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Engine:
    def __init__(self, mapping):
        self._mapping = mapping

    def connect(self):
        return _Conn(self._mapping)


SCHEMA_SQL = (
    "SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
    "WHERE SCHEMA_NAME NOT IN ('information_schema','mysql','performance_schema','sys') "
    "AND SCHEMA_NAME LIKE :p"
)
# list_tables 与 _render_one 对 TABLE_SCHEMA 的空格写法不同，两个变体都要 mock
TABLES_SQL_SPACED = (
    "SELECT TABLE_NAME, TABLE_COMMENT FROM INFORMATION_SCHEMA.TABLES "
    "WHERE TABLE_SCHEMA = :s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME"
)
TABLES_SQL_TIGHT = (
    "SELECT TABLE_NAME, TABLE_COMMENT FROM INFORMATION_SCHEMA.TABLES "
    "WHERE TABLE_SCHEMA=:s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME"
)
COLS_SQL = (
    "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT, COLUMN_KEY "
    "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=:s "
    "ORDER BY TABLE_NAME, ORDINAL_POSITION"
)


def _engine():
    # 系统库过滤在 SQL 端完成（NOT IN SYS），mock 数据只需返回业务库
    return _Engine({
        SCHEMA_SQL: [("share-order",), ("share-report",)],
        TABLES_SQL_SPACED: [("orders", "订单表"), ("users", "")],
        TABLES_SQL_TIGHT: [("orders", "订单表"), ("users", "")],
        COLS_SQL: [
            ("orders", "id", "bigint", "主键", "PRI"),
            ("orders", "amount", "decimal(10,2)", "金额", ""),
            ("users", "name", "varchar(64)", "姓名", ""),
        ],
    })


# ── 反引号转义 ────────────────────────────────────────────────────────────────
def test_q_escapes_dash_and_backtick():
    assert _q("share-order") == "`share-order`"
    assert _q("a`b") == "`a``b`"


# ── 库/表列举 ─────────────────────────────────────────────────────────────────
def test_list_business_schemas_filters_system():
    names = list_business_schemas(_engine())
    assert names == ["share-order", "share-report"]
    assert "mysql" not in names


def test_list_tables_with_schema():
    tables = list_tables(_engine(), schema="share-order")
    assert tables == [
        {"name": "share-order.orders", "comment": "订单表"},
        {"name": "share-order.users", "comment": ""},
    ]


def test_list_tables_all_schemas():
    tables = list_tables(_engine())
    # 每个 schema 各渲染两张表 → 4 条
    assert len(tables) == 4


def test_get_schema_text_format():
    text = get_schema_text(_engine(), schema="share-order")
    assert "### 库 `share-order`" in text
    assert "- 表 `share-order`.`orders`  -- 订单表" in text
    assert "id bigint [PK]  -- 主键" in text
    assert "amount decimal(10,2)" in text  # 无 key 无注释
    assert "users" in text


def test_get_schema_text_empty_fallback():
    e = _Engine({SCHEMA_SQL: []})
    assert get_schema_text(e) == "(无业务库)"

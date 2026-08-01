from sqlalchemy import text

SYS = "('information_schema','mysql','performance_schema','sys')"

def _q(n: str) -> str:
    return f"`{n.replace('`', '``')}`"   # 专治 share-order 这类横杠名

def list_business_schemas(engine, prefix: str = "share-") -> list:
    with engine.connect() as c:
        rows = c.execute(text(
            f"SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA "
            f"WHERE SCHEMA_NAME NOT IN {SYS} AND SCHEMA_NAME LIKE :p"
        ), {"p": f"{prefix}%"}).fetchall()
    return [r[0] for r in rows]

def list_tables(engine, schema=None, prefix: str = "share-") -> list:
    targets = [schema] if schema else list_business_schemas(engine, prefix)
    out = []
    with engine.connect() as c:
        for s in targets:
            rows = c.execute(text(
                "SELECT TABLE_NAME, TABLE_COMMENT FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = :s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME"
            ), {"s": s}).fetchall()
            for tname, tcom in rows:
                out.append({"name": f"{s}.{tname}", "comment": tcom or ""})
    return out

def get_schema_text(engine, schema=None, prefix: str = "share-") -> str:
    targets = [schema] if schema else list_business_schemas(engine, prefix)
    return "\n\n".join(_render_one(engine, s) for s in targets) or "(无业务库)"

def _render_one(engine, schema: str) -> str:
    with engine.connect() as c:
        tables = c.execute(text(
            "SELECT TABLE_NAME, TABLE_COMMENT FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA=:s AND TABLE_TYPE='BASE TABLE' ORDER BY TABLE_NAME"
        ), {"s": schema}).fetchall()
        cols = c.execute(text(
            "SELECT TABLE_NAME, COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT, COLUMN_KEY "
            "FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA=:s "
            "ORDER BY TABLE_NAME, ORDINAL_POSITION"
        ), {"s": schema}).fetchall()
    col_map = {}
    for tname, cname, ctype, ccom, ckey in cols:
        col_map.setdefault(tname, []).append((cname, ctype, ccom, ckey))
    lines = [f"### 库 {_q(schema)}"]
    for tname, tcom in tables:
        lines.append(f"- 表 {_q(schema)}.{_q(tname)}" + (f"  -- {tcom}" if tcom else ""))
        for cname, ctype, ccom, ckey in col_map.get(tname, []):
            tag = " [PK]" if ckey == "PRI" else (" [IDX]" if ckey else "")
            lines.append(f"    * {cname} {ctype}{tag}" + (f"  -- {ccom}" if ccom else ""))
    return "\n".join(lines)

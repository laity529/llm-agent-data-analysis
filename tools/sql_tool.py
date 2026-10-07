# ============ 导入部分 ============

# import os ：操作系统相关功能，这里用来创建文件夹、拆文件名
import os

# import sqlite3 ：Python 自带的 SQLite 数据库库（不用 pip 安装）
# SQLite 是"一个文件就是一整个数据库"的轻量数据库，最适合教学
import sqlite3

import pandas as pd
from langchain_core.tools import tool


@tool
def sql_query(csv_path: str, sql: str) -> str:
    """对 CSV 数据执行 SQL 查询并返回结果（最多20行）。
    CSV 会自动导入 SQLite，表名 = 文件名去掉 .csv 后缀。
    示例: csv_path="demo.csv", sql="SELECT region, SUM(quantity) AS total FROM demo GROUP BY region" """
    # docstring 里的"示例"很重要：模型看了示例才知道 SQL 该怎么写、表名叫什么

    # os.makedirs("data", exist_ok=True) ：创建 data 文件夹
    # exist_ok=True 的意思："文件夹已存在也不要报错"（不加的话第二次运行会崩）
    os.makedirs("data", exist_ok=True)

    # 连接数据库。data/agent.db 不存在的话，sqlite 会自动创建这个文件
    conn = sqlite3.connect("data/agent.db")

    # try/except/finally 三段式：
    #   try     -> 正常流程
    #   except  -> 出错时
    #   finally -> 不管出没出错，最后都要执行（用来保证关闭数据库连接）
    try:
        # 拆解表名的来源，以 csv_path="data/demo.csv" 为例：
        # os.path.basename(...)  -> 取路径最后一段文件名 -> "demo.csv"
        # os.path.splitext(...)  -> 拆成 (文件名, 后缀)   -> ("demo", ".csv")
        # [0]                    -> 取第一部分           -> "demo"
        table = os.path.splitext(os.path.basename(csv_path))[0]

        # 查询 SQLite 的"系统目录表" sqlite_master，看目标表存不存在
        # WHERE type='table' AND name=? 的 ? 是"占位符"，
        # 实际值放在后面的 (table,) 元组里由库安全填入——防 SQL 注入的标准写法
        # .fetchone() ：取查询结果的第一条（没有则返回 None）
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()

        # not exists ：不存在为真 -> 说明这个 CSV 还没入库，需要导入
        if not exists:
            # pandas 的 to_sql：一步把表格写进数据库成为表
            # index=False ：不要把行号存成额外的一列
            pd.read_csv(csv_path).to_sql(table, conn, index=False)

        # pd.read_sql_query(SQL语句, 连接) ：执行查询，结果直接变成 DataFrame
        # 如果 SQL 写错（比如表名不存在），这里会抛异常，跳进 except
        df = pd.read_sql_query(sql, conn)
    except Exception as e:
        # Exception 是"所有错误的总类"，as e 把错误对象接住起名叫 e
        # 把错误信息原样返回给模型，模型能看懂并自行修正 SQL 重试
        return f"SQL 错误: {e}"
    finally:
        # 无论成败都关闭连接，释放资源（数据库连接是有限的宝贵资源）
        conn.close()

    # head(20) 最多返回 20 行：防止模型一口气要几万行把上下文撑爆
    return df.head(20).to_string(index=False)

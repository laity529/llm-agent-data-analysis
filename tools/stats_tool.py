import pandas as pd
from langchain_core.tools import tool


# 设计说明（讲给学生）：这里把原来"一个函数带 operation 参数"拆成了
# 三个独立工具。原因：让模型"选工具"比让模型"填参数"更不容易出错。
# 就像把遥控器上"模式+数值"两个键，做成三个标了名字的专用键。

@tool
def stats_summary(csv_path: str) -> str:
    """对 CSV 所有数值列计算均值、中位数、标准差、最小值、最大值。"""
    # describe() 是 pandas 的"一键全套统计"：
    # 自动算出 count/mean/std/min/25%/50%/75%/max
    # round(4) 保留 4 位小数，防止 3.14159265... 刷屏
    df = pd.read_csv(csv_path)
    return df.describe().round(4).to_string()


@tool
def stats_value_counts(csv_path: str, column: str) -> str:
    """统计 CSV 某一列中每个值出现的次数。"""
    df = pd.read_csv(csv_path)
    # 防御：模型可能猜错列名（比如把 Region 写成 region），
    # 先检查再计算，给出"可用列"提示方便它自我纠正
    if column not in df.columns:
        return f"错误：列不存在，可用列 {list(df.columns)}"
    # value_counts() ：数每个值出现几次，按次数从多到少排好序
    return df[column].value_counts().to_string()


@tool
def stats_group_agg(csv_path: str, group_by: str, column: str) -> str:
    """按某列分组，对另一数值列计算总和与平均值。
    示例: group_by='region', column='quantity' 得到各地区销量统计。"""
    df = pd.read_csv(csv_path)
    # 两列都要检查：分组列和数值列缺一不可
    if group_by not in df.columns or column not in df.columns:
        return f"错误：列不存在，可用列 {list(df.columns)}"
    # 分组聚合拆解：
    #   df.groupby(group_by)      -> 按分组列把行分成几堆（北京一堆上海一堆…）
    #   [column]                  -> 每堆里只取要计算的数值列
    #   .agg(["sum", "mean"])     -> 每堆各算"总和"和"平均"两种指标
    #   .round(4)                 -> 结果保留 4 位小数
    result = df.groupby(group_by)[column].agg(["sum", "mean"]).round(4)
    return result.to_string()

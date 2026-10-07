# ============ 导入部分 ============

import time

# create_agent：LangChain 的"Agent 生成器"，一行创建会自主调用工具的智能体
# 它内部托管了完整循环：模型说要用工具 -> 执行 -> 结果回填 -> 模型继续 -> …直到回答
from langchain.agents import create_agent
from langchain_core.messages import HumanMessage   # 用消息对象（而不是字典）入史，保证格式统一

# 从我们自己的文件里导入配置好的模型和七个工具（day7 原班人马）
from llm import llm
from tools.csv_tool import read_csv
from tools.sql_tool import sql_query
from tools.stats_tool import stats_summary, stats_value_counts, stats_group_agg
from tools.chart_tool import make_chart
from tools.calculator_tool import calculator

# 会话记忆不再像 day7 那样用本文件的 _sessions 字典，
# 而是交给 memory.py 统一管理（day4 的多会话思想 + day7 的存完整消息）
import memory

# ============ 创建 Agent：一行，全部工具挂上 ============

agent = create_agent(
    model=llm,                                    # 大脑：用哪个模型思考
    tools=[read_csv, sql_query, stats_summary,    # 工具箱：7 个工具全部挂上
           stats_value_counts, stats_group_agg,
           make_chart, calculator],
)


def chat(session_id: str, user_input: str, data_file: str = "demo.csv") -> dict:
    """
    处理一轮对话（整合点：记忆交给 memory.py，标题自动生成，数据文件单独传参）。

    参数：
      session_id  会话 ID，区分不同对话（day4 的多会话）
      user_input  用户原始提问（保持干净，用来生成会话标题）
      data_file   当前数据文件路径（前端上传后文件名会变，单独传更清晰；
                  day7 是把它拼进问题文本里，效果一样但会污染标题）
    返回：
      {'reply': 回答文本, 'images': 本轮新生成的图表路径列表}
    """
    # ---------- 第 1 步：记忆 + 标题 ----------
    # 第一条提问生成侧边栏标题（day4 的体验；要在拼入文件前缀之前做，保持标题干净）
    memory.set_title_if_new(session_id, user_input)

    history = memory.get_messages(session_id)
    # 把当前数据文件作为上下文"塞"进问题里，Agent 才知道该分析哪个文件（沿用 day7 的设计）
    # 注意 append 的是 HumanMessage 对象：这样即使本轮 Agent 运行失败
    # （模型报错、网络断开），历史里存的也是标准格式，切换会话恢复时不会丢
    history.append(HumanMessage(content=f"（当前数据文件: {data_file}）{user_input}"))

    # ---------- 第 2 步：运行 Agent（核心一步！）----------
    # agent.invoke 会自动完成整个循环：模型思考 -> 调工具 -> 结果回填 -> 继续 -> 最终回答
    # 注意：模型平台在"开通模型"同步期间偶发 403 AccessDenied（请求被分到
    # 还没同步开通的实例上），这里对 403 简单重试 3 次，其他错误直接抛出
    for attempt in range(1, 4):
        try:
            result = agent.invoke({"messages": history})
            break
        except Exception as e:
            denied = "AccessDenied" in str(e) or "Error code: 403" in str(e)
            if attempt == 3 or not denied:
                raise
            print(f"[agent] 模型返回 403（平台开通同步中），第 {attempt} 次重试…")
            time.sleep(1)

    # ---------- 第 3 步：把完整过程存回记忆模块 = 有了记忆 ----------
    memory.save_messages(session_id, result["messages"])

    # ---------- 第 4 步：找出本轮新生成的图表 ----------
    # 本轮新增的消息 = result["messages"] 去掉开头的旧历史剩下的"尾巴"，
    # 里面的工具消息写着"图表已保存: charts/xxx.png"，用正则提取出来。
    # （day7 原版靠"对比 charts 目录前后差异"找新文件；改为从消息里提取后，
    #   同名图表重复生成、并发会话也不会漏报/误报，也不再需要 sleep 等文件写完）
    new_charts: list[str] = []
    for m in result["messages"][len(history):]:
        if getattr(m, "type", "") == "tool":
            new_charts += memory.extract_chart_paths(m.content)

    # ---------- 第 5 步：整理返回 ----------
    reply = result["messages"][-1].content or "（模型没有返回文本）"
    return {"reply": reply, "images": new_charts}

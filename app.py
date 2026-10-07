# ============ 导入部分 ============

import os
import uuid                   # 生成全球唯一的随机 ID（做会话 ID）
import requests               # 发 HTTP 请求的库（前端找后端要数据全靠它）
import streamlit as st        # Streamlit 前端库，约定小名 st

# ---- 页面基础设置（必须是最先调用的 st 命令）----
st.set_page_config(
    page_title="多会话数据分析 Agent",   # 浏览器标签页标题
    page_icon="📊",                      # 标签页图标
    layout="wide",                       # 宽屏布局
)
st.title("📊 多会话数据分析 Agent")
st.caption("day7 的数据分析 Agent ＋ day4 的多会话记忆 · LangChain + FastAPI + Streamlit")

# ---- 后端地址常量 ----
API_URL = "http://localhost:8000"

# ---- 初始化"页面记忆" ----
# Streamlit 每次用户操作都会把整个脚本从头到尾重跑一遍，
# st.session_state 是唯一跨"重跑"存活的地方。
# 整合后页面只记住【当前会话 ID】（day4 的做法）；
# 聊天记录一律以【后端】为唯一真实源（day7 的后端记忆 + 新增的 /sessions 接口），
# 好处：刷新页面、切换会话、甚至换浏览器打开，历史都不丢。
if "current_session_id" not in st.session_state:
    st.session_state.current_session_id = str(uuid.uuid4())


# ---- 侧边栏第 1 区：会话管理（来自 day4）----
with st.sidebar:
    st.header("💬 会话管理")

    # 新建会话：换一个新的随机 ID 即可，后端会在第一次提问时自动登记
    if st.button("➕ 新建会话", use_container_width=True):
        st.session_state.current_session_id = str(uuid.uuid4())
        st.rerun()   # 手动让页面刷新

    # 从后端拉会话列表（标题 = 每个会话的第一条提问，见 memory.set_title_if_new）
    try:
        sessions = requests.get(f"{API_URL}/sessions", timeout=2).json()
    except Exception:
        sessions = []

    st.markdown("<font style='font-size:13px; color:#aaa;'>历史会话</font>",
                unsafe_allow_html=True)
    for s in sessions:
        is_current = s["session_id"] == st.session_state.current_session_id
        label = ("🟢 " if is_current else "🗨️ ") + s["title"]
        # 当前会话高亮（primary），其余普通按钮（secondary）；点谁切换到谁
        if st.button(label, key=s["session_id"], use_container_width=True,
                     type="primary" if is_current else "secondary"):
            st.session_state.current_session_id = s["session_id"]
            st.rerun()

    st.divider()

    # ---- 侧边栏第 2 区：数据文件（来自 day7）----
    st.header("📁 数据文件")

    uploaded = st.file_uploader("上传 CSV（默认使用项目自带 demo.csv）", type="csv")

    csv_path = "demo.csv"   # 默认使用项目根目录的演示文件
    if uploaded is not None:
        os.makedirs("uploads", exist_ok=True)              # 确保目录存在
        csv_path = os.path.join("uploads", uploaded.name).replace(os.sep, "/")
        with open(csv_path, "wb") as f:                    # "wb" = 二进制写模式
            f.write(uploaded.getbuffer())                  # 把上传内容写进文件
        st.success(f"已保存: {csv_path}")

    st.info(f"当前数据文件：`{csv_path}`\n\n试试问：\n"
            "- 这个文件有哪些列？\n"
            "- 按地区统计一下销量总和\n"
            "- 把各地区的销量画成柱状图\n"
            "- 计算 (3+5)*12 等于多少")

    # 清空当前对话：删掉后端的会话记忆（新增的 DELETE 接口）+ 换新会话 ID
    if st.button("🗑️ 清空当前对话", use_container_width=True):
        requests.delete(f"{API_URL}/sessions/{st.session_state.current_session_id}",
                        timeout=5)
        st.session_state.current_session_id = str(uuid.uuid4())
        st.rerun()


# ---- 健康检查：后端没开就友好提示并停止 ----
try:
    requests.get(f"{API_URL}/health", timeout=2)
except requests.exceptions.ConnectionError:
    st.error("⚠️ 后端未启动！请先运行：`uvicorn api:app --port 8000`")
    st.stop()   # 停止执行后面的所有代码（页面到此为止）


# ---- 渲染当前会话的聊天记录（从后端拉取）----
# 为什么不学 day7 存在 st.session_state.messages 里？
# 因为整合后后端 /sessions/{id} 已经存了全部对话，
# 前端再存一份就要自己维护两边同步，切会话时还得处理缓存失效——得不偿失。
try:
    history = requests.get(f"{API_URL}/sessions/{st.session_state.current_session_id}",
                           timeout=5).json()
except Exception:
    history = []

for msg in history:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        for img_url in msg.get("images", []):
            st.image(f"{API_URL}{img_url}")   # 拼上后端地址显示图片


# ---- 用户输入区 ----
# 海象运算符 := ："赋值的同时判断"——输入了内容(非空)才进 if
if user_input := st.chat_input("输入你的问题…"):
    # 步骤 1：立刻显示用户的消息
    with st.chat_message("user"):
        st.write(user_input)

    # 步骤 2：调用后端拿回答（后端负责记忆，前端只管展示）
    with st.chat_message("assistant"):
        with st.spinner("Agent 思考中…"):
            try:
                r = requests.post(
                    f"{API_URL}/chat",
                    json={
                        "session_id": st.session_state.current_session_id,
                        "message": user_input,          # 干净的原始问题（标题也取自它）
                        "data_file": csv_path,          # 数据文件单独传（整合改动点）
                    },
                    timeout=120,   # Agent 可能连环调用工具，放宽到 120 秒
                )
                r.raise_for_status()   # 状态码不是 2xx 就抛异常，进入下面的友好提示
                resp = r.json()
            except Exception as e:
                # 不让页面直接崩出红色堆栈，而是告诉用户常见原因
                st.error(f"⚠️ 请求失败：{e}\n\n"
                         "常见原因：后端未启动；或模型报错（查看后端终端的日志，"
                         "比如模型未开通、密钥失效）。刚才的问题后端已记下，可直接重试。")
                st.stop()

        st.write(resp["reply"])
        for img_url in resp.get("images", []):
            st.image(f"{API_URL}{img_url}")

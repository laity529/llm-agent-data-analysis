# ============ 导入部分 ============

# FastAPI：现代 Python 后端框架，用"装饰器"把普通函数变成 HTTP 接口
from fastapi import FastAPI, HTTPException
# CORSMiddleware：跨域中间件。浏览器默认禁止"网页 A 去请求服务 B"，
# 我们的前端(:8501)要请求后端(:8000)，属于跨域，必须放行
from fastapi.middleware.cors import CORSMiddleware
# StaticFiles：把一个文件夹变成"可网址访问的静态资源目录"
from fastapi.staticfiles import StaticFiles
# BaseModel：pydantic 的基类，用来定义"请求/响应的 JSON 长什么样"
from pydantic import BaseModel

# 导入我们自己的 Agent 模块和记忆模块
import agent
import memory

# 创建 FastAPI 应用实例
# 整合后标题里带上"多会话"：记忆管理从 day4 搬进了后端
app = FastAPI(title="多会话数据分析 Agent API")

# ---- 配置跨域放行 ----
# 三个 * 的意思：允许任何来源、任何方法、任何头（教学图省事；
# 生产环境应把 allow_origins 写成具体的前端地址）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# ---- 把 charts 文件夹挂载成静态资源 ----
# charts/xxx.png 可以通过 http://localhost:8000/charts/xxx.png 直接访问
app.mount("/charts", StaticFiles(directory="charts"), name="charts")


# ============ 定义请求/响应的数据格式 ============

class ChatRequest(BaseModel):
    """前端 POST 过来的 JSON 必须长这样"""
    session_id: str                  # 会话 ID：区分不同对话（day4 的多会话）
    message: str                     # 用户输入的问题
    data_file: str = "demo.csv"      # 当前数据文件路径（day7 原来拼在 message 里，整合后单独传）


class ChatResponse(BaseModel):
    """后端返回给前端的 JSON 长这样"""
    reply: str                   # Agent 的文字回答
    images: list[str] = []       # 本轮生成的图表网址列表，默认空列表


class SessionInfo(BaseModel):
    """一个会话的摘要（侧边栏列表的每一行，day4 体验的后端版）"""
    session_id: str
    title: str
    message_count: int
    created_at: float


class HistoryMessage(BaseModel):
    """历史消息列表里的一条（role + 内容 + 该回复附带的图表）"""
    role: str                    # "user" 或 "assistant"
    content: str
    images: list[str] = []


def _to_url(path: str) -> str:
    """本地路径转网址：charts/xxx.png -> /charts/xxx.png（聊天和历史接口共用）"""
    return path.replace("charts", "/charts", 1)


# ============ 接口 1：健康检查 ============

@app.get("/health")
def health():
    return {"status": "ok"}


# ============ 接口 2：核心聊天接口（day7 原有，记忆部分升级） ============

@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(req: ChatRequest):
    result = agent.chat(req.session_id, req.message, req.data_file)
    return ChatResponse(reply=result["reply"],
                        images=[_to_url(img) for img in result["images"]])


# ============ 接口 3：会话列表（day4 侧边栏"历史消息"的后端化） ============

@app.get("/sessions", response_model=list[SessionInfo])
def sessions_endpoint():
    """返回所有会话的摘要（ID、标题、消息数），前端侧边栏渲染成会话切换列表。"""
    return memory.list_sessions()


# ============ 接口 4：单个会话的历史（day4 "切回旧会话能看到全部记录"） ============

@app.get("/sessions/{session_id}", response_model=list[HistoryMessage])
def history_endpoint(session_id: str):
    """返回某会话的完整聊天记录。工具中间消息不展示，
    但其中生成的图表会归属到对应的 AI 回复上一并返回。"""
    history = memory.get_history(session_id)
    # 图片路径同样要转成网址，前端才能显示
    for msg in history:
        msg["images"] = [_to_url(img) for img in msg.get("images", [])]
    return history


# ============ 接口 5：删除会话（前端"清空当前对话"按钮用） ============

@app.delete("/sessions/{session_id}")
def delete_session_endpoint(session_id: str):
    if not memory.delete_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"status": "deleted"}

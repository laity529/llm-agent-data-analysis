"""
memory.py —— 会话记忆中心（本项目整合 day4 + day7 的核心）

两个项目原来各自的记忆方案：
  day4《langchain处理记忆(自动添加历史消息).py》：
      sessions 字典 + get_session_history(session_id) + InMemoryChatMessageHistory
      → 好处：多会话隔离、按 session_id 存取
  day7《agent.py》：
      _sessions 字典直接存 Agent 跑完的完整消息列表（含工具调用消息）
      → 好处：Agent 记得中间过程，下一轮能接着说"再画一张柱状图"

整合方案：把两者合并成一个专门的记忆模块——
  1. 保留 day4 的"按 session_id 存取"模式（get_session 相当于 get_session_history）
  2. 保留 day7 的"存完整 Agent 消息列表"实现（Agent 场景必须存工具消息）
  3. 加上 day4 Streamlit 侧边栏需要的元数据：会话标题（取第一条提问）、创建时间
  4. 提供前端接口需要的三种读法：列表 / 单会话历史 / 删除

局限（和 day7 相同，要记住）：数据在内存里，后端一重启就全丢；
生产环境应把 _sessions 换成 Redis 或数据库，接口不用变。
"""

import re
import threading
import time

# 会话仓库：{ session_id: {"messages": [...], "title": str, "created_at": float} }
# messages 里存的是 LangChain 消息对象（HumanMessage/AIMessage/ToolMessage...）
_sessions: dict = {}

# uvicorn 处理请求可能开多个线程，加锁防止两个请求同时改字典出错
_lock = threading.Lock()

# 从工具返回的文本里提取图表路径的正则：能匹配 charts/chart_bar_region.png
# （也兼容 Windows 反斜杠写法 charts\chart_bar_region.png）
_CHART_RE = re.compile(r"charts[/\\][\w\-]+\.(?:png|jpg|jpeg)", re.IGNORECASE)

# 剥掉用户消息开头的"（当前数据文件: xxx）"前缀（agent.py 拼进去给模型看的上下文，
# 存进历史没问题——模型下一轮还用得上，但展示给用户时要还原成干净的原始提问）
_FILE_PREFIX_RE = re.compile(r"^（当前数据文件: [^）]*）\s*")


def get_session(session_id: str) -> dict:
    """取出（或初始化）一个会话 —— 对应 day4 的 get_session_history()

    setdefault 的思路：有就返回，没有就先建一个空会话再返回。
    """
    with _lock:
        if session_id not in _sessions:
            _sessions[session_id] = {
                "messages": [],          # Agent 的完整消息历史（day7 的存法）
                "title": "新对话",        # 侧边栏标题（day4 的"第一条消息当标题"）
                "created_at": time.time(),
            }
        return _sessions[session_id]


def get_messages(session_id: str) -> list:
    """拿该会话的完整消息历史，作为 Agent 本轮的输入。"""
    return get_session(session_id)["messages"]


def save_messages(session_id: str, messages: list) -> None:
    """把 Agent 跑完的完整消息列表存回 = 记住这一轮（day7 的第 4 步）。

    存的是 result["messages"]，包含中间所有工具调用消息，
    所以下一轮用户说"再画一张柱状图"，模型知道上一轮发生了什么。
    """
    get_session(session_id)["messages"] = messages


def set_title_if_new(session_id: str, user_input: str) -> None:
    """day4 的细节：会话的第一条用户提问当作标题，显示在侧边栏列表里。

    只截前 20 个字，防止特别长的问题把侧边栏撑爆。
    """
    session = get_session(session_id)
    if session["title"] == "新对话" and user_input.strip():
        session["title"] = user_input.strip()[:20]


def list_sessions() -> list[dict]:
    """所有【有内容】的会话的摘要列表（前端侧边栏的数据源），新的会话排前面。

    过滤掉空会话：前端每次打开页面都会产生一个全新会话 ID，
    还没说过话的会话不该出现在历史列表里。
    """
    with _lock:
        items = [
            {
                "session_id": sid,
                "title": s["title"],
                "message_count": len(s["messages"]),
                "created_at": s["created_at"],
            }
            for sid, s in _sessions.items() if s["messages"]
        ]
    items.sort(key=lambda x: x["created_at"], reverse=True)
    return items


def extract_chart_paths(text: str) -> list[str]:
    """从一段文本（通常是工具的返回结果）里提取图表路径，统一成正斜杠。

    agent.py 找"本轮画了哪些图"、get_history() 恢复历史图表，都用这一个函数。
    """
    return [p.replace("\\", "/") for p in _CHART_RE.findall(text or "")]


def get_history(session_id: str) -> list[dict]:
    """把会话消息整理成前端好渲染的 JSON 列表。

    LangChain 消息有三种类型：
      human -> 用户消息，直接展示
      ai    -> 模型消息；注意中间过程也有 ai 消息（发起工具调用、content 为空），
               只展示有文字的最终回答
      tool  -> 工具消息（中间过程，不直接展示），但从里面提取生成的图表路径，
               归属到紧随其后的 AI 回复上，这样"切换会话回来"图表还能显示
    """
    out = []
    pending_images: list[str] = []   # 还没找到"主人"的图表路径
    # 只读接口：会话不存在就返回空列表，不要顺手创建（否则会产生一堆空会话）
    with _lock:
        messages = list(_sessions.get(session_id, {}).get("messages", []))
    for m in messages:
        role = getattr(m, "type", "")
        if role == "human":
            out.append({"role": "user", "content": _FILE_PREFIX_RE.sub("", m.content),
                        "images": []})
        elif role == "tool":
            pending_images += extract_chart_paths(m.content)
        elif role == "ai":
            content = m.content if isinstance(m.content, str) else ""
            # 有文字（最终回答）或有图（它调用的工具画的）才显示一个气泡
            if content or pending_images:
                out.append({"role": "assistant", "content": content,
                            "images": pending_images})
                pending_images = []
    return out


def delete_session(session_id: str) -> bool:
    """删除一个会话（对应前端"清空当前对话"）。返回是否真的删了。"""
    with _lock:
        return _sessions.pop(session_id, None) is not None

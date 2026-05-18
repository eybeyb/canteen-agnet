import json
import uuid
import logging
import time

import fastapi
from typing import Optional, Dict
from fastapi import Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from service import diancan_service
from api.models import (
    ChatRequest, ChatResponse,
    SendMessageRequest, SendMessageResponse,
    MenuListResponse, DishItem,
)
from service.diancan_service import amap_service

logger = logging.getLogger(__name__)

# ============ 懒加载 Agent ============
_default_agent = None

def get_default_agent():
    global _default_agent
    if _default_agent is None:
        try:
            from agent.smart_agent import init_agent, tools
        except ImportError:
            from smart_dian_can.agent.smart_agent import init_agent, tools
        _default_agent = init_agent(tools=tools)
        logger.info("Agent 初始化完成")
    return _default_agent

# ============ FastAPI 应用 ============
app = fastapi.FastAPI(
    description="点餐智能体控制系统",
    title="点餐智能体控制系统",
    version="1.0.0",
)

# CORS 配置（生产环境请替换为具体域名）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 请求追踪中间件 ============
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    start_time = time.time()

    # 注入 request_id 到日志上下文
    old_factory = logging.getLogRecordFactory()
    def record_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        record.request_id = request_id
        return record
    logging.setLogRecordFactory(record_factory)

    response = await call_next(request)

    elapsed = time.time() - start_time
    logger.info(f"[{request_id}] {request.method} {request.url.path} - {response.status_code} - {elapsed:.3f}s")

    response.headers["X-Request-ID"] = request_id
    logging.setLogRecordFactory(old_factory)
    return response


# ============ 全局异常处理 ============
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    request_id = request.headers.get("X-Request-ID", "unknown")
    logger.error(f"[{request_id}] 未捕获异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "response": "",
            "error": "服务暂时不可用，请稍后重试",
            "request_id": request_id,
        }
    )


# ============ 路由 ============

@app.get("/")
def index():
    return {"message": "Hello World", "version": "1.0.0"}


@app.get("/send_message_test", response_model=SendMessageResponse)
def send_message_get(
    destination: str = Query(default="罗湖区高新技术产业第一园区", description="配送地址"),
    mode: str = Query(default="electrobike", description="交通工具"),
):
    """查询配送信息（GET方式，方便快速测试）"""
    try:
        message_data = amap_service.get_distance_duration_and_delivery(destination, mode)
        return {
            "destination": destination,
            "success": message_data.get("status") == "success",
            "data": message_data,
        }
    except Exception as e:
        logger.error(f"配送查询失败: {e}")
        return {
            "destination": destination,
            "success": False,
            "data": {"status": "error", "error_message": str(e)},
        }


@app.post("/send_message", response_model=SendMessageResponse)
def send_message_post(request: SendMessageRequest):
    """查询配送信息（POST方式，适合前端正式调用）"""
    try:
        message_data = amap_service.get_distance_duration_and_delivery(request.destination)
        return {
            "destination": request.destination,
            "success": message_data.get("status") == "success",
            "data": message_data,
        }
    except Exception as e:
        logger.error(f"配送查询失败: {e}")
        return {
            "destination": request.destination,
            "success": False,
            "data": {"status": "error", "error_message": str(e)},
        }


@app.get("/menu", response_model=MenuListResponse)
def get_menu():
    dishes = diancan_service.get_all_dish()
    return {"success": True, "data": dishes, "count": len(dishes)}


@app.post("/chat", response_model=ChatResponse)
def chat_with_agent(request: ChatRequest, x_user_id: Optional[str] = fastapi.Header(None)):
    """
    与智能点餐 Agent 对话（支持多轮记忆）

    每个用户独立的对话历史：
    - 请求头 X-User-Id 来区分不同用户
    - 不传则每次都是新会话
    """
    try:
        agent = get_default_agent()
        thread_id = x_user_id or str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        result = agent.invoke(
            {"messages": [("human", request.message)]},
            config=config,
        )

        output = result.get("messages", [])
        if output:
            ai_message = output[-1]
            ai_content = ai_message.content if hasattr(ai_message, "content") else str(ai_message)
        else:
            ai_content = ""

        try:
            parsed = json.loads(ai_content)
            friendly_reply = parsed.get("friendly_reply", ai_content)
        except (json.JSONDecodeError, TypeError):
            friendly_reply = ai_content

        return {"success": True, "response": friendly_reply}
    except Exception as e:
        logger.error(f"对话失败 user={x_user_id}: {e}")
        return {"success": False, "response": "", "error": str(e)}
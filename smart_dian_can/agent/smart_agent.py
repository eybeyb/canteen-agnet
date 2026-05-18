"""
智能点餐 Agent 模块

在 Agent 初始化时自动从 提示词/ 目录加载所有 .txt 文件内容，
注入到 system prompt 中，让 LLM 在对话开始时就已掌握商家基本信息，
无需额外调用工具即可回答常规问题（如营业时间、优惠活动等）。
"""

import os
import sys

import dotenv

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.memory import MemorySaver

from smart_dian_can.config import Config

# 确保能找到 smart_dian_can 下的各模块
if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.mcp import (
    load_all_prompts,
    get_prompt,
    recommend_dish,
    calculate_delivery_distance,
)

tools = [get_prompt, recommend_dish, calculate_delivery_distance]

dotenv.load_dotenv()


def build_system_prompt() -> str:
    """
    构建包含商家全部提示词信息的 system prompt。

    读取 提示词/ 目录下所有 .txt 文件，拼接成完整的商家信息上下文，
    嵌入到 system prompt 中。

    Returns:
        拼接后的 system prompt 字符串
    """
    # 加载所有提示词文件内容
    prompts_context = load_all_prompts()

    system_prompt = (
        "你是一名专业的智能点餐助手，服务于餐饮商家。你拥有以下商家信息作为知识库：\n"
    )

    if prompts_context:
        system_prompt += (
            f"\n【以下信息是商家预设的重要信息，请熟记并用于回答用户问题】\n"
            f"{prompts_context}\n\n"
        )
    else:
        system_prompt += (
            "\n注意：当前没有加载到任何预设的提示词信息，"
            "请通过调用'获取提示词'工具来获取商家信息。\n\n"
        )

    system_prompt += (
        "你的职责包括：\n"
        "1. 回答用户关于商家信息、营业时间、优惠活动、配送范围等常规问题\n"
        "2. 根据用户需求推荐菜品\n"
        "3. 协助用户完成点餐流程\n"
        "4. 查询配送信息\n\n"
        "【工具使用指南】\n"
        "你拥有以下工具可供调用，请根据用户需求主动选择合适的工具：\n"
        "- get_prompt：当用户询问商家信息时（营业时间、优惠活动、配送范围、点餐规则等），"
        "调用此工具获取预设信息并回答\n"
        "- recommend_dish：当用户需要推荐菜品时（口味、辣度、食材偏好等），调用此工具进行语义搜索推荐\n"
        "- calculate_delivery_distance：当用户询问配送信息时（能否送到某地址、配送时间、距离等），"
        "调用此工具查询配送信息\n\n"
        "请根据用户的具体需求，主动选择最合适的工具来提供最佳服务。"
        "输出要求：请先以JSON格式输出你的处理结果（包含思考过程和结构化数据），"
        "然后基于JSON内容生成一段自然友好、语气亲切的回复文本给顾客，"
        "回复中要包含所有必要信息，确保顾客能清楚理解。"
        "最终输出格式：{\"structured_data\": {...}, \"friendly_reply\": \"对顾客的友好回复\"}"
    )

    return system_prompt


def init_agent(tools_list: list = None, model_name: str = None):
    """
    创建智能点餐 Agent。

    在初始化时自动加载提示词文件内容注入到 system prompt 中，
    使 LLM 在对话开始前就掌握商家信息。
    使用 MemorySaver 作为记忆组件，支持多轮对话记忆。

    Args:
        tools_list: Agent 可调用的工具列表，默认使用模块级 tools
        model_name: 模型名称，默认从环境变量 LLM_MODE 读取

    Returns:
        编译后的 CompiledStateGraph 实例
    """
    if tools_list is None:
        tools_list = tools

    api_key = Config.DASHSCOPE_API_KEY
    base_url = Config.DASHSCOPE_API_BASE
    if not model_name:
        model_name = Config.LLM_MODE or "deepseek-v3-0.0.1"

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
    )

    # 构建 system prompt（自动注入提示词内容）
    system_prompt = build_system_prompt()

    # 创建记忆组件：MemorySaver 用于保存对话历史
    memory = MemorySaver()

    # 使用 create_react_agent 创建带记忆的 Agent
    agent = create_react_agent(
        model=llm,
        tools=tools_list,
        prompt=system_prompt,
        checkpointer=memory,
    )

    return agent


if __name__ == "__main__":
    # 测试模式：手动创建 Agent 并测试
    agent = init_agent()
    config = {"configurable": {"thread_id": "test-session-001"}}
    result = agent.invoke(
        {"messages": [("human", "我想吃火锅")]},
        config=config
    )
    print("\n=== 测试结果 ===")
    print(result["messages"][-1].content if result.get("messages") else "无输出")
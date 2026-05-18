"""
MCP (Model Context Protocol) 工具模块
提供从提示词文件加载内容的函数和业务工具
"""

import os
from pathlib import Path
from pydantic import BaseModel, Field
from langchain_core.tools.convert import tool


class RecommendedDish(BaseModel):
    """单条推荐菜品"""
    dish_name: str = Field(description="菜品名称")
    price: float = Field(description="价格")
    reason: str = Field(description="推荐理由")
    match_score: int = Field(description="匹配度 1-100")


class RecommendResult(BaseModel):
    """推荐结果"""
    summary: str = Field(description="一句话总结")
    dishes: list[RecommendedDish] = Field(description="推荐菜品列表")


def get_prompt_from_file(file_path: str) -> str:
    """
    从 提示词/ 目录下读取指定文件名的 .txt 文件内容

    Args:
        file_path: 文件名（不包含后缀和路径），例如 "商家基本信息"

    Returns:
        文件内容的字符串

    Raises:
        FileNotFoundError: 如果对应的 .txt 文件不存在
    """
    base_dir = Path(__file__).resolve().parent.parent
    prompt_file = base_dir / "提示词" / f"{file_path}.txt"

    if not prompt_file.exists():
        raise FileNotFoundError(
            f"提示词文件不存在: {prompt_file}。"
            f"请确认 提示词/ 目录下存在 {file_path}.txt 文件。"
        )

    with open(prompt_file, "r", encoding="utf-8") as f:
        content = f.read()

    return content


def load_all_prompts() -> str:
    """
    加载 提示词/ 目录下所有 .txt 文件的内容

    Returns:
        所有提示词文件内容的拼接字符串，每个文件用分隔符隔开
    """
    base_dir = Path(__file__).resolve().parent.parent
    prompt_dir = base_dir / "提示词"

    if not prompt_dir.exists():
        return ""

    all_content = []
    for txt_file in sorted(prompt_dir.glob("*.txt")):
        try:
            with open(txt_file, "r", encoding="utf-8") as f:
                content = f.read()
                all_content.append(f"\n{'='*50}\n【{txt_file.stem}】\n{'='*50}\n{content}")
        except Exception as e:
            print(f"警告：无法读取文件 {txt_file}: {e}")

    return "\n".join(all_content) if all_content else ""


# ============ 合并后的工具 ============

@tool(
    description="查询商家预设信息并回答用户问题。"
              "适用于用户询问营业时间、优惠活动、配送范围、点餐规则等常规问题。"
              "参数 question 是用户的问题（必填），file_path 是提示词文件名（不含路径和 .txt 后缀，例如 '商家基本信息'）。"
)
def get_prompt(question: str, file_path: str = "商家基本信息") -> str:
    """
    查询商家信息并回答用户问题

    从指定的提示词文件中获取预设信息，结合用户问题给出回答。
    合并了原有的 get_prompt 和 answer_general_question 功能。

    Args:
        question: 用户问题字符串，例如 "你们的营业时间是什么？"
        file_path: 提示词文件名（不包含路径和 .txt 后缀），
                   例如 "商家基本信息" 对应 提示词/商家基本信息.txt，
                   默认使用 "商家基本信息"

    Returns:
        包含预设信息和用户问题的综合回答字符串
    """
    base_info = get_prompt_from_file(file_path)

    return (
        f"以下是商家预设的 {file_path} 信息：\n\n"
        f"{base_info}\n\n"
        f"用户问题：{question}\n\n"
        f"请基于以上商家信息，用友好亲切的语言回答用户问题。"
    )


@tool(
    description="根据用户描述推荐菜品。"
              "适用于用户需要推荐菜品时（口味偏好、辣度、食材、场景等）。"
              "使用语义搜索从菜单中匹配最合适的菜品。"
              "参数 query 是用户需求描述，top_k 是推荐数量（默认3个）。"
)
def recommend_dish(query: str, top_k: int = 3) -> str:
    """
    智能菜品推荐

    根据用户的口味偏好、食材要求等，通过向量数据库进行语义搜索，
    推荐最匹配的菜品。

    Args:
        query: 用户需求描述，例如 "我想吃点辣的川菜"、"推荐清淡的素食"
        top_k: 返回的推荐菜品数量，默认3个

    Returns:
        格式化的推荐结果字符串
    """
    from smart_dian_can.tools.pinecone_tool import vector_db
    from smart_dian_can.tools.db_tool import DataBaseConnection

    # 从向量数据库搜索
    search_result = vector_db.search_menu(query, top_k=top_k)

    if not search_result or not search_result.get("results"):
        return "抱歉，暂时没有找到符合您需求的菜品，请换个关键词试试。"

    results = search_result["results"]

    # 获取完整菜单用于补充信息
    db = DataBaseConnection()
    all_menu = db.get_all_menu_items()

    # 构建推荐结果
    response_parts = [f"根据您的需求 \"{query}\"，为您推荐以下菜品：\n"]

    for i, item in enumerate(results, 1):
        response_parts.append(
            f"{i}. {item['dish_name']} - ¥{item['price']:.2f}\n"
            f"   分类：{item['category']} | 辣度：{item['spice_level']}\n"
            f"   口味：{item['flavor']} | 食材：{item['main_ingredients']}\n"
            f"   匹配度：{item['score']}\n"
        )

    return "\n".join(response_parts)


@tool(
    description="计算配送距离和时间。"
              "根据用户提供的配送地址和交通方式，计算与商家之间的距离、预计时间，"
              "并判断是否在配送范围内。"
              "默认使用电动车配送。用户提到走路/步行时用walking，提到开车/驾车/汽车时用driving。"
)
def calculate_delivery_distance(address: str, mode: str = "electrobike") -> str:
    """
    查询配送信息

    Args:
        address: 用户的配送地址
        mode: 交通方式，可选值：electrobike（默认）、walking、driving

    Returns:
        格式化的配送信息字符串
    """
    from smart_dian_can.tools.amap_tool import get_distance_time_and_is_can_send

    valid_modes = ["electrobike", "walking", "driving"]
    if mode not in valid_modes:
        mode = "electrobike"

    result = get_distance_time_and_is_can_send(address, mode)

    if result.get("status") == "error":
        return f"抱歉，无法查询到'{address}'的配送信息，请检查地址是否正确。"

    distance = result.get("distance", "未知")
    duration = result.get("duration", "未知")
    is_can_send = result.get("is_can_send", "未知")
    destination = result.get("destination", address)

    mode_display = {
        "electrobike": "🛵 电动车配送",
        "walking": "🚶 步行",
        "driving": "🚗 驾车"
    }
    mode_text = mode_display.get(mode, "🛵 电动车配送")

    response_parts = [
        f"📍 配送地址：{destination}",
        f"{mode_text}",
        f"📏 距离：{distance}",
        f"⏱️ 预计时间：{duration}",
        f"✅ 配送状态：{is_can_send}"
    ]

    if is_can_send == "可送达":
        response_parts.append("\n💡 温馨提示：您的地址在配送范围内，可以正常下单！")
    else:
        response_parts.append("\n⚠️ 温馨提示：您的地址超出配送范围，建议选择自取或联系店家协商。")

    return "\n".join(response_parts)
from pydantic import BaseModel, Field
from typing import Optional, List, Dict


class DishItem(BaseModel):
    id: int
    dish_name: str
    price: float
    description: Optional[str] = ""
    category: str
    spice_level: int
    spice_level_text: str
    flavor: Optional[str] = ""
    main_ingredients: Optional[str] = ""
    cooking_method: Optional[str] = ""
    is_vegetarian: bool = False
    allergens: Optional[str] = ""
    is_available: bool = True


# ====== 请求模型 ======

class ChatRequest(BaseModel):
    """对话请求"""
    message: str = Field(
        ...,
        description="用户消息",
        min_length=1,
        max_length=2000,
        example="我想吃点辣的川菜",
    )


class SendMessageRequest(BaseModel):
    """配送查询请求"""
    destination: str = Field(
        ...,
        description="配送地址",
        min_length=1,
        max_length=500,
        example="塑和公园华府",
    )


# ====== 响应模型 ======

class MenuListResponse(BaseModel):
    success: bool
    data: List[DishItem]
    count: int


class ChatResponse(BaseModel):
    success: bool
    response: str
    error: Optional[str] = None


class SendMessageResponse(BaseModel):
    destination: str
    success: bool
    data: Dict
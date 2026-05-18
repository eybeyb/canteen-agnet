"""
LLM 调用工具模块

统一管理大语言模型（DeepSeek / Qwen 等）的调用，
提供模块级快捷函数和类封装两种方式。
"""

import dotenv
from dotenv import load_dotenv

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

try:
    from config import Config
except ImportError:
    from smart_dian_can.config import Config

load_dotenv()


# ====== 模块级快捷函数 ======

def call_llm(query: str, system_prompt: str = "你是一个智能助理，可以帮助用户查询菜品信息，并提供相关推荐。") -> str:
    """
    模块级 LLM 调用函数，供 mcp.py 等外部模块直接使用。

    Args:
        query: 用户问题
        system_prompt: 系统提示词

    Returns:
        LLM 回复文本
    """
    llm = get_llm()
    chat_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{query}"),
    ])
    chain = chat_prompt | llm
    response = chain.invoke({"query": query})
    return response.content if hasattr(response, "content") else str(response)


# ====== LLM 客户端单例 ======

_llm = None


def get_llm():
    """获取 LLM 实例（单例模式），供模块级函数和外部直接调用"""
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=Config.LLM_MODE or "deepseek-v3-0.0.1",
            api_key=Config.DASHSCOPE_API_KEY,
            base_url=Config.DASHSCOPE_API_BASE or "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    return _llm


# ====== LLMTool 类（兼容旧调用方式）=====

class LLMTool:
    """LLM 工具类封装，兼容旧代码调用方式"""

    def __init__(self, model_name: str = None):
        self.model_name = model_name or Config.LLM_MODE or "deepseek-v3-0.0.1"
        self._model = None

    def get_llm(self):
        """获取 ChatOpenAI 实例"""
        if self._model is None:
            self._model = ChatOpenAI(
                model=self.model_name,
                api_key=Config.DASHSCOPE_API_KEY,
                base_url=Config.DASHSCOPE_API_BASE or "https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        return self._model

    def call_llm(self, query: str, system_prompt: str = "你是一个智能助理，可以帮助用户查询菜品信息，并提供相关推荐。") -> str:
        """调用 LLM 回答问题"""
        llm = self.get_llm()
        chat_prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("human", "{query}"),
        ])
        chain = chat_prompt | llm
        response = chain.invoke({"query": query})
        return response.content if hasattr(response, "content") else str(response)


if __name__ == "__main__":
    llm_tool = LLMTool()
    print(llm_tool.call_llm("我想吃火锅"))
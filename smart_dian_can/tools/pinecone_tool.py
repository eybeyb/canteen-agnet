"""
Pinecone 向量数据库工具模块
基于 Pinecone Built-in Inference（内置嵌入模型）快速入门模式
也兼容传统手动传入向量的方式
"""
import re
from typing import List, Dict, Any, Optional, Union

import dashscope
from langchain_text_splitters import CharacterTextSplitter
from pinecone import Pinecone

try:
    from config import Config
except ImportError:
    from smart_dian_can.config import Config
from smart_dian_can.logger import setup_logger
from smart_dian_can.tools.connection_retry import with_retry_and_fallback, make_degraded

logger = setup_logger(__name__)

from smart_dian_can.tools.db_tool import DataBaseConnection


class PineconeVectorDB:
    """
    Pinecone 向量数据库封装类
    采用内置嵌入模型方式（Pinecone 官方推荐）
    """

    # 默认配置
    DEFAULT_MODEL = "multilingual-e5-large"  # Pinecone 官方支持的通用嵌入模型
    DEFAULT_CLOUD = "aws"
    DEFAULT_REGION = "us-east-1"
    DEFAULT_INDEX_NAME = "smart-cat"

    def __init__(self):
        self.api_key = Config.PINECONE_API_KEY
        self.index_name = Config.PINECONE_INDEX_NAME or self.DEFAULT_INDEX_NAME
        self.cloud = Config.PINECONE_CLOUD
        self.region = Config.PINECONE_ENV
        self.model = Config.PINECONE_MODEL
        self.pc: Optional[Pinecone] = None
        self.index = None

        if not self.api_key or "your" in self.api_key.lower():
            logger.warning("Pinecone API Key 未配置，向量数据库功能将不可用")
        else:
            try:
                self.pc = Pinecone(api_key=self.api_key)
                logger.info("Pinecone 客户端初始化成功")
            except Exception as e:
                logger.error(f"Pinecone 客户端初始化失败: {e}")

    # ==================== 索引管理 ====================

    def initialize_index(self) -> bool:
        """
        初始化向量索引
        使用 create_index_for_model 创建支持内置嵌入模型的索引
        """
        if not self.pc:
            logger.warning("Pinecone 客户端未初始化，请先配置 PINECONE_API_KEY")
            return False

        try:
            if not self.pc.has_index(self.index_name):
                logger.info(
                    f"正在创建索引: {self.index_name} "
                    f"(模型={self.model}, 区域={self.region})"
                )
                self.pc.create_index_for_model(
                    name=self.index_name,
                    cloud=self.cloud,
                    region=self.region,
                    embed={
                        "model": self.model,
                        "field_map": {"text": "chunk_text"}
                    }
                )
                logger.info(f"索引 {self.index_name} 创建成功")
            else:
                logger.info(f"索引已存在: {self.index_name}")

            self.index = self.pc.Index(self.index_name)
            logger.info(f"索引连接成功: {self.index_name}")
            return True
        except Exception as e:
            logger.error(f"索引初始化失败: {e}")
            return False

    def delete_all(self) -> bool:
        """清空索引中所有数据"""
        if not self.index and not self.initialize_index():
            return False
        try:
            self.index.delete(delete_all=True)
            logger.info("已清空索引中所有数据")
            return True
        except Exception as e:
            logger.error(f"清空索引失败: {e}")
            return False

    def describe_index(self) -> Dict[str, Any]:
        """获取索引统计信息"""
        if not self.index and not self.initialize_index():
            return {}
        try:
            return self.index.describe_index_stats()
        except Exception as e:
            logger.error(f"获取索引信息失败: {e}")
            return {}

    # ==================== 用户流程函数（split / vector / upsert）====================

    def split(self, data: Union[str, List[str]], chunk_size: int = 150, chunk_overlap: int = 0) -> List[str]:
        """
        用 langchain 的 CharacterTextSplitter 将数据切分，返回切分结果
        data: str 或 List[str]
        """
        if isinstance(data, list):
            data = "\n".join(data)

        splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len
        )
        docs = splitter.create_documents(texts=[data])
        chunks = [doc.page_content.strip() for doc in docs if doc.page_content.strip()]
        logger.info(f"文本切分完成: {len(chunks)} 块")
        return chunks

    def vector(self, data: List[str]) -> List[Dict[str, Any]]:
        """
        传入数据列表，将数据向量化，得到向量化结果
        返回格式: [{"id": "1", "values": [0.1, ...], "metadata": {...}}, ...]
        """
        api_key = Config.DASHSCOPE_API_KEY

        if not api_key or "your" in api_key.lower():
            logger.error("DASHSCOPE_API_KEY 未配置，无法向量化")
            return []

        # 设置 DashScope API Key
        dashscope.api_key = api_key

        vectors = []
        for idx, text in enumerate(data, 1):
            try:
                # 调用 DashScope 嵌入 API
                response = dashscope.TextEmbedding.call(
                    model="text-embedding-v3",
                    input=text
                )

                # 检查响应是否成功
                if response.status_code == 200:
                    # 提取向量数据
                    embedding = response.output["embeddings"][0]["embedding"]


                    # 从文本中解析各个字段
                    dish_id = self._extract_field(text, r'菜品ID:(\d+)')
                    dish_name = self._extract_field(text, r'菜品名称:([^|]+)')
                    price = self._extract_field(text, r'价格:¥([0-9.]+)')
                    description = self._extract_field(text, r'菜品描述:([^|]+)')
                    category = self._extract_field(text, r'分类:([^|]+)')
                    spice_level = self._extract_field(text, r'辣度:([^|]+)')
                    flavor = self._extract_field(text, r'口味:([^|]+)')
                    main_ingredients = self._extract_field(text, r'主要食材:([^|]+)')
                    cooking_method = self._extract_field(text, r'烹饪方法:([^|]+)')
                    is_vegetarian = self._extract_field(text, r'素食:([^|]+)')
                    allergens = self._extract_field(text, r'过敏原:([^|]+)')

                    # 构建结构化的 metadata
                    record_id = dish_id if dish_id else f"chunk_{idx}"

                    vectors.append({
                        "id": record_id,
                        "values": embedding,
                        "metadata": {
                            "dish_id": int(dish_id) if dish_id else 0,
                            "dish_name": dish_name or "",
                            "price": float(price) if price else 0.0,
                            "description": description or "",
                            "category": category or "",
                            "spice_level": spice_level or "",
                            "flavor": flavor or "",
                            "main_ingredients": main_ingredients or "",
                            "cooking_method": cooking_method or "",
                            "is_vegetarian": is_vegetarian or "",
                            "allergens": allergens or "",
                            "search_text": text  # 保留完整文本用于搜索展示
                        }
                    })
                else:
                    logger.warning(f"向量化失败 [{idx}]: {response.message}")

            except Exception as e:
                logger.error(f"向量化异常 [{idx}]: {e}")

        logger.info(f"向量化完成: {len(vectors)} / {len(data)} 条")
        return vectors

    def search_vectors(self, query_vector: List[float], top_k: int = 5) -> List[Dict]:
        """
        使用向量搜索相似内容
        """
        if not self.index:
            logger.warning("索引未初始化，无法搜索向量")
            return []

        try:
            result = self.index.query(
                vector=query_vector,
                top_k=top_k,
                include_metadata=True,
                include_values=False
            )
            return result.get("matches", [])
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    def _extract_field(self, text: str, pattern: str) -> Optional[str]:
        """
        从文本中提取指定字段的值
        类似 Android 中使用正则表达式解析 JSON 或 XML 数据
        """
        match = re.search(pattern, text)
        return match.group(1).strip() if match else None

    def upsert(self, data: List[Dict[str, Any]]) -> bool:
        """
        将向量化的数据上传到 Pinecone
        data 格式: [{"id": "...", "values": [...], "metadata": {...}}, ...]
        """
        if not self.index and not self.initialize_index():
            return False
        try:
            self.index.upsert(vectors=data)
            logger.info(f"成功上传 {len(data)} 条向量到 Pinecone")
            return True
        except Exception as e:
            logger.error(f"上传向量失败: {e}")
            return False

    # ==================== 传统向量方式（手动提供向量） ====================

    def query_vectors(self, query: str) -> List[float]:
        """
        将查询文本转换为向量
        """
        api_key = Config.DASHSCOPE_API_KEY
        if not api_key or "your" in api_key.lower():
            logger.error("DASHSCOPE_API_KEY 未配置")
            return []

        dashscope.api_key = api_key

        try:
            resp = dashscope.TextEmbedding.call(
                model="text-embedding-v3",
                input=query
            )
            if resp.status_code == 200:
                query_embedding = resp.output["embeddings"][0]["embedding"]
                logger.info(f"查询文本已向量化，维度: {len(query_embedding)}")
                return query_embedding
            else:
                logger.warning(f"向量化失败: {resp.message}")
                return []
        except Exception as e:
            logger.error(f"向量化异常: {e}")
            return []
    # ==================== 内置模型方式（自动嵌入） ====================




    #将文本嵌入为向量

    # ==================== 业务封装：菜品向量操作 ====================


        # ... existing code ...
    @with_retry_and_fallback(
        max_retries=3,
        service_name="Pinecone搜索",
        fallback_data={"results": []}
    )
    def search_menu(self, query: str, top_k: int = 3) -> Dict[str, Any]:
            """
            根据用户描述搜索相关菜品（语义搜索）
            返回格式:
            {
                "results": [
                    {
                        "dish_id": 1,
                        "dish_name": "菜名",
                        "price": 25.0,
                        ...
                    }
                ]
            }
            """
            if not self.index and not self.initialize_index():
                return {}

            try:
                # 先将查询文本转换为向量
                query_vector = self.query_vectors(query)
                if not query_vector:
                    logger.error("查询文本向量化失败")
                    return {}

                # 使用向量搜索
                results = self.index.query(
                    vector=query_vector,
                    top_k=top_k,
                    include_metadata=True,
                    include_values=False
                )

                matches = results.get("matches", [])
                if not matches:
                    return {"results": []}

                # 格式化结果
                formatted_results = []
                for match in matches:
                    metadata = match.get("metadata", {})
                    formatted_results.append({
                        "dish_id": metadata.get("dish_id", 0),
                        "dish_name": metadata.get("dish_name", ""),
                        "price": metadata.get("price", 0.0),
                        "category": metadata.get("category", ""),
                        "spice_level": metadata.get("spice_level", ""),
                        "flavor": metadata.get("flavor", ""),
                        "main_ingredients": metadata.get("main_ingredients", ""),
                        "cooking_method": metadata.get("cooking_method", ""),
                        "is_vegetarian": metadata.get("is_vegetarian", ""),
                        "allergens": metadata.get("allergens", ""),
                        "description": metadata.get("description", ""),
                        "score": round(match.get("score", 0), 4)
                    })

                return {"results": formatted_results}
            except Exception as e:
                logger.error(f"菜品搜索失败: {e}")
                return {}
    # ... existing code ...
# ==================== 全局实例与快捷函数 ====================

vector_db = PineconeVectorDB()

if __name__ == "__main__":
        try:
            # 初始化向量数据库实例
            vector_db_instance = PineconeVectorDB()

            # 初始化索引（连接到 Pinecone）
            if not vector_db_instance.initialize_index():
                print("❌ 索引初始化失败")
                exit(1)

            # ========== 测试搜索功能 ==========
            query = "我想吃不那么辣的川菜"
            print(f"🔍 查询: \"{query}\"")

            search_result = vector_db_instance.search_menu(query, top_k=3)

            if search_result and "results" in search_result:
                results = search_result["results"]
                print(f"   找到 {len(results)} 个相关菜品:\n")
                for item in results:
                    end_item = (
                        f"菜品ID:{item['dish_id']}|"
                        f"菜品名称:{item['dish_name']}|"
                        f"价格:¥{item['price']:.2f}|"
                        f"菜品描述:{item['description']}|"
                        f"分类:{item['category']}|"
                        f"辣度:{item['spice_level']}|"
                        f"口味:{item['flavor']}|"
                        f"主要食材:{item['main_ingredients']}|"
                        f"烹饪方法:{item['cooking_method']}|"
                        f"素食:{item['is_vegetarian']}|"
                        f"过敏原:{item['allergens']}"
                    )
                    print(end_item)

            else:

                print("   未找到相关菜品")

        except Exception as e:
            print(f"❌ 执行失败: {e}")
            import traceback

            traceback.print_exc()


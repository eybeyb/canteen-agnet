# 智能点餐系统 - Day 01 开发文档

> 主题：Web应用搭建与工具封装  
> 讲师：胡中奎

---

## 阶段一：项目初始化

### 1.1 创建项目结构

在目标目录下执行：

```
smart_dian_can/
├── api/                    # API接口层
│   ├── __init__.py
│   ├── main.py            # FastAPI主应用
│   └── models.py          # 数据模型定义
├── tools/                 # 工具层
│   ├── __init__.py
│   ├── db_tool.py         # MySQL数据库工具
│   ├── pinecone_tool.py   # Pinecone向量数据库工具
│   ├── amap_tool.py       # 高德地图工具
│   └── llm_tool.py        # LLM调用工具
├── service/               # 服务层
│   ├── __init__.py
│   └── diancan_service.py # 业务服务
├── prompt/                # 提示词模板
│   ├── general_inquiry.txt
│   └── menu_inquiry.txt
├── run.py                 # 启动脚本
├── requirements.txt       # 依赖文件
└── .env                   # 环境变量配置
```

### 1.2 创建 requirements.txt

```txt
fastapi>=0.100.0
uvicorn[standard]>=0.23.0
mysql-connector-python~=9.4.0
pinecone~=7.3.0
dashscope>=1.14.0
langchain>=1.0.7
pydantic>=2.0.0
python-dotenv>=1.0.0
requests>=2.31.0
```

### 1.3 创建 .env 配置文件

```env
# 高德地图API配置
AMAP_API_KEY=your_amap_api_key

# 商户经纬度（武汉市洪山区茅店山中路创新汇天颐科技园）
MERCHANT_LONGITUDE=114.401934
MERCHANT_LATITUDE=30.465295

# 配送范围（米）
DELIVERY_RADIUS=2500

# 配送模式：1=步行，2=骑行(默认)，3=驾车
DEFAULT_PATH_MODE=2

# LLM配置（通义千问）
DASHSCOPE_API_KEY=your_dashscope_api_key
DASHSCOPE_API_BASE=https://dashscope.aliyuncs.com/api/v1
LLM_MODE=qwen-plus

# Pinecone配置
PINECONE_API_KEY=your_pinecone_api_key
PINECONE_ENV=us-east-1

# MySQL配置
MYSQL_HOST=your_host
MYSQL_PORT=3306
MYSQL_USER=root
MYSQL_PASSWORD=your_password
MYSQL_DATABASE=menu
```

---

## 阶段二：FastAPI Web应用搭建

### 2.1 创建 api/__init__.py

```python
```

### 2.2 创建 api/models.py

```python
"""
API数据模型定义
"""
from pydantic import BaseModel
from typing import Optional, List


class ChatRequest(BaseModel):
    """智能对话请求"""
    query: str


class DeliveryRequest(BaseModel):
    """配送查询请求"""
    address: str
    travel_mode: Optional[int] = 3  # 1=步行, 2=骑行, 3=驾车


class ChatResponse(BaseModel):
    """智能对话响应"""
    success: bool
    query: str
    response: Optional[str] = None
    recommendation: Optional[str] = None
    menu_ids: Optional[List[str]] = None


class DeliveryResponse(BaseModel):
    """配送查询响应"""
    success: bool
    in_range: bool
    distance: float
    formatted_address: str
    message: str
    travel_mode: int
    input_address: str


class MenuListResponse(BaseModel):
    """菜品列表响应"""
    success: bool
    menu_items: List[dict]
    count: int
    message: str
```

### 2.3 创建 api/main.py

```python
"""
FastAPI主应用
提供三个主要接口：
1. POST /chat - 智能对话接口
2. POST /delivery - 配送查询接口
3. GET /menu/list - 菜品列表接口
"""
from fastapi import FastAPI, HTTPException
from api.models import (
    ChatRequest, ChatResponse,
    DeliveryRequest, DeliveryResponse,
    MenuListResponse
)
import sys
import os

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 导入服务
from service.diancan_service import smart_chat, delivery_check
from tools.db_tool import get_menu_items_list

# 创建FastAPI应用
app = FastAPI(
    title="AiMenu智能点餐系统",
    description="智能餐厅助手API，提供智能对话、配送查询和菜品列表服务",
    version="2.0.0"
)


@app.get("/")
async def root():
    """根路径"""
    return {"message": "欢迎使用AiMenu智能点餐系统API"}


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "healthy", "service": "AiMenu API"}


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """智能对话接口"""
    try:
        result = smart_chat(request.query)

        if isinstance(result, dict) and "recommendation" in result:
            return ChatResponse(
                success=True,
                query=request.query,
                recommendation=result["recommendation"],
                menu_ids=result.get("menu_ids")
            )
        else:
            return ChatResponse(
                success=True,
                query=request.query,
                response=str(result)
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"智能对话服务失败: {str(e)}")


@app.post("/delivery", response_model=DeliveryResponse)
async def delivery_endpoint(request: DeliveryRequest):
    """配送查询接口"""
    try:
        result = delivery_check(request.address, request.travel_mode)

        if result["status"] == "success":
            return DeliveryResponse(
                success=True,
                in_range=result["in_range"],
                distance=result["distance"],
                formatted_address=result["formatted_address"],
                message=result["message"],
                travel_mode=request.travel_mode,
                input_address=request.address
            )
        else:
            return DeliveryResponse(
                success=False,
                in_range=False,
                distance=0.0,
                formatted_address=request.address,
                message=result["message"],
                travel_mode=request.travel_mode,
                input_address=request.address
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"配送查询服务失败: {str(e)}")


@app.get("/menu/list", response_model=MenuListResponse)
async def menu_list_endpoint():
    """菜品列表接口"""
    try:
        structured_data = get_menu_items_list()

        if not structured_data:
            return MenuListResponse(
                success=False,
                menu_items=[],
                count=0,
                message="当前没有可用的菜品信息"
            )

        return MenuListResponse(
            success=True,
            menu_items=structured_data,
            count=len(structured_data),
            message=f"成功获取 {len(structured_data)} 个菜品信息"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"菜品列表服务失败: {str(e)}")
```

### 2.4 创建 run.py

```python
"""
启动脚本
"""
import uvicorn


def main():
    """启动AiMenu API服务"""
    print("🍽️ AiMenu 智能点餐系统 v2.0")
    print("=" * 50)
    print("✅ 环境配置检查通过")
    print("🚀 正在启动API服务...")
    print("📍 服务地址: http://localhost:8000")
    print("📖 API文档: http://localhost:8000/docs")
    print("=" * 50)

    try:
        uvicorn.run(
            "api.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except Exception as e:
        print(f"❌ 启动失败: {e}")


if __name__ == "__main__":
    main()
```

---

## 阶段三：工具层开发

### 3.1 创建 tools/__init__.py

```python
```

### 3.2 创建 tools/db_tool.py（MySQL工具）

> 功能：连接MySQL数据库，查询菜品信息

```python
"""
MySQL数据库工具模块
查询menu数据库中的menu_items表的全部信息
"""
from typing import List, Dict, Any
import mysql.connector
import logging
from dotenv import load_dotenv
import os

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DataBaseConnection:
    """数据库连接管理类"""

    def __init__(self):
        self.connection = None
        self.cursor = None
        self.host = os.getenv("MYSQL_HOST", "localhost")
        self.port = int(os.getenv("MYSQL_PORT", "3306"))
        self.user = os.getenv("MYSQL_USER", "root")
        self.password = os.getenv("MYSQL_PASSWORD", "root")
        self.database = os.getenv("MYSQL_DATABASE", "menu")

    def connect(self) -> bool:
        """建立数据库连接"""
        try:
            self.connection = mysql.connector.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset="utf8mb4"
            )
            if self.connection.is_connected():
                self.cursor = self.connection.cursor(dictionary=True)
                logger.info(f"已成功建立数据库连接,数据库: {self.database}")
                return True
            else:
                logger.error(f"数据库连接关闭,数据库: {self.database}")
                return False
        except mysql.connector.Error as e:
            logger.error(f"数据库连接错误,异常原因 {e}")
            return False

    def dis_connect(self):
        """关闭数据库连接"""
        try:
            if self.cursor:
                self.cursor.close()
                self.cursor = None
            if self.connection and self.connection.is_connected():
                self.connection.close()
                self.connection = None
                logger.info(f"已成功关闭数据库连接")
        except mysql.connector.Error as e:
            logger.error(f"关闭数据库连接错误,异常原因 {e}")
            raise

    def __enter__(self):
        """上下文管理器入口"""
        if self.connect():
            return self
        else:
            raise Exception("无法建立数据库连接")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.dis_connect()


def get_all_menu_items() -> str:
    """
    获取所有菜单项（字符串格式，用于向量数据库）
    Returns:
        str: 所有菜品信息拼接成的完整字符串
    """
    try:
        with DataBaseConnection() as db:
            query_sql = """
                SELECT id, dish_name, price, description, category,
                       spice_level, flavor, main_ingredients, cooking_method,
                       is_vegetarian, allergens, is_available
                FROM menu_items
                WHERE is_available = 1
                ORDER BY category, dish_name
            """
            db.cursor.execute(query_sql)
            menu_items = db.cursor.fetchall()

            if not menu_items:
                return "当前没有找到任何菜品信息"

            menu_strings = []
            for item in menu_items:
                description_text = item.get('description', '') if item.get('description', '').strip() else "未知描述"
                allergens_text = item.get('allergens', '') if item.get('allergens', '').strip() else "无过敏原"
                main_ingredients_text = item.get('main_ingredients', '') if item.get('main_ingredients', '').strip() else "未知食材"
                spice_level_map = {"0": "不辣", "1": "微辣", "2": "中辣", "3": "重辣"}
                spice_text = spice_level_map.get(str(item["spice_level"]), "未知辣度")
                vegetarian_text = "是" if item['is_vegetarian'] else "否"

                menu_string = (
                    f"菜品ID:{item['id']}|菜品名称:{item['dish_name']}|价格:¥{item['price']:.2f}"
                    f"|菜品描述:{description_text}|分类:{item['category']}|辣度:{spice_text}"
                    f"|口味:{item['flavor']}|主要食材:{main_ingredients_text}"
                    f"|烹饪方法:{item['cooking_method']}|素食:{vegetarian_text}|过敏原:{allergens_text}"
                )
                menu_strings.append(menu_string)

            all_menu_info = "\n".join(menu_strings)
            logger.info(f"已成功查询到菜品信息，菜品数量: {len(menu_strings)}个")
            return all_menu_info
    except Exception as e:
        logger.error(f"查询菜品信息失败: {e}")
        return "查询菜品信息失败"


def get_menu_items_list() -> List[dict]:
    """
    获取所有菜单项（字典列表格式，用于API响应）
    Returns:
        List[dict]: 菜品信息的字典列表
    """
    try:
        with DataBaseConnection() as db:
            query_sql = """
                SELECT id, dish_name, price, description, category,
                       spice_level, flavor, main_ingredients, cooking_method,
                       is_vegetarian, allergens, is_available
                FROM menu_items
                WHERE is_available = 1
                ORDER BY category, dish_name
            """
            db.cursor.execute(query_sql)
            menu_items_result = db.cursor.fetchall()

            if not menu_items_result:
                logger.error("查询菜品信息失败: 没有找到任何菜品信息")
                return []

            menu_items = []
            spice_levels = {0: "不辣", 1: "微辣", 2: "中辣", 3: "重辣"}

            for item in menu_items_result:
                spice_text = spice_levels.get(item['spice_level'], "未知")

                processed_item = {
                    "id": item['id'],
                    "dish_name": item['dish_name'],
                    "price": float(item['price']),
                    "formatted_price": f"¥{item['price']:.2f}",
                    "description": item['description'] or "暂无描述",
                    "category": item['category'],
                    "spice_level": item['spice_level'],
                    "spice_text": spice_text,
                    "flavor": item['flavor'] or "暂无口味",
                    "main_ingredients": item['main_ingredients'] or "暂无主要食材",
                    "cooking_method": item['cooking_method'] or "暂无烹饪方法",
                    "is_vegetarian": bool(item['is_vegetarian']),
                    "vegetarian_text": "是" if item['is_vegetarian'] else "否",
                    "allergens": item['allergens'] if item['allergens'] and item['allergens'].strip() else "暂无过敏原",
                    "is_available": bool(item['is_available'])
                }
                menu_items.append(processed_item)

            logger.info(f"已成功查询到菜品信息，菜品数量: {len(menu_items)}个")
            return menu_items
    except Exception as e:
        logger.error(f"查询菜品结构化信息失败: {e}")
        return []


def get_menu_item_by_id(item_id: str) -> Dict[str, Any]:
    """根据菜品ID获取单个菜品信息"""
    try:
        with DataBaseConnection() as db:
            sql_query = """
                SELECT id, dish_name, price, description, category,
                       spice_level, flavor, main_ingredients, cooking_method,
                       is_vegetarian, allergens, is_available
                FROM menu_items
                WHERE id = %s AND is_available = 1
            """
            db.cursor.execute(sql_query, (item_id,))
            item = db.cursor.fetchone()

            if not item:
                logger.error(f"查询菜品ID{item_id}信息失败")
                return {}

            spice_levels = {0: "不辣", 1: "微辣", 2: "中辣", 3: "重辣"}
            spice_text = spice_levels.get(item['spice_level'], "未知")

            return {
                "id": item['id'],
                "dish_name": item['dish_name'],
                "price": float(item['price']),
                "formatted_price": f"¥{item['price']:.2f}",
                "description": item['description'] or "暂无描述",
                "category": item['category'],
                "spice_level": item['spice_level'],
                "spice_text": spice_text,
                "flavor": item['flavor'] or "暂无口味",
                "main_ingredients": item['main_ingredients'] or "暂无主要食材",
                "cooking_method": item['cooking_method'] or "暂无烹饪方法",
                "is_vegetarian": bool(item['is_vegetarian']),
                "vegetarian_text": "是" if item['is_vegetarian'] else "否",
                "allergens": item['allergens'] if item['allergens'] and item['allergens'].strip() else "暂无过敏原",
                "is_available": bool(item['is_available'])
            }
    except Exception as e:
        logger.error(f"查询菜品ID{item_id}信息失败: {e}")
        return {}


def get_menu_items_by_category() -> Dict[str, Any]:
    """按分类获取菜品信息"""
    try:
        menu_items = get_menu_items_list()
        if not menu_items:
            return {}

        menu_items_by_category = {}
        for item in menu_items:
            category = item['category']
            if category not in menu_items_by_category:
                menu_items_by_category[category] = []
            menu_items_by_category[category].append(item)

        return menu_items_by_category
    except Exception as e:
        logger.error(f"根据分类查询菜品信息失败: {e}")
        return {}


if __name__ == '__main__':
    # 测试数据库连接
    print("\n1. 测试数据库连接...")
    with DataBaseConnection() as db:
        db.cursor.execute("SELECT 1")
        result = db.cursor.fetchone()
        if result:
            print("✅ 数据库操作成功")

    # 测试获取菜品列表
    print("\n2. 测试获取所有菜单项...")
    results = get_menu_items_list()
    if results:
        print(f"✅ 获取到 {len(results)} 个菜品")
        for item in results[:3]:
            print(f"   - {item['dish_name']}: {item['formatted_price']}")
```

### 3.3 创建 tools/pinecone_tool.py（Pinecone向量数据库工具）

> 功能：存储和检索菜品向量数据，支持语义搜索

```python
"""
Pinecone向量数据库工具模块
存储和查询菜品信息的向量化数据，支持语义搜索
"""
import os
import re
import dashscope
from typing import List, Dict, Any
from pinecone import Pinecone
from pinecone.models import ServerlessSpec
from langchain.text_splitter import CharacterTextSplitter
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PineconeVectorDB:
    """Pinecone向量数据库管理类"""

    def __init__(self):
        self.dashscope_api_key = os.getenv("DASHSCOPE_API_KEY")
        self.pinecone_api_key = os.getenv("PINECONE_API_KEY")
        self.pinecone_env = os.getenv("PINECONE_ENV", "us-east-1")
        self.index_name = "menu-items1"
        self.model_name = "text-embedding-v4"
        self.dimension = 1536
        self.pc = None
        self.index = None

    def initialize(self) -> bool:
        """初始化Pinecone连接和索引"""
        try:
            if not self.pinecone_api_key:
                return False

            self.pc = Pinecone(api_key=self.pinecone_api_key)

            if not self.pc.has_index(self.index_name):
                self.pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric="cosine",
                    spec=ServerlessSpec(cloud="aws", region=self.pinecone_env)
                )

            self.index = self.pc.Index(self.index_name)
            logger.info(f"Pinecone索引 {self.index_name} 初始化成功")
            return True
        except Exception as e:
            logger.error(f"初始化Pinecone连接失败,原因: {e}")
            return False

    def get_dashscope_embedding(self, text: str) -> List[float]:
        """使用DashScope生成文本向量"""
        try:
            resp = dashscope.TextEmbedding.call(
                model=self.model_name,
                input=text,
                dimension=self.dimension
            )

            if resp.status_code == 200:
                embedding = resp["output"]["embeddings"][0]["embedding"]
                return embedding
            else:
                return []
        except Exception as e:
            logger.error(f"生成文本向量失败,原因: {e}")
            return []

    def _get_menu_data_from_db(self) -> str:
        """从数据库获取菜单数据"""
        try:
            from tools.db_tool import get_all_menu_items
            return get_all_menu_items()
        except Exception as e:
            logger.error(f"获取菜单数据失败,原因: {e}")
            return ""

    def _is_valid_menu_data(self, menu_data: str) -> bool:
        """验证菜单数据有效性"""
        if not menu_data:
            return False
        invalid_prefixes = ("当前没有", "查询失败")
        return not menu_data.startswith(invalid_prefixes)

    def _split_menu_data(self, menu_data: str) -> List[str]:
        """文本分割"""
        try:
            text_splitter = CharacterTextSplitter(
                separator="\n",
                chunk_size=150,
                chunk_overlap=0,
                length_function=len
            )
            dcos = text_splitter.create_documents(texts=[menu_data])
            return [doc.page_content.strip() for doc in dcos]
        except Exception as e:
            logger.error(f"文本分割失败,原因: {e}")
            return []

    def upsert_menu_data(self, menu_data: str = None, batch_size: int = 100, clear_existing: bool = True) -> bool:
        """批量插入菜品数据到向量数据库"""
        try:
            if not self.index and not self.initialize():
                return False

            if clear_existing:
                self.delete_all_items_vector_data()

            if menu_data is None:
                menu_data = self._get_menu_data_from_db()
                if not self._is_valid_menu_data(menu_data):
                    return False

            lines = self._split_menu_data(menu_data)
            if not lines:
                return False

            batch = []
            for line_num, line in enumerate(lines, 1):
                vector = self.get_dashscope_embedding(line)
                if vector and len(vector) == self.dimension:
                    metadata = {"content": line, "line_number": line_num, "type": "menu_item"}
                    record_id = f"menu_{line_num}"
                    batch.append((record_id, vector, metadata))

                    if len(batch) >= batch_size:
                        self.index.upsert(vectors=batch)
                        batch = []

            if batch:
                self.index.upsert(vectors=batch)
            logger.info(f"成功同步 {len(lines)} 条菜品数据到Pinecone")
            return True
        except Exception as e:
            logger.error(f"批量同步数据失败,原因: {e}")
            return False

    def similar_search_items(self, query: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """根据查询文本搜索相似的菜品"""
        try:
            if not self.index and not self.initialize():
                return []

            query_vector = self.get_dashscope_embedding(query)
            if not query_vector or len(query_vector) != self.dimension:
                return []

            result = self.index.query(vector=query_vector, top_k=top_k, include_metadata=True)

            similar_result = []
            for item in result['matches']:
                match_item = {
                    "id": item['id'],
                    "score": item['score'],
                    "content": item['metadata']['content'],
                    "line_number": item['metadata']['line_number']
                }
                similar_result.append(match_item)
            return similar_result
        except Exception as e:
            logger.error(f"查询向量数据失败,原因: {e}")
            return []

    def delete_all_items_vector_data(self) -> bool:
        """删除所有向量数据"""
        try:
            if not self.index and not self.initialize():
                return False

            stats = self.index.describe_index_stats()
            count = stats.total_vector_count

            if count == 0:
                return True

            self.index.delete(delete_all=True)
            logger.info("已删除所有向量数据")
            return True
        except Exception as e:
            logger.error(f"删除向量数据失败: {e}")
            return False


# 全局实例
vector_db = PineconeVectorDB()


def pinecone_connection() -> bool:
    """测试Pinecone连接"""
    return vector_db.initialize()


def sync_pinecone_data_from_database() -> bool:
    """从数据库同步数据到Pinecone"""
    return vector_db.upsert_menu_data(menu_data=None, clear_existing=True)


def search_menu_items_with_id(query: str, top_k: int = 2) -> Dict[str, Any]:
    """根据查询搜索相关菜品，返回带ID的结果"""
    try:
        similar_result = vector_db.similar_search_items(query=query, top_k=top_k)

        if not similar_result:
            return {}

        item_ids = []
        for item in similar_result:
            content = item['content']
            match = re.search(r'菜品ID:(\d+)', content)
            if match:
                item_ids.append(match.group(1))
            else:
                item_ids.append(item["id"])

        return {
            "contents": [item['content'] for item in similar_result],
            "ids": item_ids,
            "scores": [item['score'] for item in similar_result]
        }
    except Exception as e:
        logger.error(f"查询相似性菜品信息失败: {e}")
        return {}


if __name__ == "__main__":
    # 测试Pinecone连接
    print("\n1. 测试Pinecone连接...")
    if pinecone_connection():
        print("✅ Pinecone连接成功")

    # 测试数据同步
    print("\n2. 测试数据同步...")
    if sync_pinecone_data_from_database():
        print("✅ 数据同步成功")

    # 测试语义搜索
    print("\n3. 测试语义搜索...")
    result = search_menu_items_with_id("我想点川菜", top_k=2)
    if result:
        print(f"✅ 找到 {len(result['contents'])} 条相似菜品")
        for i, content in enumerate(result['contents']):
            print(f"   - {content[:50]}... (相似度: {result['scores'][i]:.4f})")
```

### 3.4 创建 tools/amap_tool.py（高德地图工具）

> 功能：计算配送距离和范围检查

```python
"""
高德地图工具模块
提供根据三种路径（步行、骑行、驾车）的配送距离查询
"""
import requests
from typing import Dict, Optional, Literal, Union, Any
import json
from requests import RequestException
import os
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3 import Retry
from dataclasses import dataclass
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 类型定义
PathMode = Literal["walking", "bicycling", "driving"]
PathModeInput = Literal["1", "2", "3"]


@dataclass
class Config:
    API_KEY: str = os.getenv("AMAP_API_KEY")
    MERCHANT_LONGITUDE: str = os.getenv("MERCHANT_LONGITUDE", "114.401934")
    MERCHANT_LATITUDE: str = os.getenv("MERCHANT_LATITUDE", "30.465295")
    DELIVERY_RADIUS: int = int(os.getenv("DELIVERY_RADIUS", "2500"))
    DEFAULT_PATH_MODE: PathModeInput = os.getenv("DEFAULT_PATH_MODE", "2")

    def __post_init__(self):
        if not self.API_KEY:
            raise ValueError("AMAP_API_KEY 环境变量未设置")


config = Config()


class PathModeConverter:
    """路径模式转换工具类"""

    MODE_MAPPING = {
        "1": "walking",
        "2": "bicycling",
        "3": "driving",
    }

    @classmethod
    def to_mode(cls, mode_input: PathModeInput) -> PathMode:
        """将输入的模式转换为内部使用的模式"""
        if mode_input in cls.MODE_MAPPING:
            return cls.MODE_MAPPING[mode_input]
        else:
            raise ValueError(f"不支持的路径模式: {mode_input}，支持的模式: {list(cls.MODE_MAPPING.keys())}")


def create_session_with_retries():
    """创建带重试机制的requests会话"""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def safe_request(base_url: str, params: dict) -> Optional[Dict]:
    """安全的HTTP请求，处理重试和SSL降级"""
    session = create_session_with_retries()
    try:
        response = session.get(base_url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.SSLError:
        try:
            http_url = base_url.replace("https://", "http://")
            response = session.get(http_url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise RequestException(f"HTTP请求失败: {e}")
    except requests.exceptions.RequestException as e:
        raise RequestException(f"HTTPS请求失败: {e}")
    except json.JSONDecodeError as e:
        raise json.JSONDecodeError(f"JSON解析错误: {e}")


def geocode_address(address: str) -> Dict[str, Any]:
    """地理编码：将地址转换为坐标"""
    try:
        if not config.API_KEY:
            raise ValueError("API_KEY不存在")

        base_url = "https://restapi.amap.com/v3/geocode/geo"
        params = {
            "key": config.API_KEY,
            "address": address,
            "output": "JSON"
        }

        response_data = safe_request(base_url, params)
        if response_data["status"] == "1" and int(response_data["count"]) > 0:
            geocodes = response_data["geocodes"]
            if geocodes and len(geocodes) > 0:
                return {
                    "formatted_address": geocodes[0]["formatted_address"],
                    "location": geocodes[0]["location"],
                    "status": "success"
                }

        return {"status": "fail", "message": "高德地图地理坐标解析失败"}
    except Exception as e:
        logger.error(f"高德地图地理坐标解析失败,原因:{e}")
        raise


def calculate_distance(origin_location: str, destination_location: str,
                       path_mode_input: PathModeInput = "2") -> Dict[str, Any]:
    """计算两个地点之间的距离和预计时间"""
    try:
        if not config.API_KEY:
            raise ValueError("AMAP_API_KEY不存在")

        path_mode = PathModeConverter.to_mode(path_mode_input)

        endpoints = {
            "walking": "https://restapi.amap.com/v5/direction/walking",
            "bicycling": "https://restapi.amap.com/v5/direction/electrobike",
            "driving": "https://restapi.amap.com/v5/direction/driving"
        }

        params = {
            "key": config.API_KEY,
            "origin": origin_location,
            "destination": destination_location,
        }

        if path_mode == "driving":
            params["show_fields"] = "cost"

        response = safe_request(endpoints[path_mode], params)
        if response.get("status") == "1":
            path = response["route"]["paths"][0]
            duration = int(path["duration"]) if path_mode == "bicycling" else int(path["cost"]["duration"])
            return {
                "distance": int(path["distance"]),
                "duration": duration,
                "status": "success"
            }

        return {"status": "fail", "message": "高德地图距离解析失败"}
    except Exception as e:
        logger.error(f"高德地图距离解析失败,原因:{e}")
        raise


def check_delivery_range(address: str, path_mode_input: PathModeInput = None) -> Dict[str, Any]:
    """检查地址是否在配送范围内"""
    try:
        if path_mode_input is None:
            path_mode_input = config.DEFAULT_PATH_MODE

        geocode_result = geocode_address(address)
        if geocode_result['status'] != "success":
            logger.error("地理位置编码失败")
            return geocode_result

        origin_location = f"{config.MERCHANT_LONGITUDE},{config.MERCHANT_LATITUDE}"
        distance_result = calculate_distance(origin_location, geocode_result['location'], path_mode_input)
        if distance_result['status'] != "success":
            return distance_result

        in_range = distance_result['distance'] <= config.DELIVERY_RADIUS
        distance_km = round(distance_result['distance'] / 1000, 2)
        return {
            "status": "success",
            "in_range": in_range,
            "distance": distance_km,
            "duration": distance_result['duration'],
            "formatted_address": geocode_result['formatted_address'],
            "message": (
                f"配送地址：{geocode_result['formatted_address']}\n"
                f"配送距离：{distance_km:.2f}公里\n"
                f"配送状态：{'在配送范围内' if in_range else '超出配送范围'}"
            )
        }
    except Exception as e:
        raise


if __name__ == "__main__":
    test_address = "武汉市洪山区光谷天地"

    print("\n=== 测试配送范围查询 ===")

    # 步行模式
    print("\n1. 步行模式测试:")
    result1 = check_delivery_range(test_address, "1")
    if result1['status'] == 'success':
        print(f"   距离: {result1['distance']}公里, 时间: {result1['duration']}秒")
        print(f"   {result1['message']}")

    # 骑行模式
    print("\n2. 骑行模式测试:")
    result2 = check_delivery_range(test_address, "2")
    if result2['status'] == 'success':
        print(f"   距离: {result2['distance']}公里, 时间: {result2['duration']}秒")
        print(f"   {result2['message']}")

    # 驾车模式
    print("\n3. 驾车模式测试:")
    result3 = check_delivery_range(test_address, "3")
    if result3['status'] == 'success':
        print(f"   距离: {result3['distance']}公里, 时间: {result3['duration']}秒")
        print(f"   {result3['message']}")
```

### 3.5 创建 tools/llm_tool.py（LLM调用工具）

> 功能：封装大模型调用（通义千问）

```python
"""
LLM调用工具模块
封装通义千问大模型调用
"""
import os
import dashscope
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LLMClient:
    """LLM客户端封装"""

    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY")
        self.api_base = os.getenv("DASHSCOPE_API_BASE", "https://dashscope.aliyuncs.com/api/v1")
        self.model = os.getenv("LLM_MODE", "qwen-plus")

        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY 环境变量未设置")

        dashscope.api_key = self.api_key

    def chat(self, prompt: str, system_prompt: str = None) -> str:
        """
        调用大模型进行对话

        Args:
            prompt: 用户输入
            system_prompt: 系统提示词

        Returns:
            str: 模型生成的回复
        """
        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = dashscope.Generation.call(
                model=self.model,
                messages=messages,
                result_format='message',
            )

            if response.status_code == 200:
                return response['output']['choices'][0]['message']['content']
            else:
                logger.error(f"LLM调用失败: {response.message}")
                return f"抱歉，LLM调用失败: {response.message}"
        except Exception as e:
            logger.error(f"LLM调用异常: {e}")
            return f"抱歉，发生了错误: {str(e)}"


# 全局实例
llm_client = LLMClient()


def chat_with_llm(prompt: str, system_prompt: str = None) -> str:
    """快捷调用函数"""
    return llm_client.chat(prompt, system_prompt)


if __name__ == "__main__":
    # 测试LLM调用
    print("\n=== 测试LLM调用 ===")
    response = chat_with_llm("你好，请介绍一下你自己")
    print(f"回复: {response}")
```

---

## 阶段四：服务层开发

### 4.1 创建 service/__init__.py

```python
```

### 4.2 创建 service/diancan_service.py

> 功能：业务服务层，组合调用各工具

```python
"""
点餐业务服务层
组合调用工具层，提供智能对话和配送查询服务
"""
import os
from dotenv import load_dotenv
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入工具
from tools.db_tool import get_menu_item_by_id
from tools.pinecone_tool import search_menu_items_with_id, pinecone_connection, sync_pinecone_data_from_database
from tools.amap_tool import check_delivery_range
from tools.llm_tool import chat_with_llm


def smart_chat(query: str) -> dict:
    """
    智能对话服务

    Args:
        query: 用户查询

    Returns:
        dict: 包含回复内容或推荐结果的字典
    """
    try:
        # 初始化向量数据库（如未初始化）
        if not pinecone_connection():
            logger.warning("Pinecone连接失败，使用纯对话模式")

        # 1. 判断是否为菜品推荐意图
        recommendation_keywords = ["推荐", "点", "想吃", "有没有", "菜单", "菜"]
        is_recommendation = any(keyword in query for keyword in recommendation_keywords)

        if is_recommendation:
            # 2. 语义搜索相关菜品
            search_result = search_menu_items_with_id(query, top_k=3)

            if search_result and search_result.get('ids'):
                # 3. 获取菜品详细信息
                recommended_items = []
                for item_id in search_result['ids']:
                    item = get_menu_item_by_id(item_id)
                    if item:
                        recommended_items.append(item)

                if recommended_items:
                    # 4. 构建推荐回复
                    recommendation_text = "根据您的需求，我为您推荐以下菜品：\n"
                    for i, item in enumerate(recommended_items, 1):
                        recommendation_text += (
                            f"{i}. {item['dish_name']} - {item['formatted_price']}\n"
                            f"   描述: {item['description']}\n"
                            f"   分类: {item['category']} | 辣度: {item['spice_text']}\n"
                        )

                    return {
                        "recommendation": recommendation_text,
                        "menu_ids": search_result['ids']
                    }

        # 5. 非推荐意图，使用纯对话模式
        # 加载提示词模板
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompt",
            "general_inquiry.txt"
        )

        system_prompt = ""
        if os.path.exists(prompt_path):
            with open(prompt_path, 'r', encoding='utf-8') as f:
                system_prompt = f.read()

        # 调用LLM
        response = chat_with_llm(query, system_prompt if system_prompt else None)
        return {"response": response}

    except Exception as e:
        logger.error(f"智能对话服务异常: {e}")
        return {"response": f"抱歉，服务发生了错误: {str(e)}"}


def delivery_check(address: str, travel_mode: int = 3) -> dict:
    """
    配送范围检查服务

    Args:
        address: 用户地址
        travel_mode: 出行模式 (1=步行, 2=骑行, 3=驾车)

    Returns:
        dict: 包含配送检查结果的字典
    """
    try:
        # 转换出行模式
        path_mode = str(travel_mode) if travel_mode else "2"

        # 调用高德地图API检查配送范围
        result = check_delivery_range(address, path_mode)

        return result

    except Exception as e:
        logger.error(f"配送查询服务异常: {e}")
        return {
            "status": "fail",
            "message": f"配送查询失败: {str(e)}"
        }


if __name__ == "__main__":
    # 测试智能对话
    print("\n=== 测试智能对话服务 ===")
    result = smart_chat("我想吃川菜，有什么推荐吗？")
    if "recommendation" in result:
        print("菜品推荐:")
        print(result["recommendation"])
        print(f"推荐菜品ID: {result.get('menu_ids')}")
    else:
        print(f"回复: {result.get('response')}")

    # 测试配送查询
    print("\n=== 测试配送查询服务 ===")
    result = delivery_check("武汉市洪山区光谷天地", 2)
    if result['status'] == 'success':
        print(result['message'])
    else:
        print(f"查询失败: {result.get('message')}")
```

---

## 阶段五：提示词模板

### 5.1 创建 prompt/general_inquiry.txt

```
你是一个智能餐厅助手，名字叫小Ai。

你的职责：
1. 回答用户关于餐厅的问题
2. 引导用户进行点餐
3. 提供餐厅相关信息（营业时间、地址、联系方式等）
4. 如果用户询问的超出你的能力范围，请友好地告知用户

注意事项：
- 回答要简洁友好
- 如果不确定答案，请诚实告知用户
- 引导用户使用点餐功能获取菜品推荐
```

### 5.2 创建 prompt/menu_inquiry.txt

```
你是一个专业的菜品推荐助手。

当用户想要点餐或询问菜品时，你应该：
1. 了解用户的口味偏好（如：辣、不辣、清淡、重口味等）
2. 了解用户的饮食限制（如：素食、海鲜过敏等）
3. 根据用户的描述，推荐合适的菜品
4. 详细介绍推荐的菜品（价格、口味、主要食材等）

回复格式：
推荐菜品：
1. [菜品名称] - ¥[价格]
   [简短描述]

请根据用户的需求提供个性化推荐。
```

---

## 阶段六：初始化数据库

### 6.1 MySQL建表语句

```sql
CREATE DATABASE IF NOT EXISTS menu CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE menu;

CREATE TABLE IF NOT EXISTS menu_items (
    id VARCHAR(36) PRIMARY KEY,
    dish_name VARCHAR(100) NOT NULL COMMENT '菜品名称',
    price DECIMAL(10, 2) NOT NULL COMMENT '价格',
    description TEXT COMMENT '菜品描述',
    category VARCHAR(50) NOT NULL COMMENT '分类：川菜、湘菜、粤菜等',
    spice_level TINYINT DEFAULT 0 COMMENT '辣度：0不辣 1微辣 2中辣 3重辣',
    flavor VARCHAR(50) COMMENT '口味：麻辣、清淡、咸鲜等',
    main_ingredients TEXT COMMENT '主要食材',
    cooking_method VARCHAR(50) COMMENT '烹饪方法',
    is_vegetarian TINYINT DEFAULT 0 COMMENT '是否素食：0否 1是',
    allergens TEXT COMMENT '过敏原',
    is_available TINYINT DEFAULT 1 COMMENT '是否上架：0下架 1上架',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='菜品表';
```

### 6.2 测试数据

```sql
USE menu;

INSERT INTO menu_items (id, dish_name, price, description, category, spice_level, flavor, main_ingredients, cooking_method, is_vegetarian, allergens) VALUES
('1', '宫保鸡丁', 38.00, '经典川菜，鸡丁香嫩，花生酥脆，酸甜微辣', '川菜', 2, '麻辣', '鸡胸肉、花生、干辣椒', '炒', 0, '花生'),
('2', '麻婆豆腐', 28.00, '四川名菜，豆腐嫩滑，麻辣鲜香', '川菜', 3, '麻辣', '豆腐、牛肉末、豆瓣酱', '烧', 0, '豆瓣酱'),
('3', '水煮鱼', 68.00, '鱼肉鲜嫩，麻辣过瘾，分量足', '川菜', 3, '麻辣', '草鱼、豆芽、豆皮', '水煮', 0, '鱼类'),
('4', '回锅肉', 42.00, '肥而不腻，色泽红亮，下饭神器', '川菜', 2, '香辣', '五花肉、青蒜、豆瓣酱', '炒', 0, '豆瓣酱'),
('5', '酸辣土豆丝', 18.00, '酸辣爽口，开胃小菜', '川菜', 1, '酸辣', '土豆、干辣椒、醋', '炒', 1, '无'),
('6', '清蒸鲈鱼', 58.00, '鱼肉鲜嫩，清淡可口', '粤菜', 0, '清淡', '鲈鱼、葱姜、蒸鱼豉油', '蒸', 0, '鱼类'),
('7', '白切鸡', 68.00, '皮脆肉嫩，原汁原味', '粤菜', 0, '鲜香', '三黄鸡、葱姜、蘸料', '煮', 0, '鸡肉'),
('8', '叉烧', 48.00, '色泽红亮，甜香可口', '粤菜', 0, '甜香', '猪肉、叉烧酱、蜂蜜', '烤', 0, '猪肉'),
('9', '干炒牛河', 38.00, '镬气十足，牛肉嫩滑', '粤菜', 0, '咸香', '牛肉、河粉、豆芽', '炒', 0, '牛肉'),
('10', '剁椒鱼头', 78.00, '鱼肉鲜美，剁椒香辣', '湘菜', 2, '香辣', '鱼头、剁椒、葱姜', '蒸', 0, '鱼类'),
('11', '辣椒炒肉', 32.00, '湖南特色，香辣下饭', '湘菜', 2, '香辣', '五花肉、螺丝椒、豆豉', '炒', 0, '豆豉'),
('12', '臭豆腐', 22.00, '外酥里嫩，闻臭吃香', '湘菜', 2, '香辣', '豆腐、辣椒油、蒜汁', '炸', 0, '无');
```

---

## 阶段七：测试与运行

### 7.1 安装依赖

```bash
cd smart_dian_can
pip install -r requirements.txt
```

### 7.2 配置环境变量

编辑 `.env` 文件，填入真实的API密钥：
- AMAP_API_KEY：高德地图API密钥
- DASHSCOPE_API_KEY：阿里云百炼API密钥
- PINECONE_API_KEY：Pinecone API密钥
- MySQL连接信息

### 7.3 初始化数据库

```bash
mysql -u root -p < sql/init.sql
```

### 7.4 测试各个模块

```bash
# 测试数据库连接
python tools/db_tool.py

# 测试Pinecone
python tools/pinecone_tool.py

# 测试高德地图
python tools/amap_tool.py

# 测试LLM
python tools/llm_tool.py

# 测试服务层
python service/diancan_service.py
```

### 7.5 启动服务

```bash
python run.py
```

启动后访问：
- API文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/health
- 菜品列表：http://localhost:8000/menu/list

---

## 项目架构回顾

```
┌─────────────────────────────────────────────────────────┐
│                      API层 (api/)                       │
│   POST /chat    │  POST /delivery  │  GET /menu/list   │
└──────────────┬──────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────┐
│                    服务层 (service/)                     │
│        smart_chat()      │      delivery_check()         │
└──────────────┬──────────────────────────────────────────┘
               │
┌──────────────▼──────────────────────────────────────────┐
│                     工具层 (tools/)                      │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌────────┐  │
│  │db_tool   │  │pinecone_  │  │ amap_tool│  │llm_tool│  │
│  │(MySQL)   │  │tool       │  │(高德地图) │  │(通义千问)│  │
│  └────┬─────┘  └─────┬─────┘  └─────┬─────┘  └────┬────┘  │
└───────┼─────────────┼───────────────┼─────────────┼───────┘
        │             │               │             │
        ▼             ▼               ▼             ▼
    ┌────────┐   ┌──────────┐   ┌─────────┐   ┌──────────┐
    │ MySQL  │   │ Pinecone │   │ 高德API │   │ DashScope│
    │ menu库 │   │ 向量数据库│   │ 地理编码│   │  通义千问 │
    └────────┘   └──────────┘   └─────────┘   └──────────┘
```

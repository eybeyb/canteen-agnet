
from typing import List, Dict, Any, Optional

try:
    from tools.db_tool import DataBaseConnection
    from tools.pinecone_tool import PineconeVectorDB
    from tools.amap_tool import get_distance_time_and_is_can_send
except ImportError:
    from smart_dian_can.tools.db_tool import DataBaseConnection
    from smart_dian_can.tools.pinecone_tool import PineconeVectorDB
    from smart_dian_can.tools.amap_tool import get_distance_time_and_is_can_send


class DiancanService:
    """点餐业务服务层，封装数据库操作"""

    def __init__(self, database: Optional[str] = None):
        self._database = database

    def _db(self) -> DataBaseConnection:
        return DataBaseConnection(database=self._database)

    def get_all_dish(self) -> List[Dict[str, Any]]:
        """获取所有可供应菜品"""
        return self._db().get_all_dish()

    def get_menu_text(self) -> str:
        """获取菜单的文本化字符串，用于向量数据库/LLM 上下文"""
        return self._db().get_all_menu_items()

    def get_dish_by_id(self, dish_id: int) -> Optional[Dict[str, Any]]:
        """根据菜品 ID 查询单个菜品"""
        return self._db().get_dish_by_id(dish_id)

    def get_dish_by_name(self, dish_name: str) -> List[Dict[str, Any]]:
        """根据菜品名称模糊搜索"""
        return self._db().get_dish_by_name(dish_name)

    def test_connection(self) -> bool:
        """测试数据库连通性"""
        return self._db().test_conn()


diancan_service = DiancanService()


class PineconeService:
    """向量数据库服务层，封装 Pinecone 操作"""

    def __init__(self):
        self._vector_db = PineconeVectorDB()

    @property
    def is_available(self) -> bool:
        """Pinecone 客户端是否可用"""
        return self._vector_db.pc is not None

    def initialize_index(self) -> bool:
        """初始化向量索引"""
        return self._vector_db.initialize_index()

    def upsert(self, vectors) -> bool:
        """批量写入向量"""
        return self._vector_db.upsert(vectors)

    def search_vectors(self, query_vector, top_k: int = 5):
        """根据查询向量搜索相似项"""
        return self._vector_db.search_vectors(query_vector, top_k=top_k)

    def search_menu(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """根据文本搜索菜品（自动嵌入，语义搜索）"""
        return self._vector_db.search_menu(query, top_k=top_k)

pinecone_service = PineconeService()
#封装amaptoolapi
class AmapService:
    #获取距离时间和是否配送
    def get_distance_duration_and_delivery(self, destination: str, traffic_mode: str = "electrobike") -> Dict[str, Any]:
        """
        获取距离、时间和是否可配送信息

        Args:
            destination: 配送地址
            traffic_mode: 交通方式，默认电动车(electrobike)

        Returns:
            包含状态、距离、时间和是否可送达的字典
        """
        from smart_dian_can.tools.amap_tool import get_distance_time_and_is_can_send
        return get_distance_time_and_is_can_send(destination, traffic_mode)

amap_service=AmapService()

if __name__ == "__main__":
    print("连接测试:", diancan_service.test_connection())
    print("\n=== 菜品列表 ===")
    for dish in diancan_service.get_all_dish():
        print(f"{dish['dish_name']} - {dish['spice_level_text']} - ¥{dish['price']}")

    print("\n=== 菜单文本 ===")
    print(diancan_service.get_menu_text())

    print("\n=== Pinecone 状态 ===")
    if pinecone_service.is_available:
        print("Pinecone 客户端可用，尝试初始化索引:", pinecone_service.initialize_index())
    else:
        print("Pinecone API Key 未配置，跳过向量库测试")
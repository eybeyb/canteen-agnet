# 数据库封装 - 带连接池
import mysql.connector
from mysql.connector import Error, pooling
from typing import Optional, List, Dict, Any
from functools import wraps

from smart_dian_can.config import Config
from smart_dian_can.logger import setup_logger

logger = setup_logger(__name__)

# ============ 连接池配置 ============
_pool_name = "smart_dian_can_pool"
_pool_size = 5
_connection_pool = None


def _get_pool() -> pooling.MySQLConnectionPool:
    """懒加载连接池"""
    global _connection_pool
    if _connection_pool is None:
        _connection_pool = pooling.MySQLConnectionPool(
            pool_name=_pool_name,
            pool_size=_pool_size,
            pool_reset_session=True,
            host=Config.MYSQL_HOST,
            port=Config.MYSQL_PORT,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DATABASE,
            charset="utf8mb4",
        )
        logger.info(f"数据库连接池初始化成功 (pool_size={_pool_size})")
    return _connection_pool


# ============ 菜单格式化（公共方法） ============

_SPICE_LEVEL_MAP = {
    0: "不辣",
    1: "微辣",
    2: "中辣",
    3: "重辣",
}


def _format_dish_string(item: Dict[str, Any]) -> str:
    """将单条菜品字典格式化为管道分隔的字符串"""
    description = item.get("description", "") or "未知描述"
    allergens = item.get("allergens", "") or "无过敏原"
    ingredients = item.get("main_ingredients", "") or "未知食材"
    spice = _SPICE_LEVEL_MAP.get(item.get("spice_level") or 0, "未知辣度")
    vegetarian = "是" if item.get("is_vegetarian") else "否"

    return (
        f"菜品ID:{item['id']}|菜品名称:{item['dish_name']}|"
        f"价格:¥{item['price']:.2f}|菜品描述:{description}|"
        f"分类:{item['category']}|辣度:{spice}|口味:{item.get('flavor', '')}|"
        f"主要食材:{ingredients}|烹饪方法:{item.get('cooking_method', '')}|"
        f"素食:{vegetarian}|过敏原:{allergens}"
    )


def _enrich_dish(item: Dict[str, Any]) -> Dict[str, Any]:
    """补充菜品字段（类型转换、辣度文本）"""
    item["price"] = float(item.get("price", 0))
    item["is_vegetarian"] = bool(item.get("is_vegetarian", False))
    spice = item.get("spice_level") or 0
    item["spice_level"] = spice
    item["spice_level_text"] = _SPICE_LEVEL_MAP.get(spice, "不辣")
    return item


# ============ 模块级快捷函数 ============

def get_all_menu() -> List[str]:
    """获取所有可用菜品的格式化字符串列表"""
    try:
        with DataBaseConnection() as db:
            sql = """SELECT id, dish_name, price, description, category,
                            spice_level, flavor, main_ingredients, cooking_method,
                            is_vegetarian, allergens
                     FROM menu_items
                     WHERE is_available = 1
                     ORDER BY category, dish_name"""
            items = db.sql_execute(sql)
            if not items:
                logger.warning("数据库中没有可用菜品")
                return []
            return [_format_dish_string(item) for item in items]
    except Exception as e:
        logger.error(f"获取菜单列表失败: {e}")
        return []



# ============ 方法装饰器 ============

def _auto_connect(func):
    """装饰器：自动管理数据库连接（用于业务方法）"""
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if self.connection and self.connection.is_connected():
            # 已在 with 语句中，直接执行
            return func(self, *args, **kwargs)
        # 未在 with 语句中，自动管理连接
        with DataBaseConnection(database=self.database) as db:
            return func(db, *args, **kwargs)
    return wrapper
# ============ 连接管理 ============

class DataBaseConnection:
    """数据库连接封装类（使用连接池）"""

    def __init__(self, database: Optional[str] = None):
        self.connection = None
        self.cursor = None
        self.database = database or Config.MYSQL_DATABASE

    def connect(self) -> bool:
        """从连接池获取连接"""
        try:
            pool = _get_pool()
            self.connection = pool.get_connection()
            if self.connection.is_connected():
                self.cursor = self.connection.cursor(dictionary=True)
                return True
            return False
        except Error as e:
            logger.error(f"数据库连接错误: {e}")
            return False

    def dis_connect(self):
        """归还连接到连接池"""
        try:
            if self.cursor:
                self.cursor.close()
                self.cursor = None
            if self.connection and self.connection.is_connected():
                self.connection.close()  # 连接池模式下 close() 即归还
                self.connection = None
        except Error as e:
            logger.error(f"关闭数据库连接错误: {e}")

    def __enter__(self):
        if self.connect():
            return self
        raise ConnectionError("无法建立数据库连接")

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.dis_connect()
        return False

    # ============ SQL 执行 ============

    def sql_execute(self, sql: str, params: tuple = None) -> List[Dict[str, Any]]:
        """执行查询，返回字典列表"""
        self.cursor.execute(sql, params or ())
        return self.cursor.fetchall()

    def sql_execute_one(self, sql: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """执行查询，返回单条结果"""
        self.cursor.execute(sql, params or ())
        return self.cursor.fetchone()

    def sql_commit(self, sql: str, params: tuple = None) -> int:
        """执行写操作，返回影响行数"""
        self.cursor.execute(sql, params or ())
        self.connection.commit()
        return self.cursor.rowcount

    # ============ 业务查询 ============

    @_auto_connect
    def test_conn(self) -> bool:
        """测试连接"""
        try:
            result = self.sql_execute_one("SELECT 1")
            return result is not None
        except Exception as e:
            logger.error(f"连接测试失败: {e}")
            return False

    @_auto_connect
    def get_all_dish(self) -> List[Dict[str, Any]]:
        """获取所有可供应的菜品，按辣度降序"""
        sql = """SELECT id, dish_name, price, description, category,
                        spice_level, flavor, main_ingredients, cooking_method,
                        is_vegetarian, allergens, is_available
                 FROM menu_items
                 WHERE is_available = 1
                 ORDER BY spice_level DESC"""
        result = self.sql_execute(sql)
        return [_enrich_dish(item) for item in (result or [])]

    @_auto_connect
    def get_all_menu_items(self) -> str:
        """获取所有菜单项（格式化字符串，用于向量数据库）"""
        sql = """SELECT id, dish_name, price, description, category,
                        spice_level, flavor, main_ingredients, cooking_method,
                        is_vegetarian, allergens
                 FROM menu_items
                 WHERE is_available = 1
                 ORDER BY category, dish_name"""
        items = self.sql_execute(sql)
        if not items:
            return "当前没有找到任何菜品信息"
        return "\n".join(_format_dish_string(item) for item in items)

    @_auto_connect
    def get_dish_by_id(self, dish_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取菜品"""
        sql = """SELECT id, dish_name, price, description, category,
                        spice_level, flavor, main_ingredients, cooking_method,
                        is_vegetarian, allergens, is_available
                 FROM menu_items WHERE id = %s"""
        return self.sql_execute_one(sql, (dish_id,))

    @_auto_connect
    def get_dish_by_name(self, dish_name: str) -> List[Dict[str, Any]]:
        """根据名称模糊搜索菜品"""
        sql = """SELECT id, dish_name, price, description, category,
                        spice_level, flavor, main_ingredients, cooking_method,
                        is_vegetarian, allergens, is_available
                 FROM menu_items
                 WHERE dish_name LIKE %s AND is_available = 1"""
        result = self.sql_execute(sql, (f"%{dish_name}%",))
        return [_enrich_dish(item) for item in (result or [])]


if __name__ == "__main__":
    with DataBaseConnection() as db:
        print("连接测试:", db.test_conn())
        print("\n=== 菜品列表 ===")
        for dish in db.get_all_dish():
            print(f"{dish['dish_name']} - {dish['spice_level_text']} - ¥{dish['price']}")
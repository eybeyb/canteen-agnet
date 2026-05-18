"""
网络连接重试与降级处理工具模块

为系统各外部依赖（高德地图、大模型API、数据库、Pinecone向量库）
提供统一的连接重试机制：
- 最多重试5次
- 5次均失败后执行降级处理（返回默认值/模拟数据/错误提示）
- 标准化结果格式
"""

import time
import logging
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, Type, Union

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 统一降级结果格式
DegradeResult = Dict[str, Any]


def make_success(data: Any = None, message: str = "成功") -> DegradeResult:
    """构建成功结果"""
    return {
        "status": "success",
        "data": data,
        "message": message,
        "degraded": False
    }


def make_degraded(fallback_data: Any = None,
                  service_name: str = "未知服务",
                  reason: str = "多次重试后连接失败") -> DegradeResult:
    """构建降级结果（5次重试全部失败后返回）"""
    logger.warning(f"⚠️ [{service_name}] 触发降级处理: {reason}")
    return {
        "status": "degraded",
        "data": fallback_data,
        "message": f"{service_name} 暂时不可用，已启用降级模式: {reason}",
        "degraded": True,
        "service_name": service_name
    }


def make_error(error: str, service_name: str = "未知服务") -> DegradeResult:
    """构建错误结果"""
    return {
        "status": "error",
        "data": None,
        "message": error,
        "degraded": False,
        "service_name": service_name
    }


def check_all_services_health() -> Dict[str, DegradeResult]:
    """
    统一健康检查：测试所有外部服务的连接状态
    包括：高德地图API、大模型API、MySQL数据库、Pinecone向量库

    Returns:
        键为服务名，值为健康检查结果的字典
    """
    results = {}

    # 1. 测试高德地图 API
    try:
        from smart_dian_can.tools.amap_tool import geocodes_location
        amap_result = test_connection(
            lambda: geocodes_location("测试地址"),
            service_name="高德地图API",
            max_retries=5,
        )
        results["高德地图API"] = amap_result
    except Exception as e:
        results["高德地图API"] = make_error(str(e), "高德地图API")

    # 2. 测试大模型 API
    try:
        from smart_dian_can.tools.llm_tool import LLMTool
        llm_tool = LLMTool()
        llm_result = test_connection(
            lambda: llm_tool.get_llm() is not None,
            service_name="大模型API",
            max_retries=5,
        )
        results["大模型API"] = llm_result
    except Exception as e:
        results["大模型API"] = make_error(str(e), "大模型API")

    # 3. 测试 MySQL 数据库
    try:
        from smart_dian_can.tools.db_tool import DataBaseConnection
        db = DataBaseConnection()
        db_result = test_connection(
            lambda: db.connect(),
            service_name="MySQL数据库",
            max_retries=5,
        )
        results["MySQL数据库"] = db_result
        if db_result["status"] != "success":
            db.dis_connect()
    except Exception as e:
        results["MySQL数据库"] = make_error(str(e), "MySQL数据库")

    # 4. 测试 Pinecone 向量库
    try:
        from smart_dian_can.tools.pinecone_tool import PineconeVectorDB
        pinecone = PineconeVectorDB()
        pinecone_result = test_connection(
            lambda: pinecone.pc is not None and pinecone.initialize_index(),
            service_name="Pinecone向量库",
            max_retries=5,
        )
        results["Pinecone向量库"] = pinecone_result
    except Exception as e:
        results["Pinecone向量库"] = make_error(str(e), "Pinecone向量库")

    # 汇总结果日志
    success_count = sum(1 for r in results.values() if r["status"] == "success")
    degraded_count = sum(1 for r in results.values() if r["status"] == "degraded")
    error_count = sum(1 for r in results.values() if r["status"] == "error")
    logger.info(
        f"📊 外部服务健康检查完成: "
        f"{success_count} 正常, {degraded_count} 降级, {error_count} 异常"
    )

    return results


def with_retry_and_fallback(
    max_retries: int = 5,
    retry_delay: float = 1.0,
    backoff_factor: float = 2.0,
    service_name: str = "未知服务",
    fallback_func: Optional[Callable[[], Any]] = None,
    fallback_data: Any = None,
    expected_exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    带重试和降级处理的装饰器

    Args:
        max_retries: 最大重试次数（默认5次）
        retry_delay: 初始重试等待秒数（默认1秒）
        backoff_factor: 退避倍数（每次重试等待时间翻倍）
        service_name: 服务名称，用于日志和降级提示
        fallback_func: 降级函数，5次重试后调用此函数获取默认数据
        fallback_data: 降级数据，5次重试后直接返回的默认数据（fallback_func优先）
        expected_exceptions: 需要重试的异常类型

    Returns:
        成功时返回 make_success(data=函数返回值)
        失败时返回 make_degraded(...) 或 make_error(...)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> DegradeResult:
            last_exception = None
            delay = retry_delay

            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"🔌 [{service_name}] 第 {attempt}/{max_retries} 次连接尝试...")
                    result = func(*args, **kwargs)
                    logger.info(f"✅ [{service_name}] 第 {attempt} 次连接成功")
                    return make_success(data=result)
                except expected_exceptions as e:
                    last_exception = e
                    logger.warning(
                        f"❌ [{service_name}] 第 {attempt}/{max_retries} 次连接失败: {e}"
                    )
                    if attempt < max_retries:
                        logger.info(f"⏳ 等待 {delay:.1f} 秒后重试...")
                        time.sleep(delay)
                        delay *= backoff_factor  # 指数退避
                    else:
                        logger.error(
                            f"💥 [{service_name}] {max_retries} 次重试全部失败，"
                            f"最后一次错误: {e}"
                        )

            # 5次重试全部失败，执行降级
            if fallback_func is not None:
                try:
                    fallback_result = fallback_func()
                    return make_degraded(
                        fallback_data=fallback_result,
                        service_name=service_name,
                        reason=f"多次重试后连接失败: {last_exception}"
                    )
                except Exception as fb_e:
                    return make_degraded(
                        fallback_data=fallback_data,
                        service_name=service_name,
                        reason=f"降级函数也失败: {fb_e}"
                    )
            else:
                return make_degraded(
                    fallback_data=fallback_data,
                    service_name=service_name,
                    reason=str(last_exception) if last_exception else "未知错误"
                )

        return wrapper
    return decorator


def test_connection(
    connect_func: Callable[[], Any],
    service_name: str = "未知服务",
    max_retries: int = 5,
    retry_delay: float = 1.0,
) -> DegradeResult:
    """
    测试单个连接的快捷函数（不装饰器方式）

    Args:
        connect_func: 连接函数，返回值非 False/None 视为成功
        service_name: 服务名称
        max_retries: 最大重试次数
        retry_delay: 初始等待秒数

    Returns:
        标准化结果
    """
    delay = retry_delay
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"🔌 [{service_name}] 连接测试 第 {attempt}/{max_retries} 次...")
            result = connect_func()
            if result:
                logger.info(f"✅ [{service_name}] 连接测试通过")
                return make_success(data=result)
            else:
                last_error = f"连接返回无效结果: {result}"
                logger.warning(f"⚠️ [{service_name}] 第 {attempt} 次: {last_error}")
        except Exception as e:
            last_error = str(e)
            logger.warning(f"❌ [{service_name}] 第 {attempt}/{max_retries} 次连接失败: {e}")

        if attempt < max_retries:
            logger.info(f"⏳ 等待 {delay:.1f} 秒后重试...")
            time.sleep(delay)
            delay *= 2  # 指数退避

    return make_degraded(
        service_name=service_name,
        reason=str(last_error) if last_error else "多次重试后连接失败"
    )


if __name__ == "__main__":
    # 测试重试机制
    print("=" * 50)
    print("连接重试与降级处理 单元测试")
    print("=" * 50)

    # 测试1: 使用装饰器
    import random

    @with_retry_and_fallback(
        max_retries=3,
        service_name="测试服务",
        fallback_data={"mock": "模拟数据"},
        expected_exceptions=(ValueError, ConnectionError)
    )
    def unstable_service(succeed_on: int = 3):
        """模拟一个不稳定服务，在指定次数后才成功"""
        if not hasattr(unstable_service, "_call_count"):
            unstable_service._call_count = 0
        unstable_service._call_count += 1
        if unstable_service._call_count < succeed_on:
            raise ConnectionError(f"模拟连接失败 #{unstable_service._call_count}")
        return {"result": "success", "attempt": unstable_service._call_count}

    print("\n--- 测试: 第2次成功 ---")
    unstable_service._call_count = 0
    result = unstable_service(succeed_on=2)
    print(f"结果: {result}")

    print("\n--- 测试: 5次都失败后降级 ---")
    unstable_service._call_count = 0
    result = unstable_service(succeed_on=99)  # 永远无法成功
    print(f"结果: {result}")

    # 测试2: 使用快捷函数
    print("\n--- 测试: 快捷函数 test_connection ---")
    def mock_fail():
        raise TimeoutError("模拟超时")

    result = test_connection(mock_fail, "模拟超时服务", max_retries=2)
    print(f"结果: {result}")

    print("\n" + "=" * 50)
    print("测试完成")
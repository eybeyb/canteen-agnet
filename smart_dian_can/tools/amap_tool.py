"""该文件用于高德地图的API开发"""
import requests
from typing import Dict
from dataclasses import dataclass
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

try:
    from config import Config
except ImportError:
    from smart_dian_can.config import Config
from logger import setup_logger

logger = setup_logger(__name__)

@dataclass
class AmapResult:
    api_key: str = Config.AMAP_API_KEY or ""
    address: str = ""
    origin_location: str = f"{Config.MERCHANT_LONGITUDE},{Config.MERCHANT_LATITUDE}"
    distance: float = Config.DELIVERY_RADIUS
    duration: str = ""
    taxi_duration: str = ""
    walk_duration: str = ""
    error: str = ""
#网络连接重试
def retry_get( url:str, max_retries:int=3, timeout:int=10):
    retries = Retry(
        total=max_retries,  # 总重试次数
        backoff_factor=1,  # 退避因子：第1次等1s，第2次等2s，第3次等4s
        status_forcelist=[500, 502, 503, 504],  # 这些状态码触发重试
        allowed_methods=frozenset(['GET', 'POST']),
        raise_on_status=False  # 不立即抛出异常，返回最后一次的响应
    )

    # 创建会话并挂载适配器
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retries)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    try:
        response = session.get(url, timeout=timeout)
        return response
    except requests.exceptions.RequestException as e:
        logger.error(f"请求失败（已重试 {max_retries} 次）: {e}")
        raise
    finally:
        session.close()  # 关闭会话，释放资源


#格式化地址
def geocodes_location(address:str):
    api_key = Config.AMAP_API_KEY
    if not api_key or "your" in api_key.lower():
        return {"error": "AMAP_API_KEY 未配置"}
    url = f"https://restapi.amap.com/v3/geocode/geo?address={address}&output=json&key={api_key}"
    try:
        # 使用带重试的请求
        response = retry_get(url, max_retries=3, timeout=10)
        response.raise_for_status()
        res = response.json()
        # 检测成功拿到没
        if (res["status"] != "1"):
            """得到数据"""
            raise Exception(f"获知地址失败,状态码:{res["status"]}")
        else:
            address = res["geocodes"][0]["formatted_address"]  # 获取地址字符串
            location = res["geocodes"][0]["location"]
            return {"address":address,"location":location}
    except Exception as e:
        return {"error": f"获知地址失败: {e}"}

#组装经纬度
def get_location(location:str):
    return f"{location['lng']},{location['lat']}"
# 获得距离，时间，三种交通工具的时间,距离
def get_distance_time(destination: str, mode: str = "electrobike"):
    config = AmapResult()
    origin_location = config.origin_location

    # 检查 origin_location 是否有效
    if not origin_location or origin_location == ",":
        return {"error": "商户位置未配置，请设置 MERCHANT_LONGITUDE 和 MERCHANT_LATITUDE"}

    # 获取目的地坐标
    temp = geocodes_location(destination)
    if "error" in temp:
        return temp
    des_location = temp["location"]

    choice = {
        "driving": "driving",
        "walking": "walking",
        "electrobike": "electrobike"
    }

    api_key = Config.AMAP_API_KEY
    if not api_key or "your" in api_key.lower():
        return {"error": "AMAP_API_KEY 未配置"}

    # 根据模式选择 API
    if mode in choice:
        # v5 版本必须通过 show_fields 参数请求 cost 数据
        url = f"https://restapi.amap.com/v5/direction/{choice[mode]}?origin={origin_location}&destination={des_location}&key={api_key}&show_fields=cost"
    else:
        return {"error": f"不支持的交通方式: {mode}"}

    try:
        # 使用带重试的请求
        response = retry_get(url, max_retries=3, timeout=10)
        response.raise_for_status()
        res = response.json()

        # 检测成功拿到没
        if res["status"] != "1":
            info = res.get("info", "未知错误")
            infocode = res.get("infocode", "")
            raise Exception(f"获知距离时间失败,状态码:{res['status']}, 信息:{info}, 错误码:{infocode}")
        else:
            # v5 版本的数据结构
            paths = res.get("route", {}).get("paths", [])

            if not paths:
                raise Exception("未找到路径数据")

            first_path = paths[0]
            distance = first_path.get("distance", "0")

            # 只有 electrobike 的 duration 在顶层，其他模式（如 driving）在 cost 里
            if mode == "electrobike":
                duration = first_path.get("duration", "0")
            else:
                duration = first_path.get("cost", {}).get("duration", "0")

            return {
                "distance": distance,
                "duration": duration
            }
    except Exception as e:
        return {"error": f"获知距离时间失败: {e}"}
#获得三种交通工具的举例与路径

#判断能不能送
def is_can_send(destination: str, mode: str = "electrobike") -> bool:
    config = AmapResult()
    distance_duration = get_distance_time(destination, mode)
    if "error" in distance_duration:
        return False
    distance = float(distance_duration.get("distance", 0))
    max_distance=config.distance
    if(distance<=max_distance):
        return "可送达"
    else:
        return "不可送达"

#将is_can_send和get_distance_time合并，并做时间距离处理

def get_distance_time_and_is_can_send(destination: str, mode: str = "electrobike") -> Dict[str, str]:
    config = AmapResult()
    distance_duration = get_distance_time(destination, mode)
    distance=None
    duration=None
    if "error" in distance_duration:
        duration="error"
        distance="error"
    else:
        distance = float(distance_duration.get("distance", 0))
        duration = int(float(distance_duration.get("duration", "0")))

    if duration != "error":
        duration_hour=int(duration/3600)
        duration_minute=int((duration-duration_hour*3600)/60)
        if duration_hour > 0:
            duration=f"{duration_hour}小时{duration_minute}分钟"
        else:
            duration=f"{duration_minute}分钟"
        distance_km=round(distance/1000,2)
        distance=f"{distance_km}公里"
        status = "success"
    else:
        status = "error"

    return {
        "status": status,
        "destination": destination,
        "mode": mode,
        "distance": distance,
        "duration": duration,
        "is_can_send": is_can_send(destination,mode)
    }




if __name__ == "__main__":
    # print(geocodes_location("罗湖外语学校"))
    # print(get_distance_time("塑和公园华府"))
    # print(is_can_send("塑和公园华府"))
    print(get_distance_time_and_is_can_send("塑和公园华府"))
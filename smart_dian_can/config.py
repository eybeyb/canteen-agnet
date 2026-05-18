import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # 高德地图
    AMAP_API_KEY = os.getenv("AMAP_API_KEY")
    MERCHANT_LONGITUDE = os.getenv("MERCHANT_LONGITUDE")
    MERCHANT_LATITUDE = os.getenv("MERCHANT_LATITUDE")
    DELIVERY_RADIUS = float(os.getenv("DELIVERY_RADIUS", 5000))
    DEFAULT_PATH_MODE = os.getenv("DEFAULT_PATH_MODE", "2")

    # LLM
    DASHSCOPE_API_KEY = os.getenv("DASHSCOPE_API_KEY")
    DASHSCOPE_API_BASE = os.getenv(
        "DASHSCOPE_API_BASE",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    LLM_MODE = os.getenv("LLM_MODE", "deepseek-v4-pro")

    # Pinecone
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
    PINECONE_ENV = os.getenv("PINECONE_ENV", "us-east-1")
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "smart-cat")
    PINECONE_MODEL = os.getenv("PINECONE_MODEL", "multilingual-e5-large")

    # MySQL
    MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", 3306))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "smart_cat")

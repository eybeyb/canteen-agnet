# 🍜 智能点餐 Agent

基于 LangGraph + FastAPI 的智能点餐助手，支持多轮对话、菜品推荐、配送查询等功能。

## ✨ 功能特性

- **智能对话**：基于 LangGraph ReAct Agent，支持多轮对话记忆
- **菜品推荐**：通过 Pinecone 向量数据库进行语义搜索，精准推荐菜品
- **配送查询**：集成高德地图 API，计算配送距离和时间
- **商家信息**：从提示词文件加载商家预设信息，回答营业时间、优惠活动等常规问题
- **REST API**：FastAPI 提供标准化接口，支持前端集成

## 🏗️ 技术架构

```
┌─────────────┐
│   前端/UI   │
└──────┬──────┘
       │ HTTP
┌──────▼──────┐
│  FastAPI    │  ← API 层（请求验证、异常处理、请求追踪）
│  (main.py)  │
└──────┬──────┘
       │
┌──────▼──────┐
│   Service   │  ← 业务层
└──────┬──────┘
       │
┌──────▼──────┐
│   Agent     │  ← LangGraph ReAct Agent + MemorySaver
│ (LangGraph) │
└──┬───┬───┬──┘
   │   │   │
┌──▼┐ ┌▼──┐ ┌▼──────────┐
│LLM│ │DB │ │  工具层    │
│   │ │   │ │           │
│通义│ │MySQL│ │ Pinecone  │
│千问│ │   │ │ 高德地图  │
└───┘ └───┘ └───────────┘
```

## 📁 项目结构

```
点餐智能体/
├── smart_dian_can/           # 主代码目录
│   ├── agent/                # Agent 模块
│   │   ├── smart_agent.py    # Agent 构建（懒加载）
│   │   └── mcp.py            # 工具定义（get_prompt, recommend_dish, calculate_delivery_distance）
│   ├── api/                  # API 层
│   │   ├── main.py           # FastAPI 应用（路由、中间件）
│   │   └── models.py         # Pydantic 请求/响应模型
│   ├── service/              # 业务层
│   │   └── diancan_service.py
│   ├── tools/                # 工具层
│   │   ├── db_tool.py        # MySQL 连接池封装
│   │   ├── pinecone_tool.py  # Pinecone 向量数据库
│   │   ├── amap_tool.py      # 高德地图 API
│   │   ├── llm_tool.py       # LLM 调用封装
│   │   └── connection_retry.py  # 重试与降级机制
│   ├── 提示词/               # 商家预设信息（.txt 文件）
│   ├── config.py             # 配置管理
│   ├── logger.py             # 日志配置
│   └── run.py                # 启动入口
├── .env.example              # 环境变量模板
├── requirements.txt          # Python 依赖
└── review.md                 # 项目 Review 报告
```

## 🚀 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/eybeyb/canteen-agnet.git
cd canteen-agnet
```

### 2. 创建虚拟环境

```bash
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的 API 密钥
```

需要配置以下服务：

| 服务 | 说明 | 获取方式 |
|------|------|----------|
| 通义千问 (DashScope) | LLM 推理 | [阿里云 DashScope](https://dashscope.aliyun.com/) |
| Pinecone | 向量数据库 | [Pinecone](https://www.pinecone.io/) |
| 高德地图 | 配送距离计算 | [高德开放平台](https://lbs.amap.com/) |
| MySQL 8.0 | 菜单数据存储 | 本地安装或云数据库 |

### 5. 初始化数据库

创建 MySQL 数据库并导入菜单表：

```sql
CREATE DATABASE smart_cat;
USE smart_cat;

CREATE TABLE menu_items (
    id INT AUTO_INCREMENT PRIMARY KEY,
    dish_name VARCHAR(100) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    spice_level INT DEFAULT 0 COMMENT '0:不辣 1:微辣 2:中辣 3:重辣',
    flavor VARCHAR(50),
    main_ingredients VARCHAR(200),
    cooking_method VARCHAR(50),
    is_vegetarian TINYINT(1) DEFAULT 0,
    allergens VARCHAR(200),
    is_available TINYINT(1) DEFAULT 1
);
```

### 6. 启动服务

```bash
# 方式一：直接运行
python -m smart_dian_can.run

# 方式二：uvicorn
uvicorn smart_dian_can.api.main:app --host 0.0.0.0 --port 8000 --reload
```

访问 http://localhost:8000/docs 查看 Swagger API 文档。

## 🔌 API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 健康检查 |
| GET | `/menu` | 获取全部菜品 |
| POST | `/chat` | 与智能 Agent 对话（支持多轮记忆） |
| POST | `/send_message` | 查询配送信息 |
| GET | `/send_message_test` | 查询配送信息（测试用） |

### 对话接口示例

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -H "X-User-Id: user-001" \
  -d '{"message": "我想吃点辣的川菜"}'
```

响应：

```json
{
  "success": true,
  "response": "为您推荐以下辣味川菜：麻婆豆腐（¥28）、水煮鱼（¥58）..."
}
```

## 🛠️ 核心优化

- **连接池**：MySQL 使用 `MySQLConnectionPool`，避免频繁创建连接
- **懒加载**：Agent 在首次调用时初始化，加快启动速度
- **请求追踪**：每个请求自动注入 `X-Request-ID`，方便排查问题
- **重试降级**：外部 API 调用内置重试机制和降级策略
- **输入验证**：Pydantic 模型对请求参数做长度和格式校验

## 📝 开发文档

详细开发文档位于 `智能点餐系统_开发资料/` 目录：

- `01_需求文档.md` — 业务需求和功能列表
- `02_技术架构文档.md` — 技术选型和架构设计
- `03_接口设计文档.md` — API 接口详细设计
- `04_开发指南.md` — 开发环境搭建和编码规范

## 📄 License

MIT
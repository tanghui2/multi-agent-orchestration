# 多Agent协作与调度系统

一个基于 Python asyncio 的多 Agent 协作框架，支持任务规划、依赖管理、上下文隔离和消息传递。

## 特性

- **任务规划**：LLM 驱动的自动任务分解
- **依赖管理**：基于拓扑排序的任务依赖执行
- **消息总线**：发布/订阅模式的 Agent 通信
- **上下文隔离**：项目级和 Agent 级上下文隔离
- **可扩展架构**：基于模板方法模式的 Agent 基类

## 项目结构

```
multi-agent-orchestration/
├── app/
│   ├── agents/          # Agent 实现
│   │   ├── base_agent.py      # Agent 基类
│   │   ├── researcher.py      # 调研 Agent
│   │   ├── coder.py           # 编码 Agent
│   │   └── reviewer.py        # 审查 Agent
│   ├── orchestrator/    # 编排器
│   │   └── orchestrator.py    # 核心编排器
│   ├── protocol/        # 协作协议
│   │   ├── message_bus.py     # 消息总线
│   │   └── task_queue.py      # 任务队列
│   ├── context/         # 上下文管理
│   │   └── context_manager.py # 上下文管理器
│   ├── config.py              # 配置管理
│   ├── llm.py                 # LLM 封装
│   ├── logger.py              # 日志
│   └── models.py              # 数据模型
├── config/
│   └── config.example.toml    # 示例配置
├── examples/
│   └── basic_usage.py         # 使用示例
├── run.py                      # 主入口
└── requirements.txt
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置

```bash
cp config/config.example.toml config/config.toml
# 编辑 config.toml 填入 API Key
```

### 3. 运行

```bash
# 演示模式
python run.py

# 示例
python examples/basic_usage.py
```

## 核心概念

### Orchestrator（编排器）

负责任务规划、Agent 调度和协作控制。

```python
from app.orchestrator import Orchestrator

orchestrator = Orchestrator()
await orchestrator.start()

# 注册 Agent
orchestrator.register_agent(ResearcherAgent())
orchestrator.register_agent(CoderAgent())

# 自动规划并执行
plan = await orchestrator.plan_and_execute(goal="调研并实现一个排序算法")
```

### Agent（智能体）

继承 BaseAgent 实现自定义 Agent。

```python
from app.agents.base_agent import BaseAgent
from app.models import AgentRole

class MyAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="我的Agent",
            role=AgentRole.CUSTOM,
            capabilities=["my_capability"],
        )

    async def execute(self, task, context_messages, project_id):
        # 实现你的逻辑
        return {"result": "success"}
```

### 协作协议

通过消息总线实现 Agent 间通信。

```python
# 请求协作
response = await agent.request_collaboration(
    receiver_id="coder_1",
    content="请帮我实现这个函数",
    task_id="task_123",
)

# 广播消息
await agent.broadcast_message("任务完成！", data={"result": "..."})
```

## 技术栈

- **Python 3.11+**：异步编程
- **Pydantic**：数据模型
- **aiohttp**：HTTP 客户端
- **tenacity**：重试机制
- **DashScope API**：LLM 服务

## 许可证

MIT

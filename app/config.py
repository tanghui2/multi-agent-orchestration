"""配置管理模块 - 单例模式"""
import os
import threading
from pathlib import Path
from typing import Optional

import tomllib
from pydantic import BaseModel, Field


class LLMSettings(BaseModel):
    """LLM 配置"""
    model: str = Field(default="qwen3.7-plus", description="模型名称")
    base_url: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1", description="API 地址")
    api_key: str = Field(default="", description="API Key")
    max_tokens: int = Field(default=4096, description="最大 Token 数")
    temperature: float = Field(default=0.7, description="温度")
    timeout: int = Field(default=60, description="超时时间（秒）")
    max_retries: int = Field(default=3, description="最大重试次数")


class OrchestratorSettings(BaseModel):
    """编排器配置"""
    max_parallel_tasks: int = Field(default=5, description="最大并行任务数")
    task_timeout: int = Field(default=300, description="任务超时时间（秒）")
    heartbeat_interval: int = Field(default=10, description="心跳间隔（秒）")
    enable_logging: bool = Field(default=True, description="是否启用日志")


class AgentSettings(BaseModel):
    """Agent 配置"""
    max_iterations: int = Field(default=10, description="最大迭代次数")
    context_window_size: int = Field(default=50, description="上下文窗口大小")
    enable_memory: bool = Field(default=True, description="是否启用记忆")


class ContextSettings(BaseModel):
    """上下文配置"""
    shared_memory_enabled: bool = Field(default=True, description="是否启用共享记忆")
    max_history_messages: int = Field(default=100, description="最大历史消息数")
    isolation_mode: str = Field(default="hybrid", description="隔离模式：full/hybrid/shared")


class AppConfig(BaseModel):
    """应用配置"""
    llm: LLMSettings = Field(default_factory=LLMSettings)
    orchestrator: OrchestratorSettings = Field(default_factory=OrchestratorSettings)
    agent: AgentSettings = Field(default_factory=AgentSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)


class Config:
    """全局配置 - 单例模式"""
    _instance: Optional["Config"] = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._config: Optional[AppConfig] = None

    def load(self, config_path: Optional[str] = None) -> AppConfig:
        """加载配置"""
        if self._config is not None:
            return self._config

        if config_path is None:
            config_path = os.getenv(
                "CONFIG_PATH",
                str(Path(__file__).parent.parent / "config" / "config.toml"),
            )

        config_data = {}
        if os.path.exists(config_path):
            with open(config_path, "rb") as f:
                config_data = tomllib.load(f)

        # 合并环境变量
        llm_data = config_data.get("llm", {})
        env_api_key = os.getenv("DASHSCOPE_API_KEY", "")
        if env_api_key:
            llm_data["api_key"] = env_api_key

        self._config = AppConfig(
            llm=LLMSettings(**llm_data),
            orchestrator=OrchestratorSettings(**config_data.get("orchestrator", {})),
            agent=AgentSettings(**config_data.get("agent", {})),
            context=ContextSettings(**config_data.get("context", {})),
        )
        return self._config

    @property
    def llm(self) -> LLMSettings:
        if self._config is None:
            self.load()
        return self._config.llm

    @property
    def orchestrator(self) -> OrchestratorSettings:
        if self._config is None:
            self.load()
        return self._config.orchestrator

    @property
    def agent(self) -> AgentSettings:
        if self._config is None:
            self.load()
        return self._config.agent

    @property
    def context(self) -> ContextSettings:
        if self._config is None:
            self.load()
        return self._config.context


def get_config(config_path: Optional[str] = None) -> AppConfig:
    """获取配置"""
    config = Config()
    return config.load(config_path)

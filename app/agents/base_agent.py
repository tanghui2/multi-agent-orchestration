"""Agent 基类 - 模板方法模式"""
import asyncio
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..config import get_config
from ..context import ContextManager
from ..llm import LLM
from ..logger import logger
from ..models import (
    AgentInfo,
    AgentRole,
    AgentStatus,
    CollaborationMessage,
    Message,
    MessageRole,
    Task,
    TaskStatus,
)
from ..protocol import MessageBus


class BaseAgent(ABC):
    """Agent 基类 - 定义 Agent 生命周期和协作协议"""

    def __init__(
        self,
        name: str,
        role: AgentRole,
        capabilities: Optional[List[str]] = None,
    ):
        config = get_config()
        self.id = f"{role.value}_{int(time.time())}"
        self.name = name
        self.role = role
        self.capabilities = capabilities or []
        self.status = AgentStatus.IDLE
        self.max_iterations = config.agent.max_iterations

        # 核心组件
        self.llm = LLM()
        self.context_manager = ContextManager()
        self.message_bus: Optional[MessageBus] = None

        # Agent 信息
        self.info = AgentInfo(
            id=self.id,
            name=name,
            role=role,
            capabilities=self.capabilities,
        )

        # 订阅消息
        if self.message_bus:
            self.message_bus.subscribe("request", self._handle_request)
            self.message_bus.subscribe("response", self._handle_response)
            self.message_bus.subscribe("broadcast", self._handle_broadcast)

    def set_message_bus(self, message_bus: MessageBus):
        """设置消息总线"""
        self.message_bus = message_bus
        self.message_bus.subscribe("request", self._handle_request)
        self.message_bus.subscribe("response", self._handle_response)
        self.message_bus.subscribe("broadcast", self._handle_broadcast)

    # ========== 核心生命周期（模板方法）==========

    async def run(self, task: Task, project_id: str) -> Task:
        """执行任务 - 模板方法"""
        try:
            self._set_status(AgentStatus.BUSY)
            task.status = TaskStatus.IN_PROGRESS
            task.assigned_to = self.id

            logger.info(f"[{self.name}] 开始执行任务: {task.title}")

            # 步骤 1: 构建上下文
            context_messages = self._build_context(task, project_id)

            # 步骤 2: 执行核心逻辑（由子类实现）
            result = await self.execute(task, context_messages, project_id)

            # 步骤 3: 处理结果
            if result:
                task.status = TaskStatus.COMPLETED
                task.output_data = result
                logger.info(f"[{self.name}] 任务完成: {task.title}")
            else:
                task.status = TaskStatus.FAILED
                task.error_message = "执行失败，无结果返回"
                logger.warning(f"[{self.name}] 任务失败: {task.title}")

            return task

        except Exception as e:
            logger.error(f"[{self.name}] 任务异常: {e}")
            task.status = TaskStatus.FAILED
            task.error_message = str(e)
            return task

        finally:
            self._set_status(AgentStatus.IDLE)

    @abstractmethod
    async def execute(
        self,
        task: Task,
        context_messages: List[Dict[str, str]],
        project_id: str,
    ) -> Optional[Dict[str, Any]]:
        """执行任务 - 由子类实现"""
        ...

    # ========== 协作协议 ==========

    async def request_collaboration(
        self,
        receiver_id: str,
        content: str,
        task_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> CollaborationMessage:
        """请求其他 Agent 协作"""
        if not self.message_bus:
            raise RuntimeError("消息总线未设置")

        logger.info(f"[{self.name}] 请求协作: {self.id} -> {receiver_id}")
        return await self.message_bus.send_request(
            sender_id=self.id,
            receiver_id=receiver_id,
            content=content,
            task_id=task_id,
            data=data,
        )

    async def respond_to_request(
        self,
        request: CollaborationMessage,
        content: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        """响应其他 Agent 的请求"""
        if not self.message_bus:
            raise RuntimeError("消息总线未设置")

        logger.info(f"[{self.name}] 响应请求: {request.sender_id} -> {self.id}")
        await self.message_bus.send_response(
            request_id=request.id,
            sender_id=self.id,
            receiver_id=request.sender_id,
            content=content,
            data=data,
        )

    async def broadcast_message(
        self,
        content: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        """广播消息给所有 Agent"""
        if not self.message_bus:
            raise RuntimeError("消息总线未设置")

        logger.info(f"[{self.name}] 广播消息")
        await self.message_bus.broadcast(
            sender_id=self.id,
            content=content,
            data=data,
        )

    # ========== 消息处理 ==========

    async def _handle_request(self, message: CollaborationMessage):
        """处理请求消息"""
        if message.receiver_id == self.id:
            logger.info(f"[{self.name}] 收到请求: {message.sender_id} -> {message.content[:50]}...")
            response = await self.on_request(message)
            if response:
                await self.respond_to_request(message, response)

    async def _handle_response(self, message: CollaborationMessage):
        """处理响应消息"""
        logger.debug(f"[{self.name}] 收到响应: {message.sender_id}")
        await self.on_response(message)

    async def _handle_broadcast(self, message: CollaborationMessage):
        """处理广播消息"""
        if message.receiver_id == self.id:
            logger.debug(f"[{self.name}] 收到广播: {message.content[:50]}...")
            await self.on_broadcast(message)

    async def on_request(self, message: CollaborationMessage) -> Optional[str]:
        """处理请求 - 可被子类覆盖"""
        return f"收到你的请求: {message.content[:50]}..."

    async def on_response(self, message: CollaborationMessage):
        """处理响应 - 可被子类覆盖"""
        pass

    async def on_broadcast(self, message: CollaborationMessage):
        """处理广播 - 可被子类覆盖"""
        pass

    # ========== 工具方法 ==========

    def _build_context(self, task: Task, project_id: str) -> List[Dict[str, str]]:
        """构建上下文消息"""
        messages = []

        # 添加系统提示
        messages.append({
            "role": "system",
            "content": self._get_system_prompt(),
        })

        # 添加项目历史
        history = self.context_manager.get_messages(project_id, limit=10)
        for msg in history:
            messages.append({
                "role": msg.role.value,
                "content": msg.content,
            })

        # 添加任务信息
        messages.append({
            "role": "user",
            "content": f"【任务】{task.title}\n【描述】{task.description}\n【类型】{task.task_type.value}\n【优先级】{task.priority.value}",
        })

        return messages

    def _get_system_prompt(self) -> str:
        """获取系统提示 - 由子类覆盖"""
        return f"你是一个{self.role.value}类型的智能体，名叫{self.name}。"

    def _set_status(self, status: AgentStatus):
        """设置状态"""
        self.status = status
        self.info.status = status

    async def add_context_message(
        self,
        project_id: str,
        content: str,
        role: MessageRole = MessageRole.ASSISTANT,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Message:
        """添加上下文消息"""
        return self.context_manager.add_message(
            project_id=project_id,
            agent_id=self.id,
            role=role,
            content=content,
            metadata=metadata,
        )

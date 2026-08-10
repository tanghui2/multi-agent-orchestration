"""上下文管理器 - 支持隔离与共享"""
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

from ..config import get_config
from ..logger import logger
from ..models import Context, Message, MessageRole


class ContextManager:
    """上下文管理器 - 支持项目级隔离和跨Agent共享"""

    def __init__(self):
        config = get_config()
        self._contexts: Dict[str, Context] = {}  # project_id -> Context
        self._agent_contexts: Dict[str, Dict[str, Context]] = defaultdict(dict)  # agent_id -> project_id -> Context
        self._shared_memory: Dict[str, Any] = {}  # 全局共享记忆
        self._max_history = config.context.max_history_messages
        self._isolation_mode = config.context.isolation_mode
        self._shared_enabled = config.context.shared_memory_enabled

    def create_context(self, project_id: str) -> Context:
        """创建项目上下文"""
        context = Context(project_id=project_id)
        self._contexts[project_id] = context
        logger.debug(f"项目上下文已创建: {project_id}")
        return context

    def get_or_create_context(self, project_id: str) -> Context:
        """获取或创建上下文"""
        if project_id not in self._contexts:
            return self.create_context(project_id)
        return self._contexts[project_id]

    def get_context(self, project_id: str) -> Optional[Context]:
        """获取上下文"""
        return self._contexts.get(project_id)

    def get_agent_context(self, agent_id: str, project_id: str) -> Optional[Context]:
        """获取Agent专属上下文"""
        return self._agent_contexts[agent_id].get(project_id)

    def create_agent_context(self, agent_id: str, project_id: str) -> Context:
        """创建Agent专属上下文"""
        context = Context(project_id=project_id)
        self._agent_contexts[agent_id][project_id] = context
        logger.debug(f"Agent上下文已创建: {agent_id} -> {project_id}")
        return context

    def add_message(
        self,
        project_id: str,
        role: MessageRole,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        agent_id: Optional[str] = None,
    ) -> Message:
        """添加消息"""
        message = Message(
            role=role,
            content=content,
            metadata=metadata or {},
        )

        # 添加到项目上下文
        context = self.get_or_create_context(project_id)
        context.messages.append(message)

        # 维护窗口大小
        if len(context.messages) > self._max_history:
            context.messages = context.messages[-self._max_history:]

        # 如果有 agent_id，同时添加到 Agent 专属上下文
        if agent_id:
            agent_context = self.get_agent_context(agent_id, project_id)
            if not agent_context:
                agent_context = self.create_agent_context(agent_id, project_id)
            agent_context.messages.append(message)
            if len(agent_context.messages) > self._max_history:
                agent_context.messages = agent_context.messages[-self._max_history:]

        context.updated_at = time.time()
        return message

    def get_messages(
        self,
        project_id: str,
        limit: Optional[int] = None,
        role: Optional[MessageRole] = None,
    ) -> List[Message]:
        """获取消息"""
        context = self._contexts.get(project_id)
        if not context:
            return []

        messages = context.messages
        if role:
            messages = [m for m in messages if m.role == role]

        if limit:
            messages = messages[-limit:]

        return messages

    def get_agent_messages(
        self,
        agent_id: str,
        project_id: str,
        limit: Optional[int] = None,
    ) -> List[Message]:
        """获取Agent专属消息"""
        context = self.get_agent_context(agent_id, project_id)
        if not context:
            return []

        messages = context.messages
        if limit:
            messages = messages[-limit:]

        return messages

    # ========== 共享记忆 ==========

    def set_shared_memory(self, key: str, value: Any) -> None:
        """设置共享记忆"""
        if self._shared_enabled:
            self._shared_memory[key] = value
            logger.debug(f"共享记忆已设置: {key}")

    def get_shared_memory(self, key: str, default: Any = None) -> Any:
        """获取共享记忆"""
        return self._shared_memory.get(key, default)

    def get_all_shared_memory(self) -> Dict[str, Any]:
        """获取所有共享记忆"""
        return dict(self._shared_memory)

    def delete_shared_memory(self, key: str) -> None:
        """删除共享记忆"""
        self._shared_memory.pop(key, None)

    def clear_shared_memory(self) -> None:
        """清空共享记忆"""
        self._shared_memory.clear()

    # ========== 构建上下文窗口 ==========

    def build_context_window(
        self,
        project_id: str,
        agent_id: Optional[str] = None,
        extra_messages: Optional[List[Message]] = None,
    ) -> List[Dict[str, str]]:
        """构建 LLM 上下文窗口"""
        messages = []

        # 添加项目历史消息
        project_messages = self.get_messages(project_id, limit=20)
        for msg in project_messages:
            messages.append({
                "role": msg.role.value,
                "content": msg.content,
            })

        # 如果有 agent_id，添加 Agent 专属消息
        if agent_id:
            agent_messages = self.get_agent_messages(agent_id, project_id, limit=10)
            for msg in agent_messages:
                messages.append({
                    "role": msg.role.value,
                    "content": f"[Agent专属] {msg.content}",
                })

        # 添加额外消息
        if extra_messages:
            for msg in extra_messages:
                messages.append({
                    "role": msg.role.value,
                    "content": msg.content,
                })

        return messages

    def clear_context(self, project_id: str) -> None:
        """清空项目上下文"""
        self._contexts.pop(project_id, None)
        # 清空相关的 Agent 上下文
        for agent_id in list(self._agent_contexts.keys()):
            self._agent_contexts[agent_id].pop(project_id, None)
        logger.info(f"项目上下文已清空: {project_id}")

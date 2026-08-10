"""数据模型定义"""
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    """任务状态"""
    PENDING = "pending"          # 待处理
    ASSIGNED = "assigned"        # 已分配
    IN_PROGRESS = "in_progress"  # 进行中
    COMPLETED = "completed"      # 已完成
    FAILED = "failed"            # 已失败
    CANCELLED = "cancelled"      # 已取消


class TaskPriority(str, Enum):
    """任务优先级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskType(str, Enum):
    """任务类型"""
    RESEARCH = "research"        # 调研
    CODE = "code"                # 编码
    REVIEW = "review"            # 审查
    ANALYSIS = "analysis"        # 分析
    PLANNING = "planning"        # 规划
    CUSTOM = "custom"            # 自定义


class MessageRole(str, Enum):
    """消息角色"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class Message(BaseModel):
    """消息"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    role: MessageRole
    content: str
    timestamp: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    """任务"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str
    task_type: TaskType = TaskType.CUSTOM
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: Optional[str] = None
    parent_id: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list)
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    completed_at: Optional[float] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentRole(str, Enum):
    """Agent 角色"""
    RESEARCHER = "researcher"      # 调研Agent
    CODER = "coder"                # 编码Agent
    REVIEWER = "reviewer"          # 审查Agent
    ANALYST = "analyst"            # 分析Agent
    PLANNER = "planner"            # 规划Agent
    CUSTOM = "custom"              # 自定义


class AgentStatus(str, Enum):
    """Agent 状态"""
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"


class AgentInfo(BaseModel):
    """Agent 信息"""
    id: str
    name: str
    role: AgentRole
    status: AgentStatus = AgentStatus.IDLE
    capabilities: List[str] = Field(default_factory=list)
    current_task_id: Optional[str] = None
    completed_tasks: List[str] = Field(default_factory=list)
    failed_tasks: List[str] = Field(default_factory=list)


class Context(BaseModel):
    """上下文"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_id: str
    messages: List[Message] = Field(default_factory=list)
    shared_memory: Dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


class Plan(BaseModel):
    """规划"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    goal: str
    tasks: List[Task] = Field(default_factory=list)
    agent_assignments: Dict[str, List[str]] = Field(default_factory=dict)  # task_id -> [agent_id]
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    status: str = "pending"


class CollaborationMessage(BaseModel):
    """协作消息"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str
    receiver_id: str
    message_type: str  # request / response / broadcast / feedback
    content: str
    task_id: Optional[str] = None
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: float = Field(default_factory=time.time)
    is_processed: bool = False


class OrchestratorState(BaseModel):
    """编排器状态"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agents: Dict[str, AgentInfo] = Field(default_factory=dict)
    tasks: Dict[str, Task] = Field(default_factory=dict)
    plans: Dict[str, Plan] = Field(default_factory=dict)
    contexts: Dict[str, Context] = Field(default_factory=dict)
    message_queue: List[CollaborationMessage] = Field(default_factory=list)
    status: str = "idle"
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)

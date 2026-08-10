"""编排器 - 多Agent协作调度核心"""
import asyncio
import time
from typing import Any, Dict, List, Optional, Type

from ..agents.base_agent import BaseAgent
from ..config import get_config
from ..context import ContextManager
from ..llm import LLM
from ..logger import logger
from ..models import (
    AgentInfo,
    AgentRole,
    AgentStatus,
    OrchestratorState,
    Plan,
    Task,
    TaskPriority,
    TaskStatus,
    TaskType,
)
from ..protocol import MessageBus, TaskQueue


class Orchestrator:
    """编排器 - 负责任务规划、调度和多Agent协作"""

    def __init__(self):
        config = get_config()
        self.state = OrchestratorState()
        self.message_bus = MessageBus()
        self.task_queue = TaskQueue()
        self.context_manager = ContextManager()
        self.llm = LLM()

        self._agent_registry: Dict[str, BaseAgent] = {}
        self._agent_capabilities: Dict[str, List[str]] = {}
        self._running = False
        self._heartbeat_task: Optional[asyncio.Task] = None
        self._max_parallel = config.orchestrator.max_parallel_tasks
        self._task_timeout = config.orchestrator.task_timeout

    # ========== Agent 注册 ==========

    def register_agent(self, agent: BaseAgent) -> AgentInfo:
        """注册 Agent"""
        agent.set_message_bus(self.message_bus)
        self._agent_registry[agent.id] = agent
        self._agent_capabilities[agent.id] = agent.capabilities

        # 更新状态
        self.state.agents[agent.id] = agent.info

        logger.info(f"Agent 已注册: {agent.name} ({agent.id}), 能力: {agent.capabilities}")
        return agent.info

    def unregister_agent(self, agent_id: str) -> bool:
        """注销 Agent"""
        agent = self._agent_registry.pop(agent_id, None)
        if agent:
            self.state.agents.pop(agent_id, None)
            logger.info(f"Agent 已注销: {agent_id}")
            return True
        return False

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """获取 Agent"""
        return self._agent_registry.get(agent_id)

    def get_available_agents(
        self,
        capability: Optional[str] = None,
        role: Optional[AgentRole] = None,
    ) -> List[BaseAgent]:
        """获取可用 Agent"""
        agents = []
        for agent_id, agent in self._agent_registry.items():
            if agent.status != AgentStatus.IDLE:
                continue
            if capability and capability not in agent.capabilities:
                continue
            if role and agent.role != role:
                continue
            agents.append(agent)
        return agents

    # ========== 任务管理 ==========

    async def create_task(
        self,
        title: str,
        description: str,
        task_type: TaskType = TaskType.CUSTOM,
        priority: TaskPriority = TaskPriority.MEDIUM,
        dependencies: Optional[List[str]] = None,
        input_data: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
    ) -> Task:
        """创建任务"""
        task = Task(
            title=title,
            description=description,
            task_type=task_type,
            priority=priority,
            dependencies=dependencies or [],
            input_data=input_data or {},
        )

        if project_id:
            task.metadata["project_id"] = project_id

        await self.task_queue.add_task(task)
        self.state.tasks[task.id] = task

        logger.info(f"任务已创建: {task.id} ({task.title})")
        return task

    async def create_plan(
        self,
        goal: str,
        tasks: List[Task],
        agent_assignments: Optional[Dict[str, List[str]]] = None,
    ) -> Plan:
        """创建规划"""
        plan = Plan(
            goal=goal,
            tasks=tasks,
            agent_assignments=agent_assignments or {},
        )
        self.state.plans[plan.id] = plan

        # 添加任务到队列
        for task in tasks:
            await self.task_queue.add_task(task)
            self.state.tasks[task.id] = task

        logger.info(f"规划已创建: {plan.id}, 目标: {goal}, 任务数: {len(tasks)}")
        return plan

    async def plan_and_execute(
        self,
        goal: str,
        project_id: Optional[str] = None,
    ) -> Plan:
        """自动规划并执行"""
        # 步骤 1: 规划任务
        tasks = await self._plan_tasks(goal, project_id)

        # 步骤 2: 创建规划
        plan = await self.create_plan(goal, tasks)

        # 步骤 3: 执行规划
        await self._execute_plan(plan, project_id)

        return plan

    async def _plan_tasks(
        self,
        goal: str,
        project_id: Optional[str] = None,
    ) -> List[Task]:
        """LLM 规划任务分解"""
        system_prompt = (
            "你是一个任务规划专家。请将用户的目标分解为可执行的子任务。"
            "每个子任务需要明确：标题、描述、类型、依赖关系。"
            "任务类型可选：research(调研)、code(编码)、review(审查)、analysis(分析)、planning(规划)。"
        )

        prompt = f"目标：{goal}\n\n请分解为 3-5 个子任务，以 JSON 数组格式返回。格式：\n"
        prompt += '[{"title":"任务标题","description":"任务描述","task_type":"类型","depends_on":[]}]'

        try:
            plan_result = await self.llm.ask_json(prompt, system_prompt=system_prompt)
            tasks = []

            for i, item in enumerate(plan_result if isinstance(plan_result, list) else [plan_result]):
                task = Task(
                    title=item.get("title", f"任务{i+1}"),
                    description=item.get("description", ""),
                    task_type=TaskType(item.get("task_type", "custom")),
                    dependencies=item.get("depends_on", []),
                )
                tasks.append(task)

            logger.info(f"任务规划完成: {len(tasks)} 个子任务")
            return tasks

        except Exception as e:
            logger.error(f"任务规划失败: {e}")
            # 回退：创建单一任务
            return [Task(title=goal, description=goal, task_type=TaskType.CUSTOM)]

    async def _execute_plan(
        self,
        plan: Plan,
        project_id: Optional[str] = None,
    ):
        """执行规划"""
        self._running = True
        self.state.status = "running"

        logger.info(f"开始执行规划: {plan.id}")

        # 按依赖关系排序任务
        sorted_tasks = self._topological_sort(plan.tasks)

        # 依次执行任务
        for task in sorted_tasks:
            if not self._running:
                break

            # 分配 Agent
            agent = await self._assign_agent(task)
            if not agent:
                logger.warning(f"无可用 Agent 执行任务: {task.title}")
                task.status = TaskStatus.FAILED
                continue

            # 执行任务（带超时）
            try:
                task.metadata["project_id"] = project_id or plan.id
                task = await asyncio.wait_for(
                    agent.run(task, project_id or plan.id),
                    timeout=self._task_timeout,
                )
            except asyncio.TimeoutError:
                logger.warning(f"任务超时: {task.title}")
                task.status = TaskStatus.FAILED
                task.error_message = "执行超时"
            except Exception as e:
                logger.error(f"任务执行失败: {task.title}, 错误: {e}")
                task.status = TaskStatus.FAILED
                task.error_message = str(e)

            # 更新规划中的任务状态
            for i, t in enumerate(plan.tasks):
                if t.id == task.id:
                    plan.tasks[i] = task
                    break

            self.state.tasks[task.id] = task

        self._running = False
        self.state.status = "idle"
        plan.status = "completed"
        logger.info(f"规划执行完成: {plan.id}")

    # ========== Agent 分配 ==========

    async def _assign_agent(self, task: Task) -> Optional[BaseAgent]:
        """为任务分配最合适的 Agent"""
        # 检查预设分配：遍历所有规划，查找 task_id 对应的 agent_id
        for plan in self.state.plans.values():
            assigned_agent_ids = plan.agent_assignments.get(task.id, [])
            for agent_id in assigned_agent_ids:
                agent = self._agent_registry.get(agent_id)
                if agent and agent.status == AgentStatus.IDLE:
                    return agent

        # 按能力匹配
        task_type_to_capability = {
            TaskType.RESEARCH: "research",
            TaskType.CODE: "coding",
            TaskType.REVIEW: "review",
            TaskType.ANALYSIS: "analysis",
            TaskType.PLANNING: "planning",
        }

        required_capability = task_type_to_capability.get(task.task_type, "")

        if required_capability:
            agents = self.get_available_agents(capability=required_capability)
            if agents:
                return agents[0]

        # 回退：选择第一个可用 Agent
        agents = self.get_available_agents()
        if agents:
            return agents[0]

        return None

    # ========== 依赖管理 ==========

    def _topological_sort(self, tasks: List[Task]) -> List[Task]:
        """拓扑排序 - 按依赖关系排序任务"""
        task_map = {t.id: t for t in tasks}
        in_degree = {t.id: 0 for t in tasks}
        adjacency_list: Dict[str, List[str]] = {t.id: [] for t in tasks}

        # 构建图
        for task in tasks:
            for dep_id in task.dependencies:
                if dep_id in task_map:
                    adjacency_list[dep_id].append(task.id)
                    in_degree[task.id] += 1

        # Kahn 算法
        queue = [tid for tid, degree in in_degree.items() if degree == 0]
        sorted_tasks = []

        while queue:
            task_id = queue.pop(0)
            sorted_tasks.append(task_map[task_id])

            for neighbor in adjacency_list[task_id]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        # 处理环形依赖（回退）
        if len(sorted_tasks) != len(tasks):
            logger.warning("检测到环形依赖，按原顺序执行")
            return tasks

        return sorted_tasks

    # ========== 生命周期 ==========

    async def start(self):
        """启动编排器"""
        await self.message_bus.start()
        self._heartbeat_task = asyncio.create_task(self._heartbeat())
        logger.info("编排器已启动")

    async def stop(self):
        """停止编排器"""
        self._running = False

        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

        await self.message_bus.stop()
        logger.info("编排器已停止")

    async def _heartbeat(self):
        """心跳 - 定期检查系统状态"""
        while True:
            try:
                await asyncio.sleep(10)

                # 更新状态时间
                self.state.updated_at = time.time()

                # 检查 Agent 状态
                idle_count = sum(
                    1 for a in self._agent_registry.values()
                    if a.status == AgentStatus.IDLE
                )
                busy_count = len(self._agent_registry) - idle_count

                # 检查待处理任务
                pending_count = len(await self.task_queue.get_pending_tasks())

                logger.debug(
                    f"心跳: {idle_count} 个空闲, {busy_count} 个忙碌, {pending_count} 个待处理任务"
                )

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳错误: {e}")

    def get_state(self) -> Dict[str, Any]:
        """获取编排器状态"""
        return {
            "status": self.state.status,
            "agents": len(self._agent_registry),
            "tasks": len(self.state.tasks),
            "plans": len(self.state.plans),
            "pending_tasks": len(self.task_queue),
            "shared_memory": len(self.context_manager.get_all_shared_memory()),
        }

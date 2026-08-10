"""任务队列 - 基于优先级的任务调度"""
import asyncio
import heapq
import time
from typing import List, Optional

from ..logger import logger
from ..models import Task, TaskPriority, TaskStatus


class TaskQueue:
    """任务队列 - 支持优先级排序和依赖管理"""

    # 优先级权重映射
    PRIORITY_WEIGHT = {
        TaskPriority.CRITICAL: 0,
        TaskPriority.HIGH: 1,
        TaskPriority.MEDIUM: 2,
        TaskPriority.LOW: 3,
    }

    def __init__(self):
        self._queue: List[tuple] = []  # (priority_weight, created_at, task_id)
        self._tasks: dict[str, Task] = {}
        self._lock = asyncio.Lock()

    async def add_task(self, task: Task) -> None:
        """添加任务到队列"""
        async with self._lock:
            self._tasks[task.id] = task
            weight = self.PRIORITY_WEIGHT.get(task.priority, 2)
            heapq.heappush(self._queue, (weight, task.created_at, task.id))
            logger.debug(f"任务已添加: {task.id} ({task.title})")

    async def get_next_task(self) -> Optional[Task]:
        """获取下一个可执行的任务"""
        async with self._lock:
            # 收集依赖未满足的任务，找到第一个可执行的后统一回填
            skipped = []
            result = None
            while self._queue:
                weight, created_at, task_id = heapq.heappop(self._queue)
                task = self._tasks.get(task_id)

                if not task:
                    continue

                # 检查任务状态
                if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
                    continue

                # 检查依赖是否满足
                if not self._dependencies_met(task):
                    skipped.append((weight, created_at, task_id))
                    continue

                # 任务可执行
                result = task
                break

            # 将跳过的任务重新入队，保持优先级顺序
            for item in skipped:
                heapq.heappush(self._queue, item)

            return result

    def _dependencies_met(self, task: Task) -> bool:
        """检查依赖是否满足"""
        if not task.dependencies:
            return True

        for dep_id in task.dependencies:
            dep_task = self._tasks.get(dep_id)
            if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                return False

        return True

    async def get_task(self, task_id: str) -> Optional[Task]:
        """获取指定任务"""
        return self._tasks.get(task_id)

    async def update_task(self, task: Task) -> None:
        """更新任务"""
        async with self._lock:
            task.updated_at = time.time()
            if task.status == TaskStatus.COMPLETED:
                task.completed_at = time.time()
            self._tasks[task.id] = task

    async def remove_task(self, task_id: str) -> None:
        """移除任务"""
        async with self._lock:
            self._tasks.pop(task_id, None)

    async def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        return list(self._tasks.values())

    async def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """按状态获取任务"""
        return [t for t in self._tasks.values() if t.status == status]

    async def get_pending_tasks(self) -> List[Task]:
        """获取待处理任务"""
        return await self.get_tasks_by_status(TaskStatus.PENDING)

    async def get_in_progress_tasks(self) -> List[Task]:
        """获取进行中的任务"""
        return await self.get_tasks_by_status(TaskStatus.IN_PROGRESS)

    def __len__(self) -> int:
        """队列长度"""
        return len([t for t in self._tasks.values()
                    if t.status in (TaskStatus.PENDING, TaskStatus.ASSIGNED)])

"""消息总线 - 基于异步的消息传递系统"""
import asyncio
import time
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, Set

from ..logger import logger
from ..models import CollaborationMessage


class MessageBus:
    """消息总线 - 支持发布/订阅模式的消息传递"""

    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self._message_queue: asyncio.Queue[CollaborationMessage] = asyncio.Queue()
        self._history: List[CollaborationMessage] = []
        self._pending_responses: Dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self._running = False
        self._processor_task: Optional[asyncio.Task] = None

    async def start(self):
        """启动消息处理循环"""
        if self._running:
            return
        self._running = True
        self._processor_task = asyncio.create_task(self._process_messages())
        logger.info("消息总线已启动")

    async def stop(self):
        """停止消息处理循环"""
        self._running = False
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        logger.info("消息总线已停止")

    def subscribe(self, message_type: str, handler: Callable):
        """订阅消息类型"""
        self._subscribers[message_type].append(handler)
        logger.debug(f"已订阅消息类型: {message_type}")

    def unsubscribe(self, message_type: str, handler: Callable):
        """取消订阅"""
        if message_type in self._subscribers:
            self._subscribers[message_type].remove(handler)

    async def publish(self, message: CollaborationMessage):
        """发布消息"""
        await self._message_queue.put(message)
        self._history.append(message)
        logger.debug(f"消息已发布: {message.sender_id} -> {message.receiver_id} ({message.message_type})")

    async def send_request(
        self,
        sender_id: str,
        receiver_id: str,
        content: str,
        task_id: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
        timeout: float = 30.0,
    ) -> CollaborationMessage:
        """发送请求并等待响应"""
        request_msg = CollaborationMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type="request",
            content=content,
            task_id=task_id,
            data=data or {},
        )

        future = asyncio.Future()
        self._pending_responses[request_msg.id] = future

        await self.publish(request_msg)

        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.warning(f"请求超时: {sender_id} -> {receiver_id}")
            raise TimeoutError(f"请求超时: {sender_id} -> {receiver_id}")
        finally:
            self._pending_responses.pop(request_msg.id, None)

    async def send_response(
        self,
        request_id: str,
        sender_id: str,
        receiver_id: str,
        content: str,
        data: Optional[Dict[str, Any]] = None,
    ):
        """发送响应"""
        response_msg = CollaborationMessage(
            sender_id=sender_id,
            receiver_id=receiver_id,
            message_type="response",
            content=content,
            data=data or {},
            is_processed=True,
        )
        response_msg.data["in_reply_to"] = request_id

        future = self._pending_responses.get(request_id)
        if future and not future.done():
            future.set_result(response_msg)
            logger.debug(f"响应已发送: {request_id}")
        else:
            await self.publish(response_msg)

    async def broadcast(
        self,
        sender_id: str,
        content: str,
        data: Optional[Dict[str, Any]] = None,
        exclude: Optional[Set[str]] = None,
    ):
        """广播消息给所有订阅者"""
        subscribers = self._get_all_subscribers()
        exclude_set = exclude or set()

        for sub_id in subscribers:
            if sub_id != sender_id and sub_id not in exclude_set:
                msg = CollaborationMessage(
                    sender_id=sender_id,
                    receiver_id=sub_id,
                    message_type="broadcast",
                    content=content,
                    data=data or {},
                )
                await self.publish(msg)

    def _get_all_subscribers(self) -> Set[str]:
        """获取所有订阅者 ID"""
        subscribers = set()
        for handlers in self._subscribers.values():
            for handler in handlers:
                if hasattr(handler, "__self__"):
                    subscribers.add(handler.__self__.id)
        return subscribers

    async def _process_messages(self):
        """消息处理循环"""
        while self._running:
            try:
                message = await self._message_queue.get()

                # 触发订阅者回调
                handlers = self._subscribers.get(message.message_type, [])
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(message)
                        else:
                            handler(message)
                    except Exception as e:
                        logger.error(f"消息处理错误: {e}")

                self._message_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"消息总线错误: {e}")

    def get_history(
        self,
        sender_id: Optional[str] = None,
        receiver_id: Optional[str] = None,
        message_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[CollaborationMessage]:
        """获取消息历史"""
        history = self._history

        if sender_id:
            history = [m for m in history if m.sender_id == sender_id]
        if receiver_id:
            history = [m for m in history if m.receiver_id == receiver_id]
        if message_type:
            history = [m for m in history if m.message_type == message_type]

        return history[-limit:]

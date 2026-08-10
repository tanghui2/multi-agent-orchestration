"""LLM 封装模块 - 支持重试和 JSON 输出"""
import json
import logging
from typing import Any, Dict, List, Optional

import aiohttp
from tenacity import (
    retry,
    retry_if_exception_type,
    wait_exponential,
    stop_after_attempt,
)

from .config import get_config

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """LLM 调用异常"""
    pass


class TokenLimitExceeded(LLMError):
    """Token 超限异常"""
    pass


class LLM:
    """LLM 封装类"""

    def __init__(self):
        config = get_config()
        self.base_url = config.llm.base_url.rstrip("/")
        self.api_key = config.llm.api_key
        self.model = config.llm.model
        self.max_tokens = config.llm.max_tokens
        self.timeout = config.llm.timeout
        self.max_retries = config.llm.max_retries

    @retry(
        retry=retry_if_exception_type((aiohttp.ClientError, TimeoutError, LLMError)),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def _call_api(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """调用 LLM API"""
        url = f"{self.base_url}/chat/completions"

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": kwargs.get("temperature", 0.7),
        }

        if kwargs.get("response_format"):
            payload["response_format"] = kwargs["response_format"]

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            ) as response:
                if response.status == 429:
                    raise LLMError("API 限流，请稍后重试")
                elif response.status >= 500:
                    raise LLMError(f"服务器错误: {response.status}")
                elif response.status != 200:
                    error_body = await response.text()
                    raise LLMError(f"API 调用失败: {response.status} - {error_body}")

                data = await response.json()
                return data

    async def ask(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> str:
        """向 LLM 提问"""
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        try:
            data = await self._call_api(full_messages, **kwargs)
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.error(f"LLM ask 调用失败: {e}")
            raise LLMError(str(e)) from e

    async def ask_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """向 LLM 提问并要求返回 JSON"""
        full_system = system_prompt or "你是一个有用的助手"
        full_system += "\n请以 json 格式输出结果，不要包含其他文字。"

        messages = [
            {"role": "user", "content": prompt},
        ]

        full_messages = [{"role": "system", "content": full_system}] + messages

        try:
            data = await self._call_api(
                full_messages,
                response_format={"type": "json_object"},
                **kwargs,
            )
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"JSON 解析失败: {e}, 原始响应: {content}")
            raise LLMError(f"JSON 解析失败: {e}") from e
        except Exception as e:
            logger.error(f"LLM ask_json 调用失败: {e}")
            raise LLMError(str(e)) from e

    async def ask_tool(
        self,
        messages: List[Dict[str, str]],
        tools: List[Dict[str, Any]],
        system_prompt: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """向 LLM 提问并支持工具调用"""
        full_messages = []
        if system_prompt:
            full_messages.append({"role": "system", "content": system_prompt})
        full_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": full_messages,
            "max_tokens": self.max_tokens,
            "temperature": kwargs.get("temperature", 0.7),
            "tools": tools,
            "tool_choice": "auto",
        }

        try:
            data = await self._call_api_with_payload(payload)
            message = data["choices"][0]["message"]

            result = {
                "content": message.get("content", ""),
                "tool_calls": message.get("tool_calls", []),
            }
            return result
        except Exception as e:
            logger.error(f"LLM ask_tool 调用失败: {e}")
            raise LLMError(str(e)) from e

    async def _call_api_with_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """直接用 payload 调用 API（不走重试装饰器）"""
        url = f"{self.base_url}/chat/completions"

        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=self.timeout,
            ) as response:
                if response.status != 200:
                    error_body = await response.text()
                    raise LLMError(f"API 调用失败: {response.status} - {error_body}")
                return await response.json()

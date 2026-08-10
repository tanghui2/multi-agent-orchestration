"""调研Agent - 负责信息搜索和调研"""
from typing import Any, Dict, List, Optional

from ..models import AgentRole, Task
from .base_agent import BaseAgent


class ResearcherAgent(BaseAgent):
    """调研Agent - 负责信息搜索、整理和分析"""

    def __init__(self, name: str = "调研Agent"):
        super().__init__(
            name=name,
            role=AgentRole.RESEARCHER,
            capabilities=["research", "search", "information_gathering", "analysis"],
        )

    def _get_system_prompt(self) -> str:
        return (
            "你是一个专业的调研Agent，擅长信息搜索、整理和分析。"
            "你的任务是根据用户需求，提供全面、准确、有价值的信息。"
            "输出要求：结构化、重点突出、注明信息来源。"
        )

    async def execute(
        self,
        task: Task,
        context_messages: List[Dict[str, str]],
        project_id: str,
    ) -> Optional[Dict[str, Any]]:
        """执行调研任务"""
        prompt = self._build_research_prompt(task)

        # 添加上下文
        messages = context_messages.copy()
        messages.append({"role": "user", "content": prompt})

        # 调用 LLM 进行调研
        response = await self.llm.ask(messages, system_prompt=self._get_system_prompt())

        # 结构化输出
        result = {
            "summary": self._extract_summary(response),
            "findings": self._extract_findings(response),
            "references": self._extract_references(response),
            "raw_response": response,
        }

        # 保存到上下文
        await self.add_context_message(
            project_id,
            f"调研结果: {result['summary']}",
            role="assistant",
        )

        return result

    def _build_research_prompt(self, task: Task) -> str:
        """构建调研提示"""
        prompt = f"""请针对以下任务进行调研：

任务标题：{task.title}
任务描述：{task.description}

请提供：
1. **核心发现**：列出 3-5 个关键信息点
2. **详细分析**：对每个发现进行深入说明
3. **数据支撑**：提供相关数据、案例或引用
4. **建议行动**：基于调研结果给出建议

输出格式要求：结构化、重点突出、便于快速阅读。"""

        return prompt

    def _extract_summary(self, text: str) -> str:
        """提取摘要"""
        lines = text.split("\n")
        summary_lines = []
        for line in lines[:5]:
            if line.strip():
                summary_lines.append(line.strip())
        return " ".join(summary_lines)[:200]

    def _extract_findings(self, text: str) -> List[str]:
        """提取发现"""
        findings = []
        for line in text.split("\n"):
            if line.strip().startswith(("*", "-", "1.", "2.", "3.", "4.", "5.")):
                findings.append(line.strip())
        return findings[:10] or [text[:100]]

    def _extract_references(self, text: str) -> List[str]:
        """提取参考"""
        references = []
        for line in text.split("\n"):
            if "http" in line or "参考" in line.lower():
                references.append(line.strip())
        return references[:5]

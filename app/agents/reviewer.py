"""审查Agent - 负责代码审查和质量检查"""
from typing import Any, Dict, List, Optional

from ..models import AgentRole, Task
from .base_agent import BaseAgent


class ReviewerAgent(BaseAgent):
    """审查Agent - 负责代码审查、质量检查和优化建议"""

    def __init__(self, name: str = "审查Agent"):
        super().__init__(
            name=name,
            role=AgentRole.REVIEWER,
            capabilities=["review", "code_review", "quality_check", "optimization"],
        )

    def _get_system_prompt(self) -> str:
        return (
            "你是一个专业的代码审查Agent，擅长代码质量检查、Bug 发现和优化建议。"
            "你需要仔细审查代码，找出潜在问题并给出改进方案。"
            "输出要求：问题分类、严重程度、具体建议。"
        )

    async def execute(
        self,
        task: Task,
        context_messages: List[Dict[str, str]],
        project_id: str,
    ) -> Optional[Dict[str, Any]]:
        """执行审查任务"""
        prompt = self._build_review_prompt(task)

        # 添加上下文
        messages = context_messages.copy()
        messages.append({"role": "user", "content": prompt})

        # 调用 LLM 进行审查
        response = await self.llm.ask(messages, system_prompt=self._get_system_prompt())

        # 解析审查结果
        result = {
            "verdict": self._determine_verdict(response),
            "issues": self._extract_issues(response),
            "suggestions": self._extract_suggestions(response),
            "score": self._calculate_score(response),
            "raw_review": response,
        }

        # 保存到上下文
        await self.add_context_message(
            project_id,
            f"审查结果: {result['verdict']}, 发现 {len(result['issues'])} 个问题",
            role="assistant",
        )

        return result

    def _build_review_prompt(self, task: Task) -> str:
        """构建审查提示"""
        code_to_review = task.input_data.get("code", "")
        review_context = task.input_data.get("context", "")

        prompt = f"""请对以下代码进行审查：

任务标题：{task.title}
审查重点：{task.description}

待审查代码：
```
{code_to_review}
```

补充上下文：
{review_context}

请从以下方面进行审查：
1. **正确性**：代码是否能正确运行？是否有逻辑错误？
2. **安全性**：是否存在安全漏洞？（如注入、越权等）
3. **性能**：是否有性能问题？是否可以优化？
4. **可读性**：代码是否易于理解？命名是否清晰？
5. **最佳实践**：是否符合编程规范和最佳实践？

请以 JSON 格式返回审查结果，格式：
{{
    "verdict": "approved|rejected|needs_revision",
    "issues": [{{"severity": "high|medium|low", "category": "", "description": "", "suggestion": ""}}],
    "suggestions": ["优化建议1", "优化建议2"],
    "score": 85
}}"""

        return prompt

    def _determine_verdict(self, response: str) -> str:
        """确定审查结论"""
        try:
            # 尝试解析 JSON
            import json
            result = json.loads(response)
            return result.get("verdict", "needs_revision")
        except (json.JSONDecodeError, ValueError):
            pass

        # 基于规则判断
        response_lower = response.lower()
        if "approved" in response_lower or "通过" in response_lower:
            return "approved"
        elif "rejected" in response_lower or "拒绝" in response_lower:
            return "rejected"
        return "needs_revision"

    def _extract_issues(self, response: str) -> List[Dict[str, str]]:
        """提取问题列表"""
        try:
            import json
            result = json.loads(response)
            return result.get("issues", [])
        except (json.JSONDecodeError, ValueError):
            pass

        # 基于规则提取
        issues = []
        for line in response.split("\n"):
            line = line.strip()
            if any(kw in line.lower() for kw in ["问题", "issue", "严重", "error", "warning"]):
                issues.append({
                    "severity": "medium",
                    "description": line[:100],
                    "suggestion": "",
                })
        return issues[:5]

    def _extract_suggestions(self, response: str) -> List[str]:
        """提取建议"""
        try:
            import json
            result = json.loads(response)
            return result.get("suggestions", [])
        except (json.JSONDecodeError, ValueError):
            pass

        suggestions = []
        for line in response.split("\n"):
            if any(kw in line.lower() for kw in ["建议", "suggest", "优化", "改进"]):
                suggestions.append(line.strip()[:100])
        return suggestions[:5]

    def _calculate_score(self, response: str) -> int:
        """计算代码质量分数"""
        verdict = self._determine_verdict(response)
        issues = self._extract_issues(response)

        # 基础分
        score = 100

        # 根据审查结论调整
        if verdict == "rejected":
            score = 30
        elif verdict == "needs_revision":
            score = 70

        # 根据问题数量扣分
        high_issues = [i for i in issues if i.get("severity") == "high"]
        medium_issues = [i for i in issues if i.get("severity") == "medium"]
        low_issues = [i for i in issues if i.get("severity") == "low"]

        score -= len(high_issues) * 20
        score -= len(medium_issues) * 10
        score -= len(low_issues) * 5

        return max(0, min(100, score))

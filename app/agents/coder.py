"""编码Agent - 负责代码生成和实现"""
import ast
from typing import Any, Dict, List, Optional

from ..models import AgentRole, Task
from .base_agent import BaseAgent


class CoderAgent(BaseAgent):
    """编码Agent - 负责代码生成、实现和优化"""

    def __init__(self, name: str = "编码Agent"):
        super().__init__(
            name=name,
            role=AgentRole.CODER,
            capabilities=["coding", "implementation", "code_generation", "optimization"],
        )

    def _get_system_prompt(self) -> str:
        return (
            "你是一个专业的编码Agent，擅长代码生成、实现和优化。"
            "你精通 Python、JavaScript 等主流编程语言。"
            "输出要求：代码可运行、注释清晰、遵循最佳实践。"
        )

    async def execute(
        self,
        task: Task,
        context_messages: List[Dict[str, str]],
        project_id: str,
    ) -> Optional[Dict[str, Any]]:
        """执行编码任务"""
        prompt = self._build_coding_prompt(task)

        # 添加上下文
        messages = context_messages.copy()
        messages.append({"role": "user", "content": prompt})

        # 调用 LLM 生成代码
        response = await self.llm.ask(messages, system_prompt=self._get_system_prompt())

        # 解析代码块
        code_blocks = self._extract_code_blocks(response)

        result = {
            "code_blocks": code_blocks,
            "explanation": self._extract_explanation(response),
            "language": self._detect_language(code_blocks),
            "can_execute": self._check_code_validity(code_blocks),
        }

        # 保存到上下文
        await self.add_context_message(
            project_id,
            f"代码生成: {len(code_blocks)} 个代码块",
            role="assistant",
        )

        return result

    def _build_coding_prompt(self, task: Task) -> str:
        """构建编码提示"""
        prompt = f"""请根据以下需求编写代码：

任务标题：{task.title}
任务描述：{task.description}

要求：
1. 代码可直接运行
2. 包含必要的注释说明
3. 遵循语言最佳实践
4. 处理边界情况和错误
5. 如果需要外部依赖，请在代码开头注明

请直接输出代码，使用 ```language 格式包裹。"""

        if task.input_data:
            prompt += f"\n\n补充输入数据：{task.input_data}"

        return prompt

    def _extract_code_blocks(self, text: str) -> List[Dict[str, str]]:
        """提取代码块"""
        code_blocks = []
        lines = text.split("\n")
        in_code = False
        current_lang = ""
        current_code = []

        for line in lines:
            if line.strip().startswith("```"):
                if in_code:
                    # 结束代码块
                    if current_code:
                        code_blocks.append({
                            "language": current_lang,
                            "code": "\n".join(current_code),
                        })
                    in_code = False
                    current_code = []
                    current_lang = ""
                else:
                    # 开始代码块
                    in_code = True
                    current_lang = line.strip()[3:].strip() or "text"
                    current_code = []
            elif in_code:
                current_code.append(line)

        # 处理未关闭的代码块
        if in_code and current_code:
            code_blocks.append({
                "language": current_lang,
                "code": "\n".join(current_code),
            })

        # 如果没有代码块，尝试直接提取 Python 代码
        if not code_blocks:
            python_code = self._try_extract_python(text)
            if python_code:
                code_blocks.append({
                    "language": "python",
                    "code": python_code,
                })

        return code_blocks

    def _try_extract_python(self, text: str) -> Optional[str]:
        """尝试直接提取 Python 代码"""
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith(("def ", "class ", "import ", "from ", "if ", "for ", "while ", "try ", "with ")):
                # 找到代码起始，提取整段
                idx = text.split("\n").index(line)
                remaining = "\n".join(text.split("\n")[idx:])
                # 截取到空行或结束
                return remaining[:2000]
        return None

    def _extract_explanation(self, text: str) -> str:
        """提取代码说明"""
        lines = text.split("\n")
        explanation_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith(("```", "def ", "class ", "import ", "from ", "#")):
                explanation_lines.append(stripped)
            if len(explanation_lines) >= 5:
                break
        return " ".join(explanation_lines)[:300]

    def _detect_language(self, code_blocks: List[Dict[str, str]]) -> str:
        """检测编程语言"""
        if not code_blocks:
            return "unknown"
        return code_blocks[0].get("language", "unknown")

    def _check_code_validity(self, code_blocks: List[Dict[str, str]]) -> bool:
        """检查代码有效性（仅检查 Python）"""
        for block in code_blocks:
            if block.get("language") == "python":
                try:
                    ast.parse(block["code"])
                    return True
                except SyntaxError:
                    return False
        return True  # 非 Python 代码默认有效

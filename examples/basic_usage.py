"""基础用法示例"""
import asyncio

from app.agents.coder import CoderAgent
from app.agents.researcher import ResearcherAgent
from app.agents.reviewer import ReviewerAgent
from app.config import get_config
from app.models import Task, TaskPriority, TaskType
from app.orchestrator import Orchestrator


async def basic_usage():
    """基础用法：创建编排器、注册 Agent、执行任务"""
    # 加载配置
    config = get_config()
    print(f"模型: {config.llm.model}")
    print(f"API: {config.llm.base_url}")

    # 创建编排器
    orchestrator = Orchestrator()
    await orchestrator.start()

    try:
        # 创建 Agent
        researcher = ResearcherAgent()
        coder = CoderAgent()
        reviewer = ReviewerAgent()

        # 注册 Agent
        orchestrator.register_agent(researcher)
        orchestrator.register_agent(coder)
        orchestrator.register_agent(reviewer)

        # 创建任务
        task = await orchestrator.create_task(
            title="调研 Python 设计模式",
            description="调研 Python 中常用的设计模式及其应用场景",
            task_type=TaskType.RESEARCH,
            priority=TaskPriority.MEDIUM,
            project_id="demo",
        )

        # 直接用 Agent 执行
        project_id = "demo"
        result = await researcher.run(task, project_id)
        print(f"\n任务状态: {result.status.value}")
        print(f"调研摘要: {result.output_data.get('summary', 'N/A')}")

    finally:
        await orchestrator.stop()


async def collaboration_example():
    """协作示例：Researcher -> Coder -> Reviewer 流水线"""
    orchestrator = Orchestrator()
    await orchestrator.start()

    try:
        # 注册 Agent
        researcher = ResearcherAgent()
        coder = CoderAgent()
        reviewer = ReviewerAgent()

        orchestrator.register_agent(researcher)
        orchestrator.register_agent(coder)
        orchestrator.register_agent(reviewer)

        project_id = "collab_demo"

        # 步骤 1: 调研
        research_task = await orchestrator.create_task(
            title="调研排序算法",
            description="调研常用排序算法的时间复杂度和空间复杂度",
            task_type=TaskType.RESEARCH,
            priority=TaskPriority.HIGH,
            project_id=project_id,
        )

        research_result = await researcher.run(research_task, project_id)
        print(f"[调研] 状态: {research_result.status.value}")

        # 步骤 2: 编码
        coding_task = await orchestrator.create_task(
            title="实现最佳排序算法",
            description="根据调研结果，实现时间复杂度最优的排序算法",
            task_type=TaskType.CODE,
            priority=TaskPriority.HIGH,
            dependencies=[research_task.id],
            input_data=research_result.output_data,
            project_id=project_id,
        )

        coding_result = await coder.run(coding_task, project_id)
        print(f"[编码] 状态: {coding_result.status.value}")

        # 步骤 3: 审查
        if coding_result.output_data.get("code_blocks"):
            review_task = await orchestrator.create_task(
                title="审查排序算法代码",
                description="检查代码正确性、性能和可读性",
                task_type=TaskType.REVIEW,
                priority=TaskPriority.MEDIUM,
                input_data={"code": coding_result.output_data["code_blocks"][0]["code"]},
                project_id=project_id,
            )

            review_result = await reviewer.run(review_task, project_id)
            print(f"[审查] 结论: {review_result.output_data.get('verdict', 'N/A')}")
            print(f"[审查] 分数: {review_result.output_data.get('score', 0)}/100")

    finally:
        await orchestrator.stop()


async def auto_planning_example():
    """自动规划示例：让 LLM 自动分解任务"""
    orchestrator = Orchestrator()
    await orchestrator.start()

    try:
        # 注册 Agent
        orchestrator.register_agent(ResearcherAgent())
        orchestrator.register_agent(CoderAgent())
        orchestrator.register_agent(ReviewerAgent())

        # 自动规划并执行
        plan = await orchestrator.plan_and_execute(
            goal="实现一个简易的计算器，支持加减乘除四种运算",
            project_id="calc_demo",
        )

        print(f"规划 ID: {plan.id}")
        print(f"任务数: {len(plan.tasks)}")
        for task in plan.tasks:
            print(f"  [{task.status.value}] {task.title}")

    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    # 选择示例运行
    print("请选择要运行的示例:")
    print("1. 基础用法")
    print("2. 协作流水线")
    print("3. 自动规划")

    choice = input("输入选项 (1/2/3): ").strip()

    if choice == "1":
        asyncio.run(basic_usage())
    elif choice == "2":
        asyncio.run(collaboration_example())
    elif choice == "3":
        asyncio.run(auto_planning_example())
    else:
        print("无效选项")

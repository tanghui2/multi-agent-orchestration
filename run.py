"""多Agent协作与调度系统 - 主入口"""
import asyncio
import sys

from app.agents.coder import CoderAgent
from app.agents.researcher import ResearcherAgent
from app.agents.reviewer import ReviewerAgent
from app.orchestrator import Orchestrator


async def demo():
    """演示多Agent协作"""
    print("=" * 60)
    print("多Agent协作与调度系统 - 演示")
    print("=" * 60)

    # 初始化编排器
    orchestrator = Orchestrator()
    await orchestrator.start()

    try:
        # 注册 Agent
        researcher = ResearcherAgent("调研专家")
        coder = CoderAgent("开发工程师")
        reviewer = ReviewerAgent("代码审查专家")

        orchestrator.register_agent(researcher)
        orchestrator.register_agent(coder)
        orchestrator.register_agent(reviewer)

        print("\n已注册 Agent:")
        for agent_id, info in orchestrator.state.agents.items():
            print(f"  - {info.name} ({info.role.value}): {info.capabilities}")

        # 示例 1: 自动规划并执行
        print("\n" + "=" * 60)
        print("示例 1: 自动规划并执行 - 实现一个快速排序算法")
        print("=" * 60)

        plan = await orchestrator.plan_and_execute(
            goal="实现一个快速排序算法，包含调研、编码和审查三个阶段",
            project_id="demo_project",
        )

        print(f"\n规划 ID: {plan.id}")
        print(f"目标: {plan.goal}")
        print(f"任务数: {len(plan.tasks)}")
        for task in plan.tasks:
            print(f"  - [{task.status.value}] {task.title}")

        # 示例 2: 手动创建任务并执行
        print("\n" + "=" * 60)
        print("示例 2: 手动任务 - 调研 Python 异步编程")
        print("=" * 60)

        from app.models import Task, TaskPriority, TaskType

        # 创建调研任务
        research_task = await orchestrator.create_task(
            title="调研 Python 异步编程",
            description="调研 Python asyncio 的核心概念、使用场景和最佳实践",
            task_type=TaskType.RESEARCH,
            priority=TaskPriority.HIGH,
            project_id="demo_project",
        )

        # 执行任务
        project_id = "demo_project"
        agent = orchestrator.get_agent(researcher.id)
        if agent:
            result = await agent.run(research_task, project_id)
            print(f"\n任务结果: {result.status.value}")
            if result.output_data:
                print(f"摘要: {result.output_data.get('summary', 'N/A')}")

        # 示例 3: 代码生成 + 审查
        print("\n" + "=" * 60)
        print("示例 3: 代码生成 + 审查")
        print("=" * 60)

        # 创建编码任务
        coding_task = await orchestrator.create_task(
            title="实现斐波那契数列",
            description="编写一个高效的斐波那契数列生成器，支持迭代和递归两种实现方式",
            task_type=TaskType.CODE,
            priority=TaskPriority.HIGH,
            project_id="demo_project",
        )

        # 执行编码
        coder_agent = orchestrator.get_agent(coder.id)
        if coder_agent:
            code_result = await coder_agent.run(coding_task, project_id)
            print(f"\n编码任务: {code_result.status.value}")
            if code_result.output_data:
                print(f"生成代码块数: {len(code_result.output_data.get('code_blocks', []))}")

                # 如果有代码，交给审查 Agent
                if code_result.output_data.get("code_blocks"):
                    review_task = await orchestrator.create_task(
                        title="审查斐波那契数列代码",
                        description="审查生成的代码，检查正确性、性能和可读性",
                        task_type=TaskType.REVIEW,
                        priority=TaskPriority.MEDIUM,
                        input_data={"code": code_result.output_data["code_blocks"][0]["code"]},
                        project_id="demo_project",
                    )

                    reviewer_agent = orchestrator.get_agent(reviewer.id)
                    if reviewer_agent:
                        review_result = await reviewer_agent.run(review_task, project_id)
                        print(f"\n审查任务: {review_result.status.value}")
                        if review_result.output_data:
                            print(f"审查结论: {review_result.output_data.get('verdict', 'N/A')}")
                            print(f"质量分数: {review_result.output_data.get('score', 'N/A')}/100")

        # 打印系统状态
        print("\n" + "=" * 60)
        print("系统状态")
        print("=" * 60)
        state = orchestrator.get_state()
        for key, value in state.items():
            print(f"  {key}: {value}")

    finally:
        await orchestrator.stop()
        print("\n编排器已停止")


if __name__ == "__main__":
    asyncio.run(demo())

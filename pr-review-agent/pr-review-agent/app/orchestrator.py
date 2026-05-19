import logging

from app.agents import CodeQualityAgent, SecurityAgent, TestWriterAgent, DocUpdaterAgent
from app.aggregator import Aggregator
from models.schemas import PRContext, ReviewReport

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Runs all 4 specialist agents sequentially (one at a time)
    to avoid RAM exhaustion on machines with limited memory.
    """

    def __init__(self):
        self.agents = [
            CodeQualityAgent(),
            SecurityAgent(),
            TestWriterAgent(),
            DocUpdaterAgent(),
        ]
        self.aggregator = Aggregator()

    async def review(self, pr_context: PRContext) -> ReviewReport:
        logger.info(
            f"[Orchestrator] Starting review for PR #{pr_context.pr_number} "
            f"in {pr_context.repo_full_name} — "
            f"{len(pr_context.changed_files)} files changed"
        )

        agent_results = []
        for agent in self.agents:
            result = await agent.run(pr_context)
            if result.error:
                logger.warning(f"[Orchestrator] Agent {result.agent_name} failed: {result.error}")
            agent_results.append(result)

        report = self.aggregator.aggregate(pr_context, agent_results)
        logger.info(
            f"[Orchestrator] Review complete. "
            f"{report.total_findings} findings "
            f"({report.critical_count} critical, {report.high_count} high)"
        )
        return report

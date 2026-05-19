import asyncio
import logging

from app.agents import CodeQualityAgent, SecurityAgent, TestWriterAgent, DocUpdaterAgent
from app.aggregator import Aggregator
from models.schemas import PRContext, ReviewReport

logger = logging.getLogger(__name__)


class Orchestrator:
    """
    Fans out the PR diff to all 4 specialist agents in parallel,
    then passes their combined results to the Aggregator.

    Parallel execution means all 4 agents call Ollama at the same time.
    Total latency = slowest agent, not sum of all agents.
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

        # Run all agents concurrently
        tasks = [agent.run(pr_context) for agent in self.agents]
        agent_results = await asyncio.gather(*tasks, return_exceptions=False)

        # Log any agent-level errors
        for result in agent_results:
            if result.error:
                logger.warning(f"[Orchestrator] Agent {result.agent_name} failed: {result.error}")

        # Aggregate and deduplicate
        report = self.aggregator.aggregate(pr_context, agent_results)
        logger.info(
            f"[Orchestrator] Review complete. "
            f"{report.total_findings} findings "
            f"({report.critical_count} critical, {report.high_count} high)"
        )
        return report

from app.agents.base_agent import BaseAgent


class CodeQualityAgent(BaseAgent):
    """
    Detects code smells, complexity issues, naming violations,
    dead code, and SOLID principle violations.
    """

    def __init__(self):
        super().__init__(
            agent_name="CodeQualityAgent",
            prompt_file="code_quality.txt"
        )

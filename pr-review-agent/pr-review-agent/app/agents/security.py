from app.agents.base_agent import BaseAgent


class SecurityAgent(BaseAgent):
    """
    Scans for OWASP Top 10 vulnerabilities, hardcoded secrets,
    SQL injection, XSS, insecure dependencies, and auth flaws.
    """

    def __init__(self):
        super().__init__(
            agent_name="SecurityAgent",
            prompt_file="security.txt"
        )

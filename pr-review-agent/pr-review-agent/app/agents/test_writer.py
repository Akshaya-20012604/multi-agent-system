from app.agents.base_agent import BaseAgent


class TestWriterAgent(BaseAgent):
    """
    Identifies new or changed methods that lack test coverage
    and generates unit test stubs (JUnit, pytest, or Jest style
    depending on the language detected in the diff).
    """

    def __init__(self):
        super().__init__(
            agent_name="TestWriterAgent",
            prompt_file="test_writer.txt"
        )

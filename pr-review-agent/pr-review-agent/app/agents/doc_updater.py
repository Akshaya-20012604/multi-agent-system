from app.agents.base_agent import BaseAgent


class DocUpdaterAgent(BaseAgent):
    """
    Checks for missing or outdated docstrings, Javadoc comments,
    and OpenAPI annotations on new/changed methods and classes.
    Generates updated documentation text.
    """

    def __init__(self):
        super().__init__(
            agent_name="DocUpdaterAgent",
            prompt_file="doc_updater.txt"
        )

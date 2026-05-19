import json
import logging
import os
import re
from abc import ABC, abstractmethod

from langchain_ollama import OllamaLLM
from langchain.prompts import PromptTemplate

from models.schemas import AgentResult, AgentFinding, PRContext, Severity

logger = logging.getLogger(__name__)


def load_prompt(filename: str) -> str:
    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")
    path = os.path.join(prompts_dir, filename)
    with open(path, "r") as f:
        return f.read()


class BaseAgent(ABC):
    """
    Base class for all specialist review agents.
    Each agent gets a PR diff, sends it to the local Ollama LLM,
    and returns structured findings.
    """

    def __init__(self, agent_name: str, prompt_file: str):
        self.agent_name = agent_name
        self.prompt_template_str = load_prompt(prompt_file)
        self.model = os.getenv("OLLAMA_MODEL", "llama3.1")
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.timeout = int(os.getenv("AGENT_TIMEOUT_SECONDS", "120"))
        self.min_confidence = float(os.getenv("MIN_CONFIDENCE_SCORE", "0.6"))

        self.llm = OllamaLLM(
            model=self.model,
            base_url=self.base_url,
            temperature=0.1,         # Low temperature = consistent, factual output
            timeout=self.timeout,
        )

    def _build_prompt(self, pr_context: PRContext) -> str:
        template = PromptTemplate.from_template(self.prompt_template_str)
        return template.format(
            pr_title=pr_context.pr_title,
            pr_body=pr_context.pr_body or "No description provided.",
            author=pr_context.author,
            base_branch=pr_context.base_branch,
            head_branch=pr_context.head_branch,
            changed_files=", ".join(pr_context.changed_files),
            diff=self._truncate_diff(pr_context.diff),
        )

    def _truncate_diff(self, diff: str, max_chars: int = 12000) -> str:
        """Truncate diff to avoid hitting context window limits."""
        if len(diff) <= max_chars:
            return diff
        truncated = diff[:max_chars]
        return truncated + "\n\n[... diff truncated for context window ...]"

    def _parse_llm_output(self, raw_output: str, pr_context: PRContext) -> list[AgentFinding]:
        """
        Parse JSON array from LLM output.
        LLMs sometimes wrap JSON in markdown code blocks — we strip those.
        """
        findings = []

        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?", "", raw_output).strip()
        cleaned = cleaned.strip("`").strip()

        # Find the JSON array in the output
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if not match:
            logger.warning(f"[{self.agent_name}] No JSON array found in output")
            return []

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as e:
            logger.error(f"[{self.agent_name}] JSON parse error: {e}")
            return []

        for item in data:
            try:
                # Normalize severity to our enum
                raw_sev = item.get("severity", "low").lower()
                severity = Severity(raw_sev) if raw_sev in Severity._value2member_map_ else Severity.LOW

                confidence = float(item.get("confidence", 0.8))
                if confidence < self.min_confidence:
                    logger.debug(f"[{self.agent_name}] Skipping low confidence finding: {item.get('category')}")
                    continue

                finding = AgentFinding(
                    agent=self.agent_name,
                    file=item.get("file", "unknown"),
                    line=item.get("line"),
                    severity=severity,
                    category=item.get("category", "General"),
                    message=item.get("message", ""),
                    suggestion=item.get("suggestion", ""),
                    confidence=confidence,
                    code_snippet=item.get("code_snippet"),
                )
                findings.append(finding)
            except Exception as e:
                logger.warning(f"[{self.agent_name}] Skipping malformed finding: {e}")

        return findings

    async def run(self, pr_context: PRContext) -> AgentResult:
        logger.info(f"[{self.agent_name}] Starting analysis for PR #{pr_context.pr_number}")
        try:
            prompt = self._build_prompt(pr_context)
            raw_output = await self.llm.ainvoke(prompt)
            findings = self._parse_llm_output(raw_output, pr_context)
            logger.info(f"[{self.agent_name}] Found {len(findings)} issues")
            return AgentResult(agent_name=self.agent_name, findings=findings)
        except Exception as e:
            logger.error(f"[{self.agent_name}] Error: {e}")
            return AgentResult(agent_name=self.agent_name, findings=[], error=str(e))

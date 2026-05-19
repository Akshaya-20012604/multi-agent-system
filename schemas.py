from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class AgentFinding(BaseModel):
    agent: str = Field(description="Name of the agent that produced this finding")
    file: str = Field(description="File path where the issue was found")
    line: Optional[int] = Field(default=None, description="Line number of the issue")
    severity: Severity = Field(description="Severity level of the finding")
    category: str = Field(description="Short category label e.g. 'SQL Injection', 'Missing docstring'")
    message: str = Field(description="Human-readable description of the issue")
    suggestion: str = Field(description="Concrete suggestion to fix the issue")
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score 0.0-1.0. Low confidence = needs human review"
    )
    code_snippet: Optional[str] = Field(
        default=None,
        description="Relevant code snippet (max 5 lines)"
    )


class AgentResult(BaseModel):
    agent_name: str
    findings: list[AgentFinding] = []
    error: Optional[str] = None
    tokens_used: int = 0


class PRContext(BaseModel):
    repo_full_name: str           # e.g. "akshayanm26/my-repo"
    pr_number: int
    pr_title: str
    pr_body: Optional[str] = ""
    author: str
    base_branch: str
    head_branch: str
    diff: str                     # Full unified diff text
    changed_files: list[str] = []
    additions: int = 0
    deletions: int = 0


class ReviewReport(BaseModel):
    pr_number: int
    repo: str
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    findings: list[AgentFinding]
    markdown_summary: str

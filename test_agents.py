"""
Tests for the aggregator and agent output parsing.
Run with: pytest tests/ -v
"""
import pytest
from models.schemas import AgentFinding, AgentResult, PRContext, Severity
from app.aggregator import Aggregator


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_pr_context():
    return PRContext(
        repo_full_name="testuser/test-repo",
        pr_number=42,
        pr_title="Add user authentication",
        pr_body="Adds JWT-based login and registration endpoints.",
        author="testuser",
        base_branch="main",
        head_branch="feature/auth",
        diff="""
diff --git a/src/auth/UserService.java b/src/auth/UserService.java
+++ b/src/auth/UserService.java
@@ -10,6 +10,20 @@
+    public String login(String username, String password) {
+        String query = "SELECT * FROM users WHERE username='" + username + "'";
+        // TODO: hash password
+        String secret = "hardcoded_jwt_secret_123";
+        return generateToken(secret);
+    }
""",
        changed_files=["src/auth/UserService.java"],
        additions=14,
        deletions=0,
    )


@pytest.fixture
def sample_findings():
    return [
        AgentFinding(
            agent="SecurityAgent",
            file="src/auth/UserService.java",
            line=13,
            severity=Severity.CRITICAL,
            category="SQL Injection",
            message="String concatenation in SQL query allows injection",
            suggestion="Use PreparedStatement with parameterized queries",
            confidence=0.95,
        ),
        AgentFinding(
            agent="SecurityAgent",
            file="src/auth/UserService.java",
            line=15,
            severity=Severity.CRITICAL,
            category="Hardcoded Secret",
            message="JWT secret is hardcoded in source code",
            suggestion="Load from environment variable: System.getenv('JWT_SECRET')",
            confidence=0.99,
        ),
        AgentFinding(
            agent="CodeQualityAgent",
            file="src/auth/UserService.java",
            line=13,
            severity=Severity.MEDIUM,
            category="SQL Injection",  # duplicate of above
            message="SQL built via string concatenation",
            suggestion="Use parameterized queries",
            confidence=0.7,
        ),
        AgentFinding(
            agent="DocUpdaterAgent",
            file="src/auth/UserService.java",
            line=10,
            severity=Severity.LOW,
            category="Missing Javadoc",
            message="Public method login() has no Javadoc",
            suggestion="Add @param username, @param password, @return JWT token",
            confidence=0.9,
        ),
    ]


# ---------------------------------------------------------------------------
# Aggregator tests
# ---------------------------------------------------------------------------

class TestAggregator:
    def test_deduplication_keeps_higher_severity(self, sample_pr_context, sample_findings):
        aggregator = Aggregator()
        agent_results = [
            AgentResult(agent_name="SecurityAgent",   findings=sample_findings[:2]),
            AgentResult(agent_name="CodeQualityAgent", findings=[sample_findings[2]]),
            AgentResult(agent_name="DocUpdaterAgent",  findings=[sample_findings[3]]),
        ]
        report = aggregator.aggregate(sample_pr_context, agent_results)

        # The SQL Injection at line 13 should appear once (CRITICAL wins over MEDIUM)
        sql_findings = [f for f in report.findings if f.category == "SQL Injection"]
        assert len(sql_findings) == 1
        assert sql_findings[0].severity == Severity.CRITICAL

    def test_total_finding_count(self, sample_pr_context, sample_findings):
        aggregator = Aggregator()
        agent_results = [AgentResult(agent_name="SecurityAgent", findings=sample_findings)]
        report = aggregator.aggregate(sample_pr_context, agent_results)
        # 4 findings but the SQL Injection is a duplicate → 3 unique
        assert report.total_findings == 3

    def test_findings_sorted_by_severity(self, sample_pr_context, sample_findings):
        aggregator = Aggregator()
        agent_results = [AgentResult(agent_name="Mixed", findings=sample_findings)]
        report = aggregator.aggregate(sample_pr_context, agent_results)
        severities = [f.severity for f in report.findings]
        # CRITICAL should come before MEDIUM, MEDIUM before LOW
        assert severities[0] == Severity.CRITICAL

    def test_markdown_generated(self, sample_pr_context, sample_findings):
        aggregator = Aggregator()
        agent_results = [AgentResult(agent_name="SecurityAgent", findings=sample_findings[:2])]
        report = aggregator.aggregate(sample_pr_context, agent_results)
        assert "## 🤖 Automated PR Review" in report.markdown_summary
        assert "SQL Injection" in report.markdown_summary
        assert "Hardcoded Secret" in report.markdown_summary

    def test_empty_findings_message(self, sample_pr_context):
        aggregator = Aggregator()
        agent_results = [AgentResult(agent_name="SecurityAgent", findings=[])]
        report = aggregator.aggregate(sample_pr_context, agent_results)
        assert report.total_findings == 0
        assert "No issues found" in report.markdown_summary

    def test_agent_error_does_not_crash(self, sample_pr_context):
        aggregator = Aggregator()
        agent_results = [
            AgentResult(agent_name="SecurityAgent", findings=[], error="Ollama timeout"),
        ]
        report = aggregator.aggregate(sample_pr_context, agent_results)
        assert report.total_findings == 0


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestSchemas:
    def test_severity_enum_values(self):
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"

    def test_agent_finding_defaults(self):
        finding = AgentFinding(
            agent="TestAgent",
            file="test.py",
            severity=Severity.LOW,
            category="Test",
            message="Test message",
            suggestion="Test suggestion",
        )
        assert finding.confidence == 0.8
        assert finding.line is None
        assert finding.code_snippet is None

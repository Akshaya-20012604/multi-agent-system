import logging
from collections import defaultdict

from models.schemas import AgentResult, AgentFinding, PRContext, ReviewReport, Severity

logger = logging.getLogger(__name__)

SEVERITY_RANK = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
}

SEVERITY_EMOJI = {
    Severity.CRITICAL: "🔴",
    Severity.HIGH: "🟠",
    Severity.MEDIUM: "🟡",
    Severity.LOW: "🔵",
    Severity.INFO: "⚪",
}


class Aggregator:
    """
    Merges findings from all agents, deduplicates overlapping issues,
    resolves conflicts (e.g. two agents flagging the same line),
    ranks by severity, and builds the final markdown review comment.
    """

    def aggregate(self, pr_context: PRContext, agent_results: list[AgentResult]) -> ReviewReport:
        all_findings: list[AgentFinding] = []
        for result in agent_results:
            all_findings.extend(result.findings)

        deduplicated = self._deduplicate(all_findings)
        ranked = sorted(deduplicated, key=lambda f: SEVERITY_RANK[f.severity])

        counts = defaultdict(int)
        for f in ranked:
            counts[f.severity] += 1

        markdown = self._build_markdown(pr_context, ranked, agent_results)

        return ReviewReport(
            pr_number=pr_context.pr_number,
            repo=pr_context.repo_full_name,
            total_findings=len(ranked),
            critical_count=counts[Severity.CRITICAL],
            high_count=counts[Severity.HIGH],
            medium_count=counts[Severity.MEDIUM],
            low_count=counts[Severity.LOW],
            findings=ranked,
            markdown_summary=markdown,
        )

    def _deduplicate(self, findings: list[AgentFinding]) -> list[AgentFinding]:
        """
        Two findings are duplicates if they point to the same file + line
        and have the same category. Keep the one with higher severity.
        """
        seen: dict[str, AgentFinding] = {}
        for finding in findings:
            key = f"{finding.file}:{finding.line}:{finding.category.lower()}"
            if key not in seen:
                seen[key] = finding
            else:
                existing = seen[key]
                if SEVERITY_RANK[finding.severity] < SEVERITY_RANK[existing.severity]:
                    logger.debug(
                        f"[Aggregator] Upgrading severity of '{finding.category}' "
                        f"at {finding.file}:{finding.line} from {existing.severity} to {finding.severity}"
                    )
                    seen[key] = finding
        return list(seen.values())

    def _build_markdown(
        self,
        pr_context: PRContext,
        findings: list[AgentFinding],
        agent_results: list[AgentResult],
    ) -> str:
        lines = []

        # Header
        lines.append("## 🤖 Automated PR Review")
        lines.append("")
        lines.append(f"**PR:** {pr_context.pr_title}  ")
        lines.append(f"**Files changed:** {len(pr_context.changed_files)}  ")
        lines.append(f"**Additions:** +{pr_context.additions}  **Deletions:** -{pr_context.deletions}")
        lines.append("")

        # Agent status
        lines.append("### Agents run")
        lines.append("")
        for result in agent_results:
            status = "✅" if not result.error else "❌"
            count = len(result.findings)
            lines.append(f"- {status} **{result.agent_name}** — {count} finding(s)")
        lines.append("")

        if not findings:
            lines.append("### ✅ No issues found!")
            lines.append("")
            lines.append("All agents reviewed the diff and found nothing to flag. Great work!")
            return "\n".join(lines)

        # Summary counts
        from collections import defaultdict
        counts = defaultdict(int)
        for f in findings:
            counts[f.severity] += 1

        lines.append("### Summary")
        lines.append("")
        lines.append("| Severity | Count |")
        lines.append("|---|---|")
        for sev in [Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW, Severity.INFO]:
            if counts[sev]:
                lines.append(f"| {SEVERITY_EMOJI[sev]} {sev.value.capitalize()} | {counts[sev]} |")
        lines.append("")

        # Findings grouped by file
        by_file: dict[str, list[AgentFinding]] = defaultdict(list)
        for f in findings:
            by_file[f.file].append(f)

        lines.append("### Findings")
        lines.append("")

        for filepath, file_findings in sorted(by_file.items()):
            lines.append(f"#### 📄 `{filepath}`")
            lines.append("")
            for finding in file_findings:
                emoji = SEVERITY_EMOJI[finding.severity]
                line_ref = f"Line {finding.line}" if finding.line else "General"
                lines.append(f"**{emoji} [{finding.severity.value.upper()}] {finding.category}** — {line_ref}  ")
                lines.append(f"*Agent: {finding.agent}* | *Confidence: {int(finding.confidence * 100)}%*  ")
                lines.append("")
                lines.append(f"> {finding.message}")
                lines.append("")
                if finding.code_snippet:
                    lines.append("```")
                    lines.append(finding.code_snippet)
                    lines.append("```")
                    lines.append("")
                lines.append(f"💡 **Suggestion:** {finding.suggestion}")
                lines.append("")
                lines.append("---")
                lines.append("")

        lines.append("*Generated by [pr-review-agent](https://github.com) — powered by Llama 3.1 (local)*")
        return "\n".join(lines)

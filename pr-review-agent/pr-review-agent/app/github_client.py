import logging
import os

from github import Github, GithubException
from github.PullRequest import PullRequest

from models.schemas import PRContext, ReviewReport

logger = logging.getLogger(__name__)


class GitHubClient:
    def __init__(self):
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable is not set")
        self.gh = Github(token)

    def build_pr_context(self, repo_full_name: str, pr_number: int) -> PRContext:
        """Fetch all data needed for review from the GitHub API."""
        logger.info(f"[GitHub] Fetching PR #{pr_number} from {repo_full_name}")
        repo = self.gh.get_repo(repo_full_name)
        pr: PullRequest = repo.get_pull(pr_number)

        # Get the unified diff
        diff = self._get_diff(pr)

        # Get list of changed files
        changed_files = [f.filename for f in pr.get_files()]

        return PRContext(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            pr_title=pr.title,
            pr_body=pr.body or "",
            author=pr.user.login,
            base_branch=pr.base.ref,
            head_branch=pr.head.ref,
            diff=diff,
            changed_files=changed_files,
            additions=pr.additions,
            deletions=pr.deletions,
        )

    def _get_diff(self, pr: PullRequest) -> str:
        """
        Fetch the raw unified diff for the PR.
        PyGitHub doesn't expose this directly, so we use the
        compare endpoint via the underlying requester.
        """
        import httpx
        token = os.getenv("GITHUB_TOKEN")
        url = pr.diff_url
        response = httpx.get(
            url,
            headers={
                "Authorization": f"token {token}",
                "Accept": "application/vnd.github.v3.diff",
            },
            follow_redirects=True,
            timeout=30,
        )
        response.raise_for_status()
        return response.text

    def post_review_comment(self, report: ReviewReport) -> bool:
        """Post the aggregated review as a PR comment."""
        try:
            repo = self.gh.get_repo(report.repo)
            pr = repo.get_pull(report.pr_number)
            pr.create_issue_comment(report.markdown_summary)
            logger.info(f"[GitHub] Posted review comment on PR #{report.pr_number}")
            return True
        except GithubException as e:
            logger.error(f"[GitHub] Failed to post comment: {e}")
            return False

    def post_error_comment(self, repo_full_name: str, pr_number: int, error_msg: str) -> None:
        """Post a brief error message if the review pipeline failed."""
        try:
            repo = self.gh.get_repo(repo_full_name)
            pr = repo.get_pull(pr_number)
            pr.create_issue_comment(
                f"## 🤖 Automated PR Review\n\n"
                f"❌ Review failed: `{error_msg}`\n\n"
                f"Please check the server logs."
            )
        except Exception:
            pass

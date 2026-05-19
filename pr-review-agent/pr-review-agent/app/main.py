import hashlib
import hmac
import logging
import os
import sqlite3

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PR Review Agent",
    description="Multi-agent AI system for automated GitHub PR reviews",
    version="1.0.0",
)


# ---------------------------------------------------------------------------
# Startup: verify Ollama is reachable and init SQLite
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup_checks():
    # Check Ollama
    import httpx
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{ollama_url}/api/tags", timeout=5)
            models = [m["name"] for m in resp.json().get("models", [])]
            logger.info(f"Ollama connection verified. Available models: {models}")
    except Exception as e:
        logger.error(f"Cannot connect to Ollama at {ollama_url}: {e}")
        logger.error("Make sure Ollama is running: `ollama serve`")

    # Init SQLite for audit log
    db_path = os.getenv("SQLITE_DB_PATH", "./pr_review.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo TEXT,
            pr_number INTEGER,
            total_findings INTEGER,
            critical_count INTEGER,
            high_count INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()
    logger.info(f"SQLite initialized at {db_path}")


# ---------------------------------------------------------------------------
# Webhook signature verification
# ---------------------------------------------------------------------------

def verify_github_signature(payload_bytes: bytes, signature_header: str | None) -> bool:
    """
    Verify the X-Hub-Signature-256 header sent by GitHub.
    Prevents random internet requests from triggering reviews.
    """
    secret = os.getenv("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        logger.warning("GITHUB_WEBHOOK_SECRET not set — skipping signature check")
        return True
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


# ---------------------------------------------------------------------------
# Background task: run the full review pipeline
# ---------------------------------------------------------------------------

async def run_review_pipeline(repo_full_name: str, pr_number: int):
    from app.github_client import GitHubClient
    from app.orchestrator import Orchestrator

    github = GitHubClient()
    orchestrator = Orchestrator()

    try:
        pr_context = github.build_pr_context(repo_full_name, pr_number)
        report = await orchestrator.review(pr_context)
        github.post_review_comment(report)

        # Save to audit log
        db_path = os.getenv("SQLITE_DB_PATH", "./pr_review.db")
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO reviews (repo, pr_number, total_findings, critical_count, high_count) VALUES (?,?,?,?,?)",
            (report.repo, report.pr_number, report.total_findings, report.critical_count, report.high_count),
        )
        conn.commit()
        conn.close()

    except Exception as e:
        logger.exception(f"Review pipeline failed for PR #{pr_number}: {e}")
        github.post_error_comment(repo_full_name, pr_number, str(e))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/")
async def health():
    return {"status": "ok", "service": "pr-review-agent"}


@app.get("/health")
async def health_check():
    """Detailed health check — useful for monitoring."""
    import httpx
    ollama_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_ok = False
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{ollama_url}/api/tags", timeout=3)
            ollama_ok = r.status_code == 200
    except Exception:
        pass
    return {
        "status": "ok",
        "ollama": "connected" if ollama_ok else "unreachable",
        "model": os.getenv("OLLAMA_MODEL", "llama3.1"),
    }


@app.post("/webhook")
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives GitHub webhook events.
    Only processes 'opened' and 'synchronize' PR events.
    Runs the review pipeline in the background so GitHub doesn't time out.
    """
    payload_bytes = await request.body()

    # Verify signature
    signature = request.headers.get("X-Hub-Signature-256")
    if not verify_github_signature(payload_bytes, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    event_type = request.headers.get("X-GitHub-Event", "")

    # Only handle pull_request events
    if event_type != "pull_request":
        return JSONResponse({"message": f"Ignoring event: {event_type}"})

    payload = await request.json()
    action = payload.get("action", "")

    # Only review when a PR is opened or new commits are pushed
    if action not in ("opened", "synchronize", "reopened"):
        return JSONResponse({"message": f"Ignoring PR action: {action}"})

    pr_number = payload["pull_request"]["number"]
    repo_full_name = payload["repository"]["full_name"]

    logger.info(f"PR #{pr_number} {action} in {repo_full_name} — queuing review")

    # Fire and forget — respond to GitHub immediately
    background_tasks.add_task(run_review_pipeline, repo_full_name, pr_number)

    return JSONResponse({"message": "Review queued", "pr": pr_number})


@app.get("/reviews")
async def list_reviews(limit: int = 20):
    """List recent reviews from the audit log."""
    db_path = os.getenv("SQLITE_DB_PATH", "./pr_review.db")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM reviews ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=os.getenv("APP_HOST", "0.0.0.0"),
        port=int(os.getenv("APP_PORT", "8000")),
        reload=True,
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )

# Multi-Agent PR Review System

A fully open-source, locally-running AI system that automatically reviews GitHub Pull Requests using multiple specialist agents.

## Tech Stack (100% Free & Open Source)

| Component | Tool |
|---|---|
| LLM (runs locally) | Ollama + Llama 3.1 8B |
| Agent framework | LangChain |
| Webhook server | FastAPI |
| GitHub integration | PyGitHub |
| Vector store | ChromaDB |
| Database | SQLite (zero setup) |
| Tunneling (local dev) | ngrok (free tier) |

---

## Prerequisites

- Python 3.10+
- Git
- 8GB+ RAM (for Llama 3.1 8B)
- A GitHub account + a test repository

---

## Step 1 — Install Ollama

Ollama lets you run LLMs 100% locally for free.

**Linux / macOS:**
```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

**Windows:**
Download from https://ollama.com/download

**Pull the model (do this once, ~5GB download):**
```bash
ollama pull llama3.1
```

**Verify it works:**
```bash
ollama run llama3.1 "Say hello in one sentence."
```

Keep Ollama running in the background — it starts automatically after install.

---

## Step 2 — Clone & Install Dependencies

```bash
git clone https://github.com/YOUR_USERNAME/pr-review-agent.git
cd pr-review-agent

# Create virtual environment
python -m venv venv

# Activate it
source venv/bin/activate        # Linux/macOS
venv\Scripts\activate           # Windows

# Install all dependencies
pip install -r requirements.txt
```

---

## Step 3 — Create a GitHub Personal Access Token

1. Go to https://github.com/settings/tokens
2. Click **Generate new token (classic)**
3. Select scopes: `repo`, `pull_requests`
4. Copy the token

---

## Step 4 — Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and fill in:
```
GITHUB_TOKEN=ghp_your_token_here
GITHUB_WEBHOOK_SECRET=any_random_string_you_choose
```

---

## Step 5 — Set Up GitHub Webhook (using ngrok for local dev)

**Install ngrok (free):**
```bash
# Linux
wget https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz
tar -xzf ngrok-v3-stable-linux-amd64.tgz
sudo mv ngrok /usr/local/bin/

# macOS
brew install ngrok

# Sign up free at https://ngrok.com and run:
ngrok config add-authtoken YOUR_NGROK_TOKEN
```

**Start the tunnel (in a separate terminal):**
```bash
ngrok http 8000
```
Copy the `https://xxxx.ngrok.io` URL — you'll use this in GitHub.

**Add webhook to your GitHub repo:**
1. Go to your repo → Settings → Webhooks → Add webhook
2. Payload URL: `https://xxxx.ngrok.io/webhook`
3. Content type: `application/json`
4. Secret: same value as `GITHUB_WEBHOOK_SECRET` in your `.env`
5. Events: select **Pull requests**

---

## Step 6 — Run the Server

```bash
# Make sure venv is activated and Ollama is running
python -m app.main
```

You should see:
```
INFO: Uvicorn running on http://0.0.0.0:8000
INFO: Ollama connection verified
INFO: ChromaDB initialized
```

---

## Step 7 — Test It

Open a Pull Request in your GitHub repo. Within ~30-60 seconds you'll see an automated review comment from your bot.

---

## Step 8 — Push to GitHub

```bash
# Initialize git (if not cloned)
git init
git add .
git commit -m "feat: initial multi-agent PR review system"

# Create repo on GitHub, then:
git remote add origin https://github.com/YOUR_USERNAME/pr-review-agent.git
git branch -M main
git push -u origin main
```

---

## Architecture

```
GitHub PR opened
       ↓
FastAPI webhook (/webhook)
       ↓
Orchestrator (LangChain)
       ↓ fans out to 4 agents in parallel
┌──────────────┬──────────────┬──────────────┬──────────────┐
│ Code Quality │   Security   │ Test Writer  │ Doc Updater  │
└──────────────┴──────────────┴──────────────┴──────────────┘
       ↓ all call Ollama (Llama 3.1) locally
Aggregator → dedup + rank by severity
       ↓
GitHub PR Comment (inline + summary)
```

---

## Project Structure

```
pr-review-agent/
├── app/
│   ├── main.py              # FastAPI app + webhook endpoint
│   ├── orchestrator.py      # LangChain multi-agent runner
│   ├── aggregator.py        # Merge + deduplicate agent outputs
│   ├── github_client.py     # GitHub API integration
│   └── agents/
│       ├── base_agent.py    # Shared agent logic
│       ├── code_quality.py  # Code smell + complexity agent
│       ├── security.py      # OWASP + secret scanning agent
│       ├── test_writer.py   # Unit test stub generator
│       └── doc_updater.py   # Javadoc / docstring updater
├── models/
│   └── schemas.py           # Pydantic data models
├── prompts/
│   ├── code_quality.txt
│   ├── security.txt
│   ├── test_writer.txt
│   └── doc_updater.txt
├── tests/
│   ├── test_agents.py
│   └── test_aggregator.py
├── scripts/
│   └── setup.sh             # One-command setup script
├── .env.example
├── .gitignore
└── requirements.txt
```

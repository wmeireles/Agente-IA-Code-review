# 🤖 Hermes Code Reviewer

Automated code review agent powered by **Hermes** (Nous Research), integrated with GitHub via webhooks.

## Architecture

```
[Developer opens PR] → [GitHub Webhook] → [FastAPI] → [Hermes Agent] → [Comments on PR]
```

## Flow

1. Developer opens/updates a Pull Request
2. GitHub sends webhook to `/webhooks/github`
3. Service validates signature, extracts PR data
4. Fetches diff and filters irrelevant files
5. Sends diff to Hermes Agent with specialized system prompt
6. Hermes returns structured JSON review (path, line, body)
7. Service posts inline comments + summary on the PR

## Setup

```bash
# Install
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your keys

# Run
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

## GitHub Webhook Configuration

1. Go to your repo → Settings → Webhooks → Add webhook
2. Payload URL: `https://your-vps.com/webhooks/github`
3. Content type: `application/json`
4. Secret: same as `GITHUB_WEBHOOK_SECRET` in .env
5. Events: select "Pull requests"

## Project Structure

```
hermes-code-reviewer/
├── app/
│   ├── core/
│   │   ├── config.py      # Settings (env vars)
│   │   └── security.py    # Webhook signature validation
│   ├── schemas/
│   │   └── review.py      # Pydantic models (structured output)
│   ├── services/
│   │   ├── github.py      # Fetch diff & files from GitHub API
│   │   ├── hermes.py      # Hermes Agent integration + system prompt
│   │   └── poster.py      # Post comments back to GitHub
│   └── main.py            # FastAPI app + webhook endpoint
├── Dockerfile
├── requirements.txt
└── .env.example
```

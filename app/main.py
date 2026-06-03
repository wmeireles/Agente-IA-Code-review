"""
Hermes Code Reviewer — FastAPI Microservice
Webhook endpoint + background processing pipeline.
"""
import json
import logging
from fastapi import FastAPI, Request, BackgroundTasks, status
from app.core.config import settings
from app.core.security import verify_github_signature
from app.schemas.review import PRPayload
from app.services.github import fetch_pr_diff, fetch_pr_files, filter_relevant_files
from app.services.hermes import agent, CodeReviewOutput
from app.services.poster import post_review_comments

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Hermes Code Reviewer",
    version="1.0.0",
    description="Automated PR review agent powered by Hermes (Nous Research)",
)


# ─── Health ───────────────────────────────────────────────────────────────────

@app.api_route("/", methods=["GET", "HEAD"])
@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"status": "healthy", "agent": agent.AGENT_NAME, "version": "1.0.0"}


# ─── Webhook Endpoint ─────────────────────────────────────────────────────────

@app.post("/webhooks/github", status_code=status.HTTP_202_ACCEPTED)
async def github_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Recebe webhook do GitHub para eventos de Pull Request.
    Valida assinatura, extrai dados e dispara revisão em background.
    Retorna 202 imediatamente para evitar timeout do GitHub.
    """
    # 1. Validar X-Hub-Signature-256
    body = await verify_github_signature(request)
    payload = json.loads(body)

    # 2. Filtrar ações relevantes
    action = payload.get("action")
    if action not in ("opened", "synchronize", "reopened"):
        return {"message": f"Ignored: {action}"}

    pr = payload.get("pull_request")
    if not pr:
        return {"message": "Not a PR event"}

    # 3. Extrair contexto do PR
    pr_data = PRPayload(
        action=action,
        number=pr["number"],
        repo_full_name=payload["repository"]["full_name"],
        pr_title=pr["title"],
        pr_body=pr.get("body"),
        head_sha=pr["head"]["sha"],
        diff_url=pr["diff_url"],
    )

    # 4. Disparar pipeline em background
    background_tasks.add_task(review_pipeline, pr_data)

    logger.info(f"Review queued: {pr_data.repo_full_name}#{pr_data.number}")
    return {"message": f"Review queued for PR #{pr_data.number}", "status": "processing"}


# ─── Review Pipeline (Background) ────────────────────────────────────────────

async def review_pipeline(pr: PRPayload):
    """
    Pipeline completo de revisão:
        1. Fetch diff do GitHub
        2. Filtrar arquivos relevantes
        3. Executar Hermes Agent (User Story)
        4. Postar resultado no PR
    """
    try:
        logger.info(f"[Pipeline] Starting: {pr.repo_full_name}#{pr.number} — {pr.pr_title}")

        # Step 1: Fetch diff
        diff = await fetch_pr_diff(pr.repo_full_name, pr.number)
        if not diff:
            logger.warning(f"[Pipeline] Empty diff for PR #{pr.number}")
            return

        # Step 2: Filter files
        files = await fetch_pr_files(pr.repo_full_name, pr.number)
        relevant = filter_relevant_files(files)
        if not relevant:
            logger.info(f"[Pipeline] PR #{pr.number}: No relevant files (all filtered)")
            return

        logger.info(f"[Pipeline] PR #{pr.number}: {len(relevant)} relevant files, {len(diff)} chars diff")

        # Step 3: Execute Hermes Agent
        review: CodeReviewOutput = await agent.execute(
            diff=diff,
            pr_title=pr.pr_title,
            pr_body=pr.pr_body or "",
        )

        logger.info(
            f"[Pipeline] PR #{pr.number}: Hermes verdict — "
            f"risk={review.risk_level}, approved={review.approved}, "
            f"comments={len(review.comments)}"
        )

        # Step 4: Post to GitHub
        await post_review_comments(
            repo_full_name=pr.repo_full_name,
            pr_number=pr.number,
            head_sha=pr.head_sha,
            review=review,
        )

        logger.info(f"[Pipeline] PR #{pr.number}: Review posted successfully")

    except Exception as e:
        logger.error(f"[Pipeline] PR #{pr.number}: Failed — {type(e).__name__}: {e}")


# ─── Entry Point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001, reload=True)

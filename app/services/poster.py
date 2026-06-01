import httpx
import logging
from app.core.config import settings
from app.schemas.review import CodeReviewResult

logger = logging.getLogger(__name__)


async def post_review_comments(
    repo_full_name: str,
    pr_number: int,
    head_sha: str,
    review: CodeReviewResult,
):
    """Posta a revisão como comentários no PR do GitHub."""
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    # 1. Posta resumo como comentário geral
    risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
    status_emoji = "✅" if review.approved else "⚠️"

    summary_body = f"""{status_emoji} **Hermes Code Review**

{review.summary}

| Risco | Status |
|-------|--------|
| {risk_emoji.get(review.risk_level, '⚪')} {review.risk_level.upper()} | {'Aprovado' if review.approved else 'Alterações necessárias'} |

{'---' if review.comments else ''}
{'📝 ' + str(len(review.comments)) + ' comentário(s) inline abaixo.' if review.comments else '🎉 Nenhum problema encontrado!'}
"""

    async with httpx.AsyncClient(timeout=30.0) as client:
        # Comentário geral no PR
        await client.post(
            f"https://api.github.com/repos/{repo_full_name}/issues/{pr_number}/comments",
            headers=headers,
            json={"body": summary_body},
        )

        # Comentários inline (por linha)
        if review.comments:
            review_payload = {
                "commit_id": head_sha,
                "body": f"Hermes encontrou {len(review.comments)} ponto(s) para revisão.",
                "event": "COMMENT",
                "comments": [
                    {
                        "path": c.path,
                        "line": c.line,
                        "body": c.body,
                    }
                    for c in review.comments
                ],
            }

            resp = await client.post(
                f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews",
                headers=headers,
                json=review_payload,
            )

            if resp.status_code >= 400:
                logger.warning(f"Failed to post inline comments: {resp.status_code} {resp.text}")

    logger.info(f"Review posted on {repo_full_name}#{pr_number}: {review.risk_level}, {len(review.comments)} comments")

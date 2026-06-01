"""
Webhook signature validation — GitHub X-Hub-Signature-256.
"""
import hmac
import hashlib
from fastapi import Request, HTTPException, status
from app.core.config import settings


async def verify_github_signature(request: Request) -> bytes:
    """
    Valida a assinatura HMAC-SHA256 do webhook do GitHub.
    Garante que o payload veio realmente do GitHub e não foi adulterado.
    """
    signature = request.headers.get("X-Hub-Signature-256")
    if not signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Hub-Signature-256 header",
        )

    body = await request.body()

    expected = "sha256=" + hmac.new(
        key=settings.GITHUB_WEBHOOK_SECRET.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook signature",
        )

    return body

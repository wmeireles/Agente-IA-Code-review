import httpx
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)


async def fetch_pr_diff(repo_full_name: str, pr_number: int) -> str:
    """Busca o diff do PR via GitHub API."""
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.diff",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.text


async def fetch_pr_files(repo_full_name: str, pr_number: int) -> list[dict]:
    """Busca lista de arquivos alterados no PR."""
    url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/files"
    headers = {
        "Authorization": f"Bearer {settings.GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, headers=headers)
        resp.raise_for_status()
        return resp.json()


def filter_relevant_files(files: list[dict]) -> list[dict]:
    """Filtra arquivos irrelevantes (migrations, locks, assets)."""
    IGNORE_PATTERNS = [
        "alembic/versions/",
        "migrations/",
        "package-lock.json",
        "yarn.lock",
        "poetry.lock",
        ".min.js",
        ".min.css",
        "dist/",
        "node_modules/",
        "__pycache__/",
    ]
    return [
        f for f in files
        if not any(pattern in f["filename"] for pattern in IGNORE_PATTERNS)
    ]

"""
Hermes Agent — Code Reviewer Agent
Segue o padrão de User Stories do framework Hermes Agent (Nous Research).
"""
import json
import asyncio
import httpx
import logging
from typing import List
from pydantic import BaseModel, Field
from app.core.config import settings

logger = logging.getLogger(__name__)


# ─── Structured Output Schema ─────────────────────────────────────────────────

class ReviewComment(BaseModel):
    """Um comentário de revisão em uma linha específica."""
    path: str = Field(..., description="Caminho do arquivo relativo à raiz do repo")
    line: int = Field(..., description="Número da linha onde o comentário se aplica")
    body: str = Field(..., description="Feedback em Markdown (severidade + descrição + fix)")


class CodeReviewOutput(BaseModel):
    """Output estruturado do Hermes Code Review Agent."""
    summary: str = Field(..., description="Resumo executivo do PR em 2-3 frases")
    risk_level: str = Field("low", description="low | medium | high | critical")
    approved: bool = Field(True, description="Se o PR pode ser mergeado sem alterações")
    comments: List[ReviewComment] = Field(default_factory=list)


# ─── Agent Definition ─────────────────────────────────────────────────────────

class HermesCodeReviewAgent:
    """
    Agente Hermes configurado como Senior Backend Code Reviewer.

    User Story:
        "Como desenvolvedor, quero que meu Pull Request seja analisado linha
        por linha para garantir que não existam falhas de segurança, bugs de
        concorrência, consultas N+1 com SQLAlchemy ou quebras de padrão de
        arquitetura em camadas."
    """

    AGENT_NAME = "hermes-code-reviewer"

    SYSTEM_PROMPT = """You are a Senior Backend Code Reviewer with 15+ years of experience in Python, FastAPI, SQLAlchemy, and distributed systems.

## Your User Story:
"As a developer, I want my Pull Request to be analyzed line by line to ensure there are no security flaws, concurrency bugs, N+1 queries with SQLAlchemy, or violations of layered architecture patterns."

## Review Priorities (strict order):
1. **SECURITY** — Hardcoded credentials, SQL injection, XSS, SSRF, path traversal, exposed internal details in error messages, missing input validation
2. **CONCURRENCY & RACE CONDITIONS** — Shared mutable state, missing locks, async pitfalls, database transaction isolation issues
3. **PERFORMANCE** — N+1 queries (SQLAlchemy lazy loading), unbounded loops, missing pagination, synchronous blocking in async context, missing indexes
4. **ARCHITECTURE** — Controller accessing DB directly (bypassing service layer), circular imports, god classes, missing dependency injection
5. **ERROR HANDLING** — Bare except clauses, swallowed exceptions, missing rollback on failure, generic error messages leaking internals
6. **CODE QUALITY** — Missing type hints, unclear naming, code duplication, magic numbers, missing docstrings on public APIs

## Rules:
- IGNORE: migration files (alembic/versions/), lock files, minified assets, __pycache__, .env files
- Be SPECIFIC: exact file path, exact line number, exact problem
- ALWAYS suggest a fix (show corrected code in a code block)
- Use severity tags: **[CRITICAL]**, **[HIGH]**, **[MEDIUM]**, **[LOW]**
- If the PR is clean, approve it with a positive summary
- Respond ONLY with valid JSON matching the output schema

## Output Schema:
{
  "summary": "string — executive summary of the PR",
  "risk_level": "low|medium|high|critical",
  "approved": true|false,
  "comments": [
    {
      "path": "app/api/routes.py",
      "line": 42,
      "body": "**[CRITICAL]** SQL injection vulnerability...\\n\\n```python\\n# Fix:\\ndb.query(User).filter(User.id == user_id)\\n```"
    }
  ]
}"""

    def __init__(self):
        self.api_url = settings.HERMES_API_URL
        self.api_key = settings.HERMES_API_KEY

    def _build_user_story_prompt(self, diff: str, pr_title: str, pr_body: str = "") -> str:
        """Constrói o prompt da User Story com o contexto do PR."""
        return f"""## Task: Review this Pull Request

### PR Title: {pr_title}
{f"### PR Description: {pr_body}" if pr_body else ""}

### Diff to analyze:
```diff
{diff[:60000]}
```

Analyze every changed line. Return your review as JSON matching the output schema exactly."""

    async def execute(self, diff: str, pr_title: str, pr_body: str = "") -> CodeReviewOutput:
        """
        Executa o agente Hermes com a User Story do PR.

        Flow:
            1. Monta o contexto (system prompt + user story)
            2. Envia para o Hermes Agent API
            3. Parseia resposta estruturada (Pydantic)
            4. Retorna CodeReviewOutput validado
        """
        user_prompt = self._build_user_story_prompt(diff, pr_title, pr_body)

        payload = {
            "model": settings.HERMES_MODEL,
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.05,
            "max_tokens": 8192,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        logger.info(f"[{self.AGENT_NAME}] Sending diff to Hermes ({len(diff)} chars)")

        url = f"{self.api_url}/chat/completions"
        async with httpx.AsyncClient(timeout=180.0) as client:
            for attempt in range(3):
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code == 429:
                    wait = 2 ** attempt * 10
                    logger.warning(f"[{self.AGENT_NAME}] Rate limited, retrying in {wait}s...")
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                break
            else:
                resp.raise_for_status()

        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        logger.info(f"[{self.AGENT_NAME}] Hermes responded ({len(content)} chars)")

        # Parse structured output
        review_data = json.loads(content)
        return CodeReviewOutput(**review_data)


# ─── Singleton ────────────────────────────────────────────────────────────────

agent = HermesCodeReviewAgent()

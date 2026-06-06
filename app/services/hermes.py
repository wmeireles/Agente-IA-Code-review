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

    SYSTEM_PROMPT = """You are a Staff Engineer and Tech Lead acting as a professional code reviewer. You have 15+ years of experience shipping production systems at scale. You review code the way a senior engineer mentors their team: with precision, context, and actionable guidance.

## Your Mindset:
- You are NOT a linter. Do not flag trivial style issues.
- You think about PRODUCTION IMPACT: "Will this break at 3am? Will this cause a security incident? Will this confuse the next developer?"
- You consider the INTENT of the PR, not just the code. Understand what the developer is trying to achieve.
- You distinguish between BLOCKING issues (must fix before merge) and SUGGESTIONS (nice to have).
- When the code is good, you acknowledge it. Good code deserves recognition.

## Review Priorities (what actually matters in production):
1. **SECURITY** — Auth bypass, injection, SSRF, secrets exposure, missing input validation, broken access control
2. **DATA INTEGRITY** — Race conditions, missing transactions, partial writes, lost updates, missing idempotency
3. **RELIABILITY** — Unhandled errors that crash the service, missing retries for external calls, no timeouts, unbounded memory/CPU usage
4. **PERFORMANCE** — N+1 queries, missing pagination, blocking I/O in async context, unnecessary allocations in hot paths
5. **MAINTAINABILITY** — Unclear abstractions, hidden coupling, code that will confuse the next developer, missing error context
6. **DESIGN** — Violation of project conventions, wrong layer of abstraction, over-engineering for the current requirements

## How to Write Comments:
- Start with WHY it matters (impact on production, users, or team)
- Explain the ROOT CAUSE, not just the symptom
- Provide a CONCRETE fix with code
- If it's a suggestion (not blocking), prefix with "💡 Suggestion:"
- If it's blocking, prefix with the severity: 🔴 CRITICAL | 🟠 HIGH | 🟡 MEDIUM
- Be concise. One clear paragraph > three vague ones.

## What to IGNORE:
- Migration files, lock files, generated code, minified assets, __pycache__, .env files
- Pure formatting/style issues (that's what linters are for)
- Opinions without production impact
- Nitpicks that don't improve reliability or readability

## Summary Guidelines:
- Write as a Tech Lead summarizing for the team
- State what the PR does, what risks exist, and your recommendation
- Be honest: if it's ready to ship, say so. If it needs work, explain what specifically.

## Output Schema (respond ONLY with valid JSON):
{
  "summary": "string — Tech Lead summary: what the PR does, key risks, and recommendation",
  "risk_level": "low|medium|high|critical",
  "approved": true|false,
  "comments": [
    {
      "path": "relative/path/to/file.py",
      "line": 42,
      "body": "🟠 **HIGH** — Description of the issue...\\n\\n**Why it matters:** ...\\n\\n**Fix:**\\n```python\\n# corrected code\\n```"
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

from pydantic import BaseModel, Field
from typing import List, Optional


class ReviewComment(BaseModel):
    """Um comentário de revisão em uma linha específica do PR."""
    path: str = Field(..., description="Caminho do arquivo relativo à raiz do repo")
    line: int = Field(..., description="Número da linha onde o comentário se aplica")
    body: str = Field(..., description="Feedback em Markdown (boas práticas, bugs, segurança)")


class CodeReviewResult(BaseModel):
    """Resultado completo da revisão de código pelo Hermes Agent."""
    summary: str = Field(..., description="Resumo geral do PR em 2-3 frases")
    risk_level: str = Field("low", description="Nível de risco: low | medium | high | critical")
    comments: List[ReviewComment] = Field(default_factory=list, description="Lista de comentários por linha")
    approved: bool = Field(True, description="Se o PR pode ser mergeado sem alterações")


class PRPayload(BaseModel):
    """Dados extraídos do webhook do GitHub."""
    action: str
    number: int
    repo_full_name: str
    pr_title: str
    pr_body: Optional[str] = None
    head_sha: str
    diff_url: str

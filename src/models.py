from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class Paper:
    source: str
    title: str
    authors: str
    summary: str
    url: str
    published: str
    arxiv_id: Optional[str] = None
    doi: Optional[str] = None
    openalex_id: Optional[str] = None
    venue: Optional[str] = None
    keywords: List[str] = field(default_factory=list)

@dataclass
class RankedPaper:
    paper: Paper
    pre_score: float
    llm_score: float
    final_score: float
    reason: str
    takeaway: str
    provider: str
    model: str

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional
import json
import os
from openai import OpenAI
from .arxiv import Paper

@dataclass
class Ranked:
    paper: Paper
    score: float
    reason: str
    takeaway: str
    provider: str
    model: str

SYSTEM = """You are a research paper triage assistant.
Score relevance to the user's interests:
AI, Computer Vision, LLM/VLM, embodied intelligence, robotics/manipulation,
intelligent manufacturing systems, digital twin, physical AI, planning/assembly, sim2real, RL.
Output JSON only.
"""

def build_user_prompt(p: Paper, keywords: List[str]) -> str:
    abstract = (p.summary or "")[:2000]
    return f"""
Title: {p.title}
Authors: {p.authors}
Published: {p.published}
Link: {p.url}
Abstract/Summary: {abstract}

Keyword hints (not strict): {", ".join(keywords[:50])}

Return JSON with fields:
score: number 0-5 (5 highest),
reason: short (<=30 words),
takeaway: 1-2 sentences, concise.
"""

def _call_llm(client: OpenAI, model: str, paper: Paper, keywords: List[str]) -> dict:
    resp = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": build_user_prompt(paper, keywords)}
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)

def rank_papers(papers: List[Paper], keywords: List[str]) -> List[Ranked]:
    """
    Priority:
      1) OpenRouter free model (fast/cheap)
      2) DeepSeek as fallback
    """

    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")

    # OpenRouter: OpenAI-compatible endpoint
    openrouter_client: Optional[OpenAI] = None
    if openrouter_key:
        openrouter_client = OpenAI(
            api_key=openrouter_key,
            base_url="https://openrouter.ai/api/v1",
        )

    # DeepSeek: OpenAI-compatible endpoint
    deepseek_client: Optional[OpenAI] = None
    if deepseek_key:
        deepseek_client = OpenAI(
            api_key=deepseek_key,
            base_url="https://api.deepseek.com",
        )

    # Choose an OpenRouter model that often has free/cheap availability
    # If this model becomes unavailable, you can swap it to another OpenRouter model.
    OPENROUTER_MODEL = "deepseek/deepseek-chat"   # OpenRouter route
    DEEPSEEK_MODEL = "deepseek-chat"              # DeepSeek direct

    ranked: List[Ranked] = []

    for p in papers:
        last_err = None

        # 1) try OpenRouter
        if openrouter_client is not None:
            try:
                data = _call_llm(openrouter_client, OPENROUTER_MODEL, p, keywords)
                ranked.append(Ranked(
                    paper=p,
                    score=float(data.get("score", 0)),
                    reason=str(data.get("reason", "")).strip(),
                    takeaway=str(data.get("takeaway", "")).strip(),
                    provider="openrouter",
                    model=OPENROUTER_MODEL
                ))
                continue
            except Exception as e:
                last_err = e

        # 2) fallback DeepSeek
        if deepseek_client is not None:
            try:
                data = _call_llm(deepseek_client, DEEPSEEK_MODEL, p, keywords)
                ranked.append(Ranked(
                    paper=p,
                    score=float(data.get("score", 0)),
                    reason=str(data.get("reason", "")).strip(),
                    takeaway=str(data.get("takeaway", "")).strip(),
                    provider="deepseek",
                    model=DEEPSEEK_MODEL
                ))
                continue
            except Exception as e:
                last_err = e

        # If both fail, record as low score
        ranked.append(Ranked(
            paper=p,
            score=0.0,
            reason=f"LLM call failed: {type(last_err).__name__}" if last_err else "LLM call failed",
            takeaway="(No summary due to LLM failure)",
            provider="none",
            model="none"
        ))

    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked

"""Optional OpenAI analysis — enable by setting OPENAI_API_KEY in .env."""

from __future__ import annotations

import json
import re
from typing import Any

from app.config import settings
from app.models.schemas import CitationStyle, ReferenceEntry, ReferenceIssue, Severity


SYSTEM_PROMPT = """You are an academic reference checker. Given a numbered list of reference lines and a target style
(APA_7, MLA_9, CHICAGO, GB_T_7714), return STRICT JSON only:
{
  "entries": [
    {
      "line_index": 0,
      "issues": [
        {
          "severity": "error|warning|info",
          "message": "short Chinese message",
          "suggested_fix": "full corrected line or null",
          "rule_hint": "one sentence teaching note or null"
        }
      ]
    }
  ],
  "summary": "one paragraph in Chinese"
}
Rules: severity must be lowercase. If no issues for a line, issues can be []. Keep messages concise."""


async def enhance_with_llm(
    style: CitationStyle,
    entries: list[ReferenceEntry],
) -> tuple[list[ReferenceEntry], str, bool] | None:
    if not settings.openai_api_key:
        return None

    try:
        from openai import AsyncOpenAI
    except ImportError:
        return None

    client = AsyncOpenAI(api_key=settings.openai_api_key)
    lines_payload = [{"line_index": e.line_index, "text": e.raw_text} for e in entries]
    user = json.dumps(
        {"style": style.value, "references": lines_payload},
        ensure_ascii=False,
    )

    resp = await client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        temperature=0.2,
    )
    raw = (resp.choices[0].message.content or "").strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    data: dict[str, Any] = json.loads(raw)

    merged: dict[int, ReferenceEntry] = {e.line_index: e.model_copy(deep=True) for e in entries}
    for block in data.get("entries", []):
        idx = int(block["line_index"])
        if idx not in merged:
            continue
        llm_issues: list[ReferenceIssue] = []
        for it in block.get("issues", []):
            sev = str(it.get("severity", "info")).lower()
            severity = Severity.ERROR if sev == "error" else Severity.WARNING if sev == "warning" else Severity.INFO
            llm_issues.append(
                ReferenceIssue(
                    line_index=idx,
                    severity=severity,
                    message=str(it.get("message", "")),
                    suggested_fix=it.get("suggested_fix"),
                    rule_hint=it.get("rule_hint"),
                )
            )
        merged[idx].issues = _dedupe_issues(merged[idx].issues + llm_issues)
    summary = str(data.get("summary", "")).strip() or "分析完成。"
    return list(merged.values()), summary, True


def _dedupe_issues(issues: list[ReferenceIssue]) -> list[ReferenceIssue]:
    seen: set[tuple] = set()
    out: list[ReferenceIssue] = []
    for i in issues:
        key = (i.message, i.severity)
        if key in seen:
            continue
        seen.add(key)
        out.append(i)
    return out

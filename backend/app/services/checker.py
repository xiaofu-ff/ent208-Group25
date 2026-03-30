from __future__ import annotations

from app.models.schemas import AnalyzeResponse, CitationStyle, ReferenceEntry
from app.services.llm import enhance_with_llm
from app.services.parsers import split_reference_lines
from app.services.styles import STYLE_CHECKERS


def _summary_line_count(entries: list[ReferenceEntry]) -> str:
    n = len(entries)
    err = sum(1 for e in entries for i in e.issues if i.severity.value == "error")
    warn = sum(1 for e in entries for i in e.issues if i.severity.value == "warning")
    return f"共解析 {n} 条引用；规则引擎检出约 {err} 处错误级、{warn} 处提醒（未含可选 AI 增强）。"


async def analyze_references(text: str, style: CitationStyle) -> AnalyzeResponse:
    pairs = split_reference_lines(text)
    checker = STYLE_CHECKERS[style.value]
    entries: list[ReferenceEntry] = []
    for line_index, raw in pairs:
        issues = checker(line_index, raw)
        entries.append(ReferenceEntry(line_index=line_index, raw_text=raw, issues=issues))

    summary = _summary_line_count(entries)
    used_llm = False

    enhanced = await enhance_with_llm(style, entries)
    if enhanced:
        entries, summary, used_llm = enhanced

    return AnalyzeResponse(style=style, entries=entries, summary=summary, used_llm=used_llm)

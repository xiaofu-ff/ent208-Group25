"""科研写作工作台：可追溯写作、综述矩阵抽取、审稿/导师模式（依赖 OpenAI）。"""

from __future__ import annotations

import csv
import io
import json
import re
from typing import Any, Literal, cast

from fastapi import HTTPException

from app.config import settings
from app.models.schemas import Severity
from app.models.workbench import (
    MatrixExtractRequest,
    MatrixExtractResponse,
    MatrixRow,
    ManuscriptReviewRequest,
    ManuscriptReviewResponse,
    PassageAnchor,
    ReviewFinding,
    SupportLink,
    TraceableWritingRequest,
    TraceableWritingResponse,
)


def _strip_code_fence(raw: str) -> str:
    t = raw.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.I)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _norm_support_strength(s: str) -> str:
    v = (s or "").lower().strip()
    if v in ("direct", "indirect", "weak", "none"):
        return v
    return "weak"


def _norm_severity(s: str) -> Severity:
    v = (s or "").lower().strip()
    if v == "error":
        return Severity.ERROR
    if v == "warning":
        return Severity.WARNING
    return Severity.INFO


def _model_error_detail(exc: Exception) -> str:
    msg = str(exc).strip() or type(exc).__name__
    if len(msg) > 600:
        msg = msg[:600] + "…"
    return (
        "调用语言模型失败（常见于网络不可达、密钥无效、或当前地区无法访问 OpenAI API）。"
        f" 可稍后重试或检查服务器出站网络与 OPENAI_API_KEY。简要信息：{msg}"
    )


async def _chat_json(system: str, user: str) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=400,
            detail="该功能需要配置 OPENAI_API_KEY。请在服务器 backend/.env 中设置后重启服务。",
        )
    try:
        from openai import AsyncOpenAI
    except ImportError as e:
        raise HTTPException(status_code=500, detail="缺少 openai 依赖") from e

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key)
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        raw = (resp.choices[0].message.content or "").strip()
        raw = _strip_code_fence(raw)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=422, detail=f"模型返回非合法 JSON: {e!s}") from e
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=_model_error_detail(e)) from e


TRACE_SYSTEM = """你是中文学术写作助手。用户会提供一段需要核查的写作 passge，以及若干条带编号的证据材料（仅用户提供的文本，不做联网检索）。
你必须输出且仅输出一个 JSON 对象（不要 markdown），结构如下：
{
  "anchors": [
    {
      "clause_index": 0,
      "clause_text": "从 passage 中拆分出的短句或小句，便于核对",
      "support_links": [{"source_id": 0, "support_strength": "direct|indirect|weak|none"}],
      "notes": "可选，对该句与证据关系的简短中文说明，可为 null"
    }
  ],
  "gaps": ["列出 passage 中可能缺乏证据支撑或需要补引用的要点，中文短句数组"],
  "contrary_notes": ["若证据之间存在张力或需谨慎外推之处，用中文列出；若无则 []"],
  "summary": "一段中文总评"
}
规则：
- source_id 必须来自用户提供的证据 id，不要编造新 id。
- support_strength 只能取 direct、indirect、weak、none 四种小写英文。
- anchors 覆盖 passage 的主要句子或小句，clause_index 从 0 递增。
- 保持客观，不要编造未在证据中出现的具体数据或结论。"""


async def traceable_writing(req: TraceableWritingRequest) -> TraceableWritingResponse:
    payload = {
        "passage": req.passage,
        "evidence_sources": [{"id": s.id, "text": s.text} for s in req.evidence_sources],
    }
    user = json.dumps(payload, ensure_ascii=False)
    data = await _chat_json(TRACE_SYSTEM, user)

    anchors_raw = data.get("anchors") or []
    anchors: list[PassageAnchor] = []
    valid_ids = {s.id for s in req.evidence_sources}
    for block in anchors_raw:
        if not isinstance(block, dict):
            continue
        links: list[SupportLink] = []
        for lk in block.get("support_links") or []:
            if not isinstance(lk, dict):
                continue
            sid = int(lk.get("source_id", -1))
            if sid not in valid_ids:
                continue
            st = _norm_support_strength(str(lk.get("support_strength", "weak")))
            links.append(
                SupportLink(
                    source_id=sid,
                    support_strength=cast(Literal["direct", "indirect", "weak", "none"], st),
                )
            )
        anchors.append(
            PassageAnchor(
                clause_index=int(block.get("clause_index", len(anchors))),
                clause_text=str(block.get("clause_text", ""))[:4000],
                support_links=links,
                notes=block.get("notes"),
            )
        )

    gaps = [str(x) for x in (data.get("gaps") or []) if str(x).strip()]
    contrary = [str(x) for x in (data.get("contrary_notes") or []) if str(x).strip()]
    summary = str(data.get("summary", "")).strip() or "分析完成。"

    return TraceableWritingResponse(
        anchors=anchors,
        gaps=gaps,
        contrary_notes=contrary,
        summary=summary,
        used_llm=True,
    )


MATRIX_SYSTEM = """你是中文科研助理。用户会提供多篇文献的片段（每条有 label 与 text）。请抽取综述矩阵字段，只输出 JSON（不要 markdown）：
{
  "rows": [
    {
      "label": "与输入 label 一致或最接近",
      "authors": "作者信息，无法判断则 null",
      "year": "年份或 null",
      "country_or_region": "国家/地区或 null",
      "study_design": "研究设计，如 RCT/队列/横断面等，无法判断则 null",
      "sample_size": "样本量或范围，无法判断则 null",
      "core_variables": "核心变量/暴露/结局，简短中文",
      "measurement": "测量方法或工具，简短中文或 null",
      "main_finding": "主要结论一句中文",
      "limitations": "局限性一句中文或 null",
      "citation_anchor": "如何从用户原文定位该条，一句中文"
    }
  ],
  "summary": "对整批文献的一句话中文概括"
}
规则：rows 数量应与文献条数一致、顺序一致；不得编造用户 text 中不存在的具体数值；不确定用 null。"""


def _matrix_rows_to_csv(rows: list[MatrixRow]) -> str:
    if not rows:
        return ""
    buf = io.StringIO()
    fieldnames = list(MatrixRow.model_fields.keys())
    w = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow({k: (v if v is not None else "") for k, v in r.model_dump().items()})
    return buf.getvalue()


async def matrix_extract(req: MatrixExtractRequest) -> MatrixExtractResponse:
    payload = {"documents": [d.model_dump() for d in req.documents]}
    user = json.dumps(payload, ensure_ascii=False)
    data = await _chat_json(MATRIX_SYSTEM, user)

    rows_out: list[MatrixRow] = []
    for block in data.get("rows") or []:
        if not isinstance(block, dict):
            continue
        rows_out.append(
            MatrixRow(
                label=str(block.get("label", ""))[:200],
                authors=block.get("authors"),
                year=block.get("year"),
                country_or_region=block.get("country_or_region"),
                study_design=block.get("study_design"),
                sample_size=block.get("sample_size"),
                core_variables=block.get("core_variables"),
                measurement=block.get("measurement"),
                main_finding=block.get("main_finding"),
                limitations=block.get("limitations"),
                citation_anchor=block.get("citation_anchor"),
            )
        )

    summary = str(data.get("summary", "")).strip() or "抽取完成。"
    csv_content = _matrix_rows_to_csv(rows_out) if req.include_csv else None

    return MatrixExtractResponse(
        rows=rows_out,
        summary=summary,
        used_llm=True,
        csv_content=csv_content,
    )


REVIEW_SYSTEM = """你是中文学术审稿与导师角色。用户会提供论文/综述正文片段以及参考文献列表（均为用户粘贴，不做联网核对）。
请输出且仅输出 JSON（不要 markdown）：
{
  "findings": [
    {
      "severity": "error|warning|info",
      "category": "如 证据支撑、引用一致性、结构逻辑、方法描述、统计表述",
      "paragraph_hint": "可定位到文中位置的中文提示，可为 null",
      "message": "问题描述",
      "suggestion": "可操作的修改建议，可为 null"
    }
  ],
  "summary": "整体评价与优先修改顺序（中文）"
}
规则：
- 不要声称已核对 DOI/期刊官网；仅基于用户文本指出不一致、跳跃、可能过度外推等。
- severity 必须小写英文三选一。
- findings 数量建议 5~20 条，优先高价值问题。"""


async def manuscript_review(req: ManuscriptReviewRequest) -> ManuscriptReviewResponse:
    payload = {"body_text": req.body_text, "references_text": req.references_text}
    user = json.dumps(payload, ensure_ascii=False)
    data = await _chat_json(REVIEW_SYSTEM, user)

    findings: list[ReviewFinding] = []
    for block in data.get("findings") or []:
        if not isinstance(block, dict):
            continue
        findings.append(
            ReviewFinding(
                severity=_norm_severity(str(block.get("severity", "info"))),
                category=str(block.get("category", "综合"))[:120],
                paragraph_hint=block.get("paragraph_hint"),
                message=str(block.get("message", ""))[:4000],
                suggestion=block.get("suggestion"),
            )
        )

    summary = str(data.get("summary", "")).strip() or "审阅完成。"

    return ManuscriptReviewResponse(findings=findings, summary=summary, used_llm=True)

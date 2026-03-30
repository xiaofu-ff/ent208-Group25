"""Heuristic rules per citation style — extend with more patterns as the project evolves."""

from __future__ import annotations

import re

from app.models.schemas import ReferenceIssue, Severity


def _issue(
    line_index: int,
    severity: Severity,
    message: str,
    suggested_fix: str | None = None,
    rule_hint: str | None = None,
    span_start: int | None = None,
    span_end: int | None = None,
) -> ReferenceIssue:
    return ReferenceIssue(
        line_index=line_index,
        severity=severity,
        message=message,
        suggested_fix=suggested_fix,
        rule_hint=rule_hint,
        span_start=span_start,
        span_end=span_end,
    )


def check_apa7(line_index: int, text: str) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    t = text.strip()
    if not t:
        return issues

    # Year in parentheses e.g. (2020)
    if not re.search(r"\(\s*19\d{2}|20\d{2}\s*\)", t):
        issues.append(
            _issue(
                line_index,
                Severity.WARNING,
                "未检测到括号内的出版年份，APA 通常要求 (YYYY)。",
                rule_hint="APA 第 7 版：期刊/书籍条目需含出版年，多为括号形式。",
            )
        )

    if re.search(r"\bdoi:\s*", t, re.I) and not re.search(r"https?://doi\.org/", t, re.I):
        issues.append(
            _issue(
                line_index,
                Severity.INFO,
                "DOI 建议写为 https://doi.org/10.xxxx 形式。",
                suggested_fix=re.sub(r"\bdoi:\s*([^\s]+)", r"https://doi.org/\1", t, flags=re.I),
                rule_hint="APA 7：优先使用可点击的 DOI URL。",
            )
        )

    if "et al" in t and "et al." not in t:
        issues.append(
            _issue(
                line_index,
                Severity.ERROR,
                "英文作者缩写应写作 “et al.”（含句点）。",
                suggested_fix=t.replace("et al", "et al."),
                rule_hint="APA：三人以上用 FirstAuthor et al.。",
            )
        )

    return issues


def check_mla9(line_index: int, text: str) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    t = text.strip()
    if not t:
        return issues

    if not re.search(r"\d{4}", t):
        issues.append(
            _issue(
                line_index,
                Severity.WARNING,
                "未找到四位数年份，MLA Works Cited 通常需要年份。",
                rule_hint="MLA 第 9 版：多数条目含出版或访问年份。",
            )
        )

    if "http" in t.lower() and "Accessed" not in t and "accessed" not in t:
        issues.append(
            _issue(
                line_index,
                Severity.INFO,
                "含 URL 的条目可考虑注明访问日期（Accessed day month year）。",
                rule_hint="MLA：网页类资源常要求访问日期。",
            )
        )

    return issues


def check_chicago(line_index: int, text: str) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    t = text.strip()
    if not t:
        return issues

    if not re.search(r"\d{4}", t):
        issues.append(
            _issue(
                line_index,
                Severity.WARNING,
                "未检测到出版年份。",
                rule_hint="Chicago 作者-日期体需年份；注释体也需完整书目信息。",
            )
        )
    return issues


def check_gb7714(line_index: int, text: str) -> list[ReferenceIssue]:
    issues: list[ReferenceIssue] = []
    t = text.strip()
    if not t:
        return issues

    if not re.search(r"\[[A-Z]\]", t):
        issues.append(
            _issue(
                line_index,
                Severity.INFO,
                "GB/T 7714 文献类型标识如 [J]、[M]、[D] 等，若缺失请核对类型。",
                rule_hint="国标：期刊[J]、专著[M]、学位论文[D] 等。",
            )
        )

    if re.search(r"[，,]\s*$", t):
        issues.append(
            _issue(
                line_index,
                Severity.WARNING,
                "条目末尾不应以逗号结尾。",
                rule_hint="中文标点规范：句末用句号。",
            )
        )

    if "doi" in t.lower() and "DOI:" not in t and "doi:" not in t:
        issues.append(
            _issue(
                line_index,
                Severity.INFO,
                "DOI 建议统一为 “DOI:” 或 “doi:” 前缀格式（按学校要求）。",
            )
        )

    return issues


STYLE_CHECKERS = {
    "APA_7": check_apa7,
    "MLA_9": check_mla9,
    "CHICAGO": check_chicago,
    "GB_T_7714": check_gb7714,
}

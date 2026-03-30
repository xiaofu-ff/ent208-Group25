from enum import Enum

from pydantic import BaseModel, Field


class CitationStyle(str, Enum):
    APA_7 = "APA_7"
    MLA_9 = "MLA_9"
    CHICAGO = "CHICAGO"
    GB_T_7714 = "GB_T_7714"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ReferenceIssue(BaseModel):
    line_index: int = Field(..., description="0-based index of the reference line in the input")
    severity: Severity
    message: str
    span_start: int | None = Field(None, description="Character offset in the line")
    span_end: int | None = None
    suggested_fix: str | None = None
    rule_hint: str | None = Field(None, description="Short explanation for learning")


class ReferenceEntry(BaseModel):
    line_index: int
    raw_text: str
    issues: list[ReferenceIssue] = Field(default_factory=list)


class AnalyzeResponse(BaseModel):
    style: CitationStyle
    entries: list[ReferenceEntry]
    summary: str
    used_llm: bool = False


class AnalyzeRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Reference list as plain text (one entry per line or paragraph)")
    style: CitationStyle = CitationStyle.APA_7


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"

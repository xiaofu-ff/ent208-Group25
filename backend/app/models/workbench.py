"""请求/响应模型：科研写作工作台（可追溯写作、综述矩阵、审稿/导师）。"""



from typing import Literal



from pydantic import BaseModel, Field



from app.models.schemas import Severity



DISCLAIMER_ZH = (

    "本结果仅基于您提交的文本由模型推断生成，不构成学术、临床或法律意见；"

    "涉及证据强度、研究设计等结论请务必由具备资质的研究者人工复核。"

)





class EvidenceSource(BaseModel):

    id: int = Field(..., ge=0, description="证据段落编号，与模型返回中的 source_id 对应")

    text: str = Field(..., min_length=1, max_length=20000, description="该文献的摘要、节选或笔记")





class TraceableWritingRequest(BaseModel):

    passage: str = Field(

        ...,

        min_length=10,

        max_length=50000,

        description="需要绑定证据的写作段落（可含多句）",

    )

    evidence_sources: list[EvidenceSource] = Field(

        ...,

        min_length=1,

        max_length=30,

        description="用户提供的证据材料列表（无需联网检索）",

    )





class SupportLink(BaseModel):

    source_id: int = Field(..., ge=0)

    support_strength: Literal["direct", "indirect", "weak", "none"] = Field(

        ...,

        description="direct=直接支持; indirect=间接; weak=弱; none=不足以支持",

    )





class PassageAnchor(BaseModel):

    clause_index: int = Field(..., ge=0)

    clause_text: str = Field(..., max_length=4000)

    support_links: list[SupportLink] = Field(default_factory=list)

    notes: str | None = Field(None, max_length=2000)





class TraceableWritingResponse(BaseModel):

    anchors: list[PassageAnchor]

    gaps: list[str] = Field(default_factory=list, description="证据链缺口提示")

    contrary_notes: list[str] = Field(default_factory=list, description="相反证据或需谨慎之处")

    summary: str = ""

    used_llm: bool = True

    disclaimer: str = DISCLAIMER_ZH





class MatrixDocument(BaseModel):

    label: str = Field(..., max_length=200, description="矩阵行标识，如 Smith2020、文献1")

    text: str = Field(

        ...,

        min_length=20,

        max_length=25000,

        description="该篇的摘要、方法节选或全文片段",

    )





class MatrixExtractRequest(BaseModel):

    documents: list[MatrixDocument] = Field(..., min_length=1, max_length=40)

    include_csv: bool = Field(False, description="为 True 时在响应中附带 CSV 文本")





class MatrixRow(BaseModel):

    label: str = ""

    authors: str | None = None

    year: str | None = None

    country_or_region: str | None = None

    study_design: str | None = None

    sample_size: str | None = None

    core_variables: str | None = None

    measurement: str | None = None

    main_finding: str | None = None

    limitations: str | None = None

    citation_anchor: str | None = Field(None, description="便于回溯到用户原文的定位说明")





class MatrixExtractResponse(BaseModel):

    rows: list[MatrixRow]

    summary: str = ""

    used_llm: bool = True

    csv_content: str | None = Field(None, description="当请求 include_csv 时返回")

    disclaimer: str = DISCLAIMER_ZH





class ManuscriptReviewRequest(BaseModel):

    body_text: str = Field(..., min_length=50, max_length=120000, description="正文或综述草稿")

    references_text: str = Field(

        ...,

        min_length=10,

        max_length=80000,

        description="参考文献列表纯文本",

    )





class ReviewFinding(BaseModel):

    severity: Severity

    category: str = Field(..., max_length=120, description="如 证据支撑、引用一致性、结构")

    paragraph_hint: str | None = Field(None, max_length=500, description="可定位到段落/小节的中文提示")

    message: str = Field(..., max_length=4000)

    suggestion: str | None = Field(None, max_length=4000)





class ManuscriptReviewResponse(BaseModel):

    findings: list[ReviewFinding]

    summary: str = ""

    used_llm: bool = True

    disclaimer: str = DISCLAIMER_ZH



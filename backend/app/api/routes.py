from fastapi import APIRouter, File, HTTPException, UploadFile

from app.models.schemas import AnalyzeRequest, AnalyzeResponse, CitationStyle, HealthResponse
from app.models.workbench import (
    ManuscriptReviewRequest,
    ManuscriptReviewResponse,
    MatrixExtractRequest,
    MatrixExtractResponse,
    TraceableWritingRequest,
    TraceableWritingResponse,
)
from app.services.checker import analyze_references
from app.services.parsers import extract_text_from_docx, extract_text_from_pdf
from app.services.workbench import manuscript_review, matrix_extract, traceable_writing

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.post("/references/analyze", response_model=AnalyzeResponse)
async def analyze_body(req: AnalyzeRequest) -> AnalyzeResponse:
    return await analyze_references(req.text, req.style)


@router.post("/references/analyze-upload", response_model=AnalyzeResponse)
async def analyze_upload(
    file: UploadFile = File(...),
    style: CitationStyle = CitationStyle.APA_7,
) -> AnalyzeResponse:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="空文件")

    name = (file.filename or "").lower()
    try:
        if name.endswith(".docx"):
            text = extract_text_from_docx(data)
        elif name.endswith(".pdf"):
            text = extract_text_from_pdf(data)
        else:
            raise HTTPException(
                status_code=400,
                detail="仅支持 .docx 或 .pdf",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"无法解析文件: {e!s}") from e

    if not text.strip():
        raise HTTPException(status_code=422, detail="未能从文件中提取到文本")

    return await analyze_references(text, style)


@router.post("/workbench/trace", response_model=TraceableWritingResponse)
async def workbench_trace(req: TraceableWritingRequest) -> TraceableWritingResponse:
    """可追溯写作：将段落与用户自备证据材料做对齐分析（需 OPENAI_API_KEY）。"""
    return await traceable_writing(req)


@router.post("/workbench/matrix/extract", response_model=MatrixExtractResponse)
async def workbench_matrix_extract(req: MatrixExtractRequest) -> MatrixExtractResponse:
    """综述矩阵：从多篇文献片段抽取结构化字段（需 OPENAI_API_KEY）。"""
    return await matrix_extract(req)


@router.post("/workbench/review/manuscript", response_model=ManuscriptReviewResponse)
async def workbench_review_manuscript(req: ManuscriptReviewRequest) -> ManuscriptReviewResponse:
    """审稿/导师模式：基于正文与参考文献列表给出结构化审阅意见（需 OPENAI_API_KEY）。"""
    return await manuscript_review(req)

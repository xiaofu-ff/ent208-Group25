import re


def split_reference_lines(text: str) -> list[tuple[int, str]]:
    """Split pasted text into logical reference lines (numbered or blank-separated blocks)."""
    text = text.strip()
    if not text:
        return []

    # Split on lines that look like new reference starts: [1], 1., (1), etc.
    lines = text.splitlines()
    merged: list[str] = []
    buf: list[str] = []

    start_pattern = re.compile(
        r"^\s*(?:\[\d+\]|\(\d+\)|\d+[\.\)、．]|（\d+）)\s*"
    )

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if buf:
                merged.append(" ".join(buf))
                buf = []
            continue
        if buf and start_pattern.match(stripped):
            merged.append(" ".join(buf))
            buf = [stripped]
        else:
            buf.append(stripped)

    if buf:
        merged.append(" ".join(buf))

    if len(merged) <= 1 and "\n\n" in text:
        parts = re.split(r"\n\s*\n+", text)
        merged = [p.strip().replace("\n", " ") for p in parts if p.strip()]

    return [(i, block) for i, block in enumerate(merged)]


def extract_text_from_docx(data: bytes) -> str:
    from io import BytesIO

    from docx import Document

    doc = Document(BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_text_from_pdf(data: bytes) -> str:
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t)
    return "\n".join(parts)

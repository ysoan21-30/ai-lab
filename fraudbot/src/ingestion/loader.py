"""Load and chunk source documents (fraud reports, policy docs, transaction
notes, etc.) before they're embedded and stored in ChromaDB.

Supports PDF (.pdf) and plain text (.txt) files.
"""

from pathlib import Path

from pypdf import PdfReader

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
SUPPORTED_EXTENSIONS = {".pdf", ".txt"}


def _extract_pdf_text(path: Path) -> str:
    reader = PdfReader(str(path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _extract_txt_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def chunk_document(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split `text` into overlapping character-based chunks.

    Consecutive chunks overlap by `overlap` characters so context isn't lost
    at chunk boundaries.
    """
    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    text = text.strip()
    if not text:
        return []

    step = chunk_size - overlap
    chunks = []
    start = 0
    length = len(text)
    while start < length:
        end = start + chunk_size
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= length:
            break
        start += step
    return chunks


def load_documents(
    source_dir: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[dict]:
    """Load PDF and .txt files from `source_dir` and split them into chunks.

    Returns a flat list of {"text": chunk, "metadata": {"source": filename,
    "chunk_index": i}} dicts, ready to be embedded and stored.
    """
    source_path = Path(source_dir)
    if not source_path.is_dir():
        raise FileNotFoundError(f"source_dir not found: {source_path}")

    documents = []
    for file_path in sorted(source_path.iterdir()):
        if not file_path.is_file():
            continue

        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            text = _extract_pdf_text(file_path)
        elif suffix == ".txt":
            text = _extract_txt_text(file_path)
        else:
            continue

        chunks = chunk_document(text, chunk_size=chunk_size, overlap=overlap)
        for i, chunk in enumerate(chunks):
            documents.append(
                {
                    "text": chunk,
                    "metadata": {"source": file_path.name, "chunk_index": i},
                }
            )

    return documents

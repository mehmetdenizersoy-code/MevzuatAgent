"""Mevzuat PDF'lerini parçalayıp yerel arama indeksi oluşturur.

Arama internet bağlantısı olmadan BM25 ile yapılır. Parçalar kaynak ve sayfa
bilgisini korur.
"""

from dataclasses import dataclass
import json
from pathlib import Path
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from rank_bm25 import BM25Okapi


@dataclass(frozen=True)
class RagChunk:
    """Mevzuat metninden bir parça ve kaynak bilgisi."""

    text: str
    source: str
    page: int
    start_index: int


@dataclass(frozen=True)
class RagBuildResult:
    """İndeks oluşturma sonucu."""

    chunks: tuple[RagChunk, ...]
    index_path: Path
    errors: tuple[str, ...]


@dataclass(frozen=True)
class RagSearchResult:
    """Bulunan parça ve arama puanı."""

    chunk: RagChunk
    score: float


def build_mevzuat_rag(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    chunk_size: int = 1200,
    chunk_overlap: int = 200,
) -> RagBuildResult:
    """PDF metnini parçalayıp yerel indekse yazar."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap must be non-negative and smaller than chunk_size")

    source_dir = Path(input_dir)
    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    index_path = target_dir / "chunks.jsonl"
    errors: list[str] = []
    chunks: list[RagChunk] = []
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        add_start_index=True,
    )

    if not source_dir.is_dir():
        return RagBuildResult((), index_path, (f"{source_dir}: directory not found",))

    documents = sorted(
        path
        for path in source_dir.iterdir()
        if path.is_file() and _is_pdf(path)
    )
    if not documents:
        errors.append(f"{source_dir}: no PDF documents found")

    for path in documents:
        try:
            reader = PdfReader(path)
            for page_number, page in enumerate(reader.pages, start=1):
                text = page.extract_text() or ""
                for document in splitter.create_documents([text]):
                    chunk_text = document.page_content.strip()
                    if chunk_text:
                        chunks.append(
                            RagChunk(
                                text=chunk_text,
                                source=path.name,
                                page=page_number,
                                start_index=document.metadata["start_index"],
                            )
                        )
        except (OSError, PdfReadError, ValueError) as exc:
            errors.append(f"{path.name}: PDF extraction failed ({exc.__class__.__name__})")

    with index_path.open("w", encoding="utf-8") as index_file:
        for chunk in chunks:
            index_file.write(json.dumps(chunk.__dict__, ensure_ascii=False) + "\n")

    manifest_path = target_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "retrieval": "BM25 lexical",
                "chunk_size": chunk_size,
                "chunk_overlap": chunk_overlap,
                "documents": [path.name for path in documents],
                "chunk_count": len(chunks),
                "errors": errors,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return RagBuildResult(tuple(chunks), index_path, tuple(errors))


def search_mevzuat_rag(
    query: str,
    index_path: str | Path = "data/legislation/rag/chunks.jsonl",
    *,
    top_k: int = 5,
) -> tuple[RagSearchResult, ...]:
    """Sorguyla en çok eşleşen parçaları bulur."""
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")
    terms = _tokenize(query)
    if not terms:
        return ()

    path = Path(index_path)
    chunks = tuple(_read_chunks(path))
    if not chunks:
        return ()

    scores = BM25Okapi([_tokenize(chunk.text) for chunk in chunks]).get_scores(terms)
    query_terms = set(terms)
    matches = [
        RagSearchResult(chunk=chunk, score=float(score))
        for chunk, score in zip(chunks, scores, strict=True)
        if query_terms.intersection(_tokenize(chunk.text))
    ]
    return tuple(sorted(matches, key=lambda match: match.score, reverse=True)[:top_k])


def _read_chunks(index_path: Path):
    with index_path.open(encoding="utf-8") as index_file:
        for line_number, line in enumerate(index_file, start=1):
            try:
                record = json.loads(line)
                yield RagChunk(
                    text=record["text"],
                    source=record["source"],
                    page=record["page"],
                    start_index=record["start_index"],
                )
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                raise ValueError(
                    f"{index_path}: invalid chunk record on line {line_number}"
                ) from exc


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\w+", text.casefold(), flags=re.UNICODE)


def _is_pdf(path: Path) -> bool:
    if path.suffix.casefold() == ".pdf":
        return True
    try:
        with path.open("rb") as file:
            return file.read(5) == b"%PDF-"
    except OSError:
        return False

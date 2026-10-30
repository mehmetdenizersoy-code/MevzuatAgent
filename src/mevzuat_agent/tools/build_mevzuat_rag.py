"""Mevzuat PDF'lerini parçalayıp yerel arama indeksi oluşturur.

Arama internet bağlantısı olmadan BM25 ile yapılır. Parçalar kaynak ve sayfa
bilgisini korur.
"""

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import importlib.util
import json
from pathlib import Path
import re

from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from rank_bm25 import BM25Okapi

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_RRF_K = 60


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
    embedding_model: str | None = DEFAULT_EMBEDDING_MODEL,
) -> RagBuildResult:
    """PDF metnini parçalayıp BM25 ve varsa embedding indekslerine yazar."""
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

    embedding_path = _embedding_path(index_path)
    if embedding_model is None:
        embedding_path.unlink(missing_ok=True)
        retrieval = "BM25 lexical"
        indexed_embedding_model = None
    elif importlib.util.find_spec("sentence_transformers") is None:
        embedding_path.unlink(missing_ok=True)
        retrieval = "BM25 lexical (install the embeddings extra for hybrid search)"
        indexed_embedding_model = None
    else:
        vectors = _encode_texts([chunk.text for chunk in chunks], embedding_model)
        embedding_path.write_text(
            json.dumps(
                {
                    "model": embedding_model,
                    "chunks_sha256": _chunks_sha256(chunks),
                    "vectors": vectors,
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )
        retrieval = "BM25 + multilingual sentence embeddings (reciprocal rank fusion)"
        indexed_embedding_model = embedding_model

    manifest_path = target_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "retrieval": retrieval,
                "embedding_model": indexed_embedding_model,
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

    path = Path(index_path)
    chunks = tuple(_read_chunks(path))
    if not chunks:
        return ()

    lexical_matches: list[tuple[int, float]] = []
    lexical_ranks: dict[int, int] = {}
    if terms:
        scores = BM25Okapi([_tokenize(chunk.text) for chunk in chunks]).get_scores(terms)
        query_terms = set(terms)
        lexical_matches = sorted(
            (
                (index, float(score))
                for index, (chunk, score) in enumerate(zip(chunks, scores, strict=True))
                if query_terms.intersection(_tokenize(chunk.text))
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        lexical_ranks = {
            chunk_index: rank
            for rank, (chunk_index, _) in enumerate(lexical_matches)
        }

    embedding_path = _embedding_path(path)
    if not embedding_path.is_file():
        if not terms:
            return ()
        return tuple(
            RagSearchResult(chunks[index], score)
            for index, score in lexical_matches[:top_k]
        )

    embedding_index = json.loads(embedding_path.read_text(encoding="utf-8"))
    if (
        embedding_index.get("chunks_sha256") != _chunks_sha256(chunks)
        or not isinstance(embedding_index.get("model"), str)
        or not isinstance(embedding_index.get("vectors"), list)
        or len(embedding_index["vectors"]) != len(chunks)
    ):
        raise ValueError(f"{embedding_path}: embedding index does not match the chunk index")

    query_vector = _encode_texts([query], embedding_index["model"])[0]
    vectors = embedding_index["vectors"]
    if not query_vector or any(
        not isinstance(vector, list) or len(vector) != len(query_vector)
        for vector in vectors
    ):
        raise ValueError(f"{embedding_path}: invalid embedding vector dimensions")

    semantic_matches = sorted(
        (
            (index, sum(float(left) * float(right) for left, right in zip(
                query_vector, vector, strict=True
            )))
            for index, vector in enumerate(vectors)
        ),
        key=lambda item: item[1],
        reverse=True,
    )
    semantic_ranks = {
        chunk_index: rank
        for rank, (chunk_index, _) in enumerate(semantic_matches)
    }
    fused_scores = {
        index: 1 / (_RRF_K + rank)
        for index, rank in lexical_ranks.items()
    }
    for index, rank in semantic_ranks.items():
        fused_scores[index] = fused_scores.get(index, 0) + 1 / (_RRF_K + rank)

    return tuple(
        RagSearchResult(chunks[index], score)
        for index, score in sorted(
            fused_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )[:top_k]
    )


@lru_cache(maxsize=2)
def _load_embedding_model(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Embedding index requires sentence-transformers; install the "
            "'embeddings' extra."
        ) from exc
    return SentenceTransformer(model_name)


def _encode_texts(texts: list[str], model_name: str) -> list[list[float]]:
    vectors = _load_embedding_model(model_name).encode(
        texts,
        normalize_embeddings=True,
    )
    return [[float(value) for value in vector] for vector in vectors]


def _embedding_path(index_path: Path) -> Path:
    return index_path.with_name(f"{index_path.stem}.embeddings.json")


def _chunks_sha256(chunks: tuple[RagChunk, ...] | list[RagChunk]) -> str:
    serialized = json.dumps(
        [chunk.__dict__ for chunk in chunks],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


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

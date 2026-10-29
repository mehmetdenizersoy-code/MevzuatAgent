"""Kod taraması için yaklaşık token ve süre hesabı yapar.

Kaynak dosyaları ve mevzuat indeksini inceler. Kod çalıştırmaz veya değiştirmez.
"""

from dataclasses import dataclass
from math import ceil
from pathlib import Path, PurePosixPath
import json
import subprocess
from urllib.error import URLError
from urllib.request import Request, urlopen

from mevzuat_agent.tools.build_mevzuat_rag import search_mevzuat_rag

DEFAULT_MODEL = "llama3.2:1b"
DEFAULT_RAG_INDEX = Path("data/legislation/rag/chunks.jsonl")
DEFAULT_OLLAMA_URL = "http://localhost:11434"
SCAN_OUTPUT_TOKENS_PER_FILE = 700
SOURCE_EXTENSIONS = frozenset(
    {
        ".c",
        ".cc",
        ".cpp",
        ".cs",
        ".go",
        ".h",
        ".hpp",
        ".java",
        ".js",
        ".jsx",
        ".kt",
        ".php",
        ".py",
        ".rb",
        ".rs",
        ".scala",
        ".sh",
        ".swift",
        ".ts",
        ".tsx",
        ".vb",
    }
)
IGNORED_DIRECTORIES = frozenset(
    {
        ".git",
        ".idea",
        ".venv",
        "bin",
        "build",
        "dist",
        "node_modules",
        "obj",
        "packages",
        "target",
        "vendor",
    }
)


@dataclass(frozen=True)
class RepositoryScanEstimate:
    """Bir depo için tarama tahmini."""

    repository: str
    branch_commit: str
    source_file_count: int
    skipped_file_count: int
    retrieved_chunk_count: int
    estimated_input_tokens: int
    estimated_output_tokens: int
    estimated_total_tokens: int
    estimated_seconds: int


@dataclass(frozen=True)
class ScanCostEstimate:
    """Tahmin ve karşılaşılan hatalar."""

    model: str
    tokens_per_second_assumption: int
    repositories: tuple[RepositoryScanEstimate, ...]
    errors: tuple[str, ...]

    @property
    def estimated_total_tokens(self) -> int:
        """Toplam token tahminini döndürür."""
        return sum(repo.estimated_total_tokens for repo in self.repositories)

    @property
    def estimated_seconds(self) -> int:
        """Toplam süre tahminini saniye olarak döndürür."""
        return sum(repo.estimated_seconds for repo in self.repositories)


@dataclass(frozen=True)
class ModelEstimate:
    """Bir modelin ölçülen hızına göre tarama süresi tahmini."""

    model: str
    tokens_per_second: float
    estimated_total_tokens: int
    estimated_seconds: int


@dataclass(frozen=True)
class ModelPoolEstimate:
    """Kurulu modellerin karşılaştırma sonucu."""

    scan: ScanCostEstimate
    models: tuple[ModelEstimate, ...]
    recommended_model: str | None
    errors: tuple[str, ...]


def estimate_scan_cost_for_model_pool(
        repository_paths: list[str | Path] | tuple[str | Path, ...],
        *,
        rag_index_path: str | Path = DEFAULT_RAG_INDEX,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        max_files: int | None = None,
        benchmark_output_tokens: int = 24,
        benchmark_timeout_seconds: float = 300,
) -> ModelPoolEstimate:
    """Kurulu Ollama modellerini hızlarına göre karşılaştırıp en hızlıyı önerir."""
    if benchmark_output_tokens <= 0:
        raise ValueError("benchmark_output_tokens must be greater than zero")
    if benchmark_timeout_seconds <= 0:
        raise ValueError("benchmark_timeout_seconds must be greater than zero")

    scan = estimate_scan_cost(
        repository_paths,
        rag_index_path=rag_index_path,
        tokens_per_second=1,
        max_files=max_files,
    )
    if scan.errors:
        return ModelPoolEstimate(scan, (), None, scan.errors)

    try:
        available_models = list_ollama_models(ollama_url)
    except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return ModelPoolEstimate(
            scan,
            (),
            None,
            (f"Ollama model list could not be loaded ({exc})",),
        )

    estimates: list[ModelEstimate] = []
    errors: list[str] = []
    for model in available_models:
        try:
            speed = benchmark_ollama_model(
                model,
                ollama_url=ollama_url,
                output_tokens=benchmark_output_tokens,
                timeout_seconds=benchmark_timeout_seconds,
            )
        except (OSError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{model}: benchmark failed ({exc})")
            continue
        estimates.append(
            ModelEstimate(
                model=model,
                tokens_per_second=speed,
                estimated_total_tokens=scan.estimated_total_tokens,
                estimated_seconds=ceil(scan.estimated_total_tokens / speed),
            )
        )

    estimates.sort(key=lambda estimate: estimate.estimated_seconds)
    recommendation = estimates[0].model if estimates else None
    if not available_models:
        errors.append("Ollama returned no installed models")
    return ModelPoolEstimate(
        scan=scan,
        models=tuple(estimates),
        recommended_model=recommendation,
        errors=tuple(errors),
    )


def list_ollama_models(ollama_url: str = DEFAULT_OLLAMA_URL) -> tuple[str, ...]:
    """Yerel Ollama'da kurulu model adlarını döndürür."""
    request = Request(f"{ollama_url.rstrip('/')}/api/tags")
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    models = payload.get("models")
    if not isinstance(models, list):
        raise ValueError("Ollama model list response is invalid")
    names = tuple(
        item["name"]
        for item in models
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    )
    return names


def benchmark_ollama_model(
        model: str,
        *,
        ollama_url: str = DEFAULT_OLLAMA_URL,
        output_tokens: int = 24,
        timeout_seconds: float = 300,
) -> float:
    """Sabit kısa bir istekle modelin üretim hızını token/sn olarak ölçer."""
    if output_tokens <= 0:
        raise ValueError("output_tokens must be greater than zero")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be greater than zero")

    request_data = json.dumps(
        {
            "model": model,
            "prompt": "Write a short numbered list of simple words.",
            "stream": False,
            "keep_alive": "0",
            "options": {
                "temperature": 0,
                "num_predict": output_tokens,
            },
        }
    ).encode("utf-8")
    request = Request(
        f"{ollama_url.rstrip('/')}/api/generate",
        data=request_data,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if payload.get("error"):
        raise ValueError(payload["error"])
    token_count = payload.get("eval_count")
    duration_ns = payload.get("eval_duration")
    if (
            not isinstance(token_count, int)
            or token_count <= 0
            or not isinstance(duration_ns, int)
            or duration_ns <= 0
    ):
        raise ValueError("Ollama response did not include valid token speed metrics")
    return token_count / (duration_ns / 1_000_000_000)


def estimate_scan_cost(
        repository_paths: list[str | Path] | tuple[str | Path, ...],
        *,
        rag_index_path: str | Path = DEFAULT_RAG_INDEX,
        model: str = DEFAULT_MODEL,
        tokens_per_second: int = 10,
        top_k: int = 3,
        prompt_overhead_tokens_per_file: int = 500,
        output_tokens_per_file: int = SCAN_OUTPUT_TOKENS_PER_FILE,
        max_file_bytes: int = 1_000_000,
        max_files: int | None = None,
) -> ScanCostEstimate:
    """Kod ve ilgili mevzuat parçalarına göre tarama süresini hesaplar.

    Token sayısı yaklaşık hesaplanır. Süre, verilen saniyedeki token hızına
    dayanır. Yerel model için para maliyeti hesaplanmaz.
    """
    if tokens_per_second <= 0:
        raise ValueError("tokens_per_second must be greater than zero")
    if top_k <= 0:
        raise ValueError("top_k must be greater than zero")
    if prompt_overhead_tokens_per_file < 0 or output_tokens_per_file < 0:
        raise ValueError("prompt and output token assumptions cannot be negative")
    if max_file_bytes <= 0:
        raise ValueError("max_file_bytes must be greater than zero")
    if max_files is not None and max_files <= 0:
        raise ValueError("max_files must be greater than zero")

    index_path = Path(rag_index_path)
    if not index_path.is_file():
        return ScanCostEstimate(
            model=model,
            tokens_per_second_assumption=tokens_per_second,
            repositories=(),
            errors=(f"{index_path}: mevzuat RAG index not found",),
        )

    estimates: list[RepositoryScanEstimate] = []
    errors: list[str] = []
    for repository_path in repository_paths:
        repository = Path(repository_path)
        try:
            branch_commit = run_git_command(repository, "rev-parse", "--abbrev-ref", "HEAD")
            commit = run_git_command(repository, "rev-parse", "--short", "HEAD")
            tracked_paths = run_git_command(repository, "ls-files", "-z")
        except (OSError, subprocess.SubprocessError, ValueError) as exc:
            errors.append(f"{repository}: cannot inventory repository ({exc})")
            continue

        input_tokens = 0
        output_tokens = 0
        retrieved_chunks = 0
        source_count = 0
        source_paths = [
            relative_path
            for relative_path in tracked_paths.split("\0")
            if relative_path and is_source_file(relative_path)
        ]
        if max_files is not None:
            skipped_count = max(0, len(source_paths) - max_files)
            source_paths = source_paths[:max_files]
        else:
            skipped_count = 0
        for relative_path in source_paths:
            source_file = repository / relative_path
            try:
                size = source_file.stat().st_size
                if size > max_file_bytes:
                    skipped_count += 1
                    continue
                code = source_file.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:
                errors.append(f"{repository / relative_path}: cannot read source file ({exc})")
                skipped_count += 1
                continue

            source_count += 1
            matches = search_mevzuat_rag(
                f"{PurePosixPath(relative_path).name}\n{code[:8000]}",
                index_path,
                top_k=top_k,
            )
            retrieved_chunks += len(matches)
            code_tokens = ceil(len(code) / 4)
            context_tokens = sum(ceil(len(match.chunk.text) / 4) for match in matches)
            input_tokens += (
                    code_tokens + context_tokens + prompt_overhead_tokens_per_file
            )
            output_tokens += output_tokens_per_file

        total_tokens = input_tokens + output_tokens
        estimates.append(
            RepositoryScanEstimate(
                repository=str(repository),
                branch_commit=f"{branch_commit}@{commit}",
                source_file_count=source_count,
                skipped_file_count=skipped_count,
                retrieved_chunk_count=retrieved_chunks,
                estimated_input_tokens=input_tokens,
                estimated_output_tokens=output_tokens,
                estimated_total_tokens=total_tokens,
                estimated_seconds=ceil(total_tokens / tokens_per_second),
            )
        )

    return ScanCostEstimate(
        model=model,
        tokens_per_second_assumption=tokens_per_second,
        repositories=tuple(estimates),
        errors=tuple(errors),
    )


def run_git_command(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip().splitlines()
        raise ValueError(detail[-1] if detail else "git command failed")
    return result.stdout.strip("\n")


def is_source_file(relative_path: str) -> bool:
    path = PurePosixPath(relative_path)
    return (
            path.suffix.casefold() in SOURCE_EXTENSIONS
            and not any(part.casefold() in IGNORED_DIRECTORIES for part in path.parts)
            and not path.name.casefold().endswith((".min.js", ".min.css"))
    )

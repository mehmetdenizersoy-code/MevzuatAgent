"""Onay kapılı LangChain tarama iş akışını kurar ve çalıştırır."""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
from pathlib import Path
import subprocess
from typing import Any

from langchain_core.runnables import Runnable, RunnableLambda

from mevzuat_agent.prompt import load_system_prompt
from mevzuat_agent.tools.estimate_scan_cost import (
    ModelPoolEstimate,
    RepositoryScanEstimate,
    estimate_scan_cost_for_model_pool,
)
from mevzuat_agent.tools.generate_scan_report import generate_scan_report
from mevzuat_agent.tools.prepare_remediation_plan import prepare_remediation_plan
from mevzuat_agent.tools.scan_repository import RepositoryScanResult, scan_repository


@dataclass(frozen=True)
class ScanApprovalRequest:
    """Tahmin ve model seçenekleriyle kullanıcıdan tarama onayı ister."""

    estimate: ModelPoolEstimate
    max_files: int
    recommended_model: str
    system_prompt: str


@dataclass(frozen=True)
class RepositoryScanArtifacts:
    """Bir depo için tarama ve üretilen raporlar."""

    scan: RepositoryScanResult
    markdown_report: Path
    html_report: Path
    remediation_plan: Path | None


@dataclass(frozen=True)
class ScanWorkflowResult:
    """Tarama iş akışı sonucu."""

    status: str
    estimate: ModelPoolEstimate
    selected_model: str | None
    repositories: tuple[RepositoryScanArtifacts, ...]


ApprovalCallback = Callable[[ScanApprovalRequest], str | None]
EstimateFunction = Callable[..., ModelPoolEstimate]
ScanFunction = Callable[..., RepositoryScanResult]
ReportFunction = Callable[..., tuple[Path, Path]]
PlanFunction = Callable[..., Path]


def build_scan_workflow(
        approval_callback: ApprovalCallback,
        *,
        estimate_function: EstimateFunction = estimate_scan_cost_for_model_pool,
        scan_function: ScanFunction = scan_repository,
        report_function: ReportFunction = generate_scan_report,
        plan_function: PlanFunction = prepare_remediation_plan,
) -> Runnable:
    """Tarama hattını LangChain Runnable aşamalarıyla kurar."""
    if not callable(approval_callback):
        raise TypeError("Tarama için açık onay callback'i sağlanmalı")

    def prepare(inputs: Mapping[str, Any]) -> dict[str, Any]:
        paths = inputs.get("repository_paths")
        if not isinstance(paths, Sequence) or isinstance(paths, (str, bytes)) or not paths:
            raise ValueError("En az bir yerel depo yolu sağlanmalı")
        repositories = tuple(Path(path).resolve() for path in paths)
        if any(not path.is_dir() for path in repositories):
            raise ValueError("Tüm depo yolları mevcut bir dizin olmalı")
        if len(set(repositories)) != len(repositories):
            raise ValueError("Aynı depo birden fazla kez seçilemez")
        max_files = inputs.get("max_files")
        if not isinstance(max_files, int) or isinstance(max_files, bool) or max_files <= 0:
            raise ValueError("max_files pozitif bir tam sayı olmalı")
        rag_index_path = Path(inputs.get("rag_index_path", "data/legislation/rag/chunks.jsonl"))
        output_dir = Path(inputs.get("output_dir", "data/reports/scans")).resolve()
        if not rag_index_path.is_file():
            raise FileNotFoundError(f"Mevzuat RAG indeksi bulunamadı: {rag_index_path}")
        if any(output_dir.is_relative_to(path) for path in repositories):
            raise ValueError("Tarama raporları kaynak depoların dışında tutulmalı")
        return {
            "repositories": repositories,
            "max_files": max_files,
            "rag_index_path": rag_index_path,
            "output_dir": output_dir,
            "system_prompt": load_system_prompt(),
        }

    def estimate(inputs: dict[str, Any]) -> dict[str, Any]:
        estimate_kwargs = {
            "rag_index_path": inputs["rag_index_path"],
            "max_files": inputs["max_files"],
        }
        pool = estimate_function(inputs["repositories"], **estimate_kwargs)
        if pool.scan.errors:
            raise RuntimeError("Tarama kapsamı tahmin edilemedi: " + "; ".join(pool.scan.errors))
        if not pool.models or pool.recommended_model is None:
            raise RuntimeError(
                "Ollama model havuzundan kullanılabilir bir model önerilmedi"
            )
        return {**inputs, "estimate": pool}

    def approve(inputs: dict[str, Any]) -> dict[str, Any]:
        request = ScanApprovalRequest(
            estimate=inputs["estimate"],
            max_files=inputs["max_files"],
            recommended_model=inputs["estimate"].recommended_model,
            system_prompt=inputs["system_prompt"],
        )
        selected_model = approval_callback(request)
        if selected_model is None:
            return {**inputs, "selected_model": None, "approved": False}
        available_models = {item.model for item in inputs["estimate"].models}
        if selected_model not in available_models:
            raise ValueError("Onaylanan model, tahmin edilen kurulu modeller arasında değil")
        return {**inputs, "selected_model": selected_model, "approved": True}

    def scan(inputs: dict[str, Any]) -> dict[str, Any]:
        if not inputs["approved"]:
            return {**inputs, "artifacts": ()}

        model_pool: ModelPoolEstimate = inputs["estimate"]
        estimate_by_repository: dict[Path, RepositoryScanEstimate] = {
            Path(item.repository).resolve(): item
            for item in model_pool.scan.repositories
        }
        artifacts: list[RepositoryScanArtifacts] = []
        output_dir = inputs["output_dir"]
        for repository in inputs["repositories"]:
            expected: RepositoryScanEstimate | None = estimate_by_repository.get(repository)
            if expected is None:
                raise RuntimeError(f"Depo tahmini bulunamadı: {repository}")
            current = _branch_commit(repository)
            if current != expected.branch_commit:
                raise RuntimeError(
                    f"Tahminden sonra depo değişti; tarama durduruldu: {repository}"
                )
            output_path = output_dir / f"{repository.name}_{_path_id(repository)}.json"
            scan_kwargs = {
                "max_files": inputs["max_files"],
                "rag_index_path": inputs["rag_index_path"],
                "model": inputs["selected_model"],
                "output_path": output_path,
            }
            scan_result = scan_function(repository, **scan_kwargs)
            markdown_path, html_path = report_function(scan_result.output_path)
            plan_path = None
            if scan_result.findings:
                plan_path = plan_function(
                    scan_result.output_path,
                    output_path=scan_result.output_path.with_name(
                        f"{scan_result.output_path.stem}_remediation_plan.md"
                    ),
                )
            artifacts.append(
                RepositoryScanArtifacts(
                    scan_result,
                    markdown_path,
                    html_path,
                    plan_path,
                )
            )
        return {**inputs, "artifacts": tuple(artifacts)}

    def finish(inputs: dict[str, Any]) -> ScanWorkflowResult:
        return ScanWorkflowResult(
            status="completed" if inputs["approved"] else "scan_declined",
            estimate=inputs["estimate"],
            selected_model=inputs["selected_model"],
            repositories=inputs["artifacts"],
        )

    return (
            RunnableLambda(prepare)
            | RunnableLambda(estimate)
            | RunnableLambda(approve)
            | RunnableLambda(scan)
            | RunnableLambda(finish)
    )


def run_scan_workflow(
        repository_paths: Sequence[str | Path],
        *,
        max_files: int,
        approval_callback: ApprovalCallback,
        rag_index_path: str | Path = "data/legislation/rag/chunks.jsonl",
        output_dir: str | Path = "data/reports/scans",
) -> ScanWorkflowResult:
    """Tahmin, kullanıcı onayı, tarama ve raporlamayı çalıştırır."""
    workflow = build_scan_workflow(approval_callback)
    return workflow.invoke(
        {
            "repository_paths": repository_paths,
            "max_files": max_files,
            "rag_index_path": rag_index_path,
            "output_dir": output_dir,
        }
    )


def _branch_commit(repository: Path) -> str:
    try:
        branch = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "--abbrev-ref", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
        commit = subprocess.run(
            ["git", "-C", str(repository), "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"Depo branch/commit bilgisi doğrulanamadı: {repository}") from exc
    return f"{branch}@{commit}"


def _path_id(path: Path) -> str:
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:8]

"""Tarama bulgularından en fazla iki düzeltme önerisi hazırlar."""

import json
from pathlib import Path


_SEVERITY_ORDER = {
    "CRITICAL": 0,
    "HIGH": 1,
    "MEDIUM": 2,
    "LOW": 3,
}


def prepare_remediation_plan(
    scan_result_path: str | Path,
    *,
    output_path: str | Path | None = None,
) -> Path:
    """En önemli iki doğrulanmış bulguyu içeren plan dosyası oluşturur."""
    source_path = Path(scan_result_path)
    try:
        result = json.loads(source_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Tarama sonucu bulunamadı: {source_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Tarama sonucu geçerli JSON değil: satır {exc.lineno}, sütun {exc.colno}"
        ) from exc
    except OSError as exc:
        raise ValueError(f"Tarama sonucu okunamadı: {exc}") from exc

    if not isinstance(result, dict) or not isinstance(result.get("findings"), list):
        raise ValueError("Tarama sonucu bulgu listesi içermiyor")
    if not result["findings"]:
        raise ValueError(
            "Doğrulanmış bulgu yok; düzeltme planı hazırlanamaz. Önce güvenilir bir tarama yapın."
        )

    findings = result["findings"]
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise ValueError(f"{index}. bulgu geçerli bir nesne değil")
        severity = str(finding.get("severity", "")).upper()
        if severity not in _SEVERITY_ORDER:
            raise ValueError(f"{index}. bulgunun önem seviyesi geçersiz")
        if not isinstance(finding.get("confidence"), int):
            raise ValueError(f"{index}. bulgunun güven puanı geçersiz")
        for field in ("file", "title", "recommendation", "evidence"):
            if not isinstance(finding.get(field), str) or not finding[field].strip():
                raise ValueError(f"{index}. bulguda '{field}' alanı eksik")

    prioritized = sorted(
        findings,
        key=lambda item: (
            _SEVERITY_ORDER[str(item["severity"]).upper()],
            -item["confidence"],
        ),
    )[:2]
    target_path = (
        Path(output_path)
        if output_path is not None
        else source_path.with_name(f"{source_path.stem}_remediation_plan.md")
    )
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(_render_plan(result, prioritized), encoding="utf-8")
    return target_path


def _render_plan(result: dict, findings: list[dict]) -> str:
    lines = [
        "# Düzeltme Planı",
        "",
        f"- **Depo:** `{_markdown(str(result.get('repository', 'Belirtilmedi')))}`",
        f"- **Dal / commit:** `{_markdown(str(result.get('branch_commit', 'Belirtilmedi')))}`",
        f"- **Model:** `{_markdown(str(result.get('model', 'Belirtilmedi')))}`",
        f"- **Seçilen bulgu:** {len(findings)}",
        "",
        "> Bu dosya yalnızca öneri sunar. Kod değişikliği için kullanıcı onayı gerekir.",
        "",
    ]
    for index, finding in enumerate(findings, start=1):
        lines.extend(
            [
                f"## {index}. [{finding['severity'].upper()}] "
                f"{_markdown(finding['title'])}",
                "",
                f"- **Konum:** `{_markdown(finding['file'])}:{finding.get('line', '?')}`",
                f"- **Güven:** {finding['confidence']} / 10",
                f"- **Mevzuat:** `{_markdown(finding.get('mevzuat_source', ''))}`, "
                f"sayfa {finding.get('mevzuat_page', '?')}",
                f"- **Bulgu:** {_markdown(finding.get('explanation', ''))}",
                f"- **Önerilen düzeltme:** {_markdown(finding['recommendation'])}",
                f"- **Kod kanıtı:** `{_markdown(finding['evidence'])}`",
                "",
            ]
        )
    lines.extend(
        [
            "## Onay",
            "",
            "Uygulamadan önce her değişiklik kullanıcıya gösterilmeli ve açık onay alınmalıdır.",
            "Onaylanan değişiklikler ayrı bir dalda uygulanmalı, test edilmeli ve diff raporlanmalıdır.",
            "",
        ]
    )
    return "\n".join(lines)


def _markdown(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")

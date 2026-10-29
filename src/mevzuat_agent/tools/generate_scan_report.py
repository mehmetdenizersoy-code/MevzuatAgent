"""Tarama sonucundan Markdown ve HTML raporu üretir."""

import html
import json
from pathlib import Path
import re
from typing import Any


def generate_scan_report(
    scan_result_path: str | Path,
    *,
    markdown_path: str | Path | None = None,
    html_path: str | Path | None = None,
) -> tuple[Path, Path]:
    """Tarama JSON'unu okuyup Markdown ve HTML raporları kaydeder."""
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

    _validate_scan_result(result)
    md_path = Path(markdown_path) if markdown_path else source_path.with_suffix(".md")
    web_path = Path(html_path) if html_path else source_path.with_suffix(".html")
    md_path.parent.mkdir(parents=True, exist_ok=True)
    web_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_render_markdown(result), encoding="utf-8")
    web_path.write_text(_render_html(result), encoding="utf-8")
    return md_path, web_path


def _validate_scan_result(result: object) -> None:
    if not isinstance(result, dict):
        raise ValueError("Tarama sonucu bir JSON nesnesi olmalı")
    for field in ("repository", "branch_commit", "model", "scan_scope"):
        if not isinstance(result.get(field), str):
            raise ValueError(f"Tarama sonucunda '{field}' metin alanı olmalı")
    if not isinstance(result.get("findings"), list):
        raise ValueError("Tarama sonucunda 'findings' listesi olmalı")
    if not isinstance(result.get("file_results"), list):
        raise ValueError("Tarama sonucunda 'file_results' listesi olmalı")
    if not isinstance(result.get("limitations"), list):
        raise ValueError("Tarama sonucunda 'limitations' listesi olmalı")


def _render_markdown(result: dict) -> str:
    findings = result["findings"]
    lines = [
        "# Mevzuat Uyumluluk Tarama Raporu",
        "",
        f"- **Depo:** `{_md(result['repository'])}`",
        f"- **Dal / commit:** `{_md(result['branch_commit'])}`",
        f"- **Model:** `{_md(result['model'])}`",
        f"- **Kapsam:** {_md(result['scan_scope'])}",
        f"- **Tarih:** {_md(str(result.get('scanned_at', 'Belirtilmedi')))}",
        f"- **İncelenen dosya:** {result.get('files_scanned', 0)} / "
        f"{result.get('files_considered', 0)}",
        f"- **Doğrulanmış bulgu:** {len(findings)}",
        "",
        "> Bu rapor otomatik araç tarafından oluşturulmuştur. Bulguları uygulamadan "
        "önce kod ve mevzuat kaynağını uzmanla doğrulayın.",
        "",
        "## Bulgular",
        "",
    ]
    if findings:
        for index, finding in enumerate(findings, start=1):
            lines.extend(
                [
                    f"### {index}. [{_md(str(finding.get('severity', 'Bilinmiyor')))}] "
                    f"{_md(str(finding.get('title', 'Başlıksız')))}",
                    "",
                    f"- **Konum:** `{_md(str(finding.get('file', '')))}:"
                    f"{finding.get('line', '?')}`",
                    f"- **Güven:** {_md(str(finding.get('confidence', '?')))} / 10",
                    f"- **Mevzuat kaynağı:** "
                    f"`{_md(str(finding.get('mevzuat_source', '')))}`, "
                    f"sayfa {_md(str(finding.get('mevzuat_page', '?')))}",
                    f"- **Açıklama:** {_md(str(finding.get('explanation', '')))}",
                    f"- **Öneri:** {_md(str(finding.get('recommendation', '')))}",
                    "",
                    "**Kod kanıtı:**",
                    "",
                    f"> `{_md(str(finding.get('evidence', '')))}`",
                    "",
                ]
            )
    else:
        lines.extend(
            [
                "Doğrulanmış bulgu üretilmedi.",
                "",
                "Bu sonuç, kodun mevzuata uygun olduğunu kanıtlamaz. Tarama kısmi "
                "olabilir veya model çıktıları doğrulamadan geçmemiş olabilir.",
                "",
            ]
        )

    lines.extend(["## Dosya sonuçları", ""])
    for file_result in result["file_results"]:
        status = file_result.get("status", "bilinmiyor")
        lines.append(
            f"- `{_md(str(file_result.get('path', '')))}` — "
            f"**{_md(_translate_status(str(status)))}**"
        )
        if file_result.get("error"):
            lines.append(f"  - {_md(_translate_message(str(file_result['error'])))}")
    lines.extend(["", "## Sınırlamalar", ""])
    if result["limitations"]:
        lines.extend(
            f"- {_md(_translate_message(str(item)))}" for item in result["limitations"]
        )
    else:
        lines.append("Bilinen bir sınırlama bildirilmedi.")
    return "\n".join(lines).rstrip() + "\n"


def _render_html(result: dict) -> str:
    findings_html = []
    for finding in result["findings"]:
        findings_html.append(
            "<article class=\"finding\">"
            f"<h3>{_html(finding.get('severity', 'Bilinmiyor'))}: "
            f"{_html(finding.get('title', 'Başlıksız'))}</h3>"
            f"<p><strong>Konum:</strong> <code>{_html(finding.get('file', ''))}:"
            f"{_html(finding.get('line', '?'))}</code> · "
            f"<strong>Güven:</strong> {_html(finding.get('confidence', '?'))}/10</p>"
            f"<p><strong>Mevzuat:</strong> {_html(finding.get('mevzuat_source', ''))}, "
            f"sayfa {_html(finding.get('mevzuat_page', '?'))}</p>"
            f"<p>{_html(finding.get('explanation', ''))}</p>"
            f"<p><strong>Öneri:</strong> {_html(finding.get('recommendation', ''))}</p>"
            f"<pre><code>{_html(finding.get('evidence', ''))}</code></pre>"
            "</article>"
        )
    if not findings_html:
        findings_html.append(
            '<p class="notice">Doğrulanmış bulgu üretilmedi. Bu sonuç, kodun '
            "mevzuata uygun olduğunu kanıtlamaz.</p>"
        )

    files_html = []
    for file_result in result["file_results"]:
        files_html.append(
            "<tr>"
            f"<td><code>{_html(file_result.get('path', ''))}</code></td>"
            f"<td>{_html(_translate_status(str(file_result.get('status', 'bilinmiyor'))))}</td>"
            f"<td>{_html(_translate_message(str(file_result.get('error') or '')))}</td>"
            "</tr>"
        )
    limitations = [
        _translate_message(str(item)) for item in result["limitations"]
    ] or ["Bilinen bir sınırlama bildirilmedi."]
    limitations_html = "".join(f"<li>{_html(item)}</li>" for item in limitations)
    file_count = f"{result.get('files_scanned', 0)} / {result.get('files_considered', 0)}"

    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mevzuat Uyumluluk Tarama Raporu</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font: 15px/1.65 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; max-width: 1080px; margin: 0 auto; padding: 32px 22px 56px; color: #24344a; background: #f3f6fa; }}
header {{ color: #f8fbff; background: linear-gradient(130deg, #112240, #1d365b); border-radius: 18px; padding: 30px; box-shadow: 0 14px 36px #152b481c; }}
header h1 {{ color: white; margin: 0 0 18px; font-size: clamp(24px, 4vw, 34px); letter-spacing: -.03em; }}
section {{ background: white; border: 1px solid #e1e7ef; border-radius: 16px; padding: 24px; margin: 20px 0; box-shadow: 0 8px 24px #152b4808; }}
h2 {{ color: #16345c; margin-top: 0; font-size: 21px; }}
.summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 10px; }}
.summary div {{ min-width: 0; padding: 12px 14px; background: #ffffff12; border: 1px solid #ffffff20; border-radius: 10px; overflow-wrap: anywhere; }}
.notice {{ color: #59400a; background: #fff4d6; border: 1px solid #f3dfa9; border-left: 4px solid #d99a00; padding: 12px 15px; border-radius: 8px; }}
.finding {{ border: 1px solid #e1e7ef; border-left: 5px solid #00afa0; border-radius: 12px; padding: 20px; margin: 14px 0; background: #fff; }}
.finding h3 {{ color: #16345c; margin: 0 0 10px; }}
table {{ border-collapse: collapse; width: 100%; overflow-wrap: anywhere; }}
th {{ color: white; background: #1d365b; }}
th, td {{ text-align: left; vertical-align: top; border-bottom: 1px solid #e1e6ef; padding: 11px; }}
tr:nth-child(even) td {{ background: #f7f9fc; }}
pre {{ white-space: pre-wrap; overflow-wrap: anywhere; color: #e8eff8; background: #172b46; padding: 15px; border-radius: 10px; }}
code {{ overflow-wrap: anywhere; }}
@media (max-width: 640px) {{ body {{ padding: 16px 12px 32px; }} header, section {{ padding: 18px; }} }}
</style>
</head>
<body>
<header>
<h1>Mevzuat Uyumluluk Tarama Raporu</h1>
<div class="summary">
<div><strong>Depo:</strong> {_html(result['repository'])}</div>
<div><strong>Dal / commit:</strong> {_html(result['branch_commit'])}</div>
<div><strong>Model:</strong> {_html(result['model'])}</div>
<div><strong>Kapsam:</strong> {_html(result['scan_scope'])}</div>
<div><strong>Tarih:</strong> {_html(result.get('scanned_at', 'Belirtilmedi'))}</div>
<div><strong>İncelenen dosya:</strong> {_html(file_count)}</div>
<div><strong>Doğrulanmış bulgu:</strong> {len(result['findings'])}</div>
</div>
<p>Bu otomatik rapordaki bulguları uygulamadan önce kodu ve mevzuat kaynağını uzmanla doğrulayın.</p>
</header>
<section><h2>Bulgular</h2>{''.join(findings_html)}</section>
<section><h2>Dosya sonuçları</h2>
<table><thead><tr><th>Dosya</th><th>Durum</th><th>Açıklama</th></tr></thead>
<tbody>{''.join(files_html)}</tbody></table>
</section>
<section><h2>Sınırlamalar</h2><ul>{limitations_html}</ul></section>
</body>
</html>
"""


def _html(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _md(value: str) -> str:
    return value.replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _translate_status(status: str) -> str:
    return {
        "scanned": "Tarandı",
        "scanned_with_rejections": "Reddedilen bulgular var",
        "no_relevant_mevzuat": "İlgili mevzuat bulunamadı",
        "error": "Hata",
    }.get(status, status)


def _translate_message(message: str) -> str:
    if not message:
        return ""
    partial_scan = re.fullmatch(
        r"Partial scan: selected (\d+) of (\d+) tracked source files\.",
        message,
    )
    if partial_scan:
        return (
            f"Kısmi tarama: {partial_scan.group(2)} kaynak dosyasından "
            f"{partial_scan.group(1)} tanesi incelendi."
        )
    truncation = re.fullmatch(r"(.+): source truncated to (\d+) characters\.", message)
    if truncation:
        return f"{truncation.group(1)}: dosyanın ilk {truncation.group(2)} karakteri incelendi."
    translations = (
        (
            "One or more selected files could not be scanned; see file results.",
            "Seçilen dosyalardan bazıları taranamadı; dosya sonuçlarına bakın.",
        ),
        (
            "One or more model findings failed evidence validation and were excluded.",
            "Kanıt doğrulamasından geçmeyen model bulguları rapora alınmadı.",
        ),
        (
            "Files without retrieved mevzuat context were not sent to Ollama.",
            "İlgili mevzuat bulunmayan dosyalar Ollama'ya gönderilmedi.",
        ),
        (
            "No matching mevzuat chunks; this file was not sent to Ollama.",
            "İlgili mevzuat parçası bulunamadı; dosya Ollama'ya gönderilmedi.",
        ),
        (
            "code evidence does not match the cited line",
            "kod kanıtı belirtilen satırla eşleşmiyor",
        ),
        (
            "cites a mevzuat page not provided to the model",
            "modele verilmeyen bir mevzuat sayfasına atıf yapıyor",
        ),
    )
    for english, turkish in translations:
        message = message.replace(english, turkish)
    message = re.sub(
        r"finding (\d+) rejected:",
        r"\1 numaralı bulgu reddedildi:",
        message,
    )
    message = message.replace(
        "Local model scan failed (JSONDecodeError):",
        "Yerel model taraması başarısız (JSON yanıtı bozuk):",
    )
    return message

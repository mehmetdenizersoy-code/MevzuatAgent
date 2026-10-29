"""Render the tracked HTML report examples as slide-ready screenshots."""

from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "docs" / "assets" / "e2e_reports"
WINDOW_SIZE = "1800,720"
SCAN_CSS = """
<style>
body{width:1600px!important;max-width:none!important;margin:0 auto!important;padding:18px!important;line-height:1.35!important}
header{padding:20px!important}header h1{font-size:28px!important;margin-bottom:12px!important}
.summary{grid-template-columns:repeat(4,1fr)!important;gap:8px!important}
.summary div{padding:8px 10px!important}
header .summary div:nth-child(5){display:none!important}
section{padding:16px!important;margin:12px 0!important}
.finding{display:inline-block!important;vertical-align:top!important;width:calc(50% - 12px)!important;margin:6px!important;padding:13px!important}
.finding h3{font-size:17px!important}.finding p{margin:8px 0!important}
pre{padding:10px!important;font-size:14px!important;margin:8px 0!important}
body>section:nth-of-type(n+2){display:none!important}
</style>
"""
REMEDIATION_CSS = """
<style>
body{width:1600px!important;max-width:none!important;margin:0 auto!important;padding:14px!important;font-size:14px!important;line-height:1.15!important}
main{padding:16px!important}body>main>h1{font-size:27px!important;margin:0 0 8px!important}
body>main>p{margin:4px 0!important}body>main>h2{font-size:19px!important;margin:8px 0 5px!important}
body>main>p:nth-of-type(2),body>main>p:nth-of-type(3){display:none!important}
pre{padding:9px!important;font-size:12px!important;line-height:1.12!important;margin:5px 0!important}
</style>
"""
REPORTS = (
    (
        "docs/examples/e2e_tarama_raporu.html",
        "scan_report_preview.png",
        SCAN_CSS,
    ),
    (
        "docs/examples/e2e_remediation_raporu.html",
        "remediation_report_preview.png",
        REMEDIATION_CSS,
    ),
)


def _find_chrome() -> str:
    candidates = (
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    for executable in ("google-chrome", "chromium", "chromium-browser"):
        located = shutil.which(executable)
        if located:
            return located
    raise RuntimeError("HTML rapor görselleri için Google Chrome veya Chromium bulunamadı.")


def _render_report(chrome: str, source: str, filename: str, css: str) -> None:
    source_path = ROOT / source
    if not source_path.is_file():
        raise FileNotFoundError(f"HTML rapor örneği bulunamadı: {source_path}")
    document = source_path.read_text(encoding="utf-8")
    if "</head>" not in document:
        raise ValueError(f"HTML raporunda </head> bölümü bulunamadı: {source_path}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    output_path = OUTPUT_DIR / filename
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        suffix=".html",
        delete=False,
    ) as temporary:
        temporary.write(document.replace("</head>", css + "</head>", 1))
        temporary_path = Path(temporary.name)

    try:
        result = subprocess.run(
            [
                chrome,
                "--headless",
                "--disable-gpu",
                "--no-sandbox",
                "--hide-scrollbars",
                "--force-device-scale-factor=1",
                f"--window-size={WINDOW_SIZE}",
                f"--screenshot={output_path}",
                temporary_path.as_uri(),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode:
            detail = (result.stderr or result.stdout).strip()
            raise RuntimeError(f"HTML rapor görseli üretilemedi: {detail[-800:]}")
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError(f"Tarayıcı boş rapor görseli üretti: {output_path}")
        print(f"Rapor görseli oluşturuldu: {output_path}")
    finally:
        temporary_path.unlink(missing_ok=True)


def main() -> None:
    chrome = _find_chrome()
    for source, filename, css in REPORTS:
        _render_report(chrome, source, filename, css)


if __name__ == "__main__":
    main()

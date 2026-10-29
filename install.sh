#!/bin/bash

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

SKIP_MODEL=0
SKIP_DATA=0
SKIP_CLONE=0
SKIP_OLLAMA=0

usage() {
    cat <<'EOF'
MevzuatAgent macOS kurulum aracı

Kullanım:
  ./install.sh [seçenekler]

Seçenekler:
  --skip-model   Ollama model kurulum/indirme sorusunu atla
  --skip-ollama  Ollama kurulum ve model indirme sorularını atla
  --skip-data    Mevzuat indirme ve RAG hazırlama sorusunu atla
  --skip-clone   repo_link.json depolarını klonlama sorusunu atla
  --help         Bu yardımı göster

Varsayılan olarak isteğe bağlı ağ ve model işlemleri kullanıcıya sorulur.
Depolar yalnızca ayrıca açıkça onaylanırsa klonlanır.
EOF
}

for argument in "$@"; do
    case "$argument" in
        --skip-model) SKIP_MODEL=1 ;;
        --skip-ollama) SKIP_OLLAMA=1 ;;
        --skip-data) SKIP_DATA=1 ;;
        --skip-clone) SKIP_CLONE=1 ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            printf 'Bilinmeyen seçenek: %s\n' "$argument" >&2
            usage >&2
            exit 2
            ;;
    esac
done

fail() {
    printf 'HATA: %s\n' "$1" >&2
    exit 1
}

ask_yes() {
    local answer
    printf '%s [y/N]: ' "$1"
    read -r answer
    [[ "$answer" == "y" || "$answer" == "Y" || "$answer" == "evet" || "$answer" == "EVET" ]]
}

echo "MevzuatAgent kurulumu"
echo "Proje klasörü: $PROJECT_ROOT"

[[ "$(uname -s)" == "Darwin" ]] || fail "Bu kurulum dosyası macOS içindir."

command -v git >/dev/null 2>&1 || fail "Git bulunamadı. Önce Xcode Command Line Tools veya Git kurun."
command -v python3 >/dev/null 2>&1 || fail "Python 3.10+ bulunamadı. Python kurup kurulumu yeniden başlatın."

PYTHON_VERSION="$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:3])))')"
python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' \
    || fail "Python 3.10 veya üzeri gerekir; bulunan sürüm: $PYTHON_VERSION"

if [[ ! -x ".venv/bin/python" ]]; then
    echo "Sanal ortam oluşturuluyor..."
    python3 -m venv .venv
fi

PYTHON=".venv/bin/python"
echo "Python: $("$PYTHON" --version)"
echo "Python bağımlılıkları kuruluyor..."
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -e '.[dev]'

mkdir -p \
    data/legislation/downloads \
    data/legislation/rag \
    data/repositories \
    data/reports/scans \
    data/reports/remediation

echo "Yapılandırmalar doğrulanıyor..."
"$PYTHON" - <<'PY'
from mevzuat_agent.tools.validate_config import validate_config

result = validate_config(".")
if result.errors:
    for error in result.errors:
        print(f"Yapılandırma hatası: {error}")
    raise SystemExit(1)
print(f"Mevzuat bağlantısı: {len(result.mevzuat_links)}")
print(f"Depo bağlantısı: {len(result.repository_links)}")
PY

OLLAMA_AVAILABLE=0
if command -v ollama >/dev/null 2>&1; then
    if ollama list >/dev/null 2>&1; then
        OLLAMA_AVAILABLE=1
        echo "Ollama servisi erişilebilir."
    else
        echo "Ollama komutu var ancak yerel servis erişilemiyor."
        echo "Ollama uygulamasını açıp bu adımı yeniden çalıştırabilirsiniz."
    fi
else
    echo "Ollama bulunamadı. Kurulum için https://ollama.com/download adresini kullanın."
    if [[ "$SKIP_OLLAMA" -eq 0 ]] \
        && command -v brew >/dev/null 2>&1 \
        && ask_yes "Homebrew ile Ollama kurulsun mu?"; then
        brew install ollama
        echo "Ollama kuruldu. Uygulamayı/servisi başlatıp kurulumu yeniden çalıştırın."
    fi
fi

if [[ "$SKIP_OLLAMA" -eq 0 && "$SKIP_MODEL" -eq 0 && "$OLLAMA_AVAILABLE" -eq 1 ]]; then
    if ask_yes "Başlangıç modeli llama3.2:1b indirilsin mi?"; then
        ollama pull llama3.2:1b
    fi
fi

if [[ "$SKIP_DATA" -eq 0 ]]; then
    if [[ -s "data/legislation/rag/chunks.jsonl" ]]; then
        echo "Mevcut mevzuat RAG indeksi bulundu; indirme adımı atlanıyor."
    elif ask_yes "mevzuat_link.json belgeleri indirilsin ve yerel BM25 indeksi oluşturulsun mu?"; then
        "$PYTHON" - <<'PY'
from pathlib import Path

from mevzuat_agent.tools.build_mevzuat_rag import build_mevzuat_rag
from mevzuat_agent.tools.download_mevzuat import download_mevzuat

download_dir = Path("data/legislation/downloads")
existing_pdfs = []
for path in download_dir.iterdir():
    if path.is_file():
        with path.open("rb") as document:
            if document.read(5) == b"%PDF-":
                existing_pdfs.append(path)
download = None
if not existing_pdfs:
    download = download_mevzuat(download_dir)
    for document in download.documents:
        print(f"İndirildi: {document.path} ({document.size_bytes} bayt)")
    for error in download.errors:
        print(f"İndirme hatası: {error}")

rag = build_mevzuat_rag(download_dir, "data/legislation/rag")
for error in rag.errors:
    print(f"RAG hatası: {error}")
if not rag.chunks:
    raise SystemExit("Kullanılabilir RAG parçası oluşmadı; indirme/PDF hatalarını kontrol edin.")
print(f"RAG indeksi oluşturuldu: {rag.index_path} ({len(rag.chunks)} parça)")
PY
    fi
fi

if [[ "$SKIP_CLONE" -eq 0 ]] && ask_yes "repo_link.json içindeki depolar data/repositories altına klonlansın mı?"; then
    "$PYTHON" - <<'PY'
from mevzuat_agent.tools.clone_repositories import clone_repositories

result = clone_repositories(
    "data/repositories",
    config_path="repo_link.json",
    user_approved=True,
)
for checkout in result.checkouts:
    print(f"Klonlandı: {checkout.path}")
for error in result.errors:
    print(f"Klonlama hatası: {error}")
if result.errors:
    raise SystemExit(1)
PY
fi

echo
echo "Kurulum tamamlandı."
echo "PyCharm yorumlayıcısı: $PROJECT_ROOT/.venv/bin/python"
echo "Uygulamayı başlatmak için: $PROJECT_ROOT/.venv/bin/mevzuat-agent"
echo "Testler: $PROJECT_ROOT/.venv/bin/python -m pytest -q"
if [[ "$OLLAMA_AVAILABLE" -eq 0 ]]; then
    echo "Not: Tarama için Ollama'yı kurup başlatın; ardından gerekli modeli indirin."
fi

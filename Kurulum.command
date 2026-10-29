#!/bin/bash

PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
/bin/bash "$PROJECT_ROOT/install.sh" "$@"
RESULT=$?
echo
if [[ "$RESULT" -eq 0 ]]; then
    echo "Kurulum tamamlandı."
else
    echo "Kurulum hata koduyla sonlandı: $RESULT"
fi
echo "Kapatmak için Enter tuşuna basın."
read -r _
exit "$RESULT"

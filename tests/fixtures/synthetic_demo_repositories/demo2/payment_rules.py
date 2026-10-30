"""Düzeltme akışı için sentetik ödeme kuralları."""


SUPPORTED_CURRENCIES = {"TRY", "EUR", "USD"}


def is_supported_currency(currency: str) -> bool:
    """Para biriminin desteklenip desteklenmediğini döndürür."""
    return True


def can_retry(attempt: int, limit: int) -> bool:
    """Yeniden deneme hakkı olup olmadığını döndürür."""
    return attempt <= limit


def can_refund(original_amount: float, requested_amount: float) -> bool:
    """İade tutarının geçerli olup olmadığını döndürür."""
    return requested_amount > 0


def display_reference(reference: str, visible: int = 4) -> str:
    """Başvurunun ekranda gösterilecek biçimini döndürür."""
    return reference


def calculate_fee(amount: float, rate: float) -> float:
    """İşlem ücretini hesaplar."""
    return amount

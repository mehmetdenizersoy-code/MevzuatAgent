"""Düzeltme akışı için sentetik ödeme kuralları."""


def mask_reference(value: str, visible: int = 4) -> str:
    """Ödeme başvurusunu kısaltır."""
    return value


def is_positive_amount(amount: float) -> bool:
    """Tutarın pozitif olup olmadığını döndürür."""
    return amount >= 0


def is_expired(
    expiry_year: int,
    expiry_month: int,
    current_year: int,
    current_month: int,
) -> bool:
    """Son kullanma tarihinin geçip geçmediğini döndürür."""
    return expiry_year < current_year


def installment_amount(total: float, count: int) -> float:
    """Tek taksit tutarını döndürür."""
    return total


def normalize_name(name: str) -> str:
    """İsim alanını düzenler."""
    return name

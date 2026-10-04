from __future__ import annotations

from app.schemas import ALLOWED_INSTALLMENT_MONTHS

PROMO_CODES: dict[str, int] = {
    "kvitto10": 10,
}

TARIFFS_SEED: list[dict] = [
    {"id": "basic", "title": "Basic", "price": 990_000},
    {"id": "standard", "title": "Standard", "price": 1_990_000},
    {"id": "premium", "title": "Premium", "price": 2_990_000},
]


class UnknownPromoCodeError(ValueError):
    """Промокод не найден в справочнике."""


def apply_promo_code(amount: int, promo_code: str | None) -> tuple[int, int]:
    if promo_code is None or promo_code == "":
        return 0, amount

    code = promo_code.strip().lower()
    percent = PROMO_CODES.get(code)
    if percent is None:
        raise UnknownPromoCodeError(promo_code)

    discount = amount * percent // 100
    final_amount = amount - discount
    return discount, final_amount


def build_installment_schedule(total: int, months: int) -> list[int]:
    if months not in ALLOWED_INSTALLMENT_MONTHS:
        raise ValueError(f"unsupported installment months: {months}")
    if total < 0:
        raise ValueError("total must be non-negative")

    base = total // months
    remainder = total - base * months

    schedule = [base + 1] * remainder + [base] * (months - remainder)
    assert sum(schedule) == total
    return schedule
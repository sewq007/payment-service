from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

PaymentMethod = Literal["card", "sbp", "installment"]
PaymentStatus = Literal["pending", "succeeded", "failed", "refunded"]

ALLOWED_INSTALLMENT_MONTHS = {3, 6, 12}


class TariffOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    price: int


class PaymentCreate(BaseModel):
    tariff_id: str
    email: EmailStr
    method: PaymentMethod
    installment_months: int | None = Field(default=None)
    promo_code: str | None = Field(default=None)

    @model_validator(mode="after")
    def _validate_installment(self) -> "PaymentCreate":
        if self.method == "installment":
            if self.installment_months is None:
                raise ValueError("installment_months is required for installment method")
            if self.installment_months not in ALLOWED_INSTALLMENT_MONTHS:
                raise ValueError(
                    f"installment_months must be one of {sorted(ALLOWED_INSTALLMENT_MONTHS)}"
                )
        else:
            self.installment_months = None
        return self


class PaymentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: PaymentStatus
    tariff_id: str
    amount: int
    discount: int
    method: PaymentMethod
    installment_months: int | None
    schedule: list[int] | None
    email: str
    created_at: datetime


class WebhookIn(BaseModel):
    payment_id: str
    status: PaymentStatus


class WebhookOut(BaseModel):
    result: Literal["ok"]


class ErrorOut(BaseModel):
    error: str
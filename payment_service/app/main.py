from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud, models, schemas
from app.database import SessionLocal, get_session, init_db
from app.services import (
    TARIFFS_SEED,
    UnknownPromoCodeError,
    apply_promo_code,
    build_installment_schedule,
)

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"succeeded", "failed"},
    "succeeded": {"refunded"},
    "failed": set(),
    "refunded": set(),
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    async with SessionLocal() as session:
        await crud.seed_tariffs(session, TARIFFS_SEED)
    yield


app = FastAPI(title="Online School Payments API", lifespan=lifespan)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@app.get("/tariffs", response_model=list[schemas.TariffOut])
async def get_tariffs(session: SessionDep) -> list[models.Tariff]:
    return await crud.list_tariffs(session)


@app.post(
    "/payments",
    response_model=schemas.PaymentOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment(
    payload: schemas.PaymentCreate,
    session: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    if idempotency_key:
        existing = await crud.get_payment_by_idempotency_key(session, idempotency_key)
        if existing is not None:
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content=schemas.PaymentOut.model_validate(existing).model_dump(
                    mode="json"
                ),
            )

    tariff = await crud.get_tariff(session, payload.tariff_id)
    if tariff is None:
        raise HTTPException(status_code=422, detail="unknown tariff_id")

    try:
        discount, amount = apply_promo_code(tariff.price, payload.promo_code)
    except UnknownPromoCodeError:
        raise HTTPException(status_code=422, detail="unknown promo_code")

    schedule: list[int] | None = None
    if payload.method == "installment":
        assert payload.installment_months is not None
        schedule = build_installment_schedule(amount, payload.installment_months)

    payment = models.Payment(
        id=str(uuid.uuid4()),
        status="pending",
        tariff_id=tariff.id,
        amount=amount,
        discount=discount,
        method=payload.method,
        installment_months=payload.installment_months,
        schedule=schedule,
        email=payload.email,
        idempotency_key=idempotency_key,
    )
    await crud.create_payment(session, payment)
    return payment


@app.get("/payments/{payment_id}", response_model=schemas.PaymentOut)
async def get_payment(payment_id: str, session: SessionDep) -> models.Payment:
    payment = await crud.get_payment(session, payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="payment not found")
    return payment


@app.post("/webhooks/bank")
async def bank_webhook(payload: schemas.WebhookIn, session: SessionDep):
    payment = await crud.get_payment(session, payload.payment_id)
    if payment is None:
        raise HTTPException(status_code=404, detail="payment not found")

    allowed = ALLOWED_TRANSITIONS.get(payment.status, set())
    if payload.status not in allowed:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "invalid_transition"},
        )

    payment.status = payload.status
    await session.commit()
    return {"result": "ok"}
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import models


async def get_tariff(session: AsyncSession, tariff_id: str) -> models.Tariff | None:
    return await session.get(models.Tariff, tariff_id)


async def list_tariffs(session: AsyncSession) -> list[models.Tariff]:
    result = await session.execute(select(models.Tariff).order_by(models.Tariff.id))
    return list(result.scalars().all())


async def seed_tariffs(session: AsyncSession, seed: list[dict]) -> None:
    existing = {t.id for t in await list_tariffs(session)}
    for item in seed:
        if item["id"] in existing:
            continue
        session.add(models.Tariff(**item))
    await session.commit()


async def get_payment(session: AsyncSession, payment_id: str) -> models.Payment | None:
    return await session.get(models.Payment, payment_id)


async def get_payment_by_idempotency_key(
    session: AsyncSession, key: str
) -> models.Payment | None:
    result = await session.execute(
        select(models.Payment).where(models.Payment.idempotency_key == key)
    )
    return result.scalar_one_or_none()


async def create_payment(session: AsyncSession, payment: models.Payment) -> models.Payment:
    session.add(payment)
    await session.commit()
    await session.refresh(payment)
    return payment
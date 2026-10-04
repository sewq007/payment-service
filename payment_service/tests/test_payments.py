from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


# ---------- 1. Промокоды ----------


async def test_payment_amount_with_and_without_promo(client):
    # без промокода
    r = await client.post(
        "/payments",
        json={"tariff_id": "standard", "email": "user@example.com", "method": "card"},
    )
    assert r.status_code == 201
    data = r.json()
    assert data["amount"] == 1_990_000
    assert data["discount"] == 0
    assert data["schedule"] is None

    # с промокодом в верхнем регистре
    r = await client.post(
        "/payments",
        json={
            "tariff_id": "standard",
            "email": "user@example.com",
            "method": "card",
            "promo_code": "KVITTO10",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["discount"] == 199_000
    assert data["amount"] == 1_791_000

    # с промокодом в нижнем регистре
    r = await client.post(
        "/payments",
        json={
            "tariff_id": "premium",
            "email": "user@example.com",
            "method": "sbp",
            "promo_code": "kvitto10",
        },
    )
    assert r.status_code == 201
    data = r.json()
    assert data["discount"] == 299_000
    assert data["amount"] == 2_691_000


async def test_unknown_promo_code_returns_422(client):
    r = await client.post(
        "/payments",
        json={
            "tariff_id": "basic",
            "email": "user@example.com",
            "method": "card",
            "promo_code": "WRONG",
        },
    )
    assert r.status_code == 422


# ---------- 2. График рассрочки ----------


@pytest.mark.parametrize("months", [3, 6, 12])
async def test_installment_schedule_sums_to_amount(client, months):
    r = await client.post(
        "/payments",
        json={
            "tariff_id": "standard",
            "email": "user@example.com",
            "method": "installment",
            "installment_months": months,
        },
    )
    assert r.status_code == 201
    data = r.json()
    schedule = data["schedule"]
    assert isinstance(schedule, list)
    assert len(schedule) == months
    assert sum(schedule) == data["amount"] == 1_990_000
    # первые платежи >= последующих
    assert all(schedule[i] >= schedule[i + 1] for i in range(len(schedule) - 1))


async def test_installment_schedule_exact_split_3_months(client):
    r = await client.post(
        "/payments",
        json={
            "tariff_id": "standard",
            "email": "user@example.com",
            "method": "installment",
            "installment_months": 3,
        },
    )
    assert r.status_code == 201
    assert r.json()["schedule"] == [663334, 663333, 663333]


async def test_installment_months_required_and_validated(client):
    # installment без месяцев -> 422
    r = await client.post(
        "/payments",
        json={"tariff_id": "basic", "email": "user@example.com", "method": "installment"},
    )
    assert r.status_code == 422

    # недопустимое значение
    r = await client.post(
        "/payments",
        json={
            "tariff_id": "basic",
            "email": "user@example.com",
            "method": "installment",
            "installment_months": 5,
        },
    )
    assert r.status_code == 422

    # для card рассрочка игнорируется -> None
    r = await client.post(
        "/payments",
        json={
            "tariff_id": "basic",
            "email": "user@example.com",
            "method": "card",
            "installment_months": 6,
        },
    )
    assert r.status_code == 201
    assert r.json()["installment_months"] is None
    assert r.json()["schedule"] is None


# ---------- 3. Идемпотентность ----------


async def test_idempotency_key_returns_same_payment(client):
    headers = {"Idempotency-Key": "abc-123"}
    body = {"tariff_id": "basic", "email": "user@example.com", "method": "card"}

    r1 = await client.post("/payments", json=body, headers=headers)
    assert r1.status_code == 201
    p1 = r1.json()

    r2 = await client.post("/payments", json=body, headers=headers)
    assert r2.status_code == 200
    p2 = r2.json()

    assert p1["id"] == p2["id"]
    assert p1["amount"] == p2["amount"]


# ---------- 4. Вебхуки ----------


async def test_webhook_valid_and_invalid_transitions(client):
    r = await client.post(
        "/payments",
        json={"tariff_id": "basic", "email": "user@example.com", "method": "card"},
    )
    pid = r.json()["id"]

    # pending -> succeeded — ok
    r = await client.post("/webhooks/bank", json={"payment_id": pid, "status": "succeeded"})
    assert r.status_code == 200
    assert r.json() == {"result": "ok"}

    # succeeded -> pending — запрещено
    r = await client.post("/webhooks/bank", json={"payment_id": pid, "status": "pending"})
    assert r.status_code == 409
    assert r.json() == {"error": "invalid_transition"}

    # статус не изменился
    r = await client.get(f"/payments/{pid}")
    assert r.json()["status"] == "succeeded"

    # succeeded -> refunded — ok
    r = await client.post("/webhooks/bank", json={"payment_id": pid, "status": "refunded"})
    assert r.status_code == 200

    # refunded -> succeeded — запрещено
    r = await client.post("/webhooks/bank", json={"payment_id": pid, "status": "succeeded"})
    assert r.status_code == 409


async def test_webhook_pending_to_failed(client):
    r = await client.post(
        "/payments",
        json={"tariff_id": "basic", "email": "user@example.com", "method": "sbp"},
    )
    pid = r.json()["id"]
    r = await client.post("/webhooks/bank", json={"payment_id": pid, "status": "failed"})
    assert r.status_code == 200

    # failed -> succeeded — запрещено
    r = await client.post("/webhooks/bank", json={"payment_id": pid, "status": "succeeded"})
    assert r.status_code == 409


# ---------- 5. 404 ----------


async def test_get_unknown_payment_returns_404(client):
    r = await client.get("/payments/does-not-exist")
    assert r.status_code == 404


async def test_webhook_unknown_payment_returns_404(client):
    r = await client.post(
        "/webhooks/bank",
        json={"payment_id": "does-not-exist", "status": "succeeded"},
    )
    assert r.status_code == 404


# ---------- Дополнительно ----------


async def test_get_tariffs(client):
    r = await client.get("/tariffs")
    assert r.status_code == 200
    data = r.json()
    assert {t["id"] for t in data} == {"basic", "standard", "premium"}
    assert all(isinstance(t["price"], int) for t in data)


async def test_unknown_tariff_returns_422(client):
    r = await client.post(
        "/payments",
        json={
            "tariff_id": "nonexistent",
            "email": "user@example.com",
            "method": "card",
        },
    )
    assert r.status_code == 422
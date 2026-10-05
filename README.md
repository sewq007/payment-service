# Online School Payments API (FastAPI)

Тестовое задание: API платежей для онлайн-школы через Квитто.

## Стек

- Python 3.11+ (проверено на 3.14)
- FastAPI + Pydantic v2
- SQLAlchemy 2 (async) + aiosqlite (SQLite)
- pytest + httpx (ASGI transport)

## Структура репозитория

```
payment-service/
├── README.md
├── AI_LOG.md
├── .gitignore
└── payment_service/
    ├── app/
    │   ├── main.py         # FastAPI-приложение и эндпоинты
    │   ├── database.py     # async engine, session, init_db
    │   ├── models.py       # SQLAlchemy-модели Tariff и Payment
    │   ├── schemas.py      # Pydantic-схемы
    │   ├── crud.py         # операции с БД
    │   └── services.py     # бизнес-логика: промокод, график рассрочки
    ├── tests/
    │   ├── conftest.py
    │   └── test_payments.py
    ├── pytest.ini
    └── requirements.txt
```

## Установка

Из корня репозитория:

```bash
cd payment_service
python -m venv .venv
# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

## Запуск

Из папки `payment_service/` (там, где лежит `app/`):

```bash
uvicorn app.main:app --reload
```

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

При первом запуске автоматически создаётся `payments.db` и засеиваются тарифы.

## Тесты

Из папки `payment_service/`:

```bash
pytest -v
```

Ожидаемо: `14 passed`.

## Примеры curl

### Тарифы

```bash
curl -s http://127.0.0.1:8000/tariffs
```

### Создание платежа (card, без промокода)

```bash
curl -s -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -d '{"tariff_id":"standard","email":"user@example.com","method":"card"}'
```

Ответ: `201`, `amount: 1990000`, `discount: 0`.

### С промокодом (регистр не важен)

```bash
curl -s -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -d '{"tariff_id":"standard","email":"user@example.com","method":"card","promo_code":"kvitto10"}'
```

Ответ: `201`, `discount: 199000`, `amount: 1791000`.

### Рассрочка на 3 месяца

```bash
curl -s -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -d '{"tariff_id":"standard","email":"user@example.com","method":"installment","installment_months":3}'
```

Ответ: `201`, `schedule: [663334, 663333, 663333]`.

### Идемпотентность

```bash
curl -s -X POST http://127.0.0.1:8000/payments \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-42" \
  -d '{"tariff_id":"basic","email":"user@example.com","method":"card"}'
# повторный вызов вернёт тот же платёж с кодом 200
```

### Получение платежа

```bash
curl -s http://127.0.0.1:8000/payments/<PAYMENT_ID>
```

### Вебхук банка

```bash
# pending -> succeeded — ok
curl -s -X POST http://127.0.0.1:8000/webhooks/bank \
  -H "Content-Type: application/json" \
  -d '{"payment_id":"<PAYMENT_ID>","status":"succeeded"}'

# succeeded -> pending — 409 invalid_transition
curl -s -X POST http://127.0.0.1:8000/webhooks/bank \
  -H "Content-Type: application/json" \
  -d '{"payment_id":"<PAYMENT_ID>","status":"pending"}'
```

> Windows PowerShell: используйте `curl.exe`, а не `curl` (последний — алиас
> на `Invoke-WebRequest` с другим синтаксисом).

## Бизнес-правила

- Все суммы — целые числа в копейках (никаких float).
- Промокод `KVITTO10` даёт -10% (регистронезависимо). Неизвестный промокод → 422.
- `method`: `card` | `sbp` | `installment`.
- `installment_months` ∈ {3, 6, 12} — обязателен для `installment`, иначе `null`.
- График рассрочки: сумма элементов равна `amount`, остаток от деления прибавляется
  к первым платежам. Пример: `1990000 / 3 → [663334, 663333, 663333]`.
- Статусы: `pending`, `succeeded`, `failed`, `refunded`.
  - `pending → succeeded`
  - `pending → failed`
  - `succeeded → refunded`
  - остальные переходы запрещены → 409 `{"error": "invalid_transition"}`.
- Идемпотентность через заголовок `Idempotency-Key`: повторный запрос возвращает
  200 и тот же объект, второго платежа не создаётся.

## Тарифы (засеиваются при старте)

| id | title | price, ₽ | price, коп. |
|---|---|---|---|
| basic | Basic | 9 900 | 990 000 |
| standard | Standard | 19 900 | 1 990 000 |
| premium | Premium | 29 900 | 2 990 000 |
# Oh!MyMind

Система **классификации, хранения и распределения потоков знаний**.

Где символ `!` нельзя (домен, часть идентификаторов): **OhiMyMind**.

Открытый репозиторий: https://github.com/askred-dot-ru/OhiMyMind

Почта — только поток №1 (самый простой вход). Не почтовый клиент: у каждого потока своя структура. Мессенджеры (Telegram, WhatsApp, Teams) и сессии LLM — следующие источники на сбор и индекс, не канал управления агентом.

v1 не связан с 1С; позже возможен исходящий HTTP.

Канон для агентов: [`memory.md`](memory.md). Текущая спека: [`openspec/specs/`](openspec/specs/). Активный change: [`openspec/changes/semantic-index-v1/`](openspec/changes/semantic-index-v1/). Архив v1 почты: [`openspec/changes/archive/2026-09-18-mail-stream-v1/`](openspec/changes/archive/2026-09-18-mail-stream-v1/).

## Запуск (v1)

```bash
cp .env.example .env   # секреты; для локального compose есть dev-defaults в docker-compose.yml
docker compose up --build
```

Откройте `PUBLIC_BASE_URL` (по умолчанию http://127.0.0.1:8798). Войдите логином из `OHIMYMIND_BOOTSTRAP_ADMIN`.

Без Docker: Postgres с `CREATE EXTENSION vector`, те же переменные (`DATABASE_URL`, `ATTACHMENTS_DIR` — хостовые пути), `alembic upgrade head`, затем `python -m app.entrypoint` и `python -m worker.main`. В коде нет DNS-имён Compose.

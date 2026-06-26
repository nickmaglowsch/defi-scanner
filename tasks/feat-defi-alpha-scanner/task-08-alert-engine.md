# Task 08: Alert Engine & Telegram Notification

## Objective
Implement the alert rule evaluation engine that checks thresholds against latest snapshots/calculations, persists fired alerts, and delivers notifications — real Telegram webhook, stub channels (log-only) for Email/Discord/Slack.

## Context
The alert engine runs after each collector cycle (or on a separate schedule), evaluates configured thresholds, and fires alerts when breached. It queries the latest snapshots and calculations from the DB. Telegram uses the Bot API (httpx POST); other channels are stubs that log the message and return a success indicator. See `updated-prd.md` Sections "Alert Engine" and "Alerts DB table".

**Quick Context**:
- Telegram Bot API: `POST https://api.telegram.org/bot{token}/sendMessage` with `chat_id` and `text`.
- Alert thresholds are configurable via env vars (with reasonable defaults: loop_yield > 10%, funding > 20%, net_carry > 12%, borrow_apy < 3%).
- Deduplication: don't re-fire the same alert for the same market within a cooldown period (ponytail: check if an alert with same alert_type + market_id was fired in the last hour).

## Target Files
- `backend/app/alerts/__init__.py`
- `backend/app/alerts/engine.py`
- `backend/app/alerts/channels.py`
- `backend/tests/test_alerts.py`

## Dependencies
- task-02 (DB models)
- task-07 (API + ranker — alerts query the same DB + calculation tables; want established query patterns)

## Steps
1. Write `backend/app/alerts/channels.py`:
   - Abstract `NotificationChannel` protocol (or simple base class) with `async def send(message: str) -> bool`.
   - `TelegramChannel`: `__init__` takes `bot_token`, `chat_id`, `httpx.AsyncClient`. `send()` → POST to Telegram Bot API. On failure: log, return False.
   - `LoggingChannel` (stub for Email/Discord/Slack): `send()` → logs message at INFO level, returns True. Include a comment: `# ponytail: real email/slack/discord impl goes here`.
   - Factory function `get_channel(name, config)` returns appropriate channel instance.
2. Write `backend/app/alerts/engine.py`:
   - `AlertEngine` class:
     - Takes async DB session factory, dict of channel instances, threshold config dict.
     - `async evaluate()`:
       1. Query latest `lending_snapshots` + `funding_snapshots` (last 1 per market).
       2. Query latest `loop_calculations` + `carry_calculations` (last 1 per market).
       3. For each threshold rule:
          - **loop_yield > X**: check `loop_calculations.effective_yield > threshold` → fire.
          - **funding_rate > X**: check `funding_snapshots.annualized_funding > threshold` → fire.
          - **net_carry > X**: check `carry_calculations.net_carry > threshold` → fire.
          - **borrow_apy < X**: check `lending_snapshots.borrow_apy < threshold` → fire.
       4. Dedup: skip if an alert with same `alert_type` + `market_id` fired within last hour (query alerts table).
       5. For each triggered alert: insert `Alert` row, call `channel.send(formatted_message)`.
     - Message format: `"🚨 {alert_type} ALERT: {market} {metric}={value}% (threshold={threshold}%)"`.
3. Wire alert engine into `backend/app/main.py`:
   - In lifespan: create `AlertEngine` with channels (telegram if token configured, else all logging), spawn background task that runs `evaluate()` every `ALERT_INTERVAL_SECONDS` (default 300, separate from collector interval).
   - If `TELEGRAM_BOT_TOKEN` is empty: skip Telegram channel registration, log warning.
4. Add alert threshold config to `backend/app/config.py` (if not already present):
   - `ALERT_LOOP_YIELD_THRESHOLD` default 10.0
   - `ALERT_FUNDING_RATE_THRESHOLD` default 20.0
   - `ALERT_NET_CARRY_THRESHOLD` default 12.0
   - `ALERT_BORROW_APY_THRESHOLD` default 3.0
5. Write `backend/tests/test_alerts.py`:
   - Test `LoggingChannel.send()` logs message and returns True.
   - Test `TelegramChannel.send()` with mocked httpx: POST to correct URL, returns True on 200.
   - Test `TelegramChannel.send()` returns False on HTTP error.
   - Test `AlertEngine.evaluate()` with mock DB data: inserts alert when threshold breached.
   - Test deduplication: no duplicate alert within cooldown window.
   - Test no alert fired when values below threshold.
   - Use test DB fixtures with sample snapshots and calculations.

## Acceptance Criteria
- [ ] `AlertEngine.evaluate()` queries latest snapshots/calcs and fires alerts for breached thresholds
- [ ] Alert deduplication: same alert_type + market_id not re-fired within 1 hour cooldown
- [ ] `TelegramChannel.send()` POSTs to correct Bot API URL and returns True on success
- [ ] `LoggingChannel.send()` logs at INFO level and returns True (stub pattern reusable for Email/Discord/Slack)
- [ ] Telegram channel skipped gracefully when `TELEGRAM_BOT_TOKEN` is empty (log warning, continue)
- [ ] Alert rows inserted into `alerts` table with correct fields
- [ ] Alert evaluation runs on schedule in FastAPI lifespan (separate from collectors)
- [ ] All tests pass: `pytest tests/test_alerts.py -v`
- [ ] Full test suite passes: `pytest -v`

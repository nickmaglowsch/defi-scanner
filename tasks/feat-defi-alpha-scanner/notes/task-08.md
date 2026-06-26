# Task 08: Alert Engine & Telegram Notification

- **Decisions**: Wired `run_alerts` into `collectors/__init__.py` as a background task alongside collectors rather than touching `main.py`, matching shared-context's preference. The alert engine runs on its own schedule (`ALERT_INTERVAL_SECONDS`, default 300s) separate from the collector cycle.
- **Deviations**: `NotificationChannel` is a `Protocol` rather than an ABC — simpler and equally effective for duck-typing. Channel factory `get_channel` takes explicit `bot_token`/`chat_id` strings rather than a full config object — the two values are all Telegram needs.
- **Trade-offs**: Query helpers (`_latest_lending`, etc.) are static methods on the engine instead of free functions. Could be extracted if reused elsewhere, but they're alert-specific queries right now.
- **Risks**: The engine queries all markets every cycle. With hundreds of markets this could be slow — consider limiting to active markets or adding an index on `observed_at` + `market_id` if latency becomes a problem.

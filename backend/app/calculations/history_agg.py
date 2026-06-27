"""Yield history aggregation — batched per-market windowed aggregates."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Minimum number of data points required before computing percentile/rank.
_MIN_POINTS = 20
# Minimum distinct days of history required.
_MIN_DAYS = 7

# ponytail: "today"/"yesterday" are relative to the latest observed_at for each
# market, not wall-clock midnight. DeFi snapshots are sparse; nearest-snapshot
# semantics avoid empty buckets on markets that haven't been seen today.
#
# "yesterday" = nearest snapshot to (latest - 24h), only if it falls in the
# window [latest-36h, latest-12h] — avoids treating today's snapshot as yesterday.
# "avg_7d" / "avg_30d" = average of all snapshots within 7d / 30d of latest.

_SQL = """
WITH latest AS (
    SELECT market_id, MAX(observed_at) AS latest_at
    FROM {table}
    WHERE market_id = ANY(:market_ids)
    GROUP BY market_id
),
snaps AS (
    SELECT s.market_id,
           s.observed_at,
           s.{field}          AS val,
           l.latest_at,
           l.latest_at - s.observed_at AS age
    FROM {table} s
    JOIN latest l ON l.market_id = s.market_id
    WHERE s.market_id = ANY(:market_ids)
      AND s.{field} IS NOT NULL
      AND s.observed_at >= l.latest_at - INTERVAL '30 days'
),
today_cte AS (
    SELECT DISTINCT ON (market_id)
           market_id, val AS today
    FROM snaps
    ORDER BY market_id, observed_at DESC
),
yesterday_candidates AS (
    SELECT market_id, val,
           ABS(EXTRACT(EPOCH FROM (age - INTERVAL '24 hours'))) AS dist_secs
    FROM snaps
    WHERE age >= INTERVAL '12 hours'
      AND age <= INTERVAL '36 hours'
),
yesterday_cte AS (
    SELECT DISTINCT ON (market_id)
           market_id, val AS yesterday
    FROM yesterday_candidates
    ORDER BY market_id, dist_secs ASC
),
agg_cte AS (
    SELECT market_id,
           AVG(val) FILTER (WHERE age <= INTERVAL '7 days')  AS avg_7d,
           AVG(val)                                           AS avg_30d
    FROM snaps
    GROUP BY market_id
)
SELECT l.market_id,
       t.today,
       y.yesterday,
       a.avg_7d,
       a.avg_30d
FROM latest l
LEFT JOIN today_cte     t ON t.market_id = l.market_id
LEFT JOIN yesterday_cte y ON y.market_id = l.market_id
LEFT JOIN agg_cte       a ON a.market_id = l.market_id
"""


async def get_yield_history(
    db: AsyncSession,
    market_ids: set[str],
    table: str,
    field: str,
) -> dict[str, dict[str, float | None]]:
    """Return per-market yield aggregates for a batch of market_ids.

    Args:
        db:         Async SQLAlchemy session.
        market_ids: Markets to aggregate. Empty set → empty dict.
        table:      Snapshot table name ('lending_snapshots' or 'funding_snapshots').
        field:      Yield column name ('deposit_apy' or 'annualized_funding').

    Returns:
        {market_id: {"today": float|None, "yesterday": float|None,
                     "avg_7d": float|None, "avg_30d": float|None}}
    """
    if not market_ids:
        return {}

    # ponytail: table/field are internal constants (not user input); format-string
    # injection is safe. Parameterizing identifiers requires quoting gymnastics
    # with no security benefit here since callers are trusted route code.
    sql = text(_SQL.format(table=table, field=field))
    result = await db.execute(sql, {"market_ids": list(market_ids)})

    out: dict[str, dict[str, float | None]] = {}
    for row in result.all():
        mid, today, yesterday, avg_7d, avg_30d = row
        out[mid] = {
            "today": float(today) if today is not None else None,
            "yesterday": float(yesterday) if yesterday is not None else None,
            "avg_7d": float(avg_7d) if avg_7d is not None else None,
            "avg_30d": float(avg_30d) if avg_30d is not None else None,
        }
    return out


# ponytail: table/field are internal constants — format-string injection is safe.
_PERCENTILE_SQL = """
WITH window_data AS (
    SELECT market_id,
           {field} AS val,
           observed_at
    FROM {table}
    WHERE market_id = ANY(:market_ids)
      AND {field} IS NOT NULL
      AND observed_at >= NOW() - INTERVAL ':window_days days'
),
counts AS (
    SELECT market_id,
           COUNT(*)                                                    AS point_count,
           COUNT(DISTINCT (observed_at AT TIME ZONE 'UTC')::date)     AS day_count
    FROM window_data
    GROUP BY market_id
),
latest_val AS (
    SELECT DISTINCT ON (market_id) market_id, val
    FROM window_data
    ORDER BY market_id, observed_at DESC
),
ranked AS (
    SELECT w.market_id,
           PERCENT_RANK() OVER (PARTITION BY w.market_id ORDER BY w.val) AS pct_rank,
           w.val,
           lv.val AS latest
    FROM window_data w
    JOIN latest_val lv ON lv.market_id = w.market_id
)
SELECT r.market_id,
       MAX(r.pct_rank) FILTER (WHERE r.val = r.latest) AS percentile,
       c.point_count,
       c.day_count
FROM ranked r
JOIN counts c ON c.market_id = r.market_id
GROUP BY r.market_id, c.point_count, c.day_count
"""


async def get_percentile(
    db: AsyncSession,
    market_ids: set[str],
    table: str,
    field: str,
    window_days: int = 90,
) -> dict[str, float | None]:
    """Return per-market percentile of the latest value within the window.

    Returns None for markets with insufficient history (< 20 points or < 7 days).

    Args:
        db:          Async SQLAlchemy session.
        market_ids:  Markets to compute. Empty set → empty dict.
        table:       Snapshot table name.
        field:       Yield column name.
        window_days: Lookback window in days (default 90).

    Returns:
        {market_id: percentile (0.0..1.0) | None}
    """
    if not market_ids:
        return {}

    # ponytail: interval literal can't be parameterised in all PG drivers;
    # window_days is an internal int, not user input — safe to interpolate.
    sql = text(
        _PERCENTILE_SQL.replace(":window_days", str(int(window_days))).format(
            table=table, field=field
        )
    )
    result = await db.execute(sql, {"market_ids": list(market_ids)})

    out: dict[str, float | None] = {}
    for mid, percentile, point_count, day_count in result.all():
        if int(point_count or 0) < _MIN_POINTS or int(day_count or 0) < _MIN_DAYS:
            out[mid] = None
        else:
            out[mid] = float(percentile) if percentile is not None else None

    # Markets not returned by the query (no data) → None.
    for mid in market_ids:
        if mid not in out:
            out[mid] = None

    return out


def _percentile_to_rank_label(percentile: float, window_days: int) -> str:
    """Convert a 0..1 percentile to a human-readable rank string."""
    pct_int = round(percentile * 100)
    if pct_int >= 99:
        return f"99th percentile ({window_days}d)"
    if pct_int >= 95:
        return f"top 5% ({window_days}d)"
    if pct_int >= 90:
        return f"top 10% ({window_days}d)"
    if pct_int >= 75:
        return f"top 25% ({window_days}d)"
    if pct_int >= 50:
        return f"above median ({window_days}d)"
    if pct_int >= 25:
        return f"below median ({window_days}d)"
    return f"bottom 25% ({window_days}d)"


async def get_historical_rank(
    db: AsyncSession,
    market_ids: set[str],
    table: str,
    field: str,
    window_days: int = 90,
) -> dict[str, str | None]:
    """Return per-market human-readable rank string (e.g. '99th percentile (90d)').

    Returns None for markets with insufficient history.
    """
    percentiles = await get_percentile(db, market_ids, table, field, window_days)
    out: dict[str, str | None] = {}
    for mid, pct in percentiles.items():
        out[mid] = _percentile_to_rank_label(pct, window_days) if pct is not None else None
    return out

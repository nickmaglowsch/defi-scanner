"""Yield history aggregation — batched per-market windowed aggregates."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

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

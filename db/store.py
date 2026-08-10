"""SQLite persistence layer."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator, Optional

from config import BASE_DIR, cfg


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or cfg.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_conn(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    conn = _connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[Path] = None) -> None:
    schema = (BASE_DIR / "db" / "schema.sql").read_text(encoding="utf-8")
    with get_conn(db_path) as conn:
        conn.executescript(schema)


def upsert_universe(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO universe(symbol, name, industry, updated_at)
            VALUES (:symbol, :name, :industry, :updated_at)
            ON CONFLICT(symbol) DO UPDATE SET
                name=excluded.name,
                industry=excluded.industry,
                updated_at=excluded.updated_at
            """,
            [
                {
                    "symbol": r["symbol"],
                    "name": r.get("name") or r["symbol"],
                    "industry": r.get("industry"),
                    "updated_at": now,
                }
                for r in rows
            ],
        )
    return len(rows)


def list_symbols() -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT symbol FROM universe ORDER BY symbol"
        ).fetchall()
    return [r["symbol"] for r in rows]


def get_symbol_names() -> dict[str, str]:
    with get_conn() as conn:
        rows = conn.execute("SELECT symbol, name FROM universe").fetchall()
    return {r["symbol"]: r["name"] for r in rows}


def insert_bars_1m(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO bars_1m(
                ts, symbol, price, change_pct, volume, volume_cum,
                open_price, high, low, prev_close
            ) VALUES (
                :ts, :symbol, :price, :change_pct, :volume, :volume_cum,
                :open_price, :high, :low, :prev_close
            )
            ON CONFLICT(ts, symbol) DO UPDATE SET
                price=excluded.price,
                change_pct=excluded.change_pct,
                volume=excluded.volume,
                volume_cum=excluded.volume_cum,
                open_price=excluded.open_price,
                high=excluded.high,
                low=excluded.low,
                prev_close=excluded.prev_close
            """,
            rows,
        )
    return len(rows)


def latest_bars_1m() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT b.*
            FROM bars_1m b
            INNER JOIN (
                SELECT symbol, MAX(ts) AS ts FROM bars_1m GROUP BY symbol
            ) t ON b.symbol = t.symbol AND b.ts = t.ts
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_bars_1m_for_day(symbol: str, day: date) -> list[dict[str, Any]]:
    prefix = day.isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM bars_1m
            WHERE symbol = ? AND ts LIKE ?
            ORDER BY ts
            """,
            (symbol, f"{prefix}%"),
        ).fetchall()
    return [dict(r) for r in rows]


def avg_volume_cum_same_tod(symbol: str, tod: str, lookback_days: int = 20) -> Optional[float]:
    """Average cumulative volume at same time-of-day over recent days (excludes today)."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT volume_cum
            FROM bars_1m
            WHERE symbol = ?
              AND TIME(ts) <= ?
              AND DATE(ts) < DATE('now', 'localtime')
              AND ts IN (
                SELECT MAX(ts)
                FROM bars_1m
                WHERE symbol = ?
                  AND TIME(ts) <= ?
                  AND DATE(ts) < DATE('now', 'localtime')
                GROUP BY DATE(ts)
              )
            ORDER BY ts DESC
            LIMIT ?
            """,
            (symbol, tod, symbol, tod, lookback_days),
        ).fetchall()
    vals = [r["volume_cum"] for r in rows if r["volume_cum"] is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def insert_bars_1d(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO bars_1d(trade_date, symbol, open, high, low, close, volume)
            VALUES (:trade_date, :symbol, :open, :high, :low, :close, :volume)
            ON CONFLICT(trade_date, symbol) DO UPDATE SET
                open=excluded.open,
                high=excluded.high,
                low=excluded.low,
                close=excluded.close,
                volume=excluded.volume
            """,
            rows,
        )
    return len(rows)


def get_bars_1d(symbol: str, limit: int = 120) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM bars_1d
            WHERE symbol = ?
            ORDER BY trade_date DESC
            LIMIT ?
            """,
            (symbol, limit),
        ).fetchall()
    return list(reversed([dict(r) for r in rows]))


def insert_institutional(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO institutional_daily(
                trade_date, symbol, foreign_net, trust_net, dealer_net
            ) VALUES (
                :trade_date, :symbol, :foreign_net, :trust_net, :dealer_net
            )
            ON CONFLICT(trade_date, symbol) DO UPDATE SET
                foreign_net=excluded.foreign_net,
                trust_net=excluded.trust_net,
                dealer_net=excluded.dealer_net
            """,
            rows,
        )
    return len(rows)


def get_institutional(trade_date: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM institutional_daily WHERE trade_date = ?
            """,
            (trade_date,),
        ).fetchall()
    return [dict(r) for r in rows]


def latest_institutional_date() -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT trade_date FROM institutional_daily ORDER BY trade_date DESC LIMIT 1"
        ).fetchone()
    return row["trade_date"] if row else None


def insert_events(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT OR IGNORE INTO events(ts, symbol, event_type, title, severity)
            VALUES (:ts, :symbol, :event_type, :title, :severity)
            """,
            rows,
        )
    return len(rows)


def get_events_since(since_iso: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM events WHERE ts >= ? ORDER BY severity DESC, ts DESC
            """,
            (since_iso,),
        ).fetchall()
    return [dict(r) for r in rows]


def insert_signals(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    prepared = []
    for r in rows:
        prepared.append(
            {
                "ts": r["ts"],
                "symbol": r["symbol"],
                "category": r["category"],
                "rule_id": r["rule_id"],
                "score": r["score"],
                "payload_json": (
                    r["payload_json"]
                    if isinstance(r.get("payload_json"), str)
                    else json.dumps(r.get("payload") or r.get("payload_json") or {}, ensure_ascii=False)
                ),
            }
        )
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO signals(ts, symbol, category, rule_id, score, payload_json)
            VALUES (:ts, :symbol, :category, :rule_id, :score, :payload_json)
            """,
            prepared,
        )
    return len(prepared)


def signal_already_digested_today(symbol: str, rule_id: str, day: date) -> bool:
    """True if this symbol+rule already exists today (pending or digested)."""
    prefix = day.isoformat()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM signals
            WHERE symbol = ? AND rule_id = ?
              AND ts LIKE ?
            LIMIT 1
            """,
            (symbol, rule_id, f"{prefix}%"),
        ).fetchone()
    return row is not None


def pending_signals(since_iso: str, until_iso: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM signals
            WHERE included_in_digest_at IS NULL
              AND ts >= ? AND ts < ?
            ORDER BY score DESC, ts DESC
            """,
            (since_iso, until_iso),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["payload"] = json.loads(d["payload_json"] or "{}")
        except json.JSONDecodeError:
            d["payload"] = {}
        out.append(d)
    return out


def all_pending_signals_for_day(day: date) -> list[dict[str, Any]]:
    prefix = day.isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM signals
            WHERE included_in_digest_at IS NULL
              AND ts LIKE ?
            ORDER BY score DESC, ts DESC
            """,
            (f"{prefix}%",),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["payload"] = json.loads(d["payload_json"] or "{}")
        except json.JSONDecodeError:
            d["payload"] = {}
        out.append(d)
    return out


def mark_signals_digested(signal_ids: list[int], digested_at: str) -> None:
    if not signal_ids:
        return
    with get_conn() as conn:
        conn.executemany(
            """
            UPDATE signals SET included_in_digest_at = ?
            WHERE id = ?
            """,
            [(digested_at, sid) for sid in signal_ids],
        )


def digest_already_sent(digest_type: str, hour_bucket: str) -> bool:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM digest_log
            WHERE digest_type = ? AND hour_bucket = ?
            """,
            (digest_type, hour_bucket),
        ).fetchone()
    return row is not None


def log_digest(
    digest_type: str,
    hour_bucket: str,
    sent_at: str,
    signal_count: int,
    message_id: str = "",
) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO digest_log(digest_type, hour_bucket, sent_at, signal_count, message_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(digest_type, hour_bucket) DO UPDATE SET
                sent_at=excluded.sent_at,
                signal_count=excluded.signal_count,
                message_id=excluded.message_id
            """,
            (digest_type, hour_bucket, sent_at, signal_count, message_id),
        )


def signals_for_day(day: date, pending_only: bool = False) -> list[dict[str, Any]]:
    prefix = day.isoformat()
    sql = """
        SELECT * FROM signals
        WHERE ts LIKE ?
    """
    if pending_only:
        sql += " AND included_in_digest_at IS NULL"
    sql += " ORDER BY score DESC, ts DESC"
    with get_conn() as conn:
        rows = conn.execute(sql, (f"{prefix}%",)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["payload"] = json.loads(d["payload_json"] or "{}")
        except json.JSONDecodeError:
            d["payload"] = {}
        out.append(d)
    return out


def latest_bar_ts() -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute("SELECT MAX(ts) AS ts FROM bars_1m").fetchone()
    return row["ts"] if row and row["ts"] else None


def count_bars_1m() -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM bars_1m").fetchone()
    return int(row["n"] if row else 0)


def recent_digest_log(limit: int = 10) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM digest_log
            ORDER BY sent_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def get_bar_for_symbol(symbol: str) -> Optional[dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM bars_1m
            WHERE symbol = ?
            ORDER BY ts DESC
            LIMIT 1
            """,
            (symbol,),
        ).fetchone()
    return dict(row) if row else None


# --- US market ---

def insert_us_bars(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO us_bars(
                ts, symbol, price, change_pct, volume,
                open_price, high, low, prev_close
            ) VALUES (
                :ts, :symbol, :price, :change_pct, :volume,
                :open_price, :high, :low, :prev_close
            )
            ON CONFLICT(ts, symbol) DO UPDATE SET
                price=excluded.price,
                change_pct=excluded.change_pct,
                volume=excluded.volume,
                open_price=excluded.open_price,
                high=excluded.high,
                low=excluded.low,
                prev_close=excluded.prev_close
            """,
            rows,
        )
    return len(rows)


def latest_us_bars() -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT b.*
            FROM us_bars b
            INNER JOIN (
                SELECT symbol, MAX(ts) AS ts FROM us_bars GROUP BY symbol
            ) t ON b.symbol = t.symbol AND b.ts = t.ts
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_us_bar(symbol: str) -> Optional[dict[str, Any]]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT * FROM us_bars
            WHERE symbol = ?
            ORDER BY ts DESC
            LIMIT 1
            """,
            (symbol,),
        ).fetchone()
    return dict(row) if row else None


def latest_us_bar_ts() -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute("SELECT MAX(ts) AS ts FROM us_bars").fetchone()
    return row["ts"] if row and row["ts"] else None


def insert_us_signals(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    prepared = []
    for r in rows:
        prepared.append(
            {
                "ts": r["ts"],
                "symbol": r["symbol"],
                "category": r["category"],
                "rule_id": r["rule_id"],
                "score": r["score"],
                "payload_json": (
                    r["payload_json"]
                    if isinstance(r.get("payload_json"), str)
                    else json.dumps(
                        r.get("payload") or r.get("payload_json") or {},
                        ensure_ascii=False,
                    )
                ),
            }
        )
    with get_conn() as conn:
        conn.executemany(
            """
            INSERT INTO us_signals(ts, symbol, category, rule_id, score, payload_json)
            VALUES (:ts, :symbol, :category, :rule_id, :score, :payload_json)
            """,
            prepared,
        )
    return len(prepared)


def us_signal_exists_today(symbol: str, rule_id: str, day: date) -> bool:
    prefix = day.isoformat()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM us_signals
            WHERE symbol = ? AND rule_id = ? AND ts LIKE ?
            LIMIT 1
            """,
            (symbol, rule_id, f"{prefix}%"),
        ).fetchone()
    return row is not None


def us_signals_for_day(day: date, pending_only: bool = False) -> list[dict[str, Any]]:
    prefix = day.isoformat()
    sql = "SELECT * FROM us_signals WHERE ts LIKE ?"
    if pending_only:
        sql += " AND included_in_digest_at IS NULL"
    sql += " ORDER BY score DESC, ts DESC"
    with get_conn() as conn:
        rows = conn.execute(sql, (f"{prefix}%",)).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["payload"] = json.loads(d["payload_json"] or "{}")
        except json.JSONDecodeError:
            d["payload"] = {}
        out.append(d)
    return out


def us_pending_signals(since_iso: str, until_iso: str) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT * FROM us_signals
            WHERE included_in_digest_at IS NULL
              AND ts >= ? AND ts < ?
            ORDER BY score DESC, ts DESC
            """,
            (since_iso, until_iso),
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["payload"] = json.loads(d["payload_json"] or "{}")
        except json.JSONDecodeError:
            d["payload"] = {}
        out.append(d)
    return out


def mark_us_signals_digested(signal_ids: list[int], digested_at: str) -> None:
    if not signal_ids:
        return
    with get_conn() as conn:
        conn.executemany(
            """
            UPDATE us_signals SET included_in_digest_at = ?
            WHERE id = ?
            """,
            [(digested_at, sid) for sid in signal_ids],
        )

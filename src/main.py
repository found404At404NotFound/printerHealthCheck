import os
import time
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine, text

DB_URL = os.environ["DB_URL"]
engine = create_engine(DB_URL, pool_pre_ping=True)

STALE_SECONDS = 6
RUN_FOR_SECONDS = 55   # stay under Appwrite's 60s default timeout


def check_health():
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=STALE_SECONDS)

    with engine.begin() as conn:
        result = conn.execute(
            text("""
                UPDATE printer
                SET "AVAILABLE" = ("LAST_PING" >= :cutoff)
                WHERE "ALLOW_OVERWRITE" = true
                RETURNING
                    "PRINTER_ID",
                    "AVAILABLE",
                    "LAST_PING"
            """),
            {"cutoff": cutoff}
        )
        return [
            {
                "printer_id": row[0],
                "available": row[1],
                "last_ping": row[2].isoformat() if row[2] else None
            }
            for row in result.fetchall()
        ]


def main(context):
    start = time.monotonic()
    updates = 0
    try:
        while time.monotonic() - start < RUN_FOR_SECONDS:
            check_health()
            updates += 1
            time.sleep(1)

        return context.res.json({
            "status": "ok",
            "updates_run": updates,
            "duration": round(time.monotonic() - start, 2)
        })

    except Exception as e:
        return context.res.json({
            "status": "error",
            "message": str(e)
        }, 500)

import os
import time
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine, text

DB_URL = os.environ["DB_URL"]

engine = create_engine(DB_URL, pool_pre_ping=True)

STALE_SECONDS = 30


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
            {
                "cutoff": cutoff
            }
        )

        return [
            {
                "printer_id": row[0],
                "available": row[1],
                "last_ping": row[2].isoformat()
                if row[2] else None
            }
            for row in result.fetchall()
        ]


def main(context):
    try:
        results = []

        # Run health check 6 times
        # once every 10 seconds
        for i in range(6):
            printers = check_health()

            results.append({
                "check": i + 1,
                "printers": printers
            })

            if i < 5:
                time.sleep(10)

        return context.res.json({
            "status": "ok",
            "checks": results
        })

    except Exception as e:
        return context.res.json({
            "status": "error",
            "message": str(e)
        }, 500)

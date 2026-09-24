import os
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine, text

DB_URL = os.environ["DB_URL"]

engine = create_engine(DB_URL, pool_pre_ping=True)

# Printer is considered offline if no heartbeat for this long
STALE_SECONDS = 30


def main(context):
    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(seconds=STALE_SECONDS)

        with engine.begin() as conn:

            # Only printers with ALLOW_OVERWRITE = true
            # can be changed automatically.
            result = conn.execute(
                text("""
                    UPDATE printer
                    SET "AVAILABLE" = (
                        "LAST_PING" >= :cutoff
                    )
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

            printers = [
                {
                    "printer_id": row[0],
                    "available": row[1],
                    "last_ping": row[2].isoformat()
                    if row[2] else None
                }
                for row in result.fetchall()
            ]

        return context.res.json({
            "status": "ok",
            "checked_at": now.isoformat(),
            "printers": printers
        })

    except Exception as e:
        return context.res.json(
            {
                "status": "error",
                "message": str(e)
            },
            500
        )

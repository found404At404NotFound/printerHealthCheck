import os
import requests

from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker


# --------------------------------------
# Database
# --------------------------------------

DB_URL = os.environ["DB_URL"]

engine = create_engine(DB_URL)
Session = sessionmaker(bind=engine)

Base = declarative_base()


# --------------------------------------
# Printer Model
# --------------------------------------

class Printer(Base):
    __tablename__ = "printer"

    ID = Column(Integer, primary_key=True, autoincrement=True)

    PRINTER_NAME = Column(String(100), nullable=False)
    BLOCK = Column(String(50), nullable=False)
    PRINTER_ID = Column(String(15), nullable=False, unique=True)
    PRINTER_LOCATION = Column(String(200), nullable=False)
    ENDPOINT_URL = Column(String(300), nullable=False)
    PASSWORD = Column(String(256), nullable=False)

    AVAILABLE = Column(Boolean, default=True)
    ALLOW_OVERWRITE = Column(Boolean, default=False)

    TOTAL_PRINTS = Column(Integer, default=0)


# --------------------------------------
# Appwrite Function
# --------------------------------------

def main(context):

    session = Session()

    checked = 0
    updated = 0
    skipped = 0

    try:

        printers = session.query(Printer).all()

        for printer in printers:

            # Don't overwrite manual availability setting
            if not printer.ALLOW_OVERWRITE:
                skipped += 1
                continue

            checked += 1

            try:

                response = requests.get(
                    printer.ENDPOINT_URL.rstrip("/") + "/health",
                    timeout=10
                )

                printer.AVAILABLE = response.status_code == 200

            except requests.RequestException:

                printer.AVAILABLE = False

            updated += 1

        session.commit()

        return context.res.json({
            "status": "success",
            "checked": checked,
            "updated": updated,
            "skipped": skipped
        })

    except Exception as e:

        session.rollback()

        return context.res.json({
            "status": "error",
            "message": str(e)
        }, 500)

    finally:

        session.close()

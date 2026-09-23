
import os
import socket
import time
import requests

from sqlalchemy import create_engine, Column, Integer, String, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker


# ======================================
# CONFIGURATION
# ======================================

DB_URL = os.environ.get("DB_URL")

if not DB_URL:
    raise RuntimeError("DB_URL environment variable is missing")


# ======================================
# DATABASE
# ======================================

print("=" * 60)
print("CAMPUSPRINTER HEALTH CHECK")
print("=" * 60)

print("[DB] Creating SQLAlchemy engine...")

engine = create_engine(
    DB_URL,
    pool_pre_ping=True,
    connect_args={
        "connect_timeout": 10
    }
)

Session = sessionmaker(bind=engine)

Base = declarative_base()


# ======================================
# PRINTER MODEL
# ======================================

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


# ======================================
# HEALTH CHECK
# ======================================

def main(context):

    print("")
    print("[START] Function execution started")
    print("[START] Python:", __import__("sys").version)

    session = Session()

    checked = 0
    updated = 0
    skipped = 0

    results = []

    try:

        # --------------------------------------
        # DATABASE TEST
        # --------------------------------------

        print("")
        print("-" * 60)
        print("[DB] Testing database connection...")
        print("-" * 60)

        try:
            connection = engine.connect()
            print("[DB] Connection successful")
            connection.close()

        except Exception as e:
            print("[DB] CONNECTION FAILED")
            print("[DB] Error:", repr(e))
            raise


        # --------------------------------------
        # GET PRINTERS
        # --------------------------------------

        print("")
        print("-" * 60)
        print("[DB] Loading printers...")
        print("-" * 60)

        printers = session.query(Printer).all()

        print(f"[DB] Found {len(printers)} printer(s)")

        if not printers:
            print("[DB] WARNING: No printers found!")


        # ======================================
        # CHECK EACH PRINTER
        # ======================================

        for printer in printers:

            print("")
            print("=" * 60)
            print(f"PRINTER: {printer.PRINTER_ID}")
            print("=" * 60)

            print("[INFO] ID:", printer.ID)
            print("[INFO] Name:", printer.PRINTER_NAME)
            print("[INFO] Block:", printer.BLOCK)
            print("[INFO] Location:", printer.PRINTER_LOCATION)
            print("[INFO] Endpoint:", printer.ENDPOINT_URL)
            print("[INFO] Current AVAILABLE:", printer.AVAILABLE)
            print("[INFO] ALLOW_OVERWRITE:", printer.ALLOW_OVERWRITE)

            # --------------------------------------
            # MANUAL OVERRIDE
            # --------------------------------------

            if not printer.ALLOW_OVERWRITE:

                print("[SKIP] ALLOW_OVERWRITE is FALSE")
                print("[SKIP] AVAILABLE will NOT be changed")

                skipped += 1

                results.append({
                    "printer_id": printer.PRINTER_ID,
                    "status": "skipped",
                    "reason": "ALLOW_OVERWRITE=false"
                })

                continue


            checked += 1

            # --------------------------------------
            # BUILD HEALTH URL
            # --------------------------------------

            endpoint = printer.ENDPOINT_URL.rstrip("/")
            health_url = endpoint + "/health"

            print("[HTTP] Endpoint:", endpoint)
            print("[HTTP] Health URL:", health_url)


            # --------------------------------------
            # DNS TEST
            # --------------------------------------

            try:

                hostname = health_url.split("//", 1)[1].split("/", 1)[0]

                print("[DNS] Hostname:", hostname)
                print("[DNS] Resolving hostname...")

                dns_start = time.time()

                dns_result = socket.gethostbyname_ex(hostname)

                dns_time = round(
                    (time.time() - dns_start) * 1000,
                    2
                )

                print("[DNS] SUCCESS")
                print("[DNS] Canonical name:", dns_result[0])
                print("[DNS] Aliases:", dns_result[1])
                print("[DNS] Addresses:", dns_result[2])
                print("[DNS] Time:", dns_time, "ms")

            except socket.gaierror as e:

                print("[DNS] FAILED")
                print("[DNS] Error:", repr(e))

                printer.AVAILABLE = False

                updated += 1

                results.append({
                    "printer_id": printer.PRINTER_ID,
                    "status": "offline",
                    "reason": "DNS failure",
                    "error": repr(e)
                })

                continue

            except Exception as e:

                print("[DNS] Unexpected error")
                print("[DNS] Error:", repr(e))


            # --------------------------------------
            # HTTP HEALTH CHECK
            # --------------------------------------

            print("[HTTP] Sending GET request...")
            print("[HTTP] Timeout: 10 seconds")

            start_time = time.time()

            try:

                response = requests.get(
                    health_url,
                    timeout=10
                )

                elapsed = round(
                    (time.time() - start_time) * 1000,
                    2
                )

                print("[HTTP] REQUEST SUCCESS")
                print("[HTTP] Status code:", response.status_code)
                print("[HTTP] Response time:", elapsed, "ms")
                print("[HTTP] Response headers:", dict(response.headers))

                body = response.text[:1000]

                print("[HTTP] Response body:", repr(body))

                if response.status_code == 200:

                    print("[RESULT] PRINTER ONLINE")

                    printer.AVAILABLE = True

                    results.append({
                        "printer_id": printer.PRINTER_ID,
                        "status": "online",
                        "http_status": response.status_code,
                        "response_time_ms": elapsed
                    })

                else:

                    print("[RESULT] PRINTER OFFLINE")
                    print(
                        "[RESULT] Unexpected HTTP status:",
                        response.status_code
                    )

                    printer.AVAILABLE = False

                    results.append({
                        "printer_id": printer.PRINTER_ID,
                        "status": "offline",
                        "http_status": response.status_code,
                        "response_time_ms": elapsed,
                        "response": body
                    })


            # --------------------------------------
            # REQUEST EXCEPTIONS
            # --------------------------------------

            except requests.exceptions.Timeout as e:

                elapsed = round(
                    (time.time() - start_time) * 1000,
                    2
                )

                print("[HTTP] TIMEOUT")
                print("[HTTP] Time:", elapsed, "ms")
                print("[HTTP] Error:", repr(e))

                printer.AVAILABLE = False

                results.append({
                    "printer_id": printer.PRINTER_ID,
                    "status": "offline",
                    "reason": "timeout",
                    "error": repr(e)
                })


            except requests.exceptions.ConnectionError as e:

                elapsed = round(
                    (time.time() - start_time) * 1000,
                    2
                )

                print("[HTTP] CONNECTION ERROR")
                print("[HTTP] Time:", elapsed, "ms")
                print("[HTTP] Error:", repr(e))

                printer.AVAILABLE = False

                results.append({
                    "printer_id": printer.PRINTER_ID,
                    "status": "offline",
                    "reason": "connection_error",
                    "error": repr(e)
                })


            except requests.exceptions.SSLError as e:

                elapsed = round(
                    (time.time() - start_time) * 1000,
                    2
                )

                print("[HTTP] SSL ERROR")
                print("[HTTP] Time:", elapsed, "ms")
                print("[HTTP] Error:", repr(e))

                printer.AVAILABLE = False

                results.append({
                    "printer_id": printer.PRINTER_ID,
                    "status": "offline",
                    "reason": "ssl_error",
                    "error": repr(e)
                })


            except requests.exceptions.RequestException as e:

                elapsed = round(
                    (time.time() - start_time) * 1000,
                    2
                )

                print("[HTTP] REQUEST ERROR")
                print("[HTTP] Time:", elapsed, "ms")
                print("[HTTP] Error:", repr(e))

                printer.AVAILABLE = False

                results.append({
                    "printer_id": printer.PRINTER_ID,
                    "status": "offline",
                    "reason": "request_error",
                    "error": repr(e)
                })


            except Exception as e:

                elapsed = round(
                    (time.time() - start_time) * 1000,
                    2
                )

                print("[HTTP] UNKNOWN ERROR")
                print("[HTTP] Time:", elapsed, "ms")
                print("[HTTP] Error:", repr(e))

                printer.AVAILABLE = False

                results.append({
                    "printer_id": printer.PRINTER_ID,
                    "status": "offline",
                    "reason": "unknown_error",
                    "error": repr(e)
                })


            updated += 1


        # ======================================
        # COMMIT
        # ======================================

        print("")
        print("=" * 60)
        print("[DB] Saving availability changes...")
        print("=" * 60)

        session.commit()

        print("[DB] COMMIT SUCCESS")


        # ======================================
        # VERIFY DATABASE VALUES
        # ======================================

        print("")
        print("=" * 60)
        print("[DB] VERIFYING FINAL VALUES")
        print("=" * 60)

        session.expire_all()

        final_printers = session.query(Printer).all()

        for printer in final_printers:

            print(
                f"[FINAL] {printer.PRINTER_ID} "
                f"AVAILABLE={printer.AVAILABLE} "
                f"ALLOW_OVERWRITE={printer.ALLOW_OVERWRITE}"
            )


        # ======================================
        # SUMMARY
        # ======================================

        print("")
        print("=" * 60)
        print("FINAL SUMMARY")
        print("=" * 60)

        print("[SUMMARY] Total printers:", len(printers))
        print("[SUMMARY] Checked:", checked)
        print("[SUMMARY] Updated:", updated)
        print("[SUMMARY] Skipped:", skipped)

        for result in results:
            print("[SUMMARY]", result)

        print("=" * 60)
        print("[DONE] Health check completed")
        print("=" * 60)


        return context.res.json({
            "status": "success",
            "checked": checked,
            "updated": updated,
            "skipped": skipped,
            "results": results
        })


    except Exception as e:

        print("")
        print("=" * 60)
        print("[FATAL] FUNCTION FAILED")
        print("=" * 60)

        print("[FATAL] Error type:", type(e).__name__)
        print("[FATAL] Error:", repr(e))

        session.rollback()

        return context.res.json({
            "status": "error",
            "error_type": type(e).__name__,
            "message": str(e),
            "results": results
        }, 500)


    finally:

        print("[DB] Closing database session")

        session.close()

        print("[DONE] Session closed")

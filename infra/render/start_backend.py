"""Listener TLS directo: sin confiar en cabeceras de un proxy TLS terminador."""
import os
from pathlib import Path
import uvicorn


def main():
    cert, key = os.getenv("TLS_CERT_FILE"), os.getenv("TLS_KEY_FILE")
    if not cert or not key or not Path(cert).is_file() or not Path(key).is_file():
        raise SystemExit("Configura certificado y clave del listener TLS privado.")
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", "10000")),
                ssl_certfile=cert, ssl_keyfile=key, proxy_headers=False, workers=1)


if __name__ == "__main__":
    main()

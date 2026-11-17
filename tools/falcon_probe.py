#!/usr/bin/env python3
"""Falcon-API-Probe: zeigt, welche Endpunkte dein Laser beantwortet.

Nur lesende Aufrufe (GET) – es werden KEINE Befehle gesendet.
Aufruf:  python3 falcon_probe.py 192.168.1.50
"""

import sys
import urllib.error
import urllib.request

PORTS = (8080, 80)
PATHS = (
    "/work/progress",
    "/work/state", "/work/status", "/work/getState",
    "/device/state", "/device/status", "/device/getState",
    "/device/info", "/device/getInfo", "/info", "/work/info",
    "/media/getCapturePhoto",
)


def main(host: str) -> None:
    for port in PORTS:
        print(f"\n=== {host}:{port} ===")
        for path in PATHS:
            url = f"http://{host}:{port}{path}"
            try:
                with urllib.request.urlopen(url, timeout=4) as r:
                    body = r.read(300)
                    ctype = r.headers.get("Content-Type", "")
                    shown = f"<{len(body)} Bytes {ctype}>" if "image" in ctype else body.decode(errors="replace")
                    print(f"  {r.status}  {path:26} {shown}")
            except urllib.error.HTTPError as e:
                print(f"  {e.code}  {path}")
            except Exception as e:  # noqa: BLE001
                print(f"  --   {path:26} {type(e).__name__}: {e}")
                if path == PATHS[0]:
                    break  # Port antwortet gar nicht


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("Aufruf: python3 falcon_probe.py <IP-des-Lasers>")
    main(sys.argv[1])

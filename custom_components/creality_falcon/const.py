"""Konstanten für die Creality-Falcon-Integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "creality_falcon"
MANUFACTURER: Final = "Creality"
DEFAULT_MODEL: Final = "Falcon T1"
DEFAULT_NAME: Final = "Falcon T1"

CONF_CAMERA_PORT: Final = "camera_port"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_PORT: Final = 8080
DEFAULT_CAMERA_PORT: Final = 8080
DEFAULT_SCAN_INTERVAL: Final = 5  # Sekunden
CANDIDATE_PORTS: Final = (8080, 80)

# --- HTTP-Endpunkte -------------------------------------------------------
# Belegt durch LightBurn-Forum (Falcon A1C/A1 Pro/T1) und KerfDesk:
PATH_PROGRESS: Final = "/work/progress"
PATH_START: Final = "/work/start"
PATH_STOP: Final = "/work/stop"
PATH_FRAME: Final = "/work/preview"
PATH_HOME: Final = "/work/home"
PATH_AUTOFOCUS: Final = "/work/probe"
PATH_ASSIST_LIGHT: Final = "/device/assistLight"
PATH_LIGHT: Final = "/device/setLight"
PATH_SNAPSHOT: Final = "/media/getCapturePhoto"

# Der Pfad für den Gerätezustand ({"errorcode":0,"payload":{"state":4}})
# ist öffentlich nicht dokumentiert. Die Integration probiert diese
# Kandidaten der Reihe nach und merkt sich den ersten, der antwortet.
STATE_PATH_CANDIDATES: Final = (
    "/work/state",
    "/work/status",
    "/device/state",
    "/device/status",
    "/work/getState",
    "/device/getState",
)

# Bisher beobachtet: state 4 während eines Alarms. Weitere Codes sind
# nicht dokumentiert und werden roh im Sensor "Zustandscode" angezeigt.
STATE_CODE_ALARM: Final = 4

STATUS_OFFLINE: Final = "offline"
STATUS_READY: Final = "bereit"
STATUS_RUNNING: Final = "laeuft"
STATUS_ALARM: Final = "alarm"
STATUS_OPTIONS: Final = [STATUS_READY, STATUS_RUNNING, STATUS_ALARM]

EVENT_JOB_STARTED: Final = f"{DOMAIN}_job_started"
EVENT_JOB_FINISHED: Final = f"{DOMAIN}_job_finished"

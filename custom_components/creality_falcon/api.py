"""Schlanker asynchroner Client für die lokale HTTP-API der Creality Falcons.

Creality dokumentiert diese API nicht. Die Endpunkte stammen aus der
LightBurn-Treiberentwicklung ("Creality Falcon HTTP") und aus KerfDesk.
Antworten haben in der Regel die Form {"errorcode": 0, "payload": {...}}.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import aiohttp

from .const import (
    PATH_ASSIST_LIGHT,
    PATH_AUTOFOCUS,
    PATH_FRAME,
    PATH_HOME,
    PATH_LIGHT,
    PATH_PROGRESS,
    PATH_SNAPSHOT,
    PATH_START,
    PATH_STOP,
    SNAPSHOT_BODY,
    STATE_PATH_CANDIDATES,
)

_LOGGER = logging.getLogger(__name__)

_TIMEOUT = aiohttp.ClientTimeout(total=8)
# Befehle wie Autofokus/Referenzfahrt antworten erst nach der Bewegung
_COMMAND_TIMEOUT = aiohttp.ClientTimeout(total=60)
_SNAPSHOT_TIMEOUT = aiohttp.ClientTimeout(total=20)

_JPEG_MAGIC = b"\xff\xd8"
_PNG_MAGIC = b"\x89PNG"


class FalconError(Exception):
    """Basisfehler."""


class FalconConnectionError(FalconError):
    """Gerät nicht erreichbar."""


class FalconNotSupportedError(FalconError):
    """Endpunkt existiert auf diesem Gerät/dieser Firmware nicht."""


class FalconCommandError(FalconError):
    """Gerät hat einen Fehlercode zurückgegeben."""


def _extract_number(data: Any, keys: tuple[str, ...]) -> float | None:
    """Zahl aus einer Antwort ziehen – egal ob roh, als Text oder in JSON."""
    if isinstance(data, bool):
        return None
    if isinstance(data, (int, float)):
        return float(data)
    if isinstance(data, str):
        try:
            return float(data.strip())
        except ValueError:
            return None
    if isinstance(data, dict):
        if "payload" in data:
            found = _extract_number(data["payload"], keys)
            if found is not None:
                return found
        for key in keys:
            if key in data:
                found = _extract_number(data[key], keys)
                if found is not None:
                    return found
    return None


class FalconApi:
    """HTTP-Client für einen Falcon-Laser."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        port: int,
        camera_port: int | None = None,
    ) -> None:
        self._session = session
        self.host = host
        self.port = port
        self.camera_port = camera_port or port
        self._state_path: str | None = None
        self._state_probed = False
        self._snapshot_method: str | None = None

    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"

    @property
    def state_path(self) -> str | None:
        """Gefundener Pfad für den Gerätezustand (None = keiner gefunden)."""
        return self._state_path

    async def _request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        port: int | None = None,
        timeout: aiohttp.ClientTimeout = _TIMEOUT,
    ) -> Any:
        url = f"http://{self.host}:{port or self.port}{path}"
        try:
            async with self._session.request(
                method, url, json=body, timeout=timeout
            ) as resp:
                if resp.status in (404, 405, 501):
                    raise FalconNotSupportedError(f"{method} {path}: HTTP {resp.status}")
                if resp.status >= 400:
                    raise FalconCommandError(f"{method} {path}: HTTP {resp.status}")
                text = await resp.text()
        except (TimeoutError, aiohttp.ClientError) as err:
            raise FalconConnectionError(f"{url}: {err}") from err

        try:
            data: Any = json.loads(text)
        except ValueError:
            return text

        if isinstance(data, dict):
            code = data.get("errorcode", data.get("code", 0))
            if isinstance(code, int) and code != 0:
                raise FalconCommandError(f"{method} {path}: errorcode {code} ({data})")
        return data

    # ------------------------------------------------------------------ Status
    async def get_progress(self) -> float | None:
        """Fortschritt als Bruchteil 0..1 (z. B. 0.504686)."""
        data = await self._request("GET", PATH_PROGRESS)
        value = _extract_number(data, ("progress", "value", "result", "percent"))
        if value is None:
            _LOGGER.debug("Unerwartete Antwort von %s: %r", PATH_PROGRESS, data)
            return None
        if value > 1.0:  # falls eine Firmware Prozent statt Bruchteil liefert
            value = value / 100.0
        return max(0.0, min(1.0, value))

    async def get_state(self) -> int | None:
        """Numerischen Gerätezustand lesen (Pfad wird beim ersten Mal ermittelt)."""
        if not self._state_probed:
            await self._probe_state_path()
        if self._state_path is None:
            return None
        try:
            data = await self._request("GET", self._state_path)
        except FalconNotSupportedError:
            self._state_path = None
            return None
        value = _extract_number(data, ("state", "status"))
        return int(value) if value is not None else None

    async def _probe_state_path(self) -> None:
        self._state_probed = True
        for path in STATE_PATH_CANDIDATES:
            try:
                data = await self._request("GET", path)
            except FalconConnectionError:
                raise
            except FalconError:
                continue
            if _extract_number(data, ("state", "status")) is not None:
                _LOGGER.info("Falcon %s: Zustands-Endpunkt gefunden: %s", self.host, path)
                self._state_path = path
                return
        _LOGGER.info(
            "Falcon %s: kein Zustands-Endpunkt gefunden, Status wird aus dem Fortschritt abgeleitet",
            self.host,
        )

    # ---------------------------------------------------------------- Befehle
    async def start_job(self) -> None:
        """Den zuletzt hochgeladenen / am Gerät gewählten Job starten."""
        await self._request("GET", PATH_START, timeout=_COMMAND_TIMEOUT)

    async def stop_job(self) -> None:
        await self._request("GET", PATH_STOP, timeout=_COMMAND_TIMEOUT)

    async def frame(self) -> None:
        """Rahmen fahren (läuft ggf. in Schleife bis Stopp)."""
        await self._request("GET", PATH_FRAME, timeout=_COMMAND_TIMEOUT)

    async def home(self) -> None:
        await self._request("POST", PATH_HOME, body={}, timeout=_COMMAND_TIMEOUT)

    async def autofocus(self) -> None:
        await self._request("GET", PATH_AUTOFOCUS, timeout=_COMMAND_TIMEOUT)

    async def set_assist_light(self, on: bool) -> None:
        """Roter Positionslaser (Assist Light 0)."""
        await self._request("POST", PATH_ASSIST_LIGHT, body={"switch": 1 if on else 0})

    async def set_light(self, duty_cycle: int) -> None:
        """Innenbeleuchtung/Lichtleiste, 0..100 %."""
        duty_cycle = max(0, min(100, int(duty_cycle)))
        await self._request("POST", PATH_LIGHT, body={"dutyCycle": duty_cycle})

    async def get_snapshot(self) -> bytes:
        """Einzelbild der Innenraumkamera (JPEG).

        Falcon T1 (per Mitschnitt von Falcon Design Space verifiziert):
            POST /media/getCapturePhoto?from=falcon
            {"exposureValue": -1, "height": 1920, "width": 2560}
        Falcon A1 Pro: GET /media/getCapturePhoto (Fallback).
        Liefert das Gerät JSON statt eines Bildes (z. B. errorcode -1),
        wird ein Fehler ausgelöst statt Müll weiterzugeben.
        """
        base = f"http://{self.host}:{self.camera_port}{PATH_SNAPSHOT}"
        attempts: list[tuple[str, str, dict[str, Any] | None]] = [
            ("POST", f"{base}?from=falcon", SNAPSHOT_BODY),
            ("GET", base, None),
        ]
        if self._snapshot_method == "GET":
            attempts.reverse()

        last_error = ""
        for method, url, body in attempts:
            try:
                async with self._session.request(
                    method, url, json=body, timeout=_SNAPSHOT_TIMEOUT
                ) as resp:
                    if resp.status >= 400:
                        last_error = f"{method}: HTTP {resp.status}"
                        continue
                    data = await resp.read()
            except TimeoutError as err:
                raise FalconConnectionError(f"{url}: Zeitüberschreitung") from err
            except aiohttp.ClientError as err:
                raise FalconConnectionError(f"{url}: {type(err).__name__}: {err}") from err

            if data.startswith(_JPEG_MAGIC) or data.startswith(_PNG_MAGIC):
                self._snapshot_method = method
                return data
            last_error = f"{method}: " + data[:120].decode("utf-8", errors="replace")

        raise FalconNotSupportedError(f"Kamera liefert kein Bild ({last_error})")

"""DataUpdateCoordinator für den Falcon-Laser."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import FalconApi, FalconConnectionError, FalconError
from .const import (
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENT_JOB_FINISHED,
    EVENT_JOB_STARTED,
    STATE_CODE_ALARM,
    STATUS_ALARM,
    STATUS_READY,
    STATUS_RUNNING,
)

_LOGGER = logging.getLogger(__name__)

# Unter dieser Schwelle gilt ein Job als "fertig" (Firmware meldet teils 0.9999...)
_DONE_THRESHOLD = 0.999


@dataclass
class FalconData:
    progress: float | None
    state_code: int | None
    status: str
    job_started: datetime | None
    estimated_end: datetime | None
    last_job_finished: datetime | None
    last_job_duration: timedelta | None


type FalconConfigEntry = ConfigEntry[FalconCoordinator]


class FalconCoordinator(DataUpdateCoordinator[FalconData]):
    """Pollt Fortschritt und Zustand und leitet Job-Ereignisse ab."""

    config_entry: FalconConfigEntry

    def __init__(self, hass: HomeAssistant, entry: FalconConfigEntry, api: FalconApi) -> None:
        interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{api.host}",
            update_interval=timedelta(seconds=interval),
        )
        self.api = api
        self._job_started: datetime | None = None
        # Erster beobachteter Punkt (Zeit, Fortschritt) für die Restzeit-Schätzung,
        # damit ein beim HA-Start bereits laufender Job korrekt hochgerechnet wird.
        self._rate_origin: tuple[datetime, float] | None = None
        self._last_finished: datetime | None = None
        self._last_duration: timedelta | None = None

    async def _async_update_data(self) -> FalconData:
        try:
            progress = await self.api.get_progress()
            state_code = await self.api.get_state()
        except FalconConnectionError as err:
            # Laser aus / nicht im WLAN: laufenden Job nicht als "fertig" werten
            raise UpdateFailed(f"Falcon nicht erreichbar: {err}") from err
        except FalconError as err:
            raise UpdateFailed(str(err)) from err

        now = dt_util.utcnow()
        running = progress is not None and 0.0 < progress < _DONE_THRESHOLD

        if state_code == STATE_CODE_ALARM:
            status = STATUS_ALARM
        elif running:
            status = STATUS_RUNNING
        else:
            status = STATUS_READY

        # --- Job-Übergänge erkennen ---------------------------------------
        if running and self._job_started is None:
            self._job_started = now
            self._rate_origin = (now, progress or 0.0)
            self.hass.bus.async_fire(
                EVENT_JOB_STARTED,
                {"entry_id": self.config_entry.entry_id, "host": self.api.host},
            )
        elif not running and self._job_started is not None:
            completed = progress is not None and progress >= _DONE_THRESHOLD
            self._last_finished = now
            self._last_duration = now - self._job_started
            self.hass.bus.async_fire(
                EVENT_JOB_FINISHED,
                {
                    "entry_id": self.config_entry.entry_id,
                    "host": self.api.host,
                    "completed": completed and status != STATUS_ALARM,
                    "alarm": status == STATUS_ALARM,
                    "duration_s": int(self._last_duration.total_seconds()),
                },
            )
            self._job_started = None
            self._rate_origin = None

        estimated_end = None
        if running and self._rate_origin is not None and progress is not None:
            t0, p0 = self._rate_origin
            elapsed = (now - t0).total_seconds()
            gained = progress - p0
            if elapsed >= 20 and gained > 0.005:
                remaining = elapsed * (1.0 - progress) / gained
                estimated_end = now + timedelta(seconds=remaining)

        return FalconData(
            progress=progress,
            state_code=state_code,
            status=status,
            job_started=self._job_started,
            estimated_end=estimated_end,
            last_job_finished=self._last_finished,
            last_job_duration=self._last_duration,
        )

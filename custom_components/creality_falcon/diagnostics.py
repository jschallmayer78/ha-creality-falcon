"""Diagnosedaten (Einstellungen → Geräte → Falcon → Diagnose herunterladen)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import FalconConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: FalconConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    data = coordinator.data
    return {
        "config": dict(entry.data),
        "options": dict(entry.options),
        "state_endpoint": coordinator.api.state_path,
        "last_update_success": coordinator.last_update_success,
        "data": {k: str(v) for k, v in asdict(data).items()} if data else None,
    }

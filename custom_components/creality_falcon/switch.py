"""Roter Positionslaser (Assist Light)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import FalconError
from .coordinator import FalconConfigEntry
from .entity import FalconEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FalconConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([FalconPointer(entry.runtime_data)])


class FalconPointer(FalconEntity, SwitchEntity):
    _attr_assumed_state = True
    _attr_icon = "mdi:crosshairs-gps"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "pointer")
        self._attr_is_on = False

    async def _set(self, on: bool) -> None:
        try:
            await self.coordinator.api.set_assist_light(on)
        except FalconError as err:
            raise HomeAssistantError(f"Positionslaser: {err}") from err
        self._attr_is_on = on
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set(False)

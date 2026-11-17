"""Innenbeleuchtung (Lichtleiste, dutyCycle 0..100)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .api import FalconError
from .coordinator import FalconConfigEntry
from .entity import FalconEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FalconConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([FalconLight(entry.runtime_data)])


class FalconLight(FalconEntity, LightEntity, RestoreEntity):
    """Kein Lese-Endpunkt bekannt → Zustand wird angenommen (assumed_state)."""

    _attr_assumed_state = True
    _attr_color_mode = ColorMode.BRIGHTNESS
    _attr_supported_color_modes = {ColorMode.BRIGHTNESS}

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "light")
        self._attr_is_on = False
        self._attr_brightness = 255

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_state()) is not None:
            self._attr_is_on = last.state == "on"
            if (b := last.attributes.get(ATTR_BRIGHTNESS)) is not None:
                self._attr_brightness = int(b)

    async def _send(self, duty: int) -> None:
        try:
            await self.coordinator.api.set_light(duty)
        except FalconError as err:
            raise HomeAssistantError(f"Licht konnte nicht geschaltet werden: {err}") from err

    async def async_turn_on(self, **kwargs: Any) -> None:
        brightness = kwargs.get(ATTR_BRIGHTNESS, self._attr_brightness or 255)
        await self._send(max(1, round(brightness * 100 / 255)))
        self._attr_brightness = brightness
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._send(0)
        self._attr_is_on = False
        self.async_write_ha_state()

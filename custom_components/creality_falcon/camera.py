"""Innenraumkamera (Snapshot über :8080/media/getCapturePhoto)."""

from __future__ import annotations

import logging

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import FalconError
from .coordinator import FalconConfigEntry
from .entity import FalconEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FalconConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    async_add_entities([FalconCamera(entry.runtime_data)])


class FalconCamera(FalconEntity, Camera):
    def __init__(self, coordinator) -> None:
        FalconEntity.__init__(self, coordinator, "camera")
        Camera.__init__(self)
        self._last_image: bytes | None = None
        self._warned = False

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        try:
            self._last_image = await self.coordinator.api.get_snapshot()
            self._warned = False
        except FalconError as err:
            if not self._warned:
                _LOGGER.warning("Falcon-Kamerabild nicht abrufbar: %s", err)
                self._warned = True
            else:
                _LOGGER.debug("Falcon-Kamerabild nicht abrufbar: %s", err)
            return None
        return self._last_image

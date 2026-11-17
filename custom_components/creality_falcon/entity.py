"""Gemeinsame Basisklasse für Falcon-Entitäten."""

from __future__ import annotations

from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_MODEL, DEFAULT_NAME, DOMAIN, MANUFACTURER
from .coordinator import FalconCoordinator


class FalconEntity(CoordinatorEntity[FalconCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: FalconCoordinator, key: str) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data.get(CONF_NAME, DEFAULT_NAME),
            manufacturer=MANUFACTURER,
            model=DEFAULT_MODEL,
            configuration_url=coordinator.api.base_url,
        )

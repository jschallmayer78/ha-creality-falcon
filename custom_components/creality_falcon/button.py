"""Tasten: Start, Stopp, Rahmen, Home, Autofokus."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .api import FalconApi, FalconError
from .coordinator import FalconConfigEntry
from .entity import FalconEntity


@dataclass(frozen=True, kw_only=True)
class FalconButtonDescription(ButtonEntityDescription):
    press_fn: Callable[[FalconApi], Awaitable[None]]


BUTTONS: tuple[FalconButtonDescription, ...] = (
    # Start ist aus Sicherheitsgründen standardmäßig deaktiviert:
    # ein Laserjob sollte nur gestartet werden, wenn jemand am Gerät ist.
    FalconButtonDescription(
        key="start",
        icon="mdi:play",
        entity_registry_enabled_default=False,
        press_fn=lambda api: api.start_job(),
    ),
    FalconButtonDescription(key="stop", icon="mdi:stop", press_fn=lambda api: api.stop_job()),
    FalconButtonDescription(
        key="frame", icon="mdi:vector-square", press_fn=lambda api: api.frame()
    ),
    FalconButtonDescription(key="home", icon="mdi:home-import-outline", press_fn=lambda api: api.home()),
    FalconButtonDescription(
        key="autofocus", icon="mdi:image-filter-center-focus", press_fn=lambda api: api.autofocus()
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FalconConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(FalconButton(coordinator, desc) for desc in BUTTONS)


class FalconButton(FalconEntity, ButtonEntity):
    entity_description: FalconButtonDescription

    def __init__(self, coordinator, description: FalconButtonDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        try:
            await self.entity_description.press_fn(self.coordinator.api)
        except FalconError as err:
            raise HomeAssistantError(f"Falcon-Befehl fehlgeschlagen: {err}") from err
        await self.coordinator.async_request_refresh()

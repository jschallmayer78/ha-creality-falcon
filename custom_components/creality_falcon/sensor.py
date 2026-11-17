"""Sensoren: Fortschritt, Status, Zustandscode, Zeiten."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import STATUS_OPTIONS
from .coordinator import FalconConfigEntry, FalconData
from .entity import FalconEntity


@dataclass(frozen=True, kw_only=True)
class FalconSensorDescription(SensorEntityDescription):
    value_fn: Callable[[FalconData], Any]


SENSORS: tuple[FalconSensorDescription, ...] = (
    FalconSensorDescription(
        key="status",
        device_class=SensorDeviceClass.ENUM,
        options=STATUS_OPTIONS,
        value_fn=lambda d: d.status,
    ),
    FalconSensorDescription(
        key="progress",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda d: None if d.progress is None else round(d.progress * 100, 2),
    ),
    FalconSensorDescription(
        key="job_started",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.job_started,
    ),
    FalconSensorDescription(
        key="estimated_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.estimated_end,
    ),
    FalconSensorDescription(
        key="last_job_finished",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: d.last_job_finished,
    ),
    FalconSensorDescription(
        key="last_job_duration",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        suggested_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=lambda d: None
        if d.last_job_duration is None
        else int(d.last_job_duration.total_seconds()),
    ),
    FalconSensorDescription(
        key="state_code",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.state_code,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FalconConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(FalconSensor(coordinator, desc) for desc in SENSORS)


class FalconSensor(FalconEntity, SensorEntity):
    entity_description: FalconSensorDescription

    def __init__(self, coordinator, description: FalconSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key == "state_code":
            return {"endpoint": self.coordinator.api.state_path}
        return None

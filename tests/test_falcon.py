from datetime import timedelta

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry, async_capture_events, async_fire_time_changed)

from custom_components.creality_falcon.api import _extract_number
from custom_components.creality_falcon.const import CONF_CAMERA_PORT, DOMAIN

HOST = "192.168.1.50"
B = f"http://{HOST}:8080"


def test_extract_number():
    assert _extract_number(0.504686, ("progress",)) == 0.504686
    assert _extract_number("0.5", ("progress",)) == 0.5
    assert _extract_number({"errorcode": 0, "payload": {"progress": 0.25}}, ("progress",)) == 0.25
    assert _extract_number({"errorcode": 0, "payload": 0.75}, ("progress",)) == 0.75
    assert _extract_number({"errorcode": 0, "payload": {"state": 4}}, ("state",)) == 4
    assert _extract_number({"errorcode": 0, "payload": {"desc": "x"}}, ("state",)) is None


async def test_config_flow_detects_port(hass):
    from unittest.mock import patch
    from custom_components.creality_falcon.api import FalconApi, FalconConnectionError
    async def fake(self):
        if self.port != 80:
            raise FalconConnectionError("nope")
        return 0.0
    with patch.object(FalconApi, "get_progress", fake):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {
            CONF_HOST: HOST, CONF_NAME: "Falcon T1", CONF_PORT: 8080, CONF_CAMERA_PORT: 8080})
    assert r["type"] == "create_entry"
    assert r["data"][CONF_PORT] == 80


async def test_config_flow_cannot_connect(hass, aioclient_mock):
    aioclient_mock.get(f"http://{HOST}:8080/work/progress", exc=aiohttp.ClientError())
    aioclient_mock.get(f"http://{HOST}:80/work/progress", exc=aiohttp.ClientError())
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {
        CONF_HOST: HOST, CONF_NAME: "Falcon T1", CONF_PORT: 8080, CONF_CAMERA_PORT: 8080})
    assert r["errors"] == {"base": "cannot_connect"}


async def _setup(hass, aioclient_mock, progress):
    aioclient_mock.get(f"{B}/work/progress", json={"errorcode": 0, "payload": {"progress": progress}})
    aioclient_mock.get(f"{B}/work/state", status=404)
    aioclient_mock.get(f"{B}/work/status", json={"errorcode": 0, "payload": {"state": 1}})
    entry = MockConfigEntry(domain=DOMAIN, unique_id=HOST, data={
        CONF_HOST: HOST, CONF_PORT: 8080, CONF_CAMERA_PORT: 8080, CONF_NAME: "Falcon T1"})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_setup_entities_and_job_events(hass, aioclient_mock):
    started = async_capture_events(hass, "creality_falcon_job_started")
    finished = async_capture_events(hass, "creality_falcon_job_finished")
    await _setup(hass, aioclient_mock, 0.5)

    assert hass.states.get("sensor.falcon_t1_fortschritt") or hass.states.get("sensor.falcon_t1_progress")
    states = {s.entity_id: s.state for s in hass.states.async_all() if "falcon" in s.entity_id}
    print(states)
    prog = next(v for k, v in states.items() if k.startswith("sensor.") and "progress" in k)
    status = next(v for k, v in states.items() if k == "sensor.falcon_t1_status")
    code = next(v for k, v in states.items() if "state_code" in k)
    assert float(prog) == 50.0 and status == "laeuft" and code == "1"
    assert len(started) == 1
    # Start-Taste standardmäßig deaktiviert
    reg = er.async_get(hass)
    start = next(e for e in reg.entities.values() if e.unique_id.endswith("_start"))
    assert start.disabled_by is not None

    # Job wird fertig
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{B}/work/progress", json={"errorcode": 0, "payload": {"progress": 1.0}})
    aioclient_mock.get(f"{B}/work/status", json={"errorcode": 0, "payload": {"state": 1}})
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert hass.states.get("sensor.falcon_t1_status").state == "bereit"
    assert len(finished) == 1 and finished[0].data["completed"] is True


async def test_alarm_and_commands(hass, aioclient_mock):
    await _setup(hass, aioclient_mock, 0.0)
    aioclient_mock.get(f"{B}/work/stop", json={"errorcode": 0})
    aioclient_mock.post(f"{B}/device/setLight", json={"errorcode": 0})
    aioclient_mock.post(f"{B}/device/assistLight", json={"errorcode": 0})
    ids = [s.entity_id for s in hass.states.async_all()]
    print(ids)
    stop = next(i for i in ids if i.startswith("button.") and "stop" in i)
    light = next(i for i in ids if i.startswith("light."))
    sw = next(i for i in ids if i.startswith("switch."))
    await hass.services.async_call("button", "press", {"entity_id": stop}, blocking=True)
    await hass.services.async_call("light", "turn_on", {"entity_id": light, "brightness": 128}, blocking=True)
    await hass.services.async_call("switch", "turn_on", {"entity_id": sw}, blocking=True)
    calls = [(m, str(u), d) for m, u, d, *_ in aioclient_mock.mock_calls]
    assert any(u.endswith("/work/stop") for _, u, _ in calls)
    assert ("POST", f"{B}/device/setLight", {"dutyCycle": 50}) in calls
    assert ("POST", f"{B}/device/assistLight", {"switch": 1}) in calls
    assert hass.states.get(light).state == "on"


async def test_estimated_end_from_rate(hass, aioclient_mock):
    await _setup(hass, aioclient_mock, 0.5)  # Job läuft schon bei HA-Start
    assert hass.states.get("sensor.falcon_t1_estimated_end").state == "unknown"
    aioclient_mock.clear_requests()
    aioclient_mock.get(f"{B}/work/progress", json={"errorcode": 0, "payload": {"progress": 0.6}})
    aioclient_mock.get(f"{B}/work/status", json={"errorcode": 0, "payload": {"state": 1}})
    future = dt_util.utcnow() + timedelta(seconds=60)
    from freezegun import freeze_time
    with freeze_time(future):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
        end = dt_util.parse_datetime(hass.states.get("sensor.falcon_t1_estimated_end").state)
        # 10 % in 60 s -> 40 % Rest = 240 s
        assert abs((end - future).total_seconds() - 240) < 10


async def test_snapshot_rejects_json(hass, aioclient_mock):
    await _setup(hass, aioclient_mock, 0.0)
    aioclient_mock.get(f"{B}/media/getCapturePhoto", text='{"errorcode":-1,"payload":{}}')
    from homeassistant.components.camera import async_get_image
    from homeassistant.exceptions import HomeAssistantError
    cam = next(s.entity_id for s in hass.states.async_all() if s.entity_id.startswith("camera."))
    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, cam)


async def test_snapshot_jpeg(hass, aioclient_mock):
    await _setup(hass, aioclient_mock, 0.0)
    aioclient_mock.get(f"{B}/media/getCapturePhoto", content=b"\xff\xd8\xff\xe0fakejpeg")
    from homeassistant.components.camera import async_get_image
    cam = next(s.entity_id for s in hass.states.async_all() if s.entity_id.startswith("camera."))
    img = await async_get_image(hass, cam)
    assert img.content.startswith(b"\xff\xd8")


async def test_progress_as_string(hass, aioclient_mock):
    await _setup(hass, aioclient_mock, "0.00")
    assert hass.states.get("sensor.falcon_t1_status").state == "bereit"
    assert float(hass.states.get("sensor.falcon_t1_progress").state) == 0.0

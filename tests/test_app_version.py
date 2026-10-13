"""HTTP 426: the API names the minimum app version and the client adopts it."""

from __future__ import annotations

import json

import pytest

from custom_components.biedronka.api import (
    BiedronkaApi,
    newest_version,
    required_version,
    version_tuple,
)
from custom_components.biedronka.const import API_APP_VERSION
from custom_components.biedronka.exceptions import BiedronkaError

# A token that does not expire, so no refresh request is made.
TOKEN = "x.eyJleHAiOiA5OTk5OTk5OTk5fQ.y"


class FakeResponse:
    def __init__(self, status: int, body: dict, headers: dict | None = None):
        self.status = status
        self._body = json.dumps(body)
        self.headers = headers or {}
        self.content_type = "application/json"
        self.method = "GET"
        self.url = "https://api.invalid/"

    async def text(self):
        return self._body

    async def json(self, content_type=None):
        return json.loads(self._body)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class FakeSession:
    """Answers 426 to any User-Agent older than `minimum`, like the real API."""

    def __init__(self, minimum: str, *, header: bool = True):
        self.minimum = minimum
        self.header = header
        self.user_agents: list[str] = []

    def request(self, method, url, **kwargs):
        agent = kwargs["headers"]["User-Agent"]
        self.user_agents.append(agent)
        version = agent.split("/", 1)[1]
        if version_tuple(version) < version_tuple(self.minimum):
            headers = (
                {
                    "min-supported-version-android": self.minimum,
                    "min-supported-version-ios": self.minimum,
                }
                if self.header
                else {}
            )
            return FakeResponse(
                426,
                {
                    "error": "Upgrade Required",
                    "message": f"Please update the app to version {self.minimum} or higher.",
                },
                headers,
            )
        return FakeResponse(200, {"card_number": "1234"})


async def test_426_switches_to_the_required_version_and_saves_it():
    saved: list[str] = []

    async def save(version: str) -> None:
        saved.append(version)

    session = FakeSession("2.30.1")
    api = BiedronkaApi(session, TOKEN, "refresh", save_app_version=save)

    assert await api.users_me() == {"card_number": "1234"}
    assert session.user_agents == [f"Android/{API_APP_VERSION}", "Android/2.30.1"]
    assert api.app_version == "2.30.1"
    assert saved == ["2.30.1"]

    await api.users_me()
    assert session.user_agents[-1] == "Android/2.30.1"
    assert len(session.user_agents) == 3


async def test_version_is_read_from_the_message_without_the_header():
    session = FakeSession("2.31.0", header=False)
    api = BiedronkaApi(session, TOKEN, "refresh")
    await api.users_me()
    assert api.app_version == "2.31.0"


async def test_saved_version_is_used_from_the_start():
    session = FakeSession("2.30.1")
    api = BiedronkaApi(session, TOKEN, "refresh", app_version="2.30.1")
    await api.users_me()
    assert session.user_agents == ["Android/2.30.1"]


async def test_426_that_names_no_newer_version_is_an_error():
    session = FakeSession("2.30.1")
    api = BiedronkaApi(session, TOKEN, "refresh")
    # A broken answer: 426 without any version we could switch to.
    def stale(method, url, **kwargs):
        session.user_agents.append(kwargs["headers"]["User-Agent"])
        return FakeResponse(426, {"message": "Upgrade Required"}, {})

    session.request = stale
    with pytest.raises(BiedronkaError, match="upgrade_required"):
        await api.users_me()
    assert len(session.user_agents) == 1


def test_version_helpers():
    assert version_tuple("2.24.0") == (2, 24, 0)
    assert version_tuple("2.24.0-beta") is None
    assert version_tuple(None) is None
    assert newest_version("1.0.0") == API_APP_VERSION
    assert newest_version("2.100.0", "garbage") == "2.100.0"
    assert required_version({"min-supported-version-android": "3.0"}, "") == "3.0"
    assert required_version({}, "Please update the app to version 2.25.1 or higher.") == (
        "2.25.1"
    )
    assert required_version({}, "Upgrade Required") is None


async def test_detected_version_is_stored_on_the_entry(hass, enable_custom_integrations):
    from unittest.mock import patch

    from pytest_homeassistant_custom_component.common import MockConfigEntry

    from custom_components.biedronka.const import CONF_APP_VERSION, DOMAIN

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={"card_number": "1234", "access_token": TOKEN, "refresh_token": "r"},
        unique_id="1234",
    )
    entry.add_to_hass(hass)
    with patch(
        "custom_components.biedronka.async_get_clientsession",
        return_value=FakeSession("2.30.1"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.data[CONF_APP_VERSION] == "2.30.1"

"""Diagnostics: raw dashboard data, to see how the app lays out offers."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from . import BiedronkaConfigEntry
from .const import CONF_ACCESS_TOKEN, CONF_CARD_NUMBER, CONF_PHONE, CONF_REFRESH_TOKEN
from .coordinator import WARSAW, as_sections
from .exceptions import BiedronkaError

TO_REDACT = {
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_PHONE,
    CONF_CARD_NUMBER,
    "first_name",
    "last_name",
    "email",
    "phone_number",
    "barcode",
}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: BiedronkaConfigEntry
) -> dict[str, Any]:
    coordinator = entry.runtime_data
    api = coordinator.api
    carousels: dict[str, Any] = {}
    try:
        dashboard = await api.dashboard()
    except BiedronkaError as err:
        dashboard = {"error": str(err)}
    for section in as_sections(dashboard):
        param = section.get("param")
        if str(section.get("type") or "").upper() != "CAROUSELS" or not param:
            continue
        try:
            carousels[str(param)] = await api.carousel(str(param))
        except BiedronkaError as err:
            carousels[str(param)] = {"error": str(err)}
    extra: dict[str, Any] = {}
    for name, call in (
        ("loyalty_actions", api.loyalty_actions),
        ("wallets", api.wallets),
        ("coupons", api.coupons),
        ("notifications", api.notifications),
    ):
        try:
            extra[name] = await call()
        except BiedronkaError as err:
            extra[name] = {"error": str(err)}
    data = coordinator.data
    now = datetime.now(WARSAW).isoformat(timespec="seconds")
    for action in data.active_loyalty_actions if data else []:
        if not action.wallet_id:
            continue
        try:
            history = await api.wallet_history(action.wallet_id, now)
        except BiedronkaError as err:
            history = {"error": str(err)}
        extra.setdefault("wallet_history", {})[action.wallet_id] = history
    return async_redact_data(
        {
            **extra,
            # The app's chosen store from users/me/ (not personal data).
            "store": (data.user.get("store") if data else None),
            "entry": {"data": dict(entry.data), "options": dict(entry.options)},
            "rewards": [
                reward.as_dict() for reward in coordinator.data.reward_history
            ]
            if coordinator.data
            else [],
            "dashboard": dashboard,
            "carousels": carousels,
        },
        TO_REDACT,
    )

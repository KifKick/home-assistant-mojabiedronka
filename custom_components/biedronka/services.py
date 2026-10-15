"""Product lookups: price and stock in your store, stock nearby, search."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN
from .coordinator import BiedronkaCoordinator
from .exceptions import BiedronkaError

ATTR_CONFIG_ENTRY = "config_entry_id"
ATTR_EAN = "ean"
ATTR_QUERY = "query"
ATTR_LATITUDE = "latitude"
ATTR_LONGITUDE = "longitude"

SERVICE_PRODUCT_INFO = "product_info"
SERVICE_PRODUCT_STOCK_NEARBY = "product_stock_nearby"
SERVICE_PRODUCT_SEARCH = "product_search"

_EAN = vol.All(cv.string, vol.Match(r"^\d{6,14}$"))
_ENTRY = vol.Optional(ATTR_CONFIG_ENTRY)

PRODUCT_INFO_SCHEMA = vol.Schema({_ENTRY: cv.string, vol.Required(ATTR_EAN): _EAN})
PRODUCT_STOCK_NEARBY_SCHEMA = vol.Schema(
    {
        _ENTRY: cv.string,
        vol.Required(ATTR_EAN): _EAN,
        vol.Inclusive(ATTR_LATITUDE, "coordinates"): cv.latitude,
        vol.Inclusive(ATTR_LONGITUDE, "coordinates"): cv.longitude,
    }
)
PRODUCT_SEARCH_SCHEMA = vol.Schema(
    {_ENTRY: cv.string, vol.Required(ATTR_QUERY): vol.All(cv.string, vol.Length(min=2))}
)


def async_setup_services(hass: HomeAssistant) -> None:
    async def product_info(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        store = _store(coordinator)
        ean = call.data[ATTR_EAN]
        price = await _call(coordinator.api.product_price(store.code, ean))
        try:
            stock = await coordinator.api.product_stock(store.code, ean)
        except BiedronkaError:
            stock = None
        return {
            "store": {"code": store.code, "name": store.name, "address": store.address},
            "price": price,
            "stock": stock,
        }

    async def product_stock_nearby(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        store = _store(coordinator)
        stores = await _call(
            coordinator.api.product_stock_nearby(
                call.data[ATTR_EAN],
                call.data.get(ATTR_LATITUDE, hass.config.latitude),
                call.data.get(ATTR_LONGITUDE, hass.config.longitude),
                store.code,
            )
        )
        return {"stores": stores if isinstance(stores, list) else []}

    async def product_search(call: ServiceCall) -> ServiceResponse:
        coordinator = _coordinator(hass, call)
        products = await _call(coordinator.api.product_search(call.data[ATTR_QUERY]))
        return {"products": products if isinstance(products, list) else []}

    for name, handler, schema in (
        (SERVICE_PRODUCT_INFO, product_info, PRODUCT_INFO_SCHEMA),
        (SERVICE_PRODUCT_STOCK_NEARBY, product_stock_nearby, PRODUCT_STOCK_NEARBY_SCHEMA),
        (SERVICE_PRODUCT_SEARCH, product_search, PRODUCT_SEARCH_SCHEMA),
    ):
        hass.services.async_register(
            DOMAIN, name, handler, schema=schema, supports_response=SupportsResponse.ONLY
        )


def _coordinator(hass: HomeAssistant, call: ServiceCall) -> BiedronkaCoordinator:
    """The chosen account, or the first loaded one."""
    entry_id = call.data.get(ATTR_CONFIG_ENTRY)
    entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
        and (entry_id is None or entry.entry_id == entry_id)
    ]
    if not entries:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="no_account"
        )
    return entries[0].runtime_data


def _store(coordinator: BiedronkaCoordinator) -> Any:
    store = coordinator.data.store if coordinator.data else None
    if store is None:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="no_store")
    return store


async def _call(request: Any) -> Any:
    try:
        return await request
    except BiedronkaError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="product_request_failed",
            translation_placeholders={"error": str(err)},
        ) from err

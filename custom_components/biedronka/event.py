"""Event entities announcing each new offer, voucher and loyalty action."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BiedronkaConfigEntry
from .coordinator import BiedronkaCoordinator
from .entity import BiedronkaEntity
from .models import OFFER_KINDS

PARALLEL_UPDATES = 0

EVENT_NEW_OFFER = "new_offer"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BiedronkaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data
    async_add_entities(
        BiedronkaNewOfferEvent(coordinator, kind) for kind in OFFER_KINDS
    )


class BiedronkaNewOfferEvent(BiedronkaEntity, EventEntity):
    """Fires once per offer, the first time the integration sees it.

    The event data is the full offer (or voucher / action), including a
    ready-made `summary`.
    """

    _attr_event_types = [EVENT_NEW_OFFER]

    def __init__(self, coordinator: BiedronkaCoordinator, kind: str) -> None:
        super().__init__(coordinator)
        self._kind = kind
        self._attr_translation_key = f"new_{kind}_offer"
        self._attr_unique_id = f"{self._card}_new_{kind}_offer"
        # The listener fires once as soon as the entity is added, and
        # async_added_to_hass announces the same snapshot again. Remember which
        # coordinator data was already sent so that pair is a single event.
        self._announced_data: object | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # The first refresh runs before entities exist; offers that appeared
        # while Home Assistant was down would otherwise never be announced.
        self._announce_new_offers()

    @callback
    def _handle_coordinator_update(self) -> None:
        self._announce_new_offers()
        super()._handle_coordinator_update()

    @callback
    def _announce_new_offers(self) -> None:
        data = self.coordinator.data
        if data is None or data is self._announced_data:
            return
        self._announced_data = data
        for offer in data.new_offers:
            if offer.category == self._kind:
                self._trigger_event(EVENT_NEW_OFFER, offer.as_dict())
                self.async_write_ha_state()

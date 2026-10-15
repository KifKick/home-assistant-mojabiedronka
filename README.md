# Biedronka (unofficial) — Home Assistant

[![CI](https://github.com/Przemko92/home-assistant-mojabiedronka/actions/workflows/ci.yml/badge.svg)](https://github.com/Przemko92/home-assistant-mojabiedronka/actions/workflows/ci.yml)
[![hacs][hacsbadge]][hacs]
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Buy Me A Coffee](https://img.shields.io/badge/Buy%20Me%20a%20Coffee-ffdd00?logo=buy-me-a-coffee&logoColor=black)](https://buymeacoffee.com/przemko92)

Unofficial [HACS](https://hacs.xyz) integration for the **Moja Biedronka** app: purchase history and Shakeomat.

Nieoficjalna integracja [HACS](https://hacs.xyz) do programu **Moja Biedronka**: historia transakcji i Shakeomat.

**Not affiliated with Jeronimo Martins Polska S.A.** · **Nie jest powiązana z Jeronimo Martins Polska S.A.**

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Przemko92&repository=home-assistant-mojabiedronka&category=integration)
[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=biedronka)

**Recommended add-on / rekomendowany dodatek:** [Browser Companion](https://github.com/Przemko92/homeassistant-browser-companion) (`https://github.com/Przemko92/homeassistant-browser-companion`) — optional manual sign-in without it (e.g. HA Container / Core) / bez niego opcjonalne logowanie ręczne (np. HA Container / Core)

> 🇬🇧 English below · 🇵🇱 Polski poniżej

---

## 🇬🇧 English

Unofficial integration for **Moja Biedronka**. It uses the private API of the mobile app. The terms of service do not cover this — use at your own risk (API changes, account, SMS limits).

Repository: [github.com/Przemko92/home-assistant-mojabiedronka](https://github.com/Przemko92/home-assistant-mojabiedronka)

**Recommended:** [Browser Companion](https://github.com/Przemko92/homeassistant-browser-companion) add-on (HA OS / Supervised). Where it cannot run — e.g. HA Container / Core — the optional manual sign-in described below works instead.

### Installation (HACS)

1. Recommended (Home Assistant OS or Supervised only) — install the **[Browser Companion](https://github.com/Przemko92/homeassistant-browser-companion)** add-on:
   - Settings → Add-ons → Add-on Store → ⋮ → **Repositories**
   - Add `https://github.com/Przemko92/homeassistant-browser-companion`
   - Install **Browser Companion**, start it, and confirm Chromium appears in the sidebar
2. HACS → ⋮ → **Custom repositories**
3. URL: `https://github.com/Przemko92/home-assistant-mojabiedronka`, category **Integration**
4. Search **Biedronka** → Download → restart Home Assistant
5. Settings → Devices & services → Add integration → **Biedronka**

You can also use the [My Home Assistant](https://my.home-assistant.io/redirect/hacs_repository/?owner=Przemko92&repository=home-assistant-mojabiedronka&category=integration) button above.

Manual: copy `custom_components/biedronka/` to `/config/custom_components/` and restart.

### Sign-in

The login page has a Cloudflare captcha, so a person has to sign in in a real browser.

- **Browser Companion — recommended** ([Browser Companion](https://github.com/Przemko92/homeassistant-browser-companion) add-on, **Home Assistant OS** or **Supervised**). The integration opens a Chromium session and waits for **HTTP 302** with `Location: app://cma20.biedronka.pl`. You complete captcha and SMS in the sidebar browser.
- **Manual auth code — optional** (any installation; the way to sign in on **Container / Core**, where the add-on cannot run). The integration shows a sign-in link. Open it on a computer, enter phone and captcha, then press F12 → Console **before** entering the SMS code. After the SMS the browser logs `Failed to launch 'app://cma20.biedronka.pl?code=…'` — paste that line (or the `app://…` address) into the form. The code expires after about a minute. If the console is empty, the Network tab shows the same address in the `Location` header of the last request.

With Supervisor you get a menu with Browser Companion first and the manual code as an alternative; without Supervisor the manual form opens directly. Re-authentication uses the same steps. To sign in again on demand (e.g. after changing phones), use ⋮ → **Reconfigure** on the integration — entities and history stay.

The official app **never shows** `refresh_token` in settings — that is expected. SMS limit: about 10 attempts, then a lockout of ~30 minutes.

### Entities

| Entity | Description |
| --- | --- |
| `sensor.biedronka_*_karta` / Loyalty card | Card number |
| Last transaction | Amount in PLN, store, receipt, line items (EAN) |
| Recent receipts | Up to 5 recent receipts in the `receipts` attribute (id, date, store, number, total, source, and slim fiscal lines). Fetched on startup and on refresh |
| Vouchers | How many vouchers are ready to use. The `vouchers` attribute lists every coupon from `GET promos/coupons/` (kind, number, status, valid_from, valid_to, discount, conditions, badges) |
| Nearest voucher expiry | Earliest `valid_to` among ready and pending vouchers that have not expired yet; that voucher's code and description are in the attributes |
| Today's spend | Sum from today's receipts |
| Shakeomat | Nearest offer: `available` / `cooldown` / `expired` / `claimed` / `none`; full list in the `offers` attribute |
| Shakeomats ready | How many Shakeomat and Shakeomarka cards can be revealed right now |
| Last Shakeomat offer | Name of the last claimed reward. Attributes: `price`, `regular_price`, `discount` (%), `omnibus_price`, `unit`, `unit_price`, `details` (limit), `valid_from`/`valid_to`, `image_url`, `ean`, `badges` and `summary` — a ready one-line Polish text for notifications. Previous rewards in `history` |
| Shakeomarka | Same as Shakeomat, for the Shakeomarka card |
| Last Shakeomarka offer | Same as Last Shakeomat offer, for Shakeomarka rewards |
| Card offers | Number of active "Tylko dla Ciebie" offers Biedronka assigned to the card (e.g. WELCOME). Each one in the `offers` attribute with prices, limit, dates and `summary` |
| New Shakeomat / Shakeomarka / card offer | Event entities: one `new_offer` event per offer, the first time the integration sees it — including offers revealed in the phone app (picked up on the next refresh). Event data = the full offer with `summary`. Offers already active when the integration starts are not announced |
| Loyalty actions | Active sticker / points campaigns ("Akcja" in the app); all of them, with rewards and wallet balance, in `actions` |
| Loyalty balance | Stickers or points collected in the current campaign. Attributes: `unit`, `collect_until`, `end_on`, `rewards` (sorted by cost), `available_rewards`, `next_reward`, `missing_to_next_reward`, and `history` — the last movements from the wallet history, where Biedronka keeps one (points wallets do; sticker wallets answer HTTP 503 and are retried once a day) |
| New voucher / New loyalty action | Event entities like the offer ones: one `new_offer` event per new ready/pending voucher or newly started campaign, with `summary` |
| Stickers change | Event entity: one `new_offer` event whenever a campaign balance changes (stickers for a purchase, stickers spent on a reward), with `delta`, `balance` and `summary`, e.g. *„+2 naklejki (Gang Zaradniaków). Masz teraz 10.”* The last balance is stored, so a change made while Home Assistant was down is announced too |
| Reward ready to claim | Event entity: one `new_offer` event when the balance first covers a reward, with the reward and `summary`. After you claim it and the balance drops below the cost, reaching it again is announced again |
| Messages / New app message | Messages in the app's inbox (`notifications/`), the newest in `latest`; the event entity fires once per new message with `title`, `preview`, `message`, `image_url` and `summary` |
| Store opening hours / Store open | Today's hours of the store chosen in the app (`store` in `users/me/`, no extra request), with address, `target_hour` and the days the API returns in the attributes; Store open is off outside today's hours or while the store is being refurbished |
| Reveal Shakeomats | `PATCH …/offers/{id}/reveal-and-activate/` for each available card — Shakeomat and Shakeomarka alike (the app uses the same call for both) |
| Auto Shakeomat | Off by default — when enabled, reveals Shakeomat and Shakeomarka cards on every refresh, using the daily limit the same way as the phone |

Several cards can be added (e.g. household members): each one is a separate entry and device named after the last four digits of the card (`Moja Biedronka 1234`), so entity IDs look like `sensor.moja_biedronka_1234_…`.

Every `summary` is a ready Polish sentence for a notification, e.g. *„Śmietanka UHT 30% Łaciata, 0,5 l: drugi za 5 zł (regularnie 9,99 zł). Limit 4 (maks. 2 szt. za 5 zł) na kartę. Ważne 12.10–17.10.”*

There are no separate “Shakeomat 1” and “Shakeomat 2” entities. The API can return further offers under the same `SHAKEOMAT` type, and besides the two daily ones there are sometimes extras, so the number of offers varies and the integration handles any count. `SHAKEOMARKA` cards have their own Shakeomarka entities. Old slot-based entities are removed from the registry on startup.

Claimed offers are stored in integration storage and survive Home Assistant restarts — a new offer does not wipe the previous one. Activation only updates the Shakeomat entities (last offer and history). It does not create a Home Assistant notification.

Refresh interval: every 15 minutes (integration options: 5–120 min).

### Services

All three return data (call them from Developer tools → Actions with "Return response", or in a script with `response_variable`). `config_entry_id` picks the card when you have several; empty = the first one.

| Service | Description |
| --- | --- |
| `biedronka.product_info` | Price card (price, regular price, promotion, limit, unit price, Omnibus) and stock of a product by barcode (`ean`) in the store chosen in the app |
| `biedronka.product_stock_nearby` | Stores that have the product, near `latitude`/`longitude` (default: Home Assistant location) |
| `biedronka.product_search` | Products whose name matches `query` |

```yaml
action: biedronka.product_info
data:
  ean: "5900512300108"
response_variable: product
```

### Out of scope for v0.1

BLIK, complaints, leaflets, household, surveys.

### Development / debug

You can test the integration itself (without the add-on) in this repo: Dev Containers → HA on port 8123. **There is no Supervisor** — Browser Companion will not install here.

Full flow (Supervisor + Ingress + add-on + Biedronka): open **homeassistant-browser-companion** in a Supervisor devcontainer. See `homeassistant-browser-companion/.devcontainer/README.md`. Keep the repositories next to each other (`GIT/moja-biedronka` and `GIT/homeassistant-browser-companion`).

Details for local HA without the add-on: [`.devcontainer/README.md`](.devcontainer/README.md). `debugpy.wait: true` pauses HA startup until you attach the debugger.

Locally without a container: `scripts/setup` then `scripts/develop`. The `config/` directory is in `.gitignore`.

**Diagnostics** (⋮ → Download diagnostics) include the raw dashboard, carousels, loyalty actions, wallets, coupons and app messages, with tokens, card number, phone and personal data redacted — handy when the app changes its API.

### API (app 2.56.0)

- `https://api.prod.biedronka.cloud/api/v7/`
- `User-Agent: Android/2.56.0`
- Token: `https://konto.biedronka.pl/realms/loyalty/protocol/openid-connect/token`

When Biedronka stops accepting an app version, the API answers **HTTP 426** with the minimum one in the `min-supported-version-android` header. The integration then switches its `User-Agent` to that version, remembers it for the entry and retries — no update or restart needed. A warning in the log tells you it happened.

### Support

If this integration helps you, you can buy a coffee: [Buy Me a Coffee](https://buymeacoffee.com/przemko92)

---

## 🇵🇱 Polski

Nieoficjalna integracja do programu **Moja Biedronka**. Korzysta z prywatnego API aplikacji mobilnej. Regulamin tego nie przewiduje — używasz na własne ryzyko (zmiany API, konto, limity SMS).

Repozytorium: [github.com/Przemko92/home-assistant-mojabiedronka](https://github.com/Przemko92/home-assistant-mojabiedronka)

**Rekomendowany:** dodatek [Browser Companion](https://github.com/Przemko92/homeassistant-browser-companion) (HA OS / Supervised). Tam, gdzie nie da się go uruchomić — np. na HA Container / Core — działa opcjonalne logowanie ręczne opisane niżej.

### Instalacja (HACS)

1. Rekomendowane (tylko Home Assistant OS albo Supervised) — zainstaluj dodatek **[Browser Companion](https://github.com/Przemko92/homeassistant-browser-companion)**:
   - Ustawienia → Dodatki → Sklep z dodatkami → ⋮ → **Repositories**
   - Dodaj `https://github.com/Przemko92/homeassistant-browser-companion`
   - Zainstaluj **Browser Companion**, uruchom go i sprawdź, czy Chromium pojawia się w sidebarze
2. HACS → ⋮ → **Custom repositories**
3. URL: `https://github.com/Przemko92/home-assistant-mojabiedronka`, kategoria **Integration**
4. Szukaj **Biedronka** → Download → restart Home Assistant
5. Ustawienia → Urządzenia i usługi → Dodaj integrację → **Biedronka**

Możesz też użyć przycisku [My Home Assistant](https://my.home-assistant.io/redirect/hacs_repository/?owner=Przemko92&repository=home-assistant-mojabiedronka&category=integration) powyżej.

Ręcznie: skopiuj `custom_components/biedronka/` do `/config/custom_components/` i zrestartuj.

### Logowanie

Strona logowania ma captchę Cloudflare, więc logować się musi człowiek w prawdziwej przeglądarce.

- **Browser Companion — rekomendowane** (dodatek [Browser Companion](https://github.com/Przemko92/homeassistant-browser-companion), **Home Assistant OS** albo **Supervised**). Integracja otwiera sesję Chromium i czeka na **HTTP 302** z `Location: app://cma20.biedronka.pl`. Captcha i SMS robisz w przeglądarce w sidebarze.
- **Ręczny kod autoryzacji — opcjonalnie** (każda instalacja; sposób logowania na **Container / Core**, gdzie dodatek nie działa). Integracja pokazuje link logowania. Otwórz go na komputerze, wpisz numer i rozwiąż captchę, a **przed** wpisaniem kodu SMS naciśnij F12 → Konsola. Po SMS przeglądarka zapisze `Failed to launch 'app://cma20.biedronka.pl?code=…'` — wklej tę linię (albo adres `app://…`) do formularza. Kod wygasa po około minucie. Jeśli konsola jest pusta, ten sam adres jest w nagłówku `Location` ostatniego żądania w zakładce Sieć.

Z Supervisorem dostajesz menu: najpierw Browser Companion, a ręczny kod jako alternatywa; bez Supervisora od razu otwiera się formularz ręczny. Ponowne logowanie przebiega tak samo. Żeby przelogować się na żądanie, użyj ⋮ → **Skonfiguruj ponownie** przy integracji — encje i historia zostają.

Oficjalna apka **nigdy nie pokazuje** `refresh_token` w ustawieniach — to normalne. Limit SMS: ok. 10 prób, potem blokada na ~30 minut.

### Encje

| Encja | Opis |
| --- | --- |
| `sensor.biedronka_*_karta` / Loyalty card | Numer karty |
| Ostatnia transakcja | Kwota PLN, sklep, paragon, pozycje (EAN) |
| Ostatnie paragony | Do 5 ostatnich paragonów w atrybucie `receipts` (id, data, sklep, numer, suma, źródło i okrojone linie fiskalne). Pobierane przy starcie i przy odświeżeniu |
| Vouchery | Ile voucherów można użyć teraz. Atrybut `vouchers` zawiera wszystkie kupony z `GET promos/coupons/` (rodzaj, numer, status, valid_from, valid_to, rabat, warunki, odznaki) |
| Najbliższe wygaśnięcie vouchera | Najwcześniejsze `valid_to` wśród gotowych i oczekujących voucherów, które jeszcze nie wygasły; kod i opis tego vouchera są w atrybutach |
| Dzisiejsze wydatki | Suma z dzisiejszych paragonów |
| Shakeomat | Najbliższa oferta: `available` / `cooldown` / `expired` / `claimed` / `none`, pełna lista w atrybucie `offers` |
| Shakeomaty do odebrania | Ile kart Shakeomatu i Shakeomarki można teraz odsłonić |
| Ostatnia oferta Shakeomatu | Nazwa ostatnio odebranej nagrody. Atrybuty: `price`, `regular_price`, `discount` (%), `omnibus_price`, `unit`, `unit_price`, `details` (limit), `valid_from`/`valid_to`, `image_url`, `ean`, `badges` oraz `summary` — gotowy tekst do powiadomienia. Wcześniejsze nagrody w `history` |
| Shakeomarka | To samo co Shakeomat, dla karty Shakeomarki |
| Ostatnia oferta Shakeomarki | To samo co Ostatnia oferta Shakeomatu, dla nagród z Shakeomarki |
| Oferty z kartą | Liczba aktywnych ofert „Tylko dla Ciebie” przydzielonych karcie przez Biedronkę (np. WELCOME). Każda w atrybucie `offers` z cenami, limitem, datami i `summary` |
| Nowa oferta Shakeomatu / Shakeomarki / z kartą | Encje zdarzeń: jedno zdarzenie `new_offer` na ofertę, gdy integracja zobaczy ją pierwszy raz — także oferty odsłonięte w aplikacji (przy najbliższym odświeżeniu). Dane zdarzenia = pełna oferta z `summary`. Oferty aktywne w chwili uruchomienia integracji nie są ogłaszane |
| Akcje lojalnościowe | Aktywne akcje z naklejkami / punktami („Akcja” w aplikacji); wszystkie, z nagrodami i saldem, w atrybucie `actions` |
| Saldo akcji lojalnościowej | Naklejki lub punkty zebrane w bieżącej akcji. Atrybuty: `unit`, `collect_until`, `end_on`, `rewards` (posortowane według kosztu), `available_rewards`, `next_reward`, `missing_to_next_reward` oraz `history` — ostatnie ruchy z historii portfela, jeśli Biedronka ją prowadzi (portfele punktów tak; portfele naklejek odpowiadają HTTP 503 i są ponawiane raz na dobę) |
| Nowy voucher / Nowa akcja lojalnościowa | Encje zdarzeń jak dla ofert: jedno zdarzenie `new_offer` na nowy voucher (gotowy / oczekujący) lub nowo rozpoczętą akcję, z `summary` |
| Zmiana naklejek | Encja zdarzeń: jedno zdarzenie `new_offer` przy każdej zmianie salda akcji (naklejki za zakupy, naklejki wydane na nagrodę), z `delta`, `balance` i `summary`, np. *„+2 naklejki (Gang Zaradniaków). Masz teraz 10.”* Ostatnie saldo jest zapamiętywane, więc zmiana z czasu, gdy Home Assistant był wyłączony, też zostanie ogłoszona |
| Nagroda do odebrania | Encja zdarzeń: jedno zdarzenie `new_offer`, gdy saldo pierwszy raz wystarcza na nagrodę, z nagrodą i `summary`. Po odebraniu nagrody, gdy saldo spadnie poniżej kosztu, ponowne uzbieranie jest znów ogłaszane |
| Wiadomości / Nowa wiadomość | Wiadomości ze skrzynki w aplikacji (`notifications/`), najnowsza w `latest`; encja zdarzeń wysyła jedno zdarzenie na nową wiadomość z `title`, `preview`, `message`, `image_url` i `summary` |
| Godziny otwarcia sklepu / Sklep otwarty | Dzisiejsze godziny sklepu wybranego w aplikacji (`store` w `users/me/`, bez dodatkowego zapytania), z adresem, `target_hour` i dniami zwróconymi przez API w atrybutach; Sklep otwarty jest wyłączony poza dzisiejszymi godzinami i w czasie remontu sklepu |
| Odbierz Shakeomaty | `PATCH …/offers/{id}/reveal-and-activate/` dla każdej dostępnej karty — Shakeomatu i Shakeomarki (aplikacja używa tego samego wywołania dla obu) |
| Auto Shakeomat | Domyślnie wyłączony — po włączeniu odsłania karty Shakeomatu i Shakeomarki przy każdym odświeżeniu, zużywając dzienny limit tak samo jak telefon |

Można dodać kilka kart (np. domowników): każda to osobny wpis i urządzenie nazwane końcówką karty (`Moja Biedronka 1234`), więc encje mają ID w stylu `sensor.moja_biedronka_1234_…`.

Każde `summary` to gotowe zdanie do powiadomienia, np. *„Śmietanka UHT 30% Łaciata, 0,5 l: drugi za 5 zł (regularnie 9,99 zł). Limit 4 (maks. 2 szt. za 5 zł) na kartę. Ważne 12.10–17.10.”*

Nie ma osobnych encji „Shakeomat 1” i „Shakeomat 2”. API potrafi podać kolejne oferty pod tym samym typem `SHAKEOMAT`, a poza dwiema dobowymi bywają dodatkowe, więc liczba ofert jest zmienna i integracja obsługuje ich dowolnie wiele. Karty `SHAKEOMARKA` mają własne encje Shakeomarki. Stare encje ze slotami są usuwane z rejestru przy starcie.

Odebrane oferty trafiają do magazynu integracji i przeżywają restart Home Assistanta — nowa oferta nie kasuje poprzedniej. Aktywacja zmienia tylko encje Shakeomatu (ostatnia oferta i historia). Nie tworzy powiadomienia Home Assistanta.

Odświeżanie: co 15 minut (opcje integracji: 5–120 min).

### Usługi

Wszystkie trzy zwracają dane (wywołaj w Narzędzia deweloperskie → Akcje z „Zwróć odpowiedź” albo w skrypcie z `response_variable`). `config_entry_id` wybiera kartę, gdy masz kilka; puste = pierwsza.

| Usługa | Opis |
| --- | --- |
| `biedronka.product_info` | Cena (cena, cena regularna, promocja, limit, cena jednostkowa, Omnibus) i dostępność produktu po kodzie kreskowym (`ean`) w sklepie wybranym w aplikacji |
| `biedronka.product_stock_nearby` | Sklepy z produktem w pobliżu `latitude`/`longitude` (domyślnie lokalizacja Home Assistanta) |
| `biedronka.product_search` | Produkty, których nazwa pasuje do `query` |

```yaml
action: biedronka.product_info
data:
  ean: "5900512300108"
response_variable: produkt
```

### Poza zakresem v0.1

BLIK, reklamacje, gazetki, gospodarstwo domowe, ankiety.

### Development / debug

Samą integrację (bez add-onu) testujesz w tym repo: Dev Containers → HA na porcie 8123. **Nie ma Supervisora** — Browser Companion się tu nie zainstaluje.

Pełny flow (Supervisor + Ingress + dodatek + Biedronka): otwórz **homeassistant-browser-companion** w devcontainerze z Supervisorem. Opis: `homeassistant-browser-companion/.devcontainer/README.md`. Repozytoria trzymaj obok siebie (`GIT/moja-biedronka` i `GIT/homeassistant-browser-companion`).

Szczegóły lokalnego HA bez add-onu: [`.devcontainer/README.md`](.devcontainer/README.md). `debugpy.wait: true` wstrzymuje start HA, aż podepniesz debugger.

Lokalnie bez kontenera: `scripts/setup` potem `scripts/develop`. Katalog `config/` jest w `.gitignore`.

**Diagnostyka** (⋮ → Pobierz diagnostykę) zawiera surowy dashboard, karuzele, akcje lojalnościowe, portfele, kupony i wiadomości z aplikacji, z ukrytymi tokenami, numerem karty, telefonem i danymi osobowymi — przydaje się, gdy aplikacja zmieni API.

### API (aplikacja 2.56.0)

- `https://api.prod.biedronka.cloud/api/v7/`
- `User-Agent: Android/2.56.0`
- Token: `https://konto.biedronka.pl/realms/loyalty/protocol/openid-connect/token`

Gdy Biedronka przestaje akceptować wersję aplikacji, API odpowiada **HTTP 426** z minimalną wersją w nagłówku `min-supported-version-android`. Integracja przełącza wtedy `User-Agent` na tę wersję, zapamiętuje ją dla wpisu i ponawia zapytanie — bez aktualizacji ani restartu. Informuje o tym ostrzeżenie w logu.

### Wsparcie

Jeśli integracja Ci pomaga, możesz postawić kawę: [Buy Me a Coffee](https://buymeacoffee.com/przemko92)

***

[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=for-the-badge

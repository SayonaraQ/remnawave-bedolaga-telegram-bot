# Changelog

## [3.7.0](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/compare/v3.6.0...v3.7.0) (2026-02-07)


### Features

* add OAuth 2.0 authorization (Google, Yandex, Discord, VK) ([97be4af](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/97be4afbffd809fe2786a6d248fc4d3f770cb8cf))
* add panel info, node usage endpoints and campaign to user detail ([287a43b](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/287a43ba6527ff3464a527821d746a68e5371bbe))
* add panel info, node usage endpoints and campaign to user detail ([0703212](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/070321230bcb868e4bc7a39c287ed3431a4aef4a))
* add tariff reorder API endpoint ([4c2e11e](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/4c2e11e64bed41592f5a12061dcca74ce43e0806))
* add TRIAL_DISABLED_FOR setting to disable trial by user type ([c4794db](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/c4794db1dd78f7c48b5da896bdb2f000e493e079))
* add user_id filter to admin tickets endpoint ([8886d0d](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/8886d0dea20aa5a31c6b6f0c3391b3c012b4b34d))
* add user_id filter to admin tickets endpoint ([d3819c4](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/d3819c492f88794e4466c2da986fd3a928d7f3df))
* block registration with disposable email addresses ([9ca24ef](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/9ca24efe434278925c0c1f8d2f2d644a67985c89))
* block registration with disposable email addresses ([116c845](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/116c8453bb371b5eacf5c9d07f497eb449a355cc))
* **ci:** add release-please and release workflows ([488d5c9](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/488d5c99f7bd6bd1927e2125a824d43376cf3403))
* **ci:** add release-please and release workflows ([9151882](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/9151882245a325761d75eab3a58d0f677219c31b))
* disable trial by user type (email/telegram/all) ([4e7438b](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/4e7438b9f9c01e30c48fcf2bbe191e9b11598185))
* migrate OAuth state storage from in-memory to Redis ([e9b98b8](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/e9b98b837a8552360ef4c41f6cd7a5779aa8b0a7))
* **notifications:** redesign version update notification ([02eca28](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/02eca28bc0f9d31495d7bbe5deb380d13e859c3f))
* **notifications:** redesign version update notification ([3f7ca7b](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/3f7ca7be3ade6892e453f86ac0c62e61ac61a11c))
* OAuth 2.0 authorization (Google, Yandex, Discord, VK) ([3cbb9ef](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/3cbb9ef024695352959ef9a82bf8b81f0ba1d940))
* pass platform-level fields from RemnaWave config to frontend ([095bc00](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/095bc00b33d7082558a8b7252906db2850dce9da))
* return 30-day daily breakdown for node usage ([7102c50](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/7102c50f52d583add863331e96f3a9de189f581a))
* return 30-day daily breakdown for node usage ([e4c65ca](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/e4c65ca220994cf08ed3510f51d9e2808bb2d154))
* serve original RemnaWave config from app-config endpoint ([43762ce](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/43762ce8f4fa7142a1ca62a92b97a027dab2564d))
* tariff reorder API endpoint ([085a617](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/085a61721a8175b3f4fd744614c446d73346f2b7))
* **websocket:** add real-time notifications for subscription and balance events ([8635042](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/86350424d50f899b2ea7762cb8533fbe9f51863e))


### Bug Fixes

* add refresh before assigning promo_groups to avoid async lazy lo… ([733be09](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/733be0965806607cef8beb30685052af22a13ab4))
* add refresh before assigning promo_groups to avoid async lazy load error ([5e75210](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/5e75210c8b3da1a738c94edf3dd02a18bbff3bb6))
* **autopay:** add 6h cooldown for insufficient balance notifications ([f7abe03](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/f7abe03dba085b07fc1dc0fc0f21613e6a6219eb))
* **autopay:** add 6h cooldown for insufficient balance notifications ([992a5cb](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/992a5cb97f5517b52bd386907a2cbc2162182c44))
* **autopay:** exclude daily subscriptions from global autopay ([3d94e63](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/3d94e63c3ca4688d5f0b513e6b678afdd3798eea))
* **autopay:** exclude daily subscriptions from global autopay ([b9352a5](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/b9352a5bd53ec82114abd46156bacc0e496dcfe1))
* **broadcast:** resolve SQLAlchemy connection closed errors ([94a00ab](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/94a00ab2694d2b13c93c73a4defb2c2019225093))
* **broadcast:** resolve SQLAlchemy connection closed errors during long broadcasts ([b8682ad](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/b8682adbbfa1674f03ea8699de4b3bd125092a9b))
* **broadcast:** stabilize mass broadcast for 100k+ users ([7956951](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/79569510d29494c0be46a8f39bc4a01e30873f21))
* **broadcast:** stabilize mass broadcast for 100k+ users ([13ebfdb](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/13ebfdb5c45f2d358b2552bfcc2e3b907ec7d567))
* **cabinet:** apply promo group discounts to addons and tariff switch ([e8a413c](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/e8a413c3c3177d8ce4931d2f82c17dce70e9aaad))
* **cabinet:** apply promo group discounts to device/traffic purchase and tariff switch ([aa1d328](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/aa1d3289e1bb2195a11c333867ac131c5460f0cc))
* **config:** make SMTP credentials optional for servers without AUTH ([02f8826](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/02f88261324d9a1574d108de815613ff77c58eab))
* **email:** handle SMTP servers without AUTH support ([989da44](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/989da445bece846dfd76768cd947549780fa30ce))
* enforce blacklist via middleware ([561708b](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/561708b7772ec5b84d6ee049aeba26dc70675583))
* enforce blacklist via middleware instead of per-handler checks ([966a599](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/966a599c2c778dce9eea3c61adf6067fb33119f6))
* exclude signature field from Telegram initData HMAC validation ([5b64046](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/5b6404613772610c595e55bde1249cdf6ec3269d))
* improve button URL resolution and pass uiConfig to frontend ([0ed98c3](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/0ed98c39b6c95911a38a26a32d0ffbcf9cfd7c80))
* increase OAuth HTTP timeout to 30s ([333a3c5](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/333a3c590120a64f6b2963efab1edd861274840c))
* move /settings routes before /{ticket_id} to fix route matching ([000d670](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/000d670869bc7eb0eb6551e1d9eabbe05cd34ea2))
* move /settings routes before /{ticket_id} to fix route matching ([0c9b69d](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/0c9b69deb0686c8e078eaf627693b84b03ffdd3c))
* parse bandwidth stats series format for node usage ([557dbf3](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/557dbf3ebe777d2137e0e28303dc2a803b15c1c6))
* parse bandwidth stats series format for node usage ([462f7a9](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/462f7a99b9d5c0b7436dbc3d6ab5db6c6cfa3118))
* pass tariff object instead of tariff_id to set_tariff_promo_groups ([1ffb8a5](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/1ffb8a5b85455396006e1fcddd48f4c9a2ca2700))
* query per-node legacy endpoint for user traffic breakdown ([b94e3ed](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/b94e3edf80e747077992c03882119c7559ad1c31))
* query per-node legacy endpoint for user traffic breakdown ([51ca3e4](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/51ca3e42b75c1870c76a1b25f667629855cfe886))
* reduce node usage to 2 API calls to avoid 429 rate limit ([c68c4e5](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/c68c4e59846abba9c7c78ae91ec18e2e0e329e3c))
* reduce node usage to 2 API calls to avoid 429 rate limit ([f00a051](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/f00a051bb323e5ba94a3c38939870986726ed58e))
* resolve circular import with lazy websocket imports ([3263606](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/32636067028bd6760ca43db2c7e1a584d147c4b2))
* restore unquote for user data parsing in telegram auth ([c2cabbe](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/c2cabbee097a41a95d16c34d43ab7e70d076c4dc))
* use accessible nodes API and fix date format for node usage ([943e9a8](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/943e9a86aaa449cd3154b0919cfdc52d2a35b509))
* use accessible nodes API and fix date format for node usage ([c4da591](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/c4da59173155e2eeb69eca21416f816fcbd1fa9c))


### Reverts

* remove signature pop from HMAC validation ([4234769](https://github.com/SayonaraQ/remnawave-bedolaga-telegram-bot/commit/4234769e92104a6c4f8f1d522e1fca25bc7b20d0))

## [3.6.0](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/compare/v3.5.0...v3.6.0) (2026-02-07)


### Features

* add OAuth 2.0 authorization (Google, Yandex, Discord, VK) ([97be4af](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/97be4afbffd809fe2786a6d248fc4d3f770cb8cf))
* add panel info, node usage endpoints and campaign to user detail ([287a43b](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/287a43ba6527ff3464a527821d746a68e5371bbe))
* add panel info, node usage endpoints and campaign to user detail ([0703212](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/070321230bcb868e4bc7a39c287ed3431a4aef4a))
* add TRIAL_DISABLED_FOR setting to disable trial by user type ([c4794db](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/c4794db1dd78f7c48b5da896bdb2f000e493e079))
* add user_id filter to admin tickets endpoint ([8886d0d](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/8886d0dea20aa5a31c6b6f0c3391b3c012b4b34d))
* add user_id filter to admin tickets endpoint ([d3819c4](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/d3819c492f88794e4466c2da986fd3a928d7f3df))
* block registration with disposable email addresses ([9ca24ef](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/9ca24efe434278925c0c1f8d2f2d644a67985c89))
* block registration with disposable email addresses ([116c845](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/116c8453bb371b5eacf5c9d07f497eb449a355cc))
* disable trial by user type (email/telegram/all) ([4e7438b](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/4e7438b9f9c01e30c48fcf2bbe191e9b11598185))
* migrate OAuth state storage from in-memory to Redis ([e9b98b8](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/e9b98b837a8552360ef4c41f6cd7a5779aa8b0a7))
* OAuth 2.0 authorization (Google, Yandex, Discord, VK) ([3cbb9ef](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/3cbb9ef024695352959ef9a82bf8b81f0ba1d940))
* return 30-day daily breakdown for node usage ([7102c50](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/7102c50f52d583add863331e96f3a9de189f581a))
* return 30-day daily breakdown for node usage ([e4c65ca](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/e4c65ca220994cf08ed3510f51d9e2808bb2d154))


### Bug Fixes

* increase OAuth HTTP timeout to 30s ([333a3c5](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/333a3c590120a64f6b2963efab1edd861274840c))
* parse bandwidth stats series format for node usage ([557dbf3](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/557dbf3ebe777d2137e0e28303dc2a803b15c1c6))
* parse bandwidth stats series format for node usage ([462f7a9](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/462f7a99b9d5c0b7436dbc3d6ab5db6c6cfa3118))
* pass tariff object instead of tariff_id to set_tariff_promo_groups ([1ffb8a5](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/1ffb8a5b85455396006e1fcddd48f4c9a2ca2700))
* query per-node legacy endpoint for user traffic breakdown ([b94e3ed](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/b94e3edf80e747077992c03882119c7559ad1c31))
* query per-node legacy endpoint for user traffic breakdown ([51ca3e4](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/51ca3e42b75c1870c76a1b25f667629855cfe886))
* reduce node usage to 2 API calls to avoid 429 rate limit ([c68c4e5](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/c68c4e59846abba9c7c78ae91ec18e2e0e329e3c))
* reduce node usage to 2 API calls to avoid 429 rate limit ([f00a051](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/f00a051bb323e5ba94a3c38939870986726ed58e))
* use accessible nodes API and fix date format for node usage ([943e9a8](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/943e9a86aaa449cd3154b0919cfdc52d2a35b509))
* use accessible nodes API and fix date format for node usage ([c4da591](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/c4da59173155e2eeb69eca21416f816fcbd1fa9c))

## [3.5.0](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/compare/v3.4.0...v3.5.0) (2026-02-06)


### Features

* add tariff reorder API endpoint ([4c2e11e](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/4c2e11e64bed41592f5a12061dcca74ce43e0806))
* pass platform-level fields from RemnaWave config to frontend ([095bc00](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/095bc00b33d7082558a8b7252906db2850dce9da))
* serve original RemnaWave config from app-config endpoint ([43762ce](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/43762ce8f4fa7142a1ca62a92b97a027dab2564d))
* tariff reorder API endpoint ([085a617](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/085a61721a8175b3f4fd744614c446d73346f2b7))


### Bug Fixes

* enforce blacklist via middleware ([561708b](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/561708b7772ec5b84d6ee049aeba26dc70675583))
* enforce blacklist via middleware instead of per-handler checks ([966a599](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/966a599c2c778dce9eea3c61adf6067fb33119f6))
* exclude signature field from Telegram initData HMAC validation ([5b64046](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/5b6404613772610c595e55bde1249cdf6ec3269d))
* improve button URL resolution and pass uiConfig to frontend ([0ed98c3](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/0ed98c39b6c95911a38a26a32d0ffbcf9cfd7c80))
* restore unquote for user data parsing in telegram auth ([c2cabbe](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/c2cabbee097a41a95d16c34d43ab7e70d076c4dc))


### Reverts

* remove signature pop from HMAC validation ([4234769](https://github.com/BEDOLAGA-DEV/remnawave-bedolaga-telegram-bot/commit/4234769e92104a6c4f8f1d522e1fca25bc7b20d0))

# Dex teardown

App: `com.dextcg.app` ("Dex - for TCG Collectors", by Dexbit), version 1.19.1 (code 113), minSdk 29, targetSdk 36. The Play page lists "Android 10 and up", 100K+ downloads, 4.3 stars from 868 reviews, and in-app purchases of $3.99 - $39.99.
Method: public web research, then static analysis only. Nothing was installed or run, no traffic was intercepted, and no API was called.

**Unverified build (APKPure mirror).** Google Play blocks the install on the emulator as an incompatible device. So the owner downloaded the XAPK from APKPure: base `com.dextcg.app.apk` (sha256 `c29b46bf0e248fb2…`), plus `config.armeabi_v7a.apk`, `config.en.apk` and `config.mdpi.apk`. The signer was not checked, because `apksigner` is not installed. Every APK finding below comes from this build.

## Public research

Each bullet carries its source URL.

- **Scope.** Pokémon TCG only: International, Japanese and Simplified Chinese. Several apps have similar names (TCGDex, DexScan, Dexi). They are different apps. https://dextcg.com
- **Scanning.** Point the camera at a card. If the match is unclear, filter by rarity or expansion. An overview screen then lets the user assign variants, and the user can set one variant for a whole batch before scanning. The card must be well lit and fully in frame. Scanning works on iOS and Android, not on the web. https://dextcg.com/help/collection/scanning-your-cards
- **The scanner is behind the paywall** (Dex+). The developer says it costs "server maintenance". A bug once gave free users the scanner, and it was reverted. https://dextcg.com/news/clarifying-our-scanner-features-access
- **Prices.** TCGplayer, Cardmarket, CardTrader and eBay, converted to the user's currency. Refresh is "periodically", with no interval published (unverified). Price data used to be Dex+ but is now free. https://dextcg.com, https://apps.apple.com/BR/app/id1555489854
- **Collection.** Owned and missing cards by set, variant and type, in a Pokédex-style view. Wishlists, folders (3 free), notes, favorites. Insights: count, total value, most expensive cards, rarity breakdown. https://dextcg.com
- **Selling.** No marketplace, no listing integration. "Marketplaces" in the app means price sources. Trade Finder matches cards between friends. https://dextcg.com
- **Business.** Free tier: all cards, all price sources, 3 folders, 5 friends. Dex+ is $3.99/month and adds the scanner, unlimited folders, widgets and CSV export. Annual and lifetime tiers exist. The team is two people. https://dextcg.com, https://apps.apple.com/BR/app/id1555489854, https://dextcg.com/news/clarifying-our-scanner-features-access
- **Pitfalls.** Reviewers dislike the monthly paywall and ask for missing regional sets (Brazilian Portuguese). There is no public evidence on scan misses or sync loss. https://apps.apple.com/BR/app/id1555489854, https://apps.appfollow.io/ios/dex-for-tcg-collectors/1555489854?country=de

## APK findings (file and function evidence)

**Framework: React Native with Expo, on Hermes.**
- `assets/index.android.bundle` is Hermes bytecode version 98 (10.6 MB, 48,243 functions).
- The native split has `libhermesvm.so`, `libreactnative.so`, `libexpo-modules-core.so`, `libexpo-sqlite.so`, `libNitroModules.so`, `libreanimated.so` and `libsentry.so`.
- Manifest meta-data enables `expo.modules.updates` with `https://u.expo.dev/…`, channel `production`. So the JS ships over the air, outside Play releases.
- REA `inspect_android_package` reads 31,617 classes. REA `search_android_classes` failed with a full inventory: JADX reports duplicate classes across the 9 dex files. So package names were read from the dex string tables.
- The bundle was decompiled with hermes-dec (P1sec, commit `a0f18f9`). It warns that v98 is not formally supported, but it decompiled the whole file. Offsets below are character offsets in that output.

**Scanning happens on a server.**
- Camera: `expo.modules.camera` (`takePictureAsync`). The only on-device model is ML Kit barcode (`assets/mlkit_barcode_models/*.tflite`, `libbarhopper_v3.so`).
- The dex packages contain no TensorFlow Lite, ONNX, PyTorch, ExecuTorch, OpenCV or VisionCamera frame processor.
- The scan function (decompiled offset 70078232) does these steps:
  1. It builds a `FormData`. It appends field `image` with `{data, filename: 'scan-….jpg', contentType: 'image/jpeg'}`.
  2. It reads `getScannerFilters()`.
  3. It posts to `scan` with `Content-Type: multipart/form-data` and a 60 s timeout.
  4. Each result is `success`, `filtered`, `empty` or `error`.
- The scanner store keeps `regionId`, `rarityIds`, `variantIds` and `selectedSets`, which the user sets. The user narrows the search before the server matches.
- Scans then live in a local list (`createScan`, `removeScan`, `clearScans`, `updateVariantForScans`), so the user can set the variant on many scans at once.

**API and users.**
- The HTTP client is `ky`, with `prefix: 'https://clients.dextcg.com/api'`, a 20 s timeout and retry limit 2. A `beforeRequest` hook adds `authorization: Bearer …`, and `auth/refresh` takes `{refreshToken}`. Dex runs its own token auth, not a hosted provider.
- Sign-in: email and password (`/auth/sign-in`, `/auth/sign-up`, `/auth/verify-email`, `/auth/forgot-password`) and Google (`RNGoogleSignin`, `SignInHubActivity`). Apple and Discord strings are present, but their sign-in use is unverified.
- Other services: RevenueCat billing, with web checkout through RevenueCat web billing (`/rcbilling/v1`, plus Stripe and Paddle strings). Statsig flags, Sentry crash reports, and WonderPush push on Firebase Messaging.

**Prices.** One average price per card per market, with the market chosen by region:
- `{'cardmarket': 'avgPriceCardmarket', 'tcgPlayer': 'avgPriceTcgPlayer', 'cardTrader': 'avgPriceCardTrader', 'ebay': 'avgPriceEbay'}`
- Default market by region: `{'international': 'tcgPlayer', 'japan': 'cardTrader', 'china': 'cardmarket'}` (module with `MARKET_ORDER_BY_REGION`, `getMarketAvgPrice`).
- No price per condition or per grade was found. `cardmarketMinimumCondition` is a link-out filter preference only.
- The TCGplayer link is an affiliate link (`partner.tcgplayer.com/APgjZo`).

**Collection shape.** Local SQLite (`expo-sqlite`) DDL, verbatim from the bundle:
- `CREATE TABLE ownedCards (id text PRIMARY KEY NOT NULL, cardId text NOT NULL, userId text NOT NULL, createdAt text NOT NULL, updatedAt text NOT NULL, quantities text NOT NULL);` with a unique index on `cardId`
- `CREATE TABLE cardNotes (… cardId …, notesPerVariant text NOT NULL);`

So the model is one row per card, with quantities per variant stored as text, and nothing else. It has no condition, no grade, no cost and no location. Folders are a server-side concept (`folders`, `folderType`, `folderCards`, binder folders).

**Sync.** Dex works offline first, with a command outbox: `claimUnprocessedSyncCommands`, `releaseSyncCommand`, `syncDate` / `lastSyncDate`, `useLastSyncSuccessDate`. Local writes queue as commands and drain to the API.

**Play filter cause.** The manifest has no `<uses-feature>` and no screen filter. The mirror build carries only an `armeabi-v7a` split, but Play builds its own split set for each device, so the split tells nothing. The block is most likely a device exclusion in the Play Console (unverified).

## Lessons for Banchi

1. **Server matching with user-set filters is the cheap path.** Neither Dex nor Collectr runs a card model on the phone. Dex lets the user narrow by set, rarity and region first. Banchi knows the box and often the set, so it can send those as filters and cut false matches.
2. **Return a typed result, not a guess.** Dex's `success / filtered / empty / error` split is a small, clear contract. "Filtered" (a match exists, but outside the user's filters) is worth copying, because it tells the user to fix the filter, not the photo.
3. **Variant is a batch step after the scan.** Dex keeps scans in a local list and sets the variant for many at once. This fits Banchi's box-at-a-time capture.
4. **Dex's data model is too thin for selling.** It stores only per-variant quantities in one row. That is enough for a collection, but a TCGplayer listing needs condition and language too (one SKU). Banchi needs one row per physical copy or per SKU, plus its location.
5. **Use an offline outbox for capture.** A local command queue that drains on reconnect suits photographing in a storage room with weak signal.
6. **Pick the market by region, and say which one.** Dex maps region to market (international → TCGplayer). Banchi sells on TCGplayer, so TCGplayer is the price of record. Name the source next to every price.
7. **Over-the-air JS updates are a double edge.** Expo Updates lets Dex fix bugs without a store release, but a bad push reaches every user at once. If Banchi's client uses OTA, gate it behind a staged channel.
8. **Do not paywall the core loop, and enforce any paywall on the server.** A bug once gave Dex's free users the paid scanner. The public post does not name the cause.

## Open gaps

- The signer of the mirror build is not verified. Install Android build-tools, then run `apksigner verify --print-certs` on the base APK and compare with the Play signer.
- The scan request's query string is not read. It is unknown whether the filters go as search params or as form fields.
- The server's matching method is unknown (embeddings, OCR, or both). Only the client is visible.
- The price refresh interval is unknown. Neither the bundle nor the website states it.
- The Apple and Discord sign-in paths are not confirmed. Only strings were seen.
- REA's class-level tools could not list the whole class inventory (duplicate-class error). The Java-side evidence is the manifest plus the dex string tables.

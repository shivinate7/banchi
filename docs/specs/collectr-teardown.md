# Collectr teardown

App: `com.collectrinc.collectr` 2.5.10 (code 748), minSdk 24, targetSdk 36. Installed from Google Play on an emulator (API 35, arm64).
Method: public web research, then static analysis of the pulled APKs only. No traffic interception, no API calls, nothing bought.

## Public research

Each bullet carries its source URL.

- **Scanning.** A camera scan finds the set, number and variant, then adds the card. The press calls it "AI-powered". It covers 25+ games and 1M+ products. https://www.getcollectr.com, https://apps.apple.com/us/app/collectr-tcg-collector-app/id1603892248
- **Accuracy is mixed** (unverified, from single reviews): under 90% for one Pro buyer, weak on Japanese variants and graded slabs. https://www.binderdex.com/blog/pokemon-card-scanner-apps-compared, https://rarecandy.com/blog/best-pokemon-card-scanner-apps
- **Prices.** Sources are TCGplayer, eBay and Cardmarket, chosen per product. Detail prices refresh every 1-2 days (help-page snippet, unverified), and the site says "daily". Graded prices come with pop reports. https://getcollectr.notion.site/Everything-You-Wanted-to-Know-About-Prices-f64d490171a549a2bcd1a037e7f74602, https://www.getcollectr.com
- **Collection.** Raw, graded and sealed items, multi-currency, P&L, trade analyzer, social showcases. Box or location tracking: not found. https://apps.apple.com/us/app/collectr-tcg-collector-app/id1603892248
- **Selling.** No checkout. The founders leave buyer and seller protection to eBay and TCGplayer. Revenue is affiliate links, an ad network, and Pro. https://betakit.com/how-collectr-bootstrapped-a-trading-card-hobby-into-an-eight-figure-business/, https://www.fintech.ca/2025/05/22/collectr-worlds-fastest-growing-collectibles-app/
- **Business.** Pro is $7.99/month or $59.99/year. The free scan cap is unpublished (one user says 35, unverified). Export is Pro-only. Import is a TCGplayer CSV emailed to support, 2-3 days (unverified). The company was bootstrapped with a $500K friends-and-family round and has 5 staff. https://apps.apple.com/us/app/collectr-tcg-collector-app/id1603892248, https://www.binderdex.com/blog/pokemon-card-scanner-apps-compared, https://betakit.com/how-collectr-bootstrapped-a-trading-card-hobby-into-an-eight-figure-business/
- **Pitfalls** (weak, from an aggregator): logouts with failed re-login, "no connection" errors, a notification prompt with no close button, wrong camera picked. https://justuseapp.com/en/app/1603892248/collectr-tcg-collector-app/problems

## APK findings (file and function evidence)

Splits pulled: `base.apk`, `split_config.arm64_v8a.apk`, `split_config.en.apk`, `split_config.es.apk`, `split_config.xxhdpi.apk`.

**Framework: Flutter.** The arm64 split ships `lib/arm64-v8a/libapp.so` (15.7 MB Dart AOT) and `libflutter.so`. Assets live under `assets/flutter_assets/`. App logic is in Dart, and the Java side is only a shell. REA's JADX tools cover that shell. REA has no native provider here (Ghidra, Hopper and IDA are not installed, and adding one would be a download), so the Dart evidence below is string literals cited by file offset in `libapp.so` (sha256 `815d203f5c0d895d…`).

**Plugins** (REA `inspect_android_method`, `io.flutter.plugins.GeneratedPluginRegistrant.registerWith`): camerawesome + camera_android_camerax, google_mlkit_barcode_scanning + mobile_scanner, flutter_appauth + flutter_web_auth_2, flutter_secure_storage, sqflite, purchases_flutter (RevenueCat), firebase_analytics/crashlytics/messaging, home_widget, location, pdfx, background_fetch, changeicon, webview_flutter.

**Scanning happens on a server, from the image.**
- Barcode scanning is the only on-device model. The models are `assets/mlkit_barcode_models/*.tflite`, `libbarhopper_v3.so` and class `com.google.mlkit.vision.barcode.bundled.internal.ThickBarcodeScannerCreator`.
- REA's class inventory has none of these: TensorFlow Lite, ML Kit text/label/object, ONNX or PyTorch (9,390 classes, coverage complete).
- Dart names show a server search: `searchWithScan` @0x7e30a, `searchWithScanPost` @0x129bfb, `ScanSearchRequest` @0xa0f90, `ScanSearchResponse`, `FetchScanOptionsResponse`.
- Conclusion: the card image is matched on the server. The proof is the scan-search request names plus the absence of any inference library in the classes and native libs.
- A pre-signed upload route exists (`/create-signed-s3-upload-url` @0x13121e). Profile photos, backgrounds and posts may also use it, so it is not proven to carry scans. The scan request's transport (an upload key or an inline body) is unknown.
- After a scan: `matchedScans` / `unmatchedScans` @0x111fd4, then a review page (`scan_search_confirmation_page`, "Continuar con Escaneos No Coincidentes?"). Foil is chosen by the user or by the server: `ScanFoilOptions.foil|nonfoil|backend` (@0x1095e7 for `.backend`).
- Free scan cap: `scansRemaining` @0x10cbc9, `scanningLimit`, "Tap here to get unlimited scans." @0x154e22. `scansRemaining` may be only a text getter. A server-side count is inferred, not proven.

**Catalog keys follow TCGplayer's shape, with a separate TCGplayer id.** Deep-link regexes use `app.getcollectr.com/sets/category/(\d+)/…?groupId=(\d+)` and `/explore/product/(\d+)`. The category, group and product tiers match TCGplayer's catalog. But the app keeps both `catalog_product_id` and a separate `tcg_id`. So Collectr likely has its own product id plus a TCGplayer mapping (inferred). That fits a catalog of 25+ games. Fields: `catalog_product_id` @0x1211d7, `tcg_id`, `tcgplayer_product_url` @0xbcfd1, `ebay_buy_link` @0xc307f.

**Prices.** Fields `market_price`, `latest_price`, `price_history`, `market_price_diff`, `market_price_percentage_diff`. Routes `/eu-pricing/toggle` @0xa94c2 (an EU price source per user), `/graded-pop` @0x11060e, `/sold-prices` @0x11f5ef. Sold comps load lazily: `We're working on gathering sold listings for your selection.` @0xc10ac.

**Collection shape** (JSON keys in `libapp.so`):
- `user_owned_product_id` @0x10f194 → `catalog_product_id`
- `product_sub_type` (printing) @0x88719
- `card_condition_id`, `card_condition_unit_price` @0x133fd1
- `grade_company` @0xacc52, `grade_id`, `grade_value`, `grade_population`
- `purchase_price`, `average_cost_paid` + `_currency`, `price_override` + `_currency`
- `portfolio_name`, plus totals: `total_cards`, `total_graded`, `total_sealed`, `total_value_currency`

`assets/flutter_assets/assets/compare-grade-config.json` maps one number grade to a list of company grade ids. Routes: `/collections`, `/collections/summary`, `/collections/export` @0xe1892, `/products/bulk-operation` @0x8d183, `/purchase-prices` @0x14930e, `/price-overrides` @0x14df89, `/profit-loss`, `/pnl-profit`, `/watchlist/`, `/trades`. Local cache: sqflite.

**Selling.** There is a browse marketplace (`MarketplaceProductListing` @0x666f9, "View Listings on" @0x12e9b2) and trades (`TradeOffer` @0xff71f). No payment, payout or shipping strings were found. "stripe" appears only as a RevenueCat store name. So buying goes out through links. Users log their own sales ("Sold price is required.", `/sold-prices/export`).

**Users.**
- Login is Auth0 on a custom domain: `auth.getcollectr.com` @0xf0627, `auth0Id`, `newAuth0RefreshToken` @0x10da51, through AppAuth, with tokens in flutter_secure_storage.
- Guest mode: unverified. "Anonymous User" @0x1419d0 and `anon-collectr.png` look like a default name and avatar, not a guest login.
- Account deletion is in the app ("Delete Account ( press and hold )").
- Firebase is used for analytics, crash reports and push only (manifest registrars). There is no Firebase Auth or Firestore.
- Images come from `public.getcollectr.com/public-assets/products/product_<id>.png` and `dmsbhobr66dx6.cloudfront.net` @0xf7467.
- Billing: RevenueCat (Play and Amazon).

## Lessons for Banchi

1. **Keep an own product id, and map it to the TCGplayer SKU.** Collectr's model hangs off `catalog_product_id` + `product_sub_type` + condition, with `tcg_id` as a separate mapping. A TCGplayer listing is per SKU (product + printing + condition + language). So each Banchi owned card must resolve to one SKU before it can list.
2. **Scan on the server, then make the user confirm.** Collectr keeps no recognition model on the device. It matches on the server, and it sends unmatched scans to a review queue instead of guessing. Plan for a "matched / needs review" split from day one, plus a foil override.
3. **Condition and grade are user input, not scan output.** Neither the public research nor the code shows condition detection. Grade is a company + grade id pair, with a cross-company table. Use the same idea if Banchi adds slabs.
4. **Store cost basis and price override per owned item, each with its currency.** Collectr has `average_cost_paid`, `price_override` and their `_currency` fields. P&L is its Pro hook.
5. **Count any free scan cap on the server.** Dex's paywall leak (see dex-research.md) shows the risk. A client-side cap is easy to bypass and drifts across devices.
6. **Prices refresh daily, not live**, with sold comps fetched on demand. Show the price date on every price Banchi uses for a TCGplayer listing.
7. **Gaps Banchi can own.** Collectr has no physical location (box or slot) field, a slow manual import (CSV by email) and Pro-only export. Ship free CSV import and export, and make "which box" a top-level field.
8. **A user complaint to avoid:** Auth0 refresh failures show up as forced logouts. Keep refresh tokens in secure storage and test the token-expiry path.

## Open gaps

- The Dart code was not decompiled (no native provider, and no Dart AOT tool without a new download). Call sites, request bodies and which server does the image matching are unknown.
- The API base host was not found as a literal. It may be built at runtime or read from config. Only `auth.getcollectr.com`, `app.`, `public.` and the CloudFront host are known.
- The price source per field is unknown: which of TCGplayer, eBay or Cardmarket feeds `market_price` and which feeds sold comps. The `/eu-pricing/toggle` route suggests Cardmarket, but this is not proven.
- The free scan cap value is unknown (it is set on the server).
- The marketplace data source (an eBay feed or Collectr's own listings) is unknown. No payment flow was seen, so it is very likely outbound links only.
- Accuracy and user complaints rest on weak public sources. Reddit and the Play reviews did not load.

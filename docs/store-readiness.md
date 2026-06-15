# Store Readiness Checklist

Status: draft checklist for App Store / Google Play submission. Verify current store rules before submitting.

## App Identity

- App name: VPN Router
- Category: VPN / Utilities
- Primary offer: simple subscription VPN routing with RU direct rules and automatic proxy routing for other traffic.
- Support URL: required before submission.
- Privacy Policy URL: required before submission.
- Terms URL: required before subscription purchase.

## Short Description Draft

VPN Router routes RU services directly and other traffic through a VPN profile with automatic node selection.

## Long Description Draft

VPN Router is a mobile VPN service focused on simple everyday use. Connect once and the app receives a subscription-aware routing config from the backend. RU domains and configured RU rule sets are routed directly, while other traffic is sent through available VPN nodes. The backend monitors node health and can remove unhealthy nodes from future configs without requiring an app update.

The service does not store browsing history or traffic content logs. Subscription state is managed through the app stores.

## Required Screenshots

- Main connect screen.
- Subscription screen before purchase.
- Privacy / terms links visible before purchase.
- Connected status screen.
- Node diagnostics screen with example regions and health.

Do not expose real user IPs, access tokens, receipts, node credentials, or internal hostnames in screenshots.

## App Store Notes

- Requires Apple Developer account with Network Extension / Packet Tunnel capability.
- App must declare VPN functionality clearly.
- Complete encryption export compliance questionnaire.
- In-app subscriptions must use Apple IAP for digital service access.
- Provide privacy policy URL and subscription terms before purchase.
- Do not claim perfect anonymity or guaranteed unblock capability.

## Google Play Notes

- Declare VPN functionality and `BIND_VPN_SERVICE` usage.
- Provide privacy policy URL in Play Console and app UI.
- Use Google Play Billing for digital subscriptions distributed through Play.

## RU Payment Notes

- YooKassa redirect payments are the first non-store RU payment provider in the backend contract.
- The app must not collect or store card details; mobile opens the provider confirmation URL.
- Backend verifies YooKassa payment status before issuing an access token.
- App Store / Google Play distribution may still require store billing for digital services in those stores; RU payments should be reviewed per distribution channel before release.
- Complete Data Safety form consistently with `docs/privacy-policy-draft.md`.
- Do not use misleading claims about traffic logging, unblock guarantees, or government/bank access.

## Privacy Labels / Data Safety Draft

Data categories expected:

- User ID or account/install identifier: collected for account and subscription handling.
- Purchase history/subscription state: collected for entitlement validation.
- Diagnostics: collected for crash/error reports and service reliability if enabled.
- App activity / browsing history: not collected.
- Traffic content: not collected.
- Precise location: not collected unless added later.

Final answers must match the production analytics, logging, support, and payment implementation.

## Pre-Submission Gates

- `make ci` passes.
- Production API uses HTTPS.
- Production secrets are not placeholders.
- Privacy policy and terms have final legal approval.
- Store product IDs match backend expected product IDs.
- Device QA passes Android development build.
- Device QA passes iOS build with Network Extension entitlement.
- sing-box/libbox GPL-compatible distribution obligations are satisfied and documented in `docs/oss-decisions.md`.

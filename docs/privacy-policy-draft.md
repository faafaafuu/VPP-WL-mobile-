# Privacy Policy Draft

Status: draft for legal review. Do not publish as final legal text without counsel approval for the target jurisdictions and app stores.

## Service Scope

VPN Router provides a mobile VPN routing service. The app routes traffic according to the active sing-box configuration and subscription status.

## Data We Collect

- Account or installation identifier.
- Device ID generated or supplied by the app for account recovery and subscription matching.
- Store receipt or purchase token during validation.
- Subscription status, product ID, platform, and expiration time.
- VPN node diagnostics needed to keep the service reliable, such as selected region, node health, latency, success rate, and aggregate traffic counters where required for operations or billing.
- Crash and error diagnostics if enabled in a production build.

## Data We Do Not Collect

- We do not store browsing history.
- We do not store DNS query contents as user activity logs.
- We do not inspect or store message contents.
- We do not store full traffic payloads.
- We do not sell personal data.

## Traffic Logs

No traffic content logs are stored. Operational systems may store minimal connection metadata only when required for security, abuse prevention, billing, support, or legal compliance.

## Receipts And Tokens

Store receipts are sent to the backend only for validation. Mobile clients must not persist receipts after activation. Access tokens are stored in Android Keystore-backed storage or iOS Keychain-backed storage.
The backend must not persist raw store receipts; MVP sandbox transaction references are deterministic SHA-256 fingerprints.

## Configuration And Secrets

VPN configs may contain sensitive connection material. Mobile clients store last-known-good configs in secure storage. Backend secrets must be provided through environment variables or a secret manager, not committed to source control.

## Data Retention

Retention should be minimized:

- Account and subscription records are retained while the account is active and for a limited operational/accounting period afterward.
- Operational diagnostics are retained only as long as needed for reliability, abuse prevention, support, and legal compliance.
- Traffic content is not retained because it is not collected.

Specific retention periods must be finalized before production launch.

## User Rights

Users should be able to request:

- access to account/subscription data;
- correction of inaccurate account data;
- deletion of account data where legally permitted;
- export of account/subscription data where required by law.

Production support tooling must include a verified deletion/export workflow before public launch.
The MVP backend exposes `GET /api/me/export` and `DELETE /api/me` as the first self-service account data export/deletion flow.

## Third Parties

The service may use:

- Apple App Store, Google Play, and YooKassa for subscription payments;
- infrastructure providers for API, database, monitoring, and VPN nodes;
- crash/error diagnostics providers if enabled.

Third-party processors must be documented before production launch.

## Children

The service is not intended for children. Age restrictions and store metadata must be finalized before publication.

## Contact

Production policy must include the legal entity name, support email, privacy contact, and jurisdiction-specific contact details where required.

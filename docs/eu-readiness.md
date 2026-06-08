# EU readiness note

Last updated: 2026-06-08

This document records the current low-impact EU readiness posture for FS!QR.
It is not a full GDPR/DSA compliance program. The current goal is to keep the
service implementation mostly unchanged while improving transparency and
cookie/advertising controls.

## Current data handled

- FSQR uploads: encrypted in the browser before upload, stored temporarily in
  the configured upload directory, and deleted manually or after the selected
  retention period.
- Group rooms: room metadata is stored in MySQL, files are stored on the
  server without end-to-end encryption, and rooms expire after the selected
  retention period.
- Note rooms: room metadata and note content are stored in MySQL. Note content
  is not end-to-end encrypted and expires after the selected retention period.
- Share links: token hashes and encrypted room passwords are stored in MySQL.
- Sessions, CSRF state, rate limits, and presence state are stored in Redis.
- IP addresses are used for rate limiting and GeoIP language detection.
- Error logs may contain operational metadata needed for troubleshooting.

## Public notices

- The privacy policy discloses the data categories, purposes, Japan-based
  storage, Google Analytics, Google AdSense, Google Forms, DB-IP, retention, and
  deletion/reporting contact route.
- The terms disclose user responsibility for shared URLs, IDs, and passwords,
  temporary retention, unencrypted Group/Note storage, prohibited content, and
  operator deletion or access restriction for abusive or illegal content.
- The contact page accepts privacy inquiries, deletion requests, and reports of
  illegal or rights-infringing content through the existing Google Form.

## Cookie and advertising controls

- Essential cookies remain always on for sessions, CSRF, language preference,
  and storing the cookie-consent choice.
- Google Analytics is loaded only when the stored consent allows analytics.
- Google AdSense is loaded only when the stored consent allows marketing.
- Existing legacy consent value `accepted` is treated as allowing both
  analytics and marketing. `rejected` disables both optional categories.
- Google AdSense EU/GDPR messaging should also be enabled in the AdSense
  console so Google can present any required ad consent flow for EEA/UK/Swiss
  traffic.

## Operational handling

- Deletion requests should include the target URL or room ID and enough detail
  to identify the resource. Use existing owner-delete or admin-delete tools to
  remove confirmed resources.
- Illegal-content or rights-infringement reports should include the target URL,
  room ID, description of the issue, and reporter contact. Confirm the target,
  remove or restrict access if appropriate, and reply through the contact route.
- Privacy inquiries should be handled manually through the Google Form inbox.

## Known gaps

- No automated data subject request workflow.
- No dedicated DSA notice-and-action database or moderation dashboard.
- No EU representative or DPO configuration in the application.
- No EU-region data separation.
- Group and Note content are not end-to-end encrypted.
- Consent receipts are not stored server-side.

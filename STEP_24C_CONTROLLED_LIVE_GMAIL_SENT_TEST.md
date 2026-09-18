# STEP 24C — Controlled Live Gmail Sent Read-Only Test

## Test objective

Validate one exact deterministic outbound RFC Message-ID against the approved TEST account's Gmail Sent metadata using read-only operations only.

## Precondition result

An existing local outbox intent was found for the approved controlled test operation.

- TEST account: `sivalingam7339@gmail.com`
- Operation ID: `controlled_test_email:v1:step24c`
- Message-ID digest: `2d7b58992e81153c`
- Fingerprint digest: `4adf1cf6dafbfe53`
- Outbox state before validation: `SENT_CONFIRMED`

The full RFC Message-ID, message body, and token/credential contents were not recorded.

## Live lookup result

The read-only Gmail Sent adapter was invoked under the required account guard, but it stopped before creating a Gmail client or making a Gmail API request. Its existing Gmail read-only token did not pass the adapter's validity/scope check. Per the read-only guard, it was not refreshed, rewritten, or reauthorized.

- Live Sent lookup performed: no (blocked by the local read-only authentication guard)
- Sent candidates: not queried
- Reconciliation result: `BLOCKED` — existing Gmail read-only authentication is not valid
- Additional send attempts during reconciliation: 0
- Outbox mutation: no
- Ledger mutation: no

## Safety verification

- No email was sent.
- No Gmail API message operation occurred; therefore no message was read, modified, deleted, labeled, or archived.
- No outbox, ledger, Sheet, Form, OAuth/token, `.env`, or Task Scheduler state was changed.
- No email body, attachment, credential, or token value was displayed or recorded.

## Failure/recovery notes

Before the controlled live validation can proceed, the existing read-only Gmail authentication must be restored through the approved operator-led OAuth recovery process. Do not manually edit token files, invent a Message-ID, or create another test intent merely to search Gmail.

## OAuth recovery — 2026-09-16

- Recovery attempted: yes
- Required TEST account: `sivalingam7339@gmail.com`
- Token path used: `C:\Mail\token.json`
- Authentication result: recovered by the existing refresh-token mechanism and validated against the approved TEST account
- Scope validation: Gmail read-only access available
- Token file updated by the legitimate refresh: yes
- `credentials.json` modified: no
- Sent lookup performed: no
- Email sent: no
- No Gmail message search, send, modify, or delete operation was performed during recovery.
- The token ACL remained inheritance-disabled with no broad access entry.

## Retried controlled live Sent reconciliation — 2026-09-16

- Authenticated TEST account: `sivalingam7339@gmail.com` (account guard passed)
- Operation ID: `controlled_test_email:v1:step24c`
- Message-ID digest: `2d7b58992e81153c`
- Fingerprint digest: `4adf1cf6dafbfe53`
- Exact Gmail Sent search key: the existing deterministic RFC Message-ID from the outbox record
- Live operation: one read-only Gmail Sent metadata lookup (`list` followed by metadata-only `get` when candidates exist)
- Sent candidates found: `0`
- Reconciliation result: `INVALID_METADATA`

The result is a validation failure. The Sent lookup found no evidence for the exact Message-ID. In addition, the existing Step 23D reconciler accepts only `customer_reply` and `internal_notification` workflow types; the isolated test intent has workflow type `controlled_test_email`, so its direct strict-evidence result is `INVALID_METADATA` rather than `NOT_FOUND`.

Safety verification: zero Gmail send attempts; no Gmail message modification/deletion; and no outbox, customer ledger, internal-notification ledger, Form-processed ledger, token, Sheet, Form, Scheduler, or `.env` modification. No email body, attachment, secret, token, or credential content was recorded.

## Supported customer-reply preflight — 2026-09-16

The one-time supported-workflow test runner passed syntax validation and performed its explicit no-send preflight. It verifies the approved TEST account and searches only for an unreplied inbound source message from the approved external TEST recipient before it is permitted to create a `customer_reply` intent.

Preflight result: **BLOCKED**. No unreplied inbound Gmail message from `arthikaraj18@gmail.com` was available. Therefore no source thread ID or source RFC Message-ID could be selected, no customer-reply outbox intent was created, and no email was sent.

This stop is intentional. Strict customer-reply reconciliation requires the genuine source thread ID and RFC Message-ID. The test must not fabricate these values or send a standalone message as a customer reply.

## Supported customer-reply live retry — 2026-09-16

- Approved TEST account guard: passed (`sivalingam7339@gmail.com`)
- Approved test recipient: `arthikaraj18@gmail.com`
- Genuine inbound source: found with a Gmail API message ID, thread ID, and RFC Message-ID; source subject matched `STEP 24C FINAL TEST - Installation Support`
- Workflow type: `customer_reply`
- Deterministic operation ID: `customer_reply:v1:1a0a91925b74841c` (derived by the existing production rule from the genuine source Gmail message ID)
- Outbound Message-ID digest: `79ffb4cb1ea00380`
- Fingerprint digest: `4eaed3bd0bd85a7f`
- Send attempt count: `1`
- Controlled email send: exactly one successful Gmail send response was received

The immediate exact read-only Gmail Sent metadata lookup returned zero candidates and the strict result was `NOT_FOUND`. A later exact read-only lookup also returned zero candidates. No resend was attempted.

The durable outbox currently reports `LEDGER_RECORDED` with `ledger_recorded=true`; however, a later zero-candidate lookup cannot independently prove strict live confirmation. Because the unattended scheduled workflow may have run concurrently, this state must not be treated as standalone proof that this controlled runner received a strict `CONFIRMED` result.

Safety: no second send; no Google Form, Google Sheet, Cases source, `.env`, credential, token, or Task Scheduler modification was made by this controlled runner. The customer-reply outbox record and its normal customer ledger transition are the only workflow-state changes.

## Final strict reconciliation after fallback fix — 2026-09-16

The Gmail Sent adapter now keeps exact RFC Message-ID lookup as its first method. When Gmail has replaced that RFC header, it uses only the existing customer-reply source thread as a bounded Sent fallback and then applies strict evidence matching.

For the already-sent legacy controlled reply (sent before the new dedicated outbound-ID marker existed):

- Account guard: passed
- Actual supported operation ID: `customer_reply:v1:1a0a91925b74841c`
- Sent candidates: `1`
- Strict reconciliation result: `CONFIRMED`
- Gmail message ID digest: `f6feeb252d2e3160`
- Gmail thread ID digest: `a700c548f42bf59c`
- Outbox state: `LEDGER_RECORDED`
- Outbox mutation during validation: no
- Email sent during fix/validation: no
- Gmail modify/delete: no
- Second email sent: no

Future customer-reply and internal-notification messages include `X-Customer-Case-Outbound-Message-ID`, containing a header-safe deterministic marker. Future strict confirmation requires that marker in addition to the existing sender, recipient, subject, operation ID, fingerprint, and workflow-specific evidence.

## Recommendation for Step 24D

Step 24D is not ready. After operator-led recovery of the existing Gmail read-only authentication, repeat this exact Step 24C lookup using the existing controlled-test outbox intent. Do not resend the test email.

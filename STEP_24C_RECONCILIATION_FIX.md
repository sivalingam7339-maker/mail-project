# STEP 24C — Gmail Sent Fallback Discovery Fix

## Problem

Gmail may replace a caller-supplied RFC `Message-ID` in the Sent copy. The former adapter searched only `rfc822msgid:` using the locally requested ID, so an accepted message could be missed.

## Safe implementation

1. Exact `in:sent rfc822msgid:` lookup remains the first discovery method.
2. If that returns no result, customer replies use only the known source Gmail thread as their bounded fallback; only messages carrying the `SENT` label are considered.
3. The candidate is pre-filtered by sender, recipient, subject, and operation-ID header, then passed to the existing strict reconciler.
4. Future outbox intents preserve a header-safe SHA-256 marker of the deterministic outbound RFC Message-ID in `X-Customer-Case-Outbound-Message-ID`.
5. Future strict reconciliation requires that marker, plus sender, recipient, subject, operation ID, fingerprint, and workflow-specific evidence.
6. Legacy intents created before the marker require all pre-existing strict evidence: sender, recipient, subject, operation ID, fingerprint, thread ID, and `In-Reply-To`. Their Gmail RFC `Message-ID` is not used as an identity requirement because Gmail replaced it.

No recipient/subject-only candidate can be confirmed. Zero candidates remain `NOT_FOUND`; conflicting evidence remains `MISMATCH`; multiple strict matches remain `AMBIGUOUS`; none can cause an automatic resend.

## Tests

Relevant local fake-only tests passed after the change:

- `test_send_outbox.py`
- `test_send_outbox_integration.py`
- `test_gmail_sent_reconciliation.py`
- `test_gmail_sent_live_adapter.py`
- `test_step24b_reconciliation_integration.py`

They cover exact matches, Gmail-replaced RFC IDs with strict legacy evidence, future outbound-ID markers, missing/conflicting candidates, ambiguity, idempotent state handling, and no-resend behavior.

## Live controlled validation

- TEST account guard: passed
- Supported workflow: `customer_reply`
- Actual operation ID: `customer_reply:v1:1a0a91925b74841c`
- Outbound Message-ID digest: `79ffb4cb1ea00380`
- Fingerprint digest: `4eaed3bd0bd85a7f`
- Bounded Sent candidates: `1`
- Strict reconciliation: `CONFIRMED`
- Outbox state after validation: `LEDGER_RECORDED`
- Outbox modified during validation: no
- Email sent during fix/validation: no
- Gmail modify/delete: no
- Second email sent: no

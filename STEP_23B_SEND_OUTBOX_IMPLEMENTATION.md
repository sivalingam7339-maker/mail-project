# STEP 23B — Send Outbox Foundation

## Architecture

`src/send_outbox.py` provides local, one-record-per-operation JSON send intents in `.send_outbox/`. Records are atomically replaced after a temporary file is flushed and synced. The module does not import Gmail clients or make network calls.

## Identity and records

- Customer operation ID: `customer_reply:v1:<incoming Gmail API message ID>`
- Internal operation ID: `internal_notification:v1:<Form Response ID>`
- The filename is a SHA-256 hash of the operation ID; the full operation ID remains in the record.
- A deterministic outbound RFC Message-ID is derived from the operation ID before any future send.

Records contain operational identifiers, timestamps, state, attempt count, Gmail identifiers when known, and hashes for recipient, subject, and intended message fingerprint. They never store OAuth material, raw MIME, attachments, invoices, images, or complete message bodies.

## State machine

`PENDING -> SENDING -> SENT_CONFIRMED -> LEDGER_RECORDED` is the normal path. A send with an uncertain outcome moves to `RECONCILIATION_REQUIRED`; it is never automatically resent. `FAILED_SAFE` also blocks automatic sending.

Valid transitions are:

- `PENDING -> SENDING` or `FAILED_SAFE`
- `SENDING -> SENT_CONFIRMED` or `RECONCILIATION_REQUIRED`
- `SENT_CONFIRMED -> LEDGER_RECORDED`
- `RECONCILIATION_REQUIRED -> SENT_CONFIRMED` or `FAILED_SAFE`

## Locking

The outbox uses its own non-blocking local Windows lock, separate from the Case Results lock. It protects intent creation and state changes, but is deliberately not held during a future Gmail network request. This protects a single Windows host only.

## Reconciliation foundation

Fake-metadata helpers verify all available evidence: sender, recipient hash, subject hash, deterministic Message-ID, operation header value, message fingerprint, and for customer replies, thread ID and `In-Reply-To`. Step 23B makes no Gmail API calls.

## Current integration status

The live customer-reply sender, internal notifier, Form processor, and existing ledgers are intentionally unchanged. Step 23C will create intents before sending, add deterministic reconciliation headers, reconcile Gmail Sent messages, then update existing ledgers only after confirmation.

**Real Gmail sending and Gmail API reconciliation are intentionally NOT implemented/tested in Step 23B.**

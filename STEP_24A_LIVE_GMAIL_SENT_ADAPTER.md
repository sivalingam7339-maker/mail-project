# STEP 24A — Live Gmail Sent Metadata Adapter

## Implementation result

`src/gmail_sent_live_adapter.py` provides an explicit-flag, read-only Sent metadata adapter. It uses only Gmail list/get metadata operations when a future operator supplies `--live-read-only` and an existing deterministic outbound RFC Message-ID.

## Authentication and guards

The adapter reads the existing Gmail read-only token without refreshing, writing, or reauthorizing it. Before any Sent lookup, it verifies the authenticated account equals the configured approved TEST account. The adapter exposes no send, modify, delete, label, or attachment methods.

## Search and returned evidence

Search is restricted to `in:sent rfc822msgid:<deterministic-message-id>`. The adapter returns only Gmail message/thread IDs and selected metadata headers: From, To, Subject, Message-ID, operation ID, In-Reply-To, and the optional fingerprint header. It never requests full bodies or attachments.

The existing Step 23C message builders do not yet write `X-Customer-Case-Message-Fingerprint`, so live metadata-only evidence currently cannot meet the strict fingerprint requirement for confirmation. This limitation is intentionally safe: it results in non-confirmation, never a resend.

## Read-only outbox helper

`reconcile_existing_intent_read_only()` loads an intent, obtains adapter evidence, and returns the Step 23D reconciliation result without changing the outbox, ledgers, Gmail state, or workflow state.

## Live test status

No live Gmail lookup was performed during implementation.

## Future controlled command

```powershell
.\.venv\Scripts\python.exe .\src\gmail_sent_live_adapter.py --live-read-only --message-id "<existing-deterministic-message-id>"
```

Run this only with an exact existing outbound Message-ID and explicit TEST-account approval.

## Step 24B requirements

Add the deterministic message-fingerprint header to future outgoing messages, implement an approved live adapter integration path that mutates outbox state only after strict confirmation, apply runtime outbox ACLs, and perform an explicitly approved TEST-only live metadata test before enabling automatic live reconciliation.

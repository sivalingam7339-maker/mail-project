# STEP 24C Final Diagnostic — Gmail Sent Lookup

## Scope and safety

This was a read-only diagnostic of the already-sent controlled `customer_reply`. No email was sent, no Gmail message was modified/deleted, and no outbox, ledger, Google Sheet, Google Form, OAuth/token, Scheduler, or `.env` state was changed.

## Local record finding

The requested record name `customer_reply:v1:step24c_final` does not exist. The actual supported customer-reply operation was correctly created by the existing deterministic production rule from the genuine Gmail source message:

- Actual operation ID: `customer_reply:v1:1a0a91925b74841c`
- Workflow type: `customer_reply`
- Outbound deterministic Message-ID digest: `79ffb4cb1ea00380`
- Fingerprint digest: `4eaed3bd0bd85a7f`
- Source/sent thread ID digest: `a700c548f42bf59c`
- Gmail API sent-message ID digest: `f6feeb252d2e3160`
- Attempt count: `1`
- Current outbox status: `LEDGER_RECORDED`

## Read-only Gmail evidence

The approved TEST account guard passed. Only Gmail profile, `messages.list`, `messages.get` with `format=metadata`, and `threads.get` with `format=metadata` were used. No body or attachment was retrieved.

| Method | Safe query / request | Candidates | Strict match | Evidence |
| --- | --- | ---: | --- | --- |
| Deterministic RFC ID with brackets | `in:sent rfc822msgid:<outbound-message-id>` | 0 | N/A | No Gmail Sent candidate was indexed under the stored deterministic RFC Message-ID. |
| Deterministic RFC ID without brackets | `in:sent rfc822msgid:outbound-message-id-without-angle-brackets` | 0 | N/A | Same result; query punctuation is not the cause. |
| Recipient plus controlled-test subject | `in:sent to:approved-test-recipient subject:controlled-test-subject` | 1 | No | Found the known sent Gmail message and the expected thread. |
| Sent day plus approved recipient | `in:sent to:approved-test-recipient after:2026/09/16 before:2026/09/17` | 1 | No | Found the same sent Gmail message. |
| Existing source-thread metadata | `threads.get(existing-source-thread-id)` | 2 | No | Found the inbound source plus the known Sent reply in the same thread. |

For the Sent candidate found by the recipient/subject, day/recipient, and thread methods:

- Gmail message ID digest: `f6feeb252d2e3160`
- Thread ID digest: `a700c548f42bf59c`
- The sender, recipient, subject, operation-ID header, fingerprint header, thread ID, and `In-Reply-To` all matched the controlled intent.
- The Gmail-returned `Message-ID` header digest was `032face5ff60e227`, which **did not** match the stored deterministic outbound Message-ID digest `79ffb4cb1ea00380`.

## Root cause

Gmail accepted the message but assigned/replaced the RFC `Message-ID` header exposed in the Sent copy. The current live adapter searches solely using the pre-send deterministic ID through `rfc822msgid:`. Gmail therefore returns zero candidates for that ID.

This is not caused by recipient, subject, thread, `In-Reply-To`, operation-ID header, fingerprint header, or Sent-folder placement: the read-only candidate found by alternative metadata-only discovery matched all of those values. The failure is specifically the mismatch between the stored requested RFC `Message-ID` and Gmail's actual Sent-copy RFC `Message-ID`.

## Safe fix required (not implemented)

Do not weaken strict reconciliation. Preserve strict identity evidence while separating **candidate discovery** from **candidate confirmation**:

1. Add a dedicated immutable custom header containing the deterministic outbound ID (for example `X-Customer-Case-Outbound-Message-ID`) to both supported send workflows.
2. Extend the metadata-only adapter to retrieve that header and the actual Gmail-returned RFC `Message-ID`.
3. Use a conservative Sent discovery fallback only when `rfc822msgid:` returns zero—scoped to the existing supported operation evidence and bounded time/recipient/thread context.
4. Confirm only a single candidate whose operation ID, fingerprint, custom deterministic-outbound-ID header, sender, recipient, subject, and workflow-specific thread/`In-Reply-To` values all match. Continue to return `NOT_FOUND`, `MISMATCH`, or `AMBIGUOUS` otherwise; never resend automatically.
5. Persist the observed Gmail RFC `Message-ID` only after strict confirmation if it is useful operational metadata; do not replace the deterministic outbound identity.

This retains, rather than bypasses, strict reconciliation: a broad discovery result is never accepted unless all deterministic and workflow-specific metadata agree.

## Files that would need modification

- `src/form_reply_sender.py` — add the dedicated deterministic-outbound-ID header for customer replies.
- `src/internal_case_notifier.py` — add the same header for internal notifications.
- `src/gmail_sent_live_adapter.py` — retrieve the additional header and implement a bounded fallback discovery method.
- `src/send_outbox.py` and/or `src/gmail_sent_reconciliation.py` — compare the preserved deterministic header while retaining strict candidate confirmation.
- Local fake test files for the above behavior.

No code change was made by this diagnostic.

# STEP 23C — Send Outbox Integration

## Implementation result

The existing customer reply and internal notification paths now create a durable intent before their Gmail send call. This step was tested only with fake callables; no Gmail API operation was executed during implementation.

## Customer reply integration

The customer operation ID is based on the incoming Gmail API message ID. A PENDING intent becomes SENDING before the send callable runs. The in-thread reply preserves recipient, subject, `In-Reply-To`, `References`, thread ID, and existing body. It now also carries deterministic `Message-ID` and `X-Customer-Case-Operation-ID` headers. A confirmed send is recorded in the outbox before the existing reply ledger is written, then becomes LEDGER_RECORDED.

## Internal notification integration

The internal operation ID is based on the existing Form Response ID. A standalone notification uses the original recipient, subject, and content, plus deterministic reconciliation headers. Confirmation is persisted as SENT_CONFIRMED; the Form processor writes the existing notification ledger and then records LEDGER_RECORDED before recording the processed-response ledger.

## Failure and restart behavior

SENDING, RECONCILIATION_REQUIRED, FAILED_SAFE, and LEDGER_RECORDED intents are never automatically resent. A pre-existing SENT_CONFIRMED intent can complete its missing existing ledger without sending again. Live Gmail Sent reconciliation is intentionally not implemented in this step, so unresolved sends remain blocked pending Step 23D.

## Idempotency

Outbox operation IDs and outbound RFC Message-IDs are deterministic. Existing intent state is authoritative over a second send attempt. The local outbox lock remains single-host protection only.

## Test results

Local fake tests verify confirmed sends, outbox state ordering, deterministic headers, no resend after restart, uncertain-send blocking, and both workflow identities.

## Live Gmail status

No real Gmail send or Gmail Sent reconciliation was performed during Step 23C.

## Safety verification

No Form response or Google Sheet was processed or modified during testing. No token, credential, `.env`, or Task Scheduler setting was modified.

## Remaining limitations and Step 23D prerequisites

Before any controlled live reconciliation/send test, implement and test a Gmail Sent metadata adapter that searches by deterministic Message-ID and verifies all stored evidence. Define operator handling for unresolved intents, apply restrictive ACLs to a runtime outbox directory if it is created, and perform a controlled test account-only approval.

# STEP 24B — Strict Reconciliation Integration

## Fingerprint headers

Customer replies and internal notifications now include `X-Customer-Case-Message-Fingerprint`. Its value is the existing Step 23B outbox `message_fingerprint`; no second fingerprint algorithm was introduced. Existing bodies and recipient/thread behavior remain unchanged.

## Explicit reconciliation integration

Adapter-injected helpers reconcile only a pre-existing uncertain outbox intent. Exact Step 23D evidence moves it to `SENT_CONFIRMED`, records the applicable existing ledger, and then moves it to `LEDGER_RECORDED`. The helpers do not send email.

## Safety behavior

`NOT_FOUND`, `MISMATCH`, `AMBIGUOUS`, and `INVALID_METADATA` leave the intent unresolved. They do not write a ledger, process a Form response, or make an intent sendable. Scheduled workflows do not instantiate or invoke the Step 24A live adapter.

## Form processor safety

The existing processor continues to record its processed-response ledger only after Case Results succeeds and its internal notification ledger is recorded. Unresolved notification outcomes still raise failure and leave the Form response unprocessed.

## Remaining prerequisites

No live Gmail reconciliation was tested. Before a controlled live test, add an explicitly approved invocation path for the Step 24A adapter, apply runtime outbox ACLs, define operator handling for unresolved intents, and use only the approved TEST account.

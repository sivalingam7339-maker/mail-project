# STEP 23D — Gmail Sent Reconciliation Adapter

## Implementation result

Step 23D adds a strict, adapter-driven Sent metadata reconciliation foundation. It does not import, initialize, or call a Gmail API client.

## States

- `CONFIRMED`: exactly one candidate satisfies every required evidence field.
- `NOT_FOUND`: no candidate matched the deterministic outbound RFC Message-ID search key.
- `MISMATCH`: candidates existed but did not satisfy strict evidence.
- `AMBIGUOUS`: multiple candidates independently satisfied all evidence.
- `INVALID_METADATA`: intent or candidate metadata is incomplete.

Only an exact `CONFIRMED` result transitions a `RECONCILIATION_REQUIRED` outbox record to `SENT_CONFIRMED`. All other results leave the intent unresolved and never make it sendable.

## Evidence

Customer reply confirmation requires sender, recipient, subject, deterministic outbound Message-ID, operation header, message fingerprint, thread ID, and `In-Reply-To`. Internal notification confirmation requires the common sender/recipient/subject/Message-ID/operation-header/fingerprint evidence without customer thread evidence.

## Failure and restart behavior

An unresolved outbox record remains `RECONCILIATION_REQUIRED` on no match, mismatch, ambiguity, or missing metadata. A re-run after confirmation is idempotent and does not search again for already confirmed/ledger-recorded states.

## Test and live status

All tests use `FakeSentMetadataAdapter` and local temporary outbox directories. Real Gmail sending and Gmail Sent searching were not performed or tested in Step 23D.

## Future controlled live-test prerequisites

Implement a Gmail Sent adapter that searches by deterministic Message-ID and fetches metadata only, apply approved runtime outbox ACLs, define operator handling for unresolved intents, and obtain explicit TEST-account-only approval before any live API test.

# STEP 24C-TEST — Isolated Controlled Test Email

## Purpose and isolation

This runner exists only to create one approved TEST self-send for a later read-only Sent reconciliation validation. It does not import or execute the automation runner, customer reply workflow, internal notification workflow, Form processor, Cases matching, or Case Results logic.

## Fixed test identity

- Test account and recipient: the approved configured TEST Gmail account
- Operation ID: `controlled_test_email:v1:step24c`
- Subject: `STEP 24C CONTROLLED TEST - DO NOT REPLY`
- Body: minimal test-only content with no customer or case data

## Outbox and headers

On an explicitly confirmed send only, the runner creates one existing Step 23B outbox intent before Gmail send. It uses the outbox deterministic RFC Message-ID and message fingerprint, and adds `Message-ID`, `X-Customer-Case-Operation-ID`, and `X-Customer-Case-Message-Fingerprint` MIME headers. No customer, internal-notification, or Form-processing ledger is used or changed.

`SENT_CONFIRMED` remains intentionally unfinalized so a later read-only reconciliation can independently validate the sent message. An uncertain result becomes `RECONCILIATION_REQUIRED` and never retries automatically.

## Dry run and controlled send

Without `--confirm-send`, the runner verifies the account and prints only account, recipient, subject, operation ID, and digests. It creates no outbox intent and makes zero Gmail send calls.

The one manual controlled send command is:

```powershell
.\.venv\Scripts\python.exe .\src\controlled_test_email.py --confirm-send
```

Do not run it more than once. After successful manual send, confirm its outbox status is `SENT_CONFIRMED`, then separately conduct the Step 24C read-only Sent lookup using the existing deterministic Message-ID. Do not send a follow-up email.

## Safety limitations

The real send command is intentionally not run by implementation or tests. Runtime outbox ACL hardening and explicit operator approval remain required before the manual send. Live reconciliation remains a separate read-only step.

# Customer Case Automation System

## 1. Project objective

The system supports a controlled customer-case workflow: monitor customer email, conservatively identify case-related messages, reply with a Google Form link, collect case details, match the submitted Order ID against current Cases data, save results, notify the internal team, and preserve idempotency and recovery safety throughout.

## 2. System architecture

```text
Customer Email
        ↓
Gmail Selection & Filtering
        ↓
Automatic Form Reply
        ↓
Google Form
        ↓
Google Sheets Response
        ↓
Order ID Case Matching
        ↓
Case Results
        ↓
Internal Team Notification
        ↓
Outbox / Ledger / Reconciliation
```

## 3. Technologies used

- Python 3.12
- Gmail API
- Google Forms
- Google Sheets API
- OAuth 2.0
- Windows Task Scheduler
- Google Sheets as the initial Cases data source
- Future Kinetiq API integration path

## 4. Main modules

| Module | Purpose |
| --- | --- |
| `gmail_reader.py` | Read-only Gmail authentication and message reading utility. |
| `gmail_selection.py` | Conservative bounded Gmail message selection for scheduled processing. |
| `customer_email_filter.py` | Determines whether a message appears to be a customer case; uncertainty is skipped. |
| `form_reply_sender.py` | Thread-based Google Form reply workflow with duplicate protection and outbox integration. |
| `sheets_reader.py` | Read-only Google Form response spreadsheet access and response-tab detection. |
| `cases_sheet_source.py` | Current read-only Cases Sheet data-source adapter. |
| `case_matching.py` | Searches all Cases rows for an Order ID and returns every status. |
| `form_case_match.py` | Connects the latest Form response to the matching workflow. |
| `new_form_response_processor.py` | Processes new Form responses in chronological order with ledgers. |
| `case_results_writer.py` | Writes and recovers idempotent Case Results rows. |
| `internal_case_notifier.py` | Creates the internal notification after Case Results completion. |
| `send_outbox.py` | Deterministic send intents, state transitions, fingerprints, and local locking. |
| `gmail_sent_reconciliation.py` | Strict Sent-evidence reconciliation for supported workflows. |
| `gmail_sent_live_adapter.py` | Read-only Gmail Sent metadata adapter using list/get only. |
| `automation_runner.py` | One-shot master runner for customer-email and Form-response workflows. |
| `retry_utils.py` | Conservative transient-failure retry helper. |
| `automation_logger.py` | Centralized local rotating logging. |
| `config.py` | TEST environment configuration loading and validation. |

## 5. Google Form

The customer case form collects:

1. Order ID
2. CX Number / Customer Number
3. Issue / Problem Description
4. Invoice
5. State
6. Pincode
7. Complete Address
8. Customer Image / Issue Image
9. Additional Remarks

Order ID is the primary case-checking identifier. Required/optional behavior is configured in the Google Form, and file fields are handled as links/values without downloading attachments into this project.

## 6. Case matching logic

Order IDs are treated as trimmed text, never converted to numbers. The matching layer reads all currently available Cases rows, searches Column A, and returns every corresponding Column G status. It never stops at the first occurrence. If no match exists, it reports `ORDER ID NOT FOUND IN CASES`.

Validated example:

```text
Order ID: 406-3192266-2263517
Spare Needed
Closed
Dropped
Closed
Closed
```

The matching logic is separated from the Cases data-source adapter, so the Google Sheet source can later be replaced by a Kinetiq API without rewriting matching behavior.

## 7. Case Results

Current Case Results schema (A:N):

```text
Timestamp | Order ID | CX Number / Customer Number | Issue / Problem Description |
Invoice | State | Pincode | Complete Address | Customer Image / Issue Image |
Additional Remarks | Case Count | Case Statuses | Result | Response ID
```

`Response ID` is the deterministic identity key for a submitted Form response. It prevents a repeated attempt from appending another Case Results row, while two legitimate identical submissions with different Response IDs remain distinct. Historical legacy rows remain unchanged and are not retroactively rewritten.

## 8. Automatic customer reply

Eligible customer-case email is selected conservatively, then replied to in the same Gmail thread with the professional Google Form message and link. Safety filters exclude self-mail, no-reply addresses, Google system/security mail, automated messages, and uncertain or unrelated messages. The customer-reply ledger and outbox prevent duplicate replies.

## 9. Internal notification

After Case Results are successfully saved or reconciled, the system prepares an internal notification for the configured internal TEST recipient. The notification ledger is recorded only after the send outcome is confirmed, preventing duplicate notifications on ordinary reruns.

## 10. Idempotency and recovery

- `.form_processed_response_ids.json` records fully completed Form responses.
- `.form_reply_replied_message_ids.json` records completed customer replies.
- `.internal_notified_response_ids.json` records completed internal notifications.
- Deterministic operation IDs, outbound RFC Message-IDs, and message fingerprints identify email send intents.
- The local outbox uses `PENDING`, `SENDING`, `SENT_CONFIRMED`, `LEDGER_RECORDED`, and reconciliation-required states.
- If Gmail acceptance is uncertain, the send remains unresolved and is **not** blindly retried.
- A response is marked processed only after Case Results and the required internal notification succeed.

## 11. Gmail reconciliation

Gmail reconciliation searches Sent metadata by the deterministic outbound RFC Message-ID and evaluates exact evidence: operation ID, fingerprint, sender/recipient, subject, and workflow-specific metadata. Supported production workflow types are `customer_reply` and `internal_notification`.

Possible outcomes are `CONFIRMED`, `NOT_FOUND`, `MISMATCH`, `AMBIGUOUS`, and `INVALID_METADATA`. Ambiguous, missing, or mismatched evidence never triggers an automatic resend.

## 12. Retry and error handling

Temporary network/API failures can be retried for up to three total attempts with exponential backoff. Permanent authentication, permission, configuration, malformed-data, and invalid-request errors are not retried. Gmail sends with uncertain acceptance are not blindly retried; reconciliation/outbox state is used instead.

## 13. Security

- OAuth 2.0 uses separate local workflow token files.
- Credentials and token files have restrictive Windows ACLs.
- `.gitignore` protects credentials, tokens, ledgers, logs, virtual environments, and `.env`.
- TEST configuration is separated into local configuration; `.env` contains no OAuth client secret, access token, refresh token, or password.
- Logs and outbox records avoid email bodies, attachment contents, OAuth values, and unnecessary customer personal data.

## 14. Logging

`logs/automation.log` records workflow start/end, success/failure, exceptions, and exit codes with timestamps. Python's rotating file handler limits each log to 1 MiB and retains three backups. Console output remains available for manual runs.

## 15. Automation

Windows Task Scheduler launches the one-shot batch launcher every five minutes and at user logon. Its execution limit is 15 minutes, restart-on-failure is configured, and wake-to-run is enabled. The task currently uses the logged-in Windows user context (`InteractiveToken`), which remains an operational limitation.

## 16. Testing results

| Step / area | Test area | Result |
| --- | --- | --- |
| Steps 1–3 | Gmail OAuth/read-only setup and Google Sheets response reading | Completed successfully |
| Steps 4–5 | Duplicate Order ID matching and Form-to-Cases matching | Completed successfully |
| Steps 6–7 | Controlled customer-reply workflow and new Form-response processing | Completed successfully |
| Steps 8–9 | Case Results and internal notification ordering | Completed successfully |
| Steps 10–11 | Unified runner, Task Scheduler launcher, and Gmail filtering | Completed successfully |
| Steps 12–14 | Validation checklist, logging, retry/recovery local tests | Completed successfully |
| Steps 15–17 | Readiness audit, local-file protection, configuration separation | Completed successfully |
| Steps 18–20 | Gmail-selection safety audit and Task Scheduler reliability hardening | Completed successfully |
| Steps 21–22 | OAuth ACL hardening, recovery documentation, Response ID design/schema implementation | Completed successfully |
| Steps 23–24B | Outbox, fake reconciliation, Sent adapter, and strict evidence local tests | Completed successfully |
| Step 24C | Final controlled live Gmail Sent reconciliation | **PASS** — a genuine supported `customer_reply` was used; exactly one controlled reply had been sent, one bounded Sent candidate was found, and strict reconciliation returned `CONFIRMED`. Gmail's RFC Message-ID replacement was handled by the strict bounded fallback fix. No second email was sent. This is **LIVE** Gmail evidence. |
| Step 24D | Final complete workflow and recovery validation | **PASS** — live Gmail customer-reply/reconciliation evidence passed; existing validated TEST evidence covered Form-to-Case Results-to-internal-notification; local/fake tests passed for idempotency, recovery, security, logging, and related workflow safety. No email was sent and no Gmail modify/delete operation occurred during Step 24D. |

## 17. Current limitations

- Kinetiq remains a manually exported/pasted Google Sheet source.
- Production accounts and resources are not configured.
- The isolated historical `controlled_test_email` is not a supported production reconciliation workflow type; supported customer-reply reconciliation was subsequently demonstrated in Step 24C.
- Scheduled execution currently depends on the logged-in Windows user.
- Independent monitoring/alerting has not yet been deployed.

## 18. Future enhancements

- Direct Kinetiq API integration
- Approved production Google account/resource migration
- Managed, unattended execution
- Independent health monitoring and alerting
- Encrypted backup/recovery procedures
- Dependency pinning and deployment packaging
- Additional operational monitoring

## 19. Final status

The TEST Customer Case Automation System has implemented its intended email-to-Form-to-Cases-to-Case-Results-to-internal-notification workflow with conservative filtering, duplicate protection, recovery controls, logging, retry handling, configuration separation, and local security protections. Steps 24C and 24D completed successfully: Step 24C provides LIVE evidence of a supported customer-reply send and strict Sent reconciliation, while Step 24D combines that LIVE evidence with existing validated TEST evidence and LOCAL/FAKE recovery, idempotency, security, scheduler, and logging tests. The project is not represented as fully production-ready: production resources are not configured, Kinetiq remains manual, scheduled execution uses the logged-in Windows user context, and independent monitoring is not deployed.

## 20. Submission checklist

- [x] Source code modules present
- [x] TEST configuration separated from business logic
- [x] Project and step documentation prepared
- [x] Local test evidence documented
- [x] Google Form and response spreadsheet configured
- [x] Cases Sheet matching configured
- [x] Case Results Response ID schema documented
- [x] Windows Task Scheduler configured for the TEST workflow
- [x] OAuth/token ACL and `.gitignore` protections documented
- [x] Known limitations and Step 24C/24D results disclosed

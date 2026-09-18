# Step 15 — Production Readiness Audit

Audit date: 2026-09-15  
Scope: static/local inspection only. No Gmail, Google API, Form, Sheet, scheduler, OAuth, token, ledger, or workflow action was performed.

## Overall readiness assessment

**NOT READY for a company/main-account production launch.** The test automation has several strong workflow safeguards, but high-priority configuration, Git hygiene, Gmail false-reply, and unattended-operation risks must be resolved first.

## PASS items

| Area | Finding | Change required |
|---|---|---|
| Python environment | Project virtual environment uses Python 3.12.10; `pip check` reported no broken requirements. | No |
| Secrets in source | Static scan found no apparent Python assignments containing client secrets, access tokens, refresh tokens, or passwords. | No |
| Token use | Tokens are read from local files; their contents are not hardcoded in source. | No |
| OAuth logging | Central runner logging records operational status/exit codes, not child stdout/stderr, credentials, tokens, addresses, attachments, invoices, or images. | No |
| Log rotation | `logs\automation.log` uses `RotatingFileHandler`, 1 MiB maximum per file, with 3 backups. | No |
| Gmail safety | Own-account, no-reply, Google-system checks, eligibility filtering, RFC threading headers, and reply duplicate ledger are present. | No |
| Form source safety | Dynamic header detection excludes `Case Results` as a Form-response source. | No |
| Cases matching | Cases are read dynamically from `Sheet1!A:G`; no fixed row limit or local Cases cache; IDs remain strings; all matching rows/statuses are retained. | No |
| Processing order | Form response → match → Case Results → internal notification → processed ledger is implemented. | No |
| Case Results safety | Existing rows are not updated; append path checks current rows before another result is appended. | No |
| Notification safety | Fixed internal test recipient, separate notification ledger, and sender-account verification are present. | No |
| Retry policy | Bounded retries cover clearly transient read/write API failures: 3 total attempts with 1s then 2s backoff. Gmail sends are not blindly retried. | No |
| Scheduler design | Launcher uses the project virtual-environment Python and absolute paths; task setup requests hidden, non-interactive execution and ignores overlapping runs. | No |

## FAIL items — resolve before production

| ID | Finding | Risk | Required change |
|---|---|---|---|
| H1 | `logs/` is not excluded by `.gitignore`; the audit also could not verify tracked-file status because `C:\Mail` is not currently a Git repository. | Runtime logs can be accidentally committed/copied; source-control protection cannot be verified. | **Configuration/repository change:** initialize or connect the intended Git repository, add `logs/` and generic runtime-secret patterns such as `token*.json` to `.gitignore`, then verify no sensitive/runtime files are tracked. |
| H2 | Customer reply eligibility is keyword/snippet-based and the sender examines only the newest inbox message. Broad words such as `help`, `service`, `order`, or `delivery` can still produce a false positive; an unrelated newer message can also prevent a valid customer case from being handled. | An unintended external recipient could receive the Form reply, or valid requests can be missed. | **Code/policy change:** establish a stricter eligibility policy (for example explicit approved channels/labels, confidence rules, a review queue, or human approval) and safely search/select eligible unprocessed messages rather than only the newest one. |
| H3 | Gmail addresses, Form URL, spreadsheet IDs, expected account, and notification recipient are hardcoded test values across source files. | Switching to the company account requires source edits and risks accidental use of test resources or recipients. | **Configuration/code change:** move environment-specific values to a protected configuration file or environment variables with validation; create a distinct production configuration and approval checklist. |
| H4 | Task Scheduler uses `Interactive` logon type. The task will not operate when the user is logged out, and sleep/restart behavior may delay processing until a user session is active. | Automation availability is not production-grade/unattended. | **Task Scheduler/configuration change:** decide on an approved service/managed-account execution model, token strategy, wake-from-sleep policy, and post-reboot behavior before production. |
| H5 | Local OAuth credentials/tokens and uploaded-file links rely on one Windows user profile and local filesystem controls; permissions/encryption/backup controls were not verified by this audit. | Account compromise, loss of tokens, or loss of recovery capability. | **Security/operations change:** enforce least-privilege NTFS ACLs, device encryption, endpoint protection, and an approved encrypted backup/revocation process. |

## WARN items

| ID | Finding | Required change |
|---|---|---|
| M1 | Case Results deduplication compares the ten Form field values rather than storing the deterministic response ID in the result row. Two legitimate submissions with identical fields could be treated as one output result. | **Code/Sheet-schema change:** add a hidden or explicit immutable response-ID column to Case Results, then deduplicate on it. |
| M2 | If Gmail accepts a customer reply or notification but the process fails before its local ledger write, the next run can send it again. The existing ledgers protect normal reruns but cannot prove an uncertain prior send outcome. | **Code/operations change:** use a durable outbox/idempotency design and/or post-send reconciliation before any later resend. |
| M3 | API calls do not have explicit per-request timeout configuration. A network stall can keep a scheduled run active; overlapping triggers are ignored while it remains active. | **Code/configuration change:** set bounded transport timeouts and monitor maximum run duration. |
| M4 | Failed runs are logged locally, but no independent alerting or health-check notification exists. | **Operations/configuration change:** add monitored log collection or an approved administrator alert path after failure thresholds. |
| M5 | The five-minute trigger is configured with a 3,650-day repetition duration, not infinite recurrence; actual task registration/state was not inspected in this audit. | **Task Scheduler verification/configuration change:** verify the registered task on the target machine, its next runs, history, restart-after-failure policy, and renewal before the duration ends. |
| M6 | Dependency ranges permit compatible package updates; there is no lock file or repeatable dependency artifact. | **Build/configuration change:** pin/lock tested production dependency versions and document update/rollback procedure. |
| M7 | Google Form file-upload links may expose invoices/images in Google Drive. Their ownership, sharing permissions, retention, and deletion policy were outside this audit. | **Google Workspace/configuration policy change:** verify file access and retention before production. |
| M8 | Retry currently treats Case Results append as recoverable by rechecking existing fields first. This reduces duplicate risk but does not give a formal exactly-once guarantee during an ambiguous API response. | **Code/Sheet-schema change:** resolve together with M1 through persisted deterministic response IDs. |

## LOW items

| ID | Finding | Required change |
|---|---|---|
| L1 | Local test scripts reside under `src`; production packaging does not separate test modules from application modules. | **Project-structure change:** move tests to a `tests/` directory when packaging/CI is introduced. |
| L2 | Log rotation caps local storage at roughly 4 MiB total (active plus backups), which may be insufficient for incident retention. | **Operations/configuration change:** define retention, archival, and secure cleanup policy. |
| L3 | The project documentation does not yet define a production incident runbook, rollback plan, or account/token revocation procedure. | **Documentation/operations change:** create and review an operational runbook. |

## Security findings

- `credentials.json` and the currently named OAuth/token files are ignored locally. Python source uses file paths and OAuth libraries rather than embedded secret values.
- The static log scan found no matches for common token/secret patterns. This is not a substitute for formal secret scanning or access-control verification.
- `.gitignore` currently misses `logs/` and does not use a generic `token*.json` rule. It explicitly lists known token files, which protects current names but is fragile when a new token file is added.
- No source-control repository was available at `C:\Mail`, so this audit could not prove that sensitive or runtime files have never been committed elsewhere.

## Test versus production separation

Current explicit test configuration:

- Gmail account: `sivalingam7339@gmail.com`
- Internal notification recipient: `durafit91customermail@gmail.com`
- Form URL and Google spreadsheet IDs: test resources embedded in source

Before a company/main-account switch, do not simply replace strings. Create a reviewed production configuration, re-authorize OAuth with the company account and least required scopes, validate recipient policy, migrate/initialize clean ledgers deliberately, verify Form/Drive sharing, and perform a controlled staging test.

## Configuration inventory

| Value category | Current handling | Classification | Recommended destination |
|---|---|---|---|
| Project paths / virtual-environment path | Hardcoded for `C:\Mail` | Safe local configuration | Environment/config file for portability |
| Gmail test account | Hardcoded `EXPECTED_ACCOUNT` | Test-only / production-sensitive | Protected environment/config setting |
| Internal recipient | Hardcoded constant | Test-only / production-sensitive | Protected environment/config setting with allowlist validation |
| Form URL | Hardcoded | Production-sensitive | Protected environment/config setting |
| Form/Cases spreadsheet IDs | Hardcoded | Production-sensitive | Protected environment/config setting |
| OAuth token filenames | Hardcoded local paths | Safe local configuration | Keep local; document permissions/backup/revocation |
| Retry/log limits | Source constants | Safe configuration | Configurable operational settings if requirements differ |

## Gmail and workflow safety review

- Customer messages are threaded correctly with `In-Reply-To`, `References`, and Gmail `threadId`.
- Own-account, Google, and no-reply/system sends are blocked.
- The reply ledger prevents normal duplicate replies after confirmed sends.
- `--dry-run` previews selection without sending.
- Filtering is conservative in intent but heuristic in implementation; H2 remains the primary customer-facing risk.
- Form rows are deterministically identified from sheet row, timestamp, and trimmed Order ID; source-row deletion/reordering would change that identifier and can affect historical duplicate detection.
- Cases are read fresh every run. Duplicate Order IDs return every matching status in current sheet order.
- The processed ledger is updated only after Case Results and required notification steps complete.
- Internal notification is a fixed-recipient standalone email, not a customer-thread reply.

## Retry and failure recovery review

- Retryable: temporary network/connection/timeouts, Google transport errors, and HTTP 429/500/502/503/504.
- Permanent/unknown errors are not retried.
- Maximum three attempts use exponential 1-second then 2-second delays.
- Retry events and exhausted failures are logged with operation names and non-sensitive categories.
- Gmail sends are intentionally not retried in-process because acceptance may be uncertain; scheduled reruns depend on ledgers and current state.

## Scheduler review

Configured concept: task name `Customer Case Automation`; hidden PowerShell action; launcher `C:\Mail\run_automation.bat`; working directory `C:\Mail`; logon trigger and five-minute interval; current-user interactive context; overlapping runs ignored.

This audit inspected the setup script, not the registered Windows task. Interactive execution preserves access to the current user’s OAuth token files but creates the logged-out/sleep/reboot availability limitation in H4.

## Backup and recovery recommendations

Before migration, use an approved encrypted backup process for:

- `credentials.json` and OAuth token files (restricted-access backup only)
- `.form_reply_replied_message_ids.json`
- `.form_processed_response_ids.json`
- `.internal_notified_response_ids.json`
- `logs\` for the organization’s chosen retention period
- source code, `requirements.txt`, batch launcher, and scheduler setup script
- documented Google Form, Form response spreadsheet, Cases Sheet, and Case Results export/ownership information

Never copy tokens, credentials, invoices, or customer images into unencrypted shared locations.

## Recommended fixes by priority

### HIGH

1. Resolve Git/repository hygiene: use the intended repository; ignore `logs/`, generic token files, and runtime artifacts; verify no sensitive history. **Configuration/repository change.**
2. Replace or gate heuristic newest-message auto-replies with an approved, stricter eligibility/review policy. **Code/policy change.**
3. Introduce reviewed test/staging/production configuration separation before changing any account or recipient. **Code/configuration change.**
4. Establish an unattended, approved Scheduler/service identity and token availability strategy. **Task Scheduler/security configuration change.**
5. Apply access controls, encryption, backup, and token-revocation procedures for local OAuth material. **Security/operations change.**

### MEDIUM

1. Persist deterministic response IDs in Case Results to support exact deduplication/recovery. **Code/Sheet-schema change.**
2. Add durable send reconciliation/outbox behavior for ambiguous Gmail send outcomes. **Code/operations change.**
3. Add API timeout limits and operational alerting/health monitoring. **Code/operations change.**
4. Verify the actual registered Scheduler task and its failure/restart/sleep behavior. **Task Scheduler configuration verification.**
5. Pin dependencies and verify Form-upload Drive permissions/retention. **Build/Google Workspace configuration change.**

### LOW

1. Separate test modules from production source and document retention/runbook/rollback processes. **Project/documentation change.**
2. Define longer-term secure log retention and archival policy. **Operations configuration change.**

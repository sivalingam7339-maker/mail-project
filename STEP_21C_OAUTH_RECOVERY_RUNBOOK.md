# STEP 21C — OAuth Recovery Runbook

**Environment: TEST**

**Documentation only — no credentials or token values are stored in this document.**

## 1. Purpose

This runbook provides a safe, operator-led recovery process when OAuth authorization stops working. OAuth recovery requires an operator who can sign in to Windows and complete the browser-based authorization flow; it must never be attempted unattended by the scheduled automation.

## 2. Current TEST Environment

- Project root: `C:\Mail`
- Environment: TEST (`APP_ENV=test`)
- TEST Gmail account: the approved account configured by `GMAIL_ACCOUNT` in the local `.env` file. Verify it in the browser before granting any OAuth consent.
- OAuth client file: `credentials.json`
- Separate workflow token files:
  - `token.json` — Gmail reader
  - `token_sheets.json` — read-only Google Sheets access
  - `token_sheets_write.json` — Case Results Google Sheets write access
  - `token_reply_sender.json` — customer Gmail reply sender
  - `token_internal_notifier.json` — internal Gmail notifier

These filenames identify local files only. This runbook intentionally contains no OAuth client, access-token, refresh-token, or authorization-code value.

## 3. OAuth File Security

The OAuth client file and the five workflow token files have inheritance disabled. Full Control is restricted to:

- `DESKTOP-IAKA2IP\shanm`
- `NT AUTHORITY\SYSTEM`
- `BUILTIN\Administrators`

Do not loosen these ACLs to troubleshoot an OAuth problem. Do not copy OAuth files into another directory merely to inspect or back them up.

## 4. Token Expired or Invalid Recovery

1. Stop, or avoid running, the affected workflow until recovery is complete.
2. Identify the affected workflow and its corresponding token filename from the list above.
3. Sign in to Windows as the intended TEST operator.
4. Start recovery manually, never through the unattended scheduled task.
5. Run only the affected existing application workflow so its existing OAuth flow can refresh or recreate its own token.
6. In the browser, verify that the selected Google account is the approved TEST account before granting consent.
7. Allow the existing application OAuth flow to create or update the required token file. Never manually create token JSON.
8. Do not paste, share, print, email, or log token contents.
9. After authorization succeeds, run the affected workflow manually once and verify its normal success output.
10. Only then return to relying on Task Scheduler.

## 5. Token File Deleted

If a token file is missing, do not attempt to restore its contents from chat, email, a log, or a manually edited file. Use the same operator-led authorization process for the affected workflow. The existing OAuth flow will create the appropriate token after successful authorization with the approved TEST account. Perform one manual workflow verification before resuming scheduled execution.

## 6. OAuth Consent Revoked

If Google consent was revoked, the affected workflow must be reauthorized through its existing OAuth flow. Sign in as the intended Windows user, select the approved TEST Google account, complete consent only for the expected workflow, and manually verify the workflow after authorization.

## 7. Wrong Google Account

Before clicking **Allow** in a Google authorization page:

1. Inspect the account shown by Google.
2. Confirm it is the approved TEST account configured by `GMAIL_ACCOUNT`.
3. If a different account is shown, choose **Use another account** or cancel the flow; do not grant consent.
4. After authorization, use the workflow's existing account verification output before restoring scheduled operation.

Never authorize an unknown, personal, customer, or production account for the TEST project.

## 8. Credential File Lost or Invalid

`credentials.json` is the OAuth client configuration, not a workflow token. If it is lost or invalid, obtain or recreate it only through the authorized Google Cloud OAuth setup process for this project. Restore it using approved secure handling and reapply the required restrictive ACL.

Never store its contents in email, chat, logs, Git, project documentation, or an unapproved backup location.

## 9. Safe Backup Policy

- Do not store token backups inside `C:\Mail`.
- Do not store OAuth files in logs.
- Do not email OAuth files.
- Do not commit OAuth files to Git.
- If an organizational backup is required, use approved encrypted secure storage with restricted access.
- Never record OAuth secret values in documentation, tickets, chat, or runbooks.

## 10. Revocation or Security Incident

If an OAuth credential or token may have been exposed:

1. Stop the affected automation workflow.
2. Revoke or rotate the affected authorization through the appropriate Google account and Google Cloud controls.
3. Obtain authorized replacement credentials only when required, then reauthorize the intended TEST account.
4. Verify the affected workflow manually before resuming automation.
5. Record the incident and remediation actions without recording any secret values.

## 11. TEST to PRODUCTION Migration

TEST and PRODUCTION must remain separate. Production requires its own approved configuration and, where appropriate, separate:

- Google accounts
- OAuth client credentials
- OAuth token files
- environment configuration values

Never reuse TEST tokens for production. Do not switch accounts by editing a token file.

## 12. Scheduled Task Considerations

The current `Customer Case Automation` Task Scheduler task uses `InteractiveToken`: it runs only while the intended Windows user is logged in. Interactive OAuth recovery cannot safely be performed by the unattended scheduler.

Perform recovery manually as the intended operator, complete authorization in the browser, validate the affected workflow, then confirm the scheduled task is ready before resuming normal operation.

## 13. Post-Recovery Checklist

- [ ] Correct TEST Google account verified
- [ ] Correct workflow and token file identified
- [ ] OAuth authorization completed by the operator
- [ ] Required token file recreated or updated by the existing application flow
- [ ] No OAuth secret was exposed
- [ ] Manual workflow test succeeded
- [ ] Task Scheduler state confirmed as `Ready`
- [ ] `LastTaskResult` checked after a scheduled execution
- [ ] Automation logs checked for normal completion

## 14. Security Rules

- Never share `credentials.json`.
- Never share `token*.json`.
- Never paste token contents into chat.
- Never commit OAuth files to Git.
- Never put OAuth secrets in `.env` or documentation.
- Never send OAuth files by email.
- Never authorize an unknown Google account.

Created as part of the Customer Case Automation production-readiness work.

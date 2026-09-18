# Step 18 — Gmail Message Selection Safety Audit

Audit date: 2026-09-15  
Scope: static source/configuration inspection only. No Gmail, Google API, email send, Form, Sheet, OAuth/token, Scheduler, or ledger operation occurred.

## Current Gmail selection behavior

`form_reply_sender.py` calls Gmail `messages.list` with:

```text
labelIds=["INBOX"]
maxResults=1
```

It then fetches metadata for that single returned message. There is no Gmail `q` search expression, no unread constraint, no date/age cutoff, no pagination, no message cursor/watermark, and no dedicated Gmail label.

Consequences:

- Only the newest Inbox message is considered per five-minute run.
- An unrelated newest message causes the run to skip; an older eligible customer request is not inspected in that run.
- Multiple eligible requests arriving together are handled at most one at a time, and only if each becomes the newest returned candidate on a later run.
- With a new/empty reply ledger, an old historical Inbox message that matches the keyword filter can receive a delayed first reply.

## Current filtering behavior

The local `customer_email_filter.py` rejects own-account, Google-system, no-reply/automated sender patterns, automated/security/unsubscribe content, and common promotional/unrelated content. It accepts a message when the subject or Gmail snippet includes at least one customer-case keyword (for example: issue, support, technician, order, delivery, repair, warranty).

The filter is intentionally conservative in wording but remains heuristic. It uses sender, subject, and snippet—not a full message-body analysis—and broad terms such as `help`, `service`, `order`, and `delivery` can occur in unrelated genuine human mail.

## Current duplicate protection behavior

`.form_reply_replied_message_ids.json` stores a Gmail message ID after a successful reply. On later runs, the same incoming message ID is blocked before another send. The ledger is atomically replaced locally.

This prevents normal duplicate replies after a confirmed send. It does not:

- prevent first-time reply to a historical message absent from the ledger;
- make a failed/ambiguous Gmail send exactly-once; or
- help when only a newer unrelated email keeps an eligible request from selection.

## Findings

### HIGH

| ID | Finding | Risk | Code change required |
|---|---|---|---|
| H1 | No first-run baseline or message-age limit exists. An empty ledger plus historical Inbox mail can produce delayed replies to old customer emails. | Customer-facing incorrect/late reply at production enablement. | Yes |
| H2 | Selection examines only one newest Inbox message with no restrictive Gmail query or pagination. A newer unrelated message blocks older eligible requests; multiple requests can be missed or delayed indefinitely. | Missed, delayed, or non-deterministic customer handling. | Yes |
| H3 | The current Gmail query is only `INBOX`; it does not explicitly exclude sent/draft/trash/spam categories or select a controlled automation intake set. | Broad Inbox exposure combined with heuristic filtering increases false-reply risk. | Yes |

### MEDIUM

| ID | Finding | Risk | Code change required |
|---|---|---|---|
| M1 | Eligibility is keyword/snippet based and does not require a narrow support-intake channel or confidence threshold. | A real but unrelated human message can be eligible. | Yes / policy decision |
| M2 | No separate selection ledger/cursor records the first-run cutoff, observed messages, skipped decisions, or selection status. | Limited auditability and difficult recovery after history/import changes. | Yes |
| M3 | Customer replies are not retried blindly, which is correct for uncertain sends, but a send accepted by Gmail before a local ledger persistence failure may be resent later. | Narrow duplicate-send window. | Yes, for exact-once/reconciliation goal |
| M4 | Unread/read state is ignored. Existing old unread mail and historical read Inbox mail are equally eligible if selected. | State alone does not prevent historical replies. | Yes |

### LOW

| ID | Finding | Risk | Code change required |
|---|---|---|---|
| L1 | The existing `APP_ENV` configuration system does not yet define Gmail selection policy settings. | Future safe policy changes require source edits. | Yes |
| L2 | Console/output logging indicates eligibility or skip reason but does not persist a minimal per-message selection audit record. | Reduced operational diagnosis. | Yes, if needed operationally |

## Recommended safe design

### Selection policy

Replace “newest Inbox message only” with a bounded scan of candidate messages ordered oldest-first, while retaining the existing filter and reply ledger.

Recommended candidate requirements:

1. Use Gmail search to limit candidates to Inbox mail and exclude common non-customer categories, for example a configurable base query such as `in:inbox -from:me -category:promotions -category:social -category:updates`.
2. Fetch a bounded configured page/batch, not unlimited history; inspect every candidate in the batch that is not already in the reply ledger.
3. Fetch each candidate’s `internalDate`, then reject messages older than a configured maximum age or a persisted production activation cutoff.
4. Apply the existing sender/system and customer-case eligibility filter after selection narrowing.
5. Process eligible candidates oldest-first, so close-together requests are handled predictably.
6. Do not change Gmail read state or labels unless a later approved design explicitly permits it.

### First production run: mandatory no-historical-reply safeguard

Do **not** enable sending against an empty production ledger.

Recommended first-run procedure:

1. Configure production account/resource values and validate with dry-run/observe-only mode.
2. Record a durable local `automation_activation_timestamp` (UTC) at the approved cutover time, without sending messages.
3. For subsequent runs, consider only messages whose Gmail `internalDate` is after that activation timestamp and within the configured maximum age.
4. Keep the cutoff until an approved operator intentionally changes it. Do not infer it from Inbox state, unread state, or current time on every run.
5. Require a manual review of the first eligible batch before enabling sends.

This prevents historical Inbox mail from being selected simply because it was never recorded in the reply ledger.

### Multiple new customer emails

At each scheduled run, scan up to a small configured batch size (for example 10–25), filter all unrecorded candidates, sort eligible messages by `internalDate` ascending, and process each independently. Continue after non-eligible messages. Stop only on a safety-critical failure and leave unprocessed candidates for the next run.

The existing message-ID ledger remains the primary confirmed-send duplicate protection. A selection/cutoff state file should be atomically persisted separately from it and must not replace the send ledger.

### Already-replied messages

Before any candidate send, check `.form_reply_replied_message_ids.json`. Skip ledgered IDs without API-side Gmail state change. For an ambiguous send outcome, do not immediately retry `messages.send`; instead flag/log the message for reconciliation against sent-message metadata or approved manual review.

### Gmail label recommendation

For the current least-change safety posture, do **not** add/modify Gmail labels automatically. A dedicated manually managed intake label could later improve routing, but adopting it requires explicit user approval, OAuth scope review, and a separate design because label mutation changes Gmail state.

## Configuration support

Step 17’s `.env` / `config.py` can support future non-secret Gmail-selection settings without hardcoding. Recommended future keys:

```text
GMAIL_SELECTION_QUERY=
GMAIL_SELECTION_BATCH_SIZE=
GMAIL_MAX_MESSAGE_AGE_MINUTES=
GMAIL_ACTIVATION_CUTOFF_UTC=
GMAIL_FIRST_RUN_MODE=observe
```

These are policy/configuration values, not OAuth secrets. They are not implemented by this audit, and no production values are proposed here.

## Recommendation for continuous five-minute execution

Do not use the present selector unchanged for production. Implement H1–H3 first, conduct a dry-run/observe-only cutover with a persisted activation cutoff, then run a controlled multi-message test before enabling scheduled customer sends. Keep the five-minute Scheduler cadence only after candidate selection is bounded, age-limited, ledger-aware, and capable of handling multiple eligible messages safely.

## Recommended implementation plan

1. **High priority:** add configuration-backed first-run observe mode and durable activation cutoff; block all messages at/before cutoff.
2. **High priority:** replace newest-only listing with a constrained query, bounded batch scan, per-message metadata, reply-ledger check, and oldest-first eligible processing.
3. **High priority:** define/approve customer-intake criteria and strengthen the eligibility policy before company-account rollout.
4. **Medium priority:** add minimal safe selection/audit state and an ambiguous-send reconciliation path.
5. **Low priority:** consider a manually managed dedicated intake label only after a separate scope/state-change review.

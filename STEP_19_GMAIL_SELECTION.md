# Step 19 — Safe Gmail Message Selection

## Purpose

This step makes scheduled customer replies conservative: the automation considers a small, recent inbox batch, selects at most one eligible message, and never replies to mail that existed before the automation was activated.

## Configuration

Configuration is local in `.env` and is loaded through `src/config.py`:

- `GMAIL_MAX_AGE_HOURS`: maximum message age eligible for consideration. The TEST setting is 24 hours.
- `GMAIL_BATCH_SIZE`: maximum number of Gmail search results inspected in one run. The TEST setting is 10.

Do not put OAuth credentials, tokens, or passwords in `.env`.

## First-run protection

On the first execution after this change, `form_reply_sender.py` creates the local, ignored file `.gmail_activation.json` containing a UTC activation cutoff and exits successfully in observe-only mode. It does not authenticate to Gmail, search Gmail, or send a reply.

On subsequent runs, a message is eligible only when Gmail's `internalDate` is later than that stable cutoff. The cutoff is never advanced on later runs. To intentionally establish a new cutoff, an operator must make a deliberate, documented operational decision; do not delete the file as a routine retry action.

## Candidate selection

Each normal run performs a bounded inbox search using a query equivalent to:

```
in:inbox newer_than:<derived-days>d -category:promotions -category:social -category:updates
```

The code also enforces the exact age limit locally from Gmail's `internalDate`, so the coarse Gmail day query cannot extend eligibility beyond `GMAIL_MAX_AGE_HOURS`.

For each fetched candidate, the automation rejects messages that are:

- at or before the activation cutoff;
- older than the configured maximum age;
- already present in `.form_reply_replied_message_ids.json`;
- missing required Gmail metadata;
- sent by the configured automation account, a no-reply sender, or Google system sender; or
- rejected by the existing conservative customer-case filter.

Remaining candidates are ordered oldest first. Exactly one is selected per run. The existing reply ledger is written only after Gmail confirms the send.

## Safe manual test sequence

1. Run the local fake-data test only:

   ```powershell
   .\.venv\Scripts\python.exe .\src\test_gmail_selection.py
   ```

2. For a controlled first live observation, run the sender once. It should only create the activation cutoff and print the observe-mode message:

   ```powershell
   .\.venv\Scripts\python.exe .\src\form_reply_sender.py --dry-run
   ```

3. Send a new, clearly customer-case test email after the cutoff time, then run the same dry-run command. Confirm the selected sender and subject before any non-dry-run execution.

4. Re-run the dry-run command and verify an already-replied message is skipped by the existing reply ledger after a successful real send.

## Continuous scheduling recommendation

Keep the existing five-minute schedule. The one-message-per-run limit deliberately favors safety over throughput: multiple eligible recent messages are handled across later runs, oldest first. Monitor `logs/automation.log` and the console/task history for selection counts and errors.


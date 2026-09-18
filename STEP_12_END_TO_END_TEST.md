# Step 12 — End-to-End Customer Case Automation Validation

## Objective

Manually validate the complete controlled test flow without changing source code:

```text
Customer case email → eligible Gmail reply → Form submission → Cases match
→ Case Results row → internal notification → processed/duplicate protection
```

This document is a test plan. It does **not** mean the end-to-end workflow has passed.

## Test environment

| Item | Value |
|---|---|
| Project root | `C:\Mail` |
| Test Gmail account | `sivalingam7339@gmail.com` |
| Internal notification recipient | `durafit91customermail@gmail.com` |
| Form URL | `https://docs.google.com/forms/d/e/1FAIpQLSeSAf_GzBfFWZGawWlydaCeFUpjxmBWPC_z_Fo8ZJtEocUSMg/viewform?usp=dialog` |
| Cases spreadsheet | `13GCCLEPHCA87xfcQUBbEITcu0XeyRAuPugq2Qp1lcHg` |
| Cases tab / columns | `Sheet1`; Order ID = A, Status = G |
| Form response spreadsheet | `1HcMJO_hLRYmAeanmwpEXtJQHSL0Ik5y40GyIW8Psb6g` |
| Source / output tabs | `Form responses 1` / `Case Results` |
| Known Order ID | `406-3192266-2263517` |
| Expected Case Count | `5` |
| Expected statuses, in order | `Spare Needed | Closed | Dropped | Closed | Closed` |

## Preconditions

- [ ] Signed in to the test Gmail account and the internal test mailbox is accessible.
- [ ] Google OAuth tokens already authorize the intended test account.
- [ ] The Cases Sheet currently contains the known test Order ID and all five expected statuses.
- [ ] The `Case Results` tab exists and its header row is intact.
- [ ] No unrelated email is newer than the intended customer test email in the test Gmail inbox.
- [ ] Use a separate external/test sender account for the customer email. Do **not** send it from `sivalingam7339@gmail.com`; own-account mail is intentionally blocked.
- [ ] The Form response used in this test has not already been submitted; each new submission has a new timestamp/row and is therefore separately processable.

## Test record

| Field | Record during test |
|---|---|
| Tester / date | |
| External test sender address | |
| Customer test email subject | |
| Form response sheet row | |
| Case Results row | |
| Internal notification message ID / time | |
| Overall status | PASS / FAIL |

## Validation steps

### 1. Verify Gmail filtering blocks system/no-reply mail

Use the local-only filter demo; it does not connect to Gmail:

```powershell
cd C:\Mail
.\.venv\Scripts\python.exe .\src\customer_email_filter.py
```

Expected result: the fake `no-reply@accounts.google.com` example is classified `AUTOMATED/SYSTEM`; promotional and unclear examples are skipped; the fake product/technician issue is `ELIGIBLE`.

Actual result: `____________________________________________`

Status: [ ] PASS [ ] FAIL

### 2. Send a clear customer-case test email

From the separate external/test sender, email `sivalingam7339@gmail.com` with a clearly eligible request, for example:

```text
Subject: Need technician for product issue

Hello, my product is not working and I need technician support for my order.
```

Expected result: the email becomes the newest inbox item in the test Gmail account. Do not use a newsletter, alert, Google security message, promotion, or an ambiguous greeting.

Actual result: `____________________________________________`

Status: [ ] PASS [ ] FAIL

### 3. Safe Gmail eligibility dry run

Run this before any real customer reply:

```powershell
cd C:\Mail
.\.venv\Scripts\python.exe .\src\form_reply_sender.py --dry-run
```

Expected result: console output says `ELIGIBLE and selected for reply`, shows the external sender and `Re:` subject, then says `DRY RUN: no email was sent.`

Actual result: `____________________________________________`

Status: [ ] PASS [ ] FAIL

### 4. Send the controlled Form-link reply

After Step 3 passes, run the customer-reply workflow once:

```powershell
cd C:\Mail
.\.venv\Scripts\python.exe .\src\form_reply_sender.py
```

Expected result: exactly one reply is sent in the original Gmail thread to the external test sender, with the configured Google Form link. The reply ledger prevents a second reply to that same incoming Gmail message ID.

Actual result: `____________________________________________`

Status: [ ] PASS [ ] FAIL

### 5. Submit the customer Form manually

Open the Form link from the reply (or the listed Form URL) and submit one complete test response using this Order ID:

```text
406-3192266-2263517
```

Complete all required Form fields with test-safe data. Include invoice/image links only if intentionally testing those fields.

Expected result: one new row appears in `Form responses 1` with a new timestamp. Do not edit or delete any response rows.

Actual result: `____________________________________________`

Status: [ ] PASS [ ] FAIL

### 6. Process the new response and write the result

Run the Form processing workflow once:

```powershell
cd C:\Mail
.\.venv\Scripts\python.exe .\src\new_form_response_processor.py
```

Expected console result:

```text
New responses found: 1
...
Order ID: 406-3192266-2263517
Matching Cases: 5
406-3192266-2263517 - Spare Needed
406-3192266-2263517 - Closed
406-3192266-2263517 - Dropped
406-3192266-2263517 - Closed
406-3192266-2263517 - Closed
Writing Case Result...
Case result saved successfully.
Preparing internal notification...
Internal notification sent successfully.
Response processed successfully.
```

Expected Sheet result: exactly one new `Case Results` row preserving the submitted Form fields, with:

```text
Case Count: 5
Case Statuses: Spare Needed | Closed | Dropped | Closed | Closed
Result: MATCH FOUND
```

Actual result: `____________________________________________`

Status: [ ] PASS [ ] FAIL

### 7. Verify the internal notification

Open `durafit91customermail@gmail.com` and inspect the new standalone message.

Expected result:

- Subject: `New Customer Case - 406-3192266-2263517`
- Recipient is the internal test address only; it is not a reply to the customer thread.
- Customer details, Form details, all five statuses in order, case count `5`, and `Result: MATCH FOUND` are present.
- Invoice/image sections appear only if supplied in the Form response.

Actual result: `____________________________________________`

Status: [ ] PASS [ ] FAIL

### 8. Verify duplicate protection

Without submitting another Form response, run the processor again:

```powershell
cd C:\Mail
.\.venv\Scripts\python.exe .\src\new_form_response_processor.py
```

Expected result:

```text
New responses found: 0
No new responses found.
Processed: 0
```

Confirm all of the following:

- [ ] No duplicate `Case Results` row was appended.
- [ ] No second internal notification was sent.
- [ ] The existing Form response is not printed as newly processed.
- [ ] The Form-response and notification ledgers remain responsible for the skip behavior.

Actual result: `____________________________________________`

Status: [ ] PASS [ ] FAIL

## Final acceptance criteria

Mark the end-to-end validation **PASS** only when every item is true:

- [ ] System/no-reply/promotional/unclear mail is skipped; a clear customer case is eligible.
- [ ] The initial reply goes only to the eligible external customer/test sender and contains the Form link.
- [ ] A new Form submission is detected once.
- [ ] The exact Order ID is matched against all current Cases Sheet rows.
- [ ] All five expected statuses appear in the existing Cases row order.
- [ ] One complete Case Results row is appended with count `5` and `MATCH FOUND`.
- [ ] One standalone internal notification reaches `durafit91customermail@gmail.com`.
- [ ] Rerunning without a new Form response creates neither a duplicate result row nor notification.
- [ ] No unrelated customer reply, Cases Sheet write, or source Form-response Sheet write occurred.

Final status: [ ] PASS [ ] FAIL

Notes / defects found:

`________________________________________________________________________`

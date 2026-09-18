# Step 17 — Configuration Separation

The application loads non-secret TEST settings from `C:\Mail\.env`. `APP_ENV` defaults to `test` when absent.

Configurable values are the expected Gmail account, internal notification recipient, Form URL, Form-response spreadsheet ID, Cases spreadsheet ID/tab, and Case Results tab.

OAuth credentials, tokens, passwords, and client secrets must not be placed in `.env`; the existing credential/token files remain the OAuth mechanism. `.env` and `.env.*` are ignored by Git and must never be committed, printed, or shared.

Production values have not been added. A future production host can use a reviewed protected `.env` with `APP_ENV=production` and approved production resource identifiers, without changing business logic.

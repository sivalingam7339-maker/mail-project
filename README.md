# Gmail API read-only test (Step 1)

This project authenticates only **sivalingam7339@gmail.com** through Google OAuth 2.0, then prints the latest 10 Gmail messages. It requests only `gmail.readonly`, so it cannot send, reply to, delete, archive, label, or mark messages as read.

## Project layout

```
.
├── .gitignore
├── credentials.json     # You add this locally; ignored by Git
├── requirements.txt
├── src/
│   └── gmail_reader.py
└── token.json           # Created after authorization; ignored by Git
```

## Google Cloud Console setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create a new project (for example, `gmail-readonly-test`). Make sure that project is selected.
2. Open **APIs & Services** > **Library**, search for **Gmail API**, open it, and click **Enable**.
3. Open **Google Auth platform** > **Branding**. If prompted, click **Get Started**. Enter an app name, choose a user support email, and enter a developer contact email.
4. Under **Audience**, choose **External** for a personal `gmail.com` account. In the test-user section, add `sivalingam7339@gmail.com`, then save. (Choose **Internal** only if this is a Google Workspace project and that account belongs to its organization.)
5. Open **Google Auth platform** > **Data Access**. Add the Gmail scope `https://www.googleapis.com/auth/gmail.readonly`, save it, and keep the app in testing for this development-only project.
6. Open **Google Auth platform** > **Clients** > **Create Client**. Select **Desktop app**, name it (for example, `VS Code Gmail reader`), and create it.
7. Download the OAuth client JSON. Save it exactly as `credentials.json` in this project root (`C:\Mail\credentials.json`). Never commit or share this file.

Google's current Gmail Python quickstart documents the Gmail API enablement, Desktop app client, and local credential JSON flow; its read-only OAuth scope is also the minimum scope used here. [Official Gmail Python quickstart](https://developers.google.com/workspace/gmail/api/quickstart/python) · [Official OAuth consent configuration guide](https://developers.google.com/workspace/guides/configure-oauth-consent)

## Exact PowerShell commands

Prerequisite: install Python 3.10 or newer and ensure `python --version` works in the VS Code terminal. Then run:

```powershell
cd C:\Mail
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python .\src\gmail_reader.py
```

If PowerShell blocks activation for this session, run the following once, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## First authorization

The first run opens a browser. Sign in specifically as `sivalingam7339@gmail.com`, review the request for read-only Gmail access, and approve it. The program displays the authenticated Gmail address before it reads anything; it stops without displaying messages if a different account was selected.

`token.json` is then created locally and is used only to refresh this authorization. To switch accounts or force consent again, delete only `token.json` and run the script again. Do not delete or edit Gmail messages.

## Output and safety

For each of the 10 newest messages, the script prints From, To, Subject, Date, Gmail Email ID, and body. It safely uses plain text when present and converts HTML-only content into text. Missing headers and empty bodies are shown with clear placeholders. The script uses only Gmail `list`, `getProfile`, and `get` read operations.

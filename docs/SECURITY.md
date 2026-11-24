# Secrets & credential security

## Where secrets live

| Store | What | Risk |
|---|---|---|
| **DPAPI vault (preferred)** | Kite API key/secret, access token, password, TOTP secret; Groww secrets | Ciphertext only your Windows user can decrypt |
| `.env` (legacy) | Non-secret flags (`KITE_ENABLE`, redirect URL, etc.) | Must stay gitignored; never commit |

Vault path (default):

`%LOCALAPPDATA%\Rangebook\secrets\credentials.dpapi`

Override with `RANGEBOOK_SECRETS_DIR` if needed.

## One-time migrate

```powershell
python secrets_store.py migrate
python secrets_store.py status
```

This copies secret keys into the DPAPI vault and comments them out of `.env`.

## Daily token refresh

`python kite_login.py` still works. The access token is written to the vault (not `.env`) when DPAPI is available.

## Hardening checklist

1. Run migrate once on this machine.
2. Confirm `.env` is in `.gitignore` (it is).
3. Do not sync `.env` via OneDrive/Dropbox if it still holds secrets.
4. BitLocker on the system drive adds disk-at-rest protection under the same Windows user.
5. Never paste API secrets into chat, screenshots, or commits.

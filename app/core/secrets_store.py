"""OS-backed secret vault for Kite/Groww credentials.

On Windows, secrets are encrypted with DPAPI (CryptProtectData) bound to the
current Windows user. The ciphertext lives under LocalAppData — outside the
git repo — so a cloned project tree never contains live tokens.

Lookup order for each key:
  1) DPAPI vault (preferred)
  2) process environment / .env (legacy fallback)

Migrate once:
  python secrets_store.py migrate
  python secrets_store.py status
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional

# Sensitive keys we prefer not to leave in plaintext .env after migrate.
SECRET_KEYS = (
    "KITE_API_KEY",
    "KITE_API_SECRET",
    "KITE_ACCESS_TOKEN",
    "KITE_USER_ID",
    "KITE_ZERODHA_USER_ID",
    "KITE_PASSWORD",
    "KITE_TOTP_SECRET",
    "GROWW_API_KEY",
    "GROWW_API_SECRET",
    "GROWW_ACCESS_TOKEN",
    "GROWW_TOTP_KEY",
    "GROWW_TOTP_SECRET",
)


def _vault_dir() -> Path:
    override = os.environ.get("RANGEBOOK_SECRETS_DIR", "").strip()
    if override:
        return Path(override)
    local = os.environ.get("LOCALAPPDATA") or os.environ.get("HOME") or str(Path.home())
    return Path(local) / "Rangebook" / "secrets"


def vault_path() -> Path:
    return _vault_dir() / "credentials.dpapi"


def _is_windows() -> bool:
    return os.name == "nt"


def _dpapi_protect(raw: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    def _blob(data: bytes) -> DATA_BLOB:
        buf = ctypes.create_string_buffer(data, len(data))
        return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    in_blob = _blob(raw)
    out_blob = DATA_BLOB()
    if not crypt32.CryptProtectData(
        ctypes.byref(in_blob),
        "RangebookSecrets",
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError("CryptProtectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _dpapi_unprotect(raw: bytes) -> bytes:
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    def _blob(data: bytes) -> DATA_BLOB:
        buf = ctypes.create_string_buffer(data, len(data))
        return DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    in_blob = _blob(raw)
    out_blob = DATA_BLOB()
    if not crypt32.CryptUnprotectData(
        ctypes.byref(in_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(out_blob),
    ):
        raise OSError("CryptUnprotectData failed")
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree(out_blob.pbData)


def _load_vault() -> Dict[str, str]:
    path = vault_path()
    if not path.is_file():
        return {}
    raw = path.read_bytes()
    if not raw:
        return {}
    if _is_windows():
        try:
            plain = _dpapi_unprotect(raw)
        except OSError:
            return {}
    else:
        # Non-Windows fallback: refuse plaintext vault files for safety.
        return {}
    try:
        data = json.loads(plain.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): str(v) for k, v in data.items() if v is not None and str(v) != ""}


def _save_vault(data: Dict[str, str]) -> Path:
    if not _is_windows():
        raise RuntimeError(
            "DPAPI vault is Windows-only. On other OS set RANGEBOOK_SECRETS_DIR "
            "with an external secret manager, or keep using environment variables."
        )
    path = vault_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    # Restrictive ACL best-effort: user-only directory on NTFS via default inheritance.
    payload = json.dumps(data, indent=2, sort_keys=True).encode("utf-8")
    sealed = _dpapi_protect(payload)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(sealed)
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return path


def get(name: str, default: Optional[str] = None) -> Optional[str]:
    """Read one secret: vault first, then environment."""
    key = str(name).strip()
    vault = _load_vault()
    if key in vault and vault[key]:
        return vault[key]
    env = os.environ.get(key, "").strip()
    return env or default


def set_secret(name: str, value: str) -> Path:
    key = str(name).strip()
    data = _load_vault()
    val = str(value).strip()
    if val:
        data[key] = val
        os.environ[key] = val
    elif key in data:
        del data[key]
        os.environ.pop(key, None)
    return _save_vault(data)


def delete_secret(name: str) -> Path:
    data = _load_vault()
    data.pop(str(name).strip(), None)
    os.environ.pop(str(name).strip(), None)
    return _save_vault(data)


def apply_to_environ(keys: Optional[Iterable[str]] = None) -> int:
    """Copy vault secrets into os.environ.

    Vault wins for known SECRET_KEYS so a leftover plaintext .env cannot
    override the migrated DPAPI values. Other keys only fill empty slots.
    """
    vault = _load_vault()
    n = 0
    wanted = set(keys) if keys is not None else set(vault)
    secret = set(SECRET_KEYS)
    for key in wanted:
        val = vault.get(key)
        if not val:
            continue
        cur = os.environ.get(key, "").strip()
        if key in secret or not cur:
            if cur != val:
                os.environ[key] = val
                n += 1
    return n


def status() -> Dict[str, object]:
    vault = _load_vault()
    present = sorted(k for k in SECRET_KEYS if vault.get(k))
    env_only = sorted(
        k for k in SECRET_KEYS if not vault.get(k) and os.environ.get(k, "").strip()
    )
    return {
        "windows_dpapi": _is_windows(),
        "vault_path": str(vault_path()),
        "vault_exists": vault_path().is_file(),
        "vault_keys": present,
        "env_fallback_keys": env_only,
    }


def migrate_from_env(env_path: Optional[Path] = None, *, scrub_env: bool = True) -> Dict[str, object]:
    """Copy SECRET_KEYS from .env / environ into the DPAPI vault, then scrub .env lines."""
    root = Path(__file__).resolve().parent
    path = Path(env_path) if env_path else root / ".env"
    # Ensure .env is loaded into environ first.
    try:
        import groww_data  # noqa: F401
    except Exception:
        pass
    moved: List[str] = []
    data = _load_vault()
    for key in SECRET_KEYS:
        val = os.environ.get(key, "").strip()
        if not val:
            continue
        data[key] = val
        moved.append(key)
    if not moved:
        return {"moved": [], "vault_path": str(vault_path()), "scrubbed": False}
    dest = _save_vault(data)
    apply_to_environ(moved)
    scrubbed = False
    if scrub_env and path.is_file():
        lines = path.read_text(encoding="utf-8").splitlines(True)
        out = []
        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                out.append(line)
                continue
            key = stripped.split("=", 1)[0].strip()
            if key in SECRET_KEYS:
                out.append(f"# {key}=  # moved to DPAPI vault {dest}\n")
                scrubbed = True
            else:
                out.append(line)
        path.write_text("".join(out), encoding="utf-8")
    return {"moved": moved, "vault_path": str(dest), "scrubbed": scrubbed}


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(argv or sys.argv[1:])
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        print("Commands: status | migrate | set KEY VALUE | get KEY | delete KEY")
        return 0
    cmd = argv[0]
    if cmd == "status":
        print(json.dumps(status(), indent=2))
        return 0
    if cmd == "migrate":
        print(json.dumps(migrate_from_env(), indent=2))
        return 0
    if cmd == "set" and len(argv) >= 3:
        print(set_secret(argv[1], " ".join(argv[2:])))
        return 0
    if cmd == "get" and len(argv) >= 2:
        print(get(argv[1]) or "")
        return 0
    if cmd == "delete" and len(argv) >= 2:
        print(delete_secret(argv[1]))
        return 0
    print("Unknown command", cmd)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

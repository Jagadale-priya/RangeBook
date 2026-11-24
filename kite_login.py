"""Root entrypoint — delegates to app/market/kite_login.py."""
import path_setup  # noqa: F401
import runpy

if __name__ == "__main__":
    runpy.run_module("kite_login", run_name="__main__")

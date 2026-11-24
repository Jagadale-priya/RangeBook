"""Root entrypoint — delegates to app/api/stock_signal_ml.py."""
import path_setup  # noqa: F401
from app.api.stock_signal_ml import main

if __name__ == "__main__":
    main()

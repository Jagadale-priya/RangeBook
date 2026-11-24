"""Shim — implementation lives in tools/train/train_fno_models.py."""
from tools.train.train_fno_models import *  # noqa: F403

if __name__ == "__main__":
    from tools.train.train_fno_models import main

    raise SystemExit(main())

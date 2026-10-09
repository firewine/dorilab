from __future__ import annotations

import json

from .config import APP_MODE
from .worker import refresh_remote_state


def main() -> None:
    if APP_MODE == "DEMO":
        print(json.dumps({"state": "LOCAL_ONLY", "detail": "explicit DEMO mode"}))
        return
    print(json.dumps(refresh_remote_state()))


if __name__ == "__main__":
    main()

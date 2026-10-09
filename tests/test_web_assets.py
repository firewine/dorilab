from __future__ import annotations

import hashlib
import re

import pytest

from dorilab.api import WEB_ROOT


@pytest.mark.parametrize("page", ["/", "/assets/blackboard-observer.html"])
def test_rebuilt_ui_uses_current_assets_in_existing_browser(client, page):
    response = client.get(page)
    assert response.status_code == 200
    assert response.headers["Cache-Control"] == "no-store"
    assets = re.findall(r'"(/assets/([a-zA-Z0-9_-]+\.(?:js|css))\?v=([a-f0-9]+))"', response.text)
    assert {filename for _, filename, _ in assets} == (
        {"styles.css", "setup-demo.js", "app.js", "learning-sets.js", "development.js"}
        if page == "/" else {"blackboard-observer.css", "blackboard-observer.js"}
    )
    for url, filename, version in assets:
        current = (WEB_ROOT / filename).read_bytes()
        assert version == hashlib.sha256(current).hexdigest()[:12]
        fetched = client.get(url)
        assert fetched.status_code == 200
        assert fetched.content == current
        assert fetched.headers["Cache-Control"] == "no-store"

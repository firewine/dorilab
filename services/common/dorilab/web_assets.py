"""Version local assets so an existing browser loads the rebuilt Docker UI."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles


def html_response(path: Path, web_root: Path) -> Response:
    content = path.read_text(encoding="utf-8")

    def version(match):
        name = match.group(1)
        asset = web_root / name
        checksum = hashlib.sha256(asset.read_bytes()).hexdigest()[:12]
        return f'"/assets/{name}?v={checksum}"'

    content = re.sub(r'"/assets/([a-zA-Z0-9_-]+\.(?:js|css))"', version, content)
    return Response(content, media_type="text/html", headers={"Cache-Control": "no-store"})


class LocalWebAssets(StaticFiles):
    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 200 and path == "blackboard-observer.html":
            return html_response(Path(self.directory) / path, Path(self.directory))
        response.headers["Cache-Control"] = "no-store"
        return response

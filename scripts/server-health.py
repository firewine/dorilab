"""Read-only Render -> Neon probe; never log credentials or response bodies."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
import time

import httpx

ORIGIN = "https://dorilab-api-worker.onrender.com"


def main():
    os.umask(0o077)
    result = {"checked_at": datetime.now(timezone.utc).isoformat(),
              "state": "CHECK_FAILED", "api": "UNKNOWN", "database": "UNKNOWN",
              "model_calls": 0, "business_writes": 0}
    try:
        identities = json.loads(Path('/run/secrets/sites_identities.json').read_text())['identities']
        identity, actors = next(iter(identities.items()))
        if not actors:
            raise ValueError('empty actor mapping')
        headers = {
            'Authorization': 'Bearer ' + Path('/run/secrets/sites_gateway_token').read_text().strip(),
            'X-DoriLab-Site-User': identity,
            'X-DoriLab-Legacy-Actor': 'engineer@demo' if 'engineer@demo' in actors else actors[0],
        }
        with httpx.Client(base_url=ORIGIN, headers=headers, timeout=35,
                          follow_redirects=False, trust_env=False) as client:
            for attempt in range(3):
                try:
                    response = client.get('/api/v1/status')
                    result['http_status'] = response.status_code
                    if response.status_code in (401, 403):
                        result['state'] = 'API_AUTH_FAILED'
                        break
                    if response.status_code == 200:
                        data = response.json()
                        result['api'] = data.get('backend') if data.get('backend') == 'READY' else 'UNAVAILABLE'
                        result['database'] = 'READY' if data.get('database') == 'READY' else 'UNAVAILABLE'
                        result['state'] = 'HEALTHY' if result['api'] == result['database'] == 'READY' else 'DB_UNAVAILABLE'
                        break
                    result['state'] = 'API_UNAVAILABLE'
                    if response.status_code < 500:
                        break
                except httpx.RequestError:
                    result['state'] = 'API_UNREACHABLE'
                if attempt < 2:
                    time.sleep(10)
    except Exception as error:
        # Do not record exception messages: credentials/response text may be present.
        result['error_type'] = type(error).__name__
    directory = Path('/records')
    directory.mkdir(exist_ok=True)
    last = directory / 'last.json'
    previous = {}
    if last.exists():
        try:
            previous = json.loads(last.read_text())
        except (ValueError, OSError):
            pass
    result['previous_state'] = previous.get('state')
    result['state_changed'] = previous.get('state') != result['state']
    temporary = directory / 'last.tmp'
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    temporary.chmod(0o600)
    temporary.replace(last)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['state'] == 'HEALTHY' else 1


if __name__ == '__main__':
    raise SystemExit(main())

from pathlib import Path


ROOT = Path("/app")


def service_block(compose: str, name: str, next_name: str) -> str:
    start = compose.index(f"  {name}:\n")
    end = compose.index(f"  {next_name}:\n", start)
    return compose[start:end]


def test_tunnel_and_database_are_not_published_or_overprivileged():
    compose = (ROOT / "compose.yaml").read_text()
    db = service_block(compose, "db", "migrate")
    tunnel = service_block(compose, "llm-tunnel", "volumes")
    assert "ports:" not in db
    assert "ports:" not in tunnel
    assert "privileged:" not in compose
    assert "network_mode:" not in compose
    assert "/var/run/docker.sock" not in compose


def test_api_and_worker_do_not_receive_ssh_key_and_browser_has_no_secret_names():
    compose = (ROOT / "compose.yaml").read_text()
    api = service_block(compose, "api", "worker")
    worker = service_block(compose, "worker", "llm-tunnel")
    assert "DORILAB_SSH_KEY_PATH" not in api
    assert "DORILAB_SSH_KEY_PATH" not in worker
    browser = "\n".join(path.read_text() for path in (ROOT / "apps/web").glob("*.*"))
    assert "inference_token" not in browser
    assert "db_password" not in browser

from pathlib import Path


ROOT = Path("/app")


def test_runpod_bundle_uses_authenticated_current_boot_and_quarantines_mismatch():
    script = (ROOT / "scripts/dev.sh").read_text()
    current_boot = (ROOT / "scripts/remote/current_boot.sh").read_text()
    version_receipt = (ROOT / "scripts/remote/version_receipt.sh").read_text()

    assert "run/*/model_receipt.json" not in script
    assert "run/$current_boot/model_receipt.json" in script
    assert "receipts/by-boot/$current_boot" in script
    assert 'packages/contracts/model_profiles/rc3.json' in script
    assert 'inference.pending-$current_boot' in script
    assert "The approved reference/runpod/inference baseline was not replaced" in script
    assert "Authorization" in current_boot
    assert "Authorization" in version_receipt
    assert "print(boot_id)" in current_boot
    assert "sys.stdout.buffer.write(response.read())" in version_receipt
    assert "print(token" not in current_boot
    assert "print(token" not in version_receipt

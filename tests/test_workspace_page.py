from conftest import sign_in


PROJECT = "00000000-0000-4000-8000-000000000001"


def test_workspace_evidence_projection_preserves_scope_and_adoption_metadata(client):
    headers = sign_in(client)
    artifact = client.post(
        f"/api/v1/projects/{PROJECT}/artifacts",
        headers=headers,
        files={"file": ("workspace-reference.md", b"synthetic workspace reference", "text/markdown")},
        data={
            "rights_status": "PUBLIC",
            "edition": "DEMO-1",
            "adopted": "true",
            "applicability_status": "APPLICABLE",
        },
    )
    assert artifact.status_code == 201, artifact.text
    evidence = client.post(
        f"/api/v1/projects/{PROJECT}/evidence",
        headers=headers,
        json={
            "artifact_id": artifact.json()["id"],
            "display_id": "WORKSPACE-REF",
            "kind": "REFERENCE",
            "basis": "USER_CONFIRMED_EXCERPT",
            "scope": {},
            "locator": "section DEMO",
            "quote": "workspace projection fixture",
            "provenance": {"created_in": "TEST"},
        },
    )
    assert evidence.status_code == 201, evidence.text

    listed = client.get(f"/api/v1/projects/{PROJECT}/evidence")
    assert listed.status_code == 200
    item = next(row for row in listed.json() if row["display_id"] == "WORKSPACE-REF")
    assert item["rights_status"] == "PUBLIC"
    assert item["edition"] == "DEMO-1"
    assert item["adopted"] is True
    assert item["applicability_status"] == "APPLICABLE"
    assert item["artifact_sha256"] == artifact.json()["sha256"]

    detail = client.get(f"/api/v1/evidence/{item['id']}")
    assert detail.status_code == 200
    assert detail.json()["download_artifact_id"] == artifact.json()["id"]
    assert detail.json()["quote"] == "workspace projection fixture"

from conftest import sign_in


PROJECT = "00000000-0000-4000-8000-000000000001"
CLAIM = "00000000-0000-4000-8000-000000000101"


def test_requirement_matrix_is_server_backed_and_scoped(client):
    headers = sign_in(client)
    response = client.get(f"/api/v1/projects/{PROJECT}/requirements")
    assert response.status_code == 200
    rows = response.json()
    assert [row["display_id"] for row in rows] == ["MIS-001", "THM-041", "THM-042", "MEC-011", "EEE-021"]

    thm_041 = next(row for row in rows if row["display_id"] == "THM-041")
    assert thm_041["ui_status"] == "NEEDS_EVIDENCE"
    assert thm_041["display_claim"] == "CLM-TH-INPUT"
    assert thm_041["claim_id"] == CLAIM

    detail = client.get(f"/api/v1/requirements/{thm_041['id']}")
    assert detail.status_code == 200
    assert detail.json()["parent_ref"] == "SYS-THERM"
    assert detail.json()["source_chapter"] == 19

    updated = client.put(
        f"/api/v1/claims/{CLAIM}",
        headers=headers,
        json={
            "question": "변경된 형상에서 열모델 입력 근거가 충분한가?",
            "scope": {"unit": "DORI-01", "configuration": "Rev.C", "run": "TVAC-03"},
            "expected_version": 1,
        },
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2

    claim = client.get(f"/api/v1/claims/{CLAIM}")
    assert claim.status_code == 200
    assert [revision["version"] for revision in claim.json()["revisions"]] == [2, 1]
    assert claim.json()["requirements"][0]["display_id"] == "THM-041"

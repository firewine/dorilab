from conftest import sign_in


PROJECT = "00000000-0000-4000-8000-000000000001"
CLAIM = "00000000-0000-4000-8000-000000000101"


def test_profile_reference_chapter_and_original_download(client):
    sign_in(client)
    chapter = client.get("/api/v1/reference/final-goal/chapters/1")
    assert chapter.status_code == 200
    body = chapter.json()
    assert body["title"].startswith("1. KASA, ECSS, NASA")
    assert body["content"].startswith("## 1. KASA, ECSS, NASA")
    assert len(body["sha256"]) == 64

    missing = client.get("/api/v1/reference/final-goal/chapters/21")
    assert missing.status_code == 404

    download = client.get("/api/v1/reference/final-goal/download")
    assert download.status_code == 200
    assert download.content.startswith("# DoriLab".encode())
    assert "DoriLab_Final_Goal_KASA_ECSS_NASA.md" in download.headers["content-disposition"]


def test_profile_documents_tailoring_and_approver_boundary(client):
    headers = sign_in(client)
    profile = client.get(f"/api/v1/projects/{PROJECT}/profile")
    assert profile.status_code == 200
    assert profile.json()["project"]["framework"] == "KASA"

    denied = client.put(
        f"/api/v1/projects/{PROJECT}/profile",
        headers=headers,
        json={"framework": "NASA", "framework_edition": None, "expected_version": 1},
    )
    assert denied.status_code == 403

    document = client.put(
        f"/api/v1/projects/{PROJECT}/documents/KASA-SE-REQ",
        headers=headers,
        json={
            "profile": "KASA",
            "title": "한국형 시스템엔지니어링 프로세스 및 요구조건",
            "revision": "1.0 / 2025-06-30",
            "product_level": "열제어 장비",
            "clause_locator": "원문 연결 대기",
            "adoption_note": "실제 채택 전 등록 정보",
        },
    )
    assert document.status_code == 200
    assert document.json()["status"] == "UNCONFIRMED"

    tailoring = client.post(
        f"/api/v1/projects/{PROJECT}/tailoring",
        headers=headers,
        json={
            "profile": "KASA",
            "title": "시험 검토 테일러링",
            "clause_locator": "원문 연결 대기",
            "reason": "제품 수준에 맞춘 검토 후보",
            "owner": "시스템 엔지니어",
        },
    )
    assert tailoring.status_code == 201
    tailoring_body = tailoring.json()
    engineer_decision = client.post(
        f"/api/v1/tailoring/{tailoring_body['id']}/decision",
        headers=headers,
        json={"disposition": "APPROVED", "expected_version": tailoring_body["version"]},
    )
    assert engineer_decision.status_code == 403

    review = client.post(
        f"/api/v1/projects/{PROJECT}/reviews",
        headers={**headers, "Idempotency-Key": "profile-stale-review"},
        json={"claim_id": CLAIM, "evidence_ids": [], "mode": "SIMULATED"},
    )
    assert review.status_code == 202

    approver_headers = sign_in(client, "approver@demo")
    decided = client.post(
        f"/api/v1/tailoring/{tailoring_body['id']}/decision",
        headers=approver_headers,
        json={"disposition": "APPROVED", "expected_version": tailoring_body["version"]},
    )
    assert decided.status_code == 200
    assert decided.json()["status"] == "APPROVED"

    applied = client.put(
        f"/api/v1/projects/{PROJECT}/profile",
        headers=approver_headers,
        json={"framework": "NASA", "framework_edition": None, "expected_version": 1},
    )
    assert applied.status_code == 200
    assert applied.json()["framework"] == "NASA"
    assert applied.json()["version"] == 2
    job = client.get(f"/api/v1/jobs/{review.json()['job_id']}").json()["job"]
    assert job["freshness"] == "STALE"

    state = client.get(f"/api/v1/projects/{PROJECT}/profile").json()
    assert state["documents"][0]["document_code"] == "KASA-SE-REQ"
    assert state["tailoring"][0]["status"] == "APPROVED"

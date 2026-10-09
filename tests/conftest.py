from __future__ import annotations

import shutil

import pytest
from fastapi.testclient import TestClient

from dorilab.api import app
from dorilab.config import ARTIFACT_ROOT, EXPORT_ROOT
from dorilab.db import connection


@pytest.fixture(autouse=True)
def clean_business_rows():
    with connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM claim_revisions")
        cur.execute(
            """TRUNCATE learning_datasets,learning_examples,orchestration_checkpoints,orchestration_node_attempts,orchestration_runs,board_events,object_dependencies,work_items,agent_contributions,configuration_changes,verification_closures,data_quality_assessments,phase_transition_decisions,gate_decisions,tailoring_decisions,project_documents,report_exports,evidence_requests,human_reviews,validations,model_runs,retrieval_runs,
               review_attempts,review_jobs,context_snapshots,evidence,source_spans,artifact_versions
               RESTART IDENTITY CASCADE"""
        )
        cur.execute(
            """DELETE FROM requirements WHERE id NOT IN (
                 '00000000-0000-4000-8000-000000000201'::uuid,
                 '00000000-0000-4000-8000-000000000202'::uuid,
                 '00000000-0000-4000-8000-000000000203'::uuid,
                 '00000000-0000-4000-8000-000000000204'::uuid,
                 '00000000-0000-4000-8000-000000000205'::uuid);
               DELETE FROM claims WHERE id <> '00000000-0000-4000-8000-000000000101'::uuid;
               UPDATE claims SET question='TVAC-03 열모델 상관 검토에 필요한 근거가 충분한가?',
                 scope='{"unit":"DORI-01","configuration":"TVAC-03","run":"RUN-DEMO-01"}'::jsonb,
                 version=1,status='OPEN',review_purpose='INPUT_READINESS'
               WHERE id='00000000-0000-4000-8000-000000000101'::uuid;
               DELETE FROM projects WHERE id <> '00000000-0000-4000-8000-000000000001'::uuid;
               UPDATE projects SET framework='KASA',framework_edition=NULL,adoption_status='UNCONFIRMED',
                 baseline_display_id='BL-003',product_configuration='Rev.C',test_run='TVAC-03',
                 current_phase=4,version=1,updated_at=now()
               WHERE id='00000000-0000-4000-8000-000000000001'::uuid;
               UPDATE requirements SET review_purpose='INPUT_READINESS',version=1 WHERE id='00000000-0000-4000-8000-000000000202'::uuid;
               UPDATE requirements SET review_purpose='PRODUCT_PERFORMANCE',version=1 WHERE id='00000000-0000-4000-8000-000000000203'::uuid;
               INSERT INTO claim_revisions(claim_id,project_id,version,question,scope,status,created_by,review_purpose)
               SELECT id,project_id,version,question,scope,status,created_by,review_purpose FROM claims
               WHERE id='00000000-0000-4000-8000-000000000101'::uuid;
               DELETE FROM audit_events WHERE action <> 'SEED';
               DELETE FROM system_state;"""
        )
    shutil.rmtree(ARTIFACT_ROOT, ignore_errors=True)
    shutil.rmtree(EXPORT_ROOT, ignore_errors=True)
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
    yield


@pytest.fixture()
def client():
    return TestClient(app)


def sign_in(client: TestClient, user="engineer@demo"):
    response = client.post("/api/v1/session", json={"user_id": user})
    assert response.status_code == 200
    return {"X-DoriLab-CSRF": "1"}

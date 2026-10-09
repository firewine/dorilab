from __future__ import annotations

import pytest

from dorilab.learning_import import parse_100q_handoff
from dorilab.db import connection
from conftest import sign_in
from test_document_rag import PROJECT, upload_document


def handoff(*, count=100, missing_answer=False, metadata=False):
    sections = ["## 3. Q001~Q100 원래 입력·답안과 문항별 보완점"]
    for number in range(1, count + 1):
        split = "EVALUATION" if number > 87 else "TRAIN"
        answer = "" if missing_answer and number == 3 else "Draft answer for review."
        source = 'C002' if number > 87 else 'C001'
        meta = f'''**출처:** {source} · Example paper
**원자료 계열:** `paper-{source.lower()}` · **사례 성격:** `AI_AUTHORED_SOURCE_REVIEW_QUESTION`
**검토 분류:** 입력 보강
''' if metadata else ''
        sections.append(f"""### Q{number:03d} · 문헌 이해 · {split}

{meta}
**원래 질문**

What does this source establish?

**원래 모델 입력 전체**

```text
Source: Example paper\nQuestion: What does this source establish?
```

**원래 정답 초안**

{answer}

**원래 오답**

Wrong draft answer.

**원래 오답 이유**

It overstates the evidence.

**원래 최소 채점항목**

- Separate observations and claims.

**검토에서 관찰한 점**

The question needs clearer inputs.

**수정 제안**

Review the paper before approving.

**원문 확인 범위**

Original paper not verified.

**원본 출처 연결:** `{source}` · DOI `10.0000/example`
**위치:** p. 2, line 3
**접근 상태:** `ABSTRACT_ONLY`
**주소:** https://example.com/paper

**라벨 상태** `DRAFT_UNREVIEWED`
""")
    sections.append("## 4. 원본 출처 등록부")
    sections.append("### C001 source material")
    return "\n".join(sections)


def test_100q_import_separates_train_and_evaluation_and_marks_everything_unapproved():
    result = parse_100q_handoff(handoff())

    assert (result["example_count"], result["train_count"], result["evaluation_count"]) == (100, 87, 13)
    assert result["training_started"] is False
    assert result["approval_required"] is True
    assert result["rows"][0]["id"] == "Q001"
    assert result["rows"][0]["review_status"] == "DRAFT_UNREVIEWED"
    assert result["rows"][0]["training_eligible"] is False
    assert result["rows"][0]["rejected_draft"] == "Wrong draft answer."
    assert all(not row["training_eligible"] for row in result["rows"])
    assert all(row["split"] == "EVALUATION" for row in result["rows"][-13:])


def test_100q_import_rejects_wrong_count_or_missing_labels():
    try:
        parse_100q_handoff(handoff(count=99))
    except ValueError as exc:
        assert str(exc) == "HANDOFF_EXPECTED_100_QUESTIONS"
    else:
        raise AssertionError("incomplete handoff must not import")

    try:
        parse_100q_handoff(handoff(missing_answer=True))
    except ValueError as exc:
        assert str(exc) == "HANDOFF_REQUIRED_FIELD_MISSING:Q003"
    else:
        raise AssertionError("missing answer must not import")


def test_100q_import_rejects_unexpected_label_status_and_ignores_rewrite_proposals():
    source = handoff().replace("## 4. 원본 출처 등록부", "## 4. 원본 출처 등록부\n\n### RW-Q001-PREFERENCE-01\nproposal data")
    result = parse_100q_handoff(source)
    assert result["example_count"] == 100
    assert all(not row["id"].startswith("RW-") for row in result["rows"])

    unlabeled = handoff().replace("DRAFT_UNREVIEWED", "APPROVED", 1)
    try:
        parse_100q_handoff(unlabeled)
    except ValueError as exc:
        assert str(exc) == "HANDOFF_UNEXPECTED_LABEL_STATUS:Q001"
    else:
        raise AssertionError("approved status must not be inferred")


def test_web_import_preview_accepts_training_markdown_and_never_creates_examples_or_jobs(client):
    headers = sign_in(client)
    artifact = upload_document(
        client, headers, name="DoriLab_100Q_handoff.md", content=handoff().encode(),
        purpose="TRAINING", rights="UNCONFIRMED", edition="handoff-v1.0",
    )
    response = client.post(
        f"/api/v1/projects/{PROJECT}/learning/import-preview", headers=headers,
        json={"artifact_id": artifact["id"]},
    )
    assert response.status_code == 200, response.text
    preview = response.json()
    assert (preview["example_count"], preview["train_count"], preview["evaluation_count"]) == (100, 87, 13)
    assert preview["source_sha256"] == artifact["sha256"]
    assert preview["rights_confirmed"] is False
    assert preview["training_started"] is False
    overview = client.get(f"/api/v1/projects/{PROJECT}/learning").json()
    assert overview["examples"] == []
    assert overview["training"]["state"] == "BLOCKED"
    assert overview["training"]["job_id"] is None

    operational = upload_document(client, headers, purpose="OPERATIONAL_EVIDENCE")
    denied = client.post(
        f"/api/v1/projects/{PROJECT}/learning/import-preview", headers=headers,
        json={"artifact_id": operational["id"]},
    )
    assert denied.status_code == 422


def test_handoff_preserves_declared_classification_and_notes_without_paper_verification():
    result = parse_100q_handoff(handoff(metadata=True))
    first = result['rows'][0]
    assert first['source']['id'] == 'C001'
    assert first['family_key'] == 'paper-c001'
    assert first['origin'] == 'AI_AUTHORED_SOURCE_REVIEW_QUESTION'
    assert first['review_classification'] == '입력 보강'
    assert first['source']['confirmation_scope'] == 'Original paper not verified.'
    assert first['source']['locator'] == 'p. 2, line 3'
    assert first['source']['doi'] == '10.0000/example'
    assert first['source']['verification'] == 'HANDOFF_DECLARATION_NOT_VERIFIED'
    assert first['rubric'] == '- Separate observations and claims.'
    assert first['rejected_reason_draft'] == 'It overstates the evidence.'
    assert first['classification_issues'] == []
    supplemental = parse_100q_handoff(handoff(metadata=True).replace('**출처:** C001 ·', '**출처:** S-HOTAI ·'))
    assert supplemental['rows'][0]['source']['id'] == 'S-HOTAI'
    assert supplemental['rows'][0]['classification_issues'] == []
    overlap = parse_100q_handoff(handoff(metadata=True).replace('`paper-c002`', '`paper-c001`'))
    assert all('SOURCE_FAMILY_SPLIT_CONFLICT' in row['classification_issues'] for row in overlap['rows'])
    assert all(row['split'] == 'EVALUATION' for row in overlap['rows'][-13:])


def register(client, headers, artifact, key='register-set-0001'):
    return client.post(f'/api/v1/projects/{PROJECT}/learning/imports',
                       headers={**headers, 'Idempotency-Key': key}, json={'artifact_id': artifact['id']})


def saved_set(client, headers, **kwargs):
    artifact = upload_document(client, headers, name='100Q_handoff.md', content=handoff(metadata=True).encode(),
                               purpose='TRAINING', rights='UNCONFIRMED', edition='handoff-v1', **kwargs)
    response = register(client, headers, artifact)
    assert response.status_code == 201, response.text
    detail = client.get(f"/api/v1/learning/imports/{response.json()['id']}")
    assert detail.status_code == 200, detail.text
    return artifact, detail.json()


def decide(client, headers, item, **kwargs):
    payload = {'expected_version': item['version'], 'decision': 'APPROVED',
               'note': 'Reviewed the supplied question, answer, and stated limits.', 'review_confirmed': True}
    payload.update(kwargs)
    return client.post(f"/api/v1/learning/import-items/{item['id']}/decisions", headers=headers, json=payload)


def test_import_persists_all_drafts_and_deduplicates_reupload_keys(client):
    headers = sign_in(client)
    artifact, batch = saved_set(client, headers)
    assert batch['counts'] == {'DRAFT': 100, 'APPROVED': 0, 'REJECTED': 0}
    assert batch['source_snapshot']['sha256'] == artifact['sha256']
    assert batch['source_snapshot']['rights_status'] == 'UNCONFIRMED'
    assert all(i['status'] == 'DRAFT' and i['version'] == 1 for i in batch['items'])
    assert all(i['decision_history'] == [] and not i['training_eligible'] for i in batch['items'])
    assert (batch['train_count'], batch['evaluation_count']) == (87, 13)
    repeat = register(client, headers, artifact)
    assert repeat.json()['duplicate'] and repeat.json()['id'] == batch['id']
    alias = upload_document(client, headers, name='renamed.md', content=handoff(metadata=True).encode(),
                            purpose='TRAINING', rights='UNCONFIRMED', edition='handoff-v1')
    assert register(client, headers, alias, key='reupload-alias-001').json()['id'] == batch['id']
    other = upload_document(client, headers, name='other.md', content=handoff(metadata=True).replace('Draft answer', 'Updated draft answer').encode(),
                            purpose='TRAINING', rights='UNCONFIRMED', edition='handoff-v1')
    conflict = register(client, headers, other, key='reupload-alias-001')
    assert conflict.status_code == 409 and conflict.json()['detail'] == 'IDEMPOTENCY_KEY_CONFLICT'
    overview = client.get(f'/api/v1/projects/{PROJECT}/learning').json()
    assert len(overview['imports']) == 1 and overview['examples'] == []
    with connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT count(*) AS n FROM learning_import_items')
        assert cur.fetchone()['n'] == 100


@pytest.mark.parametrize('reviewer', ['reviewer@demo', 'approver@demo'])
def test_individual_review_preserves_original_wrong_answer_and_edited_approved_text(client, reviewer):
    headers = sign_in(client)
    _, batch = saved_set(client, headers)
    item = batch['items'][0]
    headers = sign_in(client, reviewer)
    response = decide(client, headers, item, prompt='Reviewed input with explicit scope.', completion='Corrected answer with limits.')
    assert response.status_code == 200, response.text
    reviewed = response.json()
    assert reviewed['status'] == 'APPROVED' and reviewed['version'] == 2
    assert reviewed['approval_scope'] == 'LOCAL_LABEL_REVIEW_ONLY'
    assert reviewed['original_source_verified'] is False and reviewed['training_eligible'] is False
    assert reviewed['original_payload'] == item['original_payload']
    assert reviewed['reviewed_prompt'] == 'Reviewed input with explicit scope.'
    assert reviewed['reviewed_completion'] == 'Corrected answer with limits.'
    assert reviewed['rejected_draft'] == 'Wrong draft answer.'
    decision = reviewed['decision_history'][0]
    assert decision['reviewed_by'] == reviewer and decision['reviewed_at']
    assert (decision['from_version'], decision['to_version']) == (1, 2)
    rejected = decide(client, headers, batch['items'][1], decision='REJECTED', review_confirmed=False, note='Source inputs are inadequate.')
    assert rejected.status_code == 200 and rejected.json()['reviewed_completion'] is None
    refreshed = client.get(f"/api/v1/learning/imports/{batch['id']}").json()
    assert refreshed['counts'] == {'DRAFT': 98, 'APPROVED': 1, 'REJECTED': 1}
    assert refreshed['items'][0]['decision_history'] == reviewed['decision_history']
    assert decide(client, headers, item).status_code == 409
    assert decide(client, headers, batch['items'][2], expected_version=2).status_code == 409
    assert decide(client, headers, batch['items'][2], review_confirmed=False).status_code == 409
    assert decide(client, headers, batch['items'][2], note=' ').status_code == 422
    with connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT count(*) AS n FROM audit_events WHERE action='REVIEW_IMPORTED_LEARNING_ITEM'")
        assert cur.fetchone()['n'] == 2
        for table in ('model_runs', 'review_jobs', 'human_reviews', 'learning_datasets', 'gate_decisions'):
            cur.execute(f'SELECT count(*) AS n FROM {table}')
            assert cur.fetchone()['n'] == 0


def test_evaluation_review_never_moves_the_item_to_training(client):
    headers = sign_in(client)
    artifact, batch = saved_set(client, headers)
    headers = sign_in(client, 'reviewer@demo')
    response = decide(client, headers, batch['items'][-1])
    assert response.status_code == 200, response.text
    evaluation = response.json()
    assert evaluation['split'] == 'EVALUATION' and not evaluation['training_eligible']
    assert evaluation['training_blockers'] == ['EVALUATION_EXCLUDED_FROM_TRAINING']
    assert decide(client, headers, batch['items'][-2], split='TRAIN').status_code == 422
    repeated = register(client, headers, artifact, key='reviewed-reimport-001').json()
    assert repeated['counts']['APPROVED'] == 1 and repeated['counts']['DRAFT'] == 99
    assert repeated['id'] == batch['id']


@pytest.mark.parametrize('user', ['engineer@demo', 'viewer@demo'])
def test_import_approval_roles_and_csrf_are_enforced(client, user):
    headers = sign_in(client)
    artifact, batch = saved_set(client, headers)
    headers = sign_in(client, user)
    assert decide(client, headers, batch['items'][0]).status_code == 403
    if user == 'viewer@demo':
        assert register(client, headers, artifact, key='viewer-import-001').status_code == 403
    sign_in(client, 'reviewer@demo')
    assert client.post(f"/api/v1/learning/import-items/{batch['items'][0]['id']}/decisions",
                       json={'expected_version': 1, 'decision': 'REJECTED', 'note': 'No CSRF'}).status_code == 403


@pytest.mark.parametrize('change', ['edition', 'rights', 'bytes', 'item'])
def test_source_change_keeps_history_but_blocks_new_approval(client, change):
    from dorilab.db import connection
    from dorilab.storage import resolved_path
    headers = sign_in(client)
    artifact, batch = saved_set(client, headers)
    headers = sign_in(client, 'reviewer@demo')
    accepted = decide(client, headers, batch['items'][0]).json()
    with connection() as conn, conn.cursor() as cur:
        if change == 'edition':
            cur.execute("UPDATE artifact_versions SET edition='changed' WHERE id=%s", (artifact['id'],))
        elif change == 'rights':
            cur.execute("UPDATE artifact_versions SET rights_status='RESTRICTED' WHERE id=%s", (artifact['id'],))
        elif change == 'bytes':
            cur.execute('SELECT object_key FROM artifact_versions WHERE id=%s', (artifact['id'],))
            resolved_path(cur.fetchone()['object_key']).write_bytes(b'Changed file')
        else:
            cur.execute("UPDATE learning_import_items SET original_payload=jsonb_set(original_payload,'{completion_draft}', '\"tampered\"') WHERE import_id=%s", (batch['id'],))
    reloaded = client.get(f"/api/v1/learning/imports/{batch['id']}").json()
    assert reloaded['items'][0]['status'] == 'APPROVED'
    assert reloaded['items'][0]['decision_history'] == accepted['decision_history']
    assert reloaded['items'][0]['freshness'] == 'STALE'
    assert decide(client, headers, batch['items'][1]).status_code == 409
    assert decide(client, headers, batch['items'][1], decision='REJECTED', review_confirmed=False).status_code == 200


def test_wrong_project_and_malformed_set_cannot_partially_import(client):
    from dorilab.db import connection
    headers = sign_in(client)
    artifact, batch = saved_set(client, headers)
    other = client.post('/api/v1/projects', headers=headers,
                        json={'display_id': 'OTHER-SET', 'name': 'Other private project', 'framework': 'KASA'}).json()
    response = client.post(f"/api/v1/projects/{other['id']}/learning/imports", headers={**headers, 'Idempotency-Key': 'wrong-project-001'},
                           json={'artifact_id': artifact['id']})
    assert response.status_code == 404
    headers = sign_in(client, 'reviewer@demo')
    assert client.get(f"/api/v1/projects/{other['id']}/learning").status_code == 404
    headers = sign_in(client)
    private = upload_document(client, headers, name='private.md', content=handoff().encode(), purpose='TRAINING', project=other['id'])
    private_response = client.post(f"/api/v1/projects/{other['id']}/learning/imports", headers={**headers, 'Idempotency-Key': 'private-project-001'}, json={'artifact_id': private['id']})
    assert private_response.status_code == 201
    private_id = private_response.json()['id']
    headers = sign_in(client, 'reviewer@demo')
    assert client.get(f'/api/v1/learning/imports/{private_id}').status_code == 404
    headers = sign_in(client)
    for contents in (handoff(count=99), handoff(missing_answer=True), 'unsupported format'):
        bad = upload_document(client, headers, name='incomplete.md', content=contents.encode(), purpose='TRAINING')
        invalid = register(client, headers, bad, key=f"bad-set-{bad['id']}")
        assert invalid.status_code == 422
    with connection() as conn, conn.cursor() as cur:
        cur.execute('SELECT count(*) AS n FROM learning_import_items')
        assert cur.fetchone()['n'] == 200


def test_mixed_handoff_cannot_be_reused_as_verified_paper_chunk_for_manual_examples(client):
    from test_document_rag import parse_document
    headers = sign_in(client)
    artifact, _ = saved_set(client, headers)
    parsed = parse_document(client, headers, artifact['id'])
    response = client.post(f'/api/v1/projects/{PROJECT}/learning/examples', headers={**headers, 'Idempotency-Key': 'mixed-set-example-001'},
                           json={'title': 'Do not leak evaluation labels', 'family_key': 'invented-family', 'split': 'TRAIN',
                                 'origin': 'HUMAN_AUTHORED', 'source_chunk_id': parsed['chunks'][0]['id'],
                                 'prompt': 'New prompt', 'completion': 'New completion'})
    assert response.status_code == 409 and response.json()['detail'] == 'HANDOFF_REVIEW_SET_NOT_ORIGINAL_SOURCE'

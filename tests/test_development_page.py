from pathlib import Path


def test_management_page_is_separate_and_uses_local_preparation_routes(client):
    response = client.get('/')
    assert 'data-page="development"' in response.text
    assert 'id="developmentGoals"' in response.text
    assert 'id="developmentDocuments"' in response.text
    assert 'id="developmentLearning"' in response.text
    script = Path('/app/apps/web/development.js').read_text()
    assert 'learning/examples' in script and 'learning/datasets' in script
    assert 'openRunpodSettings()' in script
    assert 'RunPod 학습 실행 · 준비 대기' in script
    assert 'disabled title=' in script
    assert 'closest("button[data-page], a[data-page]")' in Path('/app/apps/web/app.js').read_text()
    assert 'localStorage' not in script
    assert '/generations' not in script and '/reviews' not in script


def test_current_release_allows_authoring_review_but_keeps_datasets_unreleased(client):
    from conftest import sign_in
    headers = sign_in(client)
    project = '00000000-0000-4000-8000-000000000001'
    catalog = client.get(f'/api/v1/projects/{project}/development').json()
    assert catalog['released_sections'] == ['goals', 'documents', 'learning']
    data = client.get(f'/api/v1/projects/{project}/learning').json()
    assert data['example_authoring_enabled'] is True
    assert data['example_review_enabled'] is True
    assert data['preparation_enabled'] is False
    response = client.post(f'/api/v1/projects/{project}/learning/examples',headers={**headers,'Idempotency-Key':'not-released-01'},
        json={'title':'Unreleased','family_key':'synthetic','split':'TRAIN','origin':'HUMAN_AUTHORED',
              'source_chunk_id':'00000000-0000-4000-8000-000000000099','prompt':'Question','completion':'Answer'})
    assert response.status_code == 404  # no invented source chunks
    missing_decision = client.post('/api/v1/learning/examples/00000000-0000-4000-8000-000000000099/decisions',
        headers=headers,json={'expected_version':1,'decision':'APPROVED','note':'Unknown case','data_use_confirmed':True})
    assert missing_decision.status_code == 404
    for path, payload in (
        (f'/api/v1/projects/{project}/learning/datasets',
         {'name':'unreleased','split':'TRAIN','example_ids':['00000000-0000-4000-8000-000000000099']}),
    ):
        response = client.post(path,headers={**headers,'Idempotency-Key':'not-released-01'},json=payload)
        assert response.status_code == 501
        assert response.json()['detail'].startswith('LEARNING_PREPARATION_NOT_RELEASED')

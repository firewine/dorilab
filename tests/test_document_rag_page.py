from pathlib import Path


ROOT = Path("/app")


def test_workspace_exposes_governed_document_rag_flow():
    html = (ROOT / "apps/web/index.html").read_text(encoding="utf-8")
    script = (ROOT / "apps/web/app.js").read_text(encoding="utf-8")

    assert "업로드 · 파싱 · 색인" in html
    assert 'name="usage_purpose"' in html
    assert 'value="OPERATIONAL_EVIDENCE"' in html
    assert "문서 RAG" in script
    assert "data-run-retrieval" in script
    assert "/retrievals" in script
    assert "retrieval_run_id" in script
    assert "검색 결과는 Evidence 수용이나 공식 판정을 뜻하지 않는다" in script
    assert "localStorage" not in script

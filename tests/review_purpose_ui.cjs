// Run in the existing Node container with server-produced assessment_scope JSON.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('/web/app.js', 'utf8');
const scopes = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const roots = {closureContent: {innerHTML: ''}};
const context = vm.createContext({
  state: {requirements: [], jobs: [], requests: [], evidence: [], project: {framework: 'KASA'}, closureData: {claims: [], history: []}},
  $: id => roots[id], escapeHtml, icon: () => '', gateByKey: () => null,
  gateChecklist: () => '', profiles: {KASA: {name: 'KASA', output: 'Internal review'}},
  selectedWorkspaceClaim: () => ({display_id: 'SYNTHETIC'}),
});
for (const name of ['assessmentScopeNotice', 'reviewPurposeOptions', 'closureStatusPill', 'closureClaimView', 'renderClosureProductMatrix', 'renderClosureProcessMatrix', 'renderClosure', 'renderWorkspaceResult']) {
  const start = source.indexOf(`function ${name}(`);
  assert(start >= 0, name);
  const next = source.slice(start + 1).search(/\n(?:async )?function /);
  const end = next < 0 ? source.length : start + 1 + next;
  vm.runInContext(source.slice(start, end), context);
}
for (const scope of Object.values(scopes)) {
  const html = context.assessmentScopeNotice(scope);
  for (const key of ['label', 'result_scope', 'no_action_required_meaning', 'product_performance_status']) {
    assert(html.includes(escapeHtml(scope[key])), key);
  }
}
assert(context.assessmentScopeNotice({...scopes.INPUT_READINESS, label: '<script>bad</script>'}).includes('&lt;script&gt;'));
const input = scopes.INPUT_READINESS;
const performance = scopes.PRODUCT_PERFORMANCE;
const unknown = scopes.UNSPECIFIED;
const claim = {id: 'input-claim', display_id: 'SYNTHETIC', review_purpose: 'INPUT_READINESS'};
const closure = {id: 'closed-input', result: 'SATISFIED', review_purpose: input.review_purpose, assessment_scope: input};
const view = {claim, assessment_scope: input, current_closure: closure, ready_for_satisfied: true, checks: [{code: 'RULE_JUDGEMENT', satisfied: true}]};
context.state.closureData = {claims: [view], history: []};
// A legacy/malformed product link cannot inherit an input closure in the UI.
context.state.requirements = [{id: 'product', display_id: 'THM-042', claim_id: claim.id, review_purpose: performance.review_purpose, assessment_scope: performance}];
let html = context.renderClosureProductMatrix(view);
assert(html.includes('PERFORMANCE_ASSESSMENT_UNSUPPORTED'));
assert(html.includes(performance.label));
assert(html.includes('NOT_EVALUATED'));
assert(!html.includes('SATISFIED'));
context.state.requirements = [{id: 'input', claim_id: claim.id, review_purpose: input.review_purpose, assessment_scope: input}];
assert(context.renderClosureProductMatrix(view).includes(`${input.label} / SATISFIED`));
context.renderClosure();
assert(roots.closureContent.innerHTML.includes(input.result_scope));
assert(roots.closureContent.innerHTML.includes(input.closure_label));
assert(!roots.closureContent.innerHTML.includes('기준 충족'));
view.assessment_scope = unknown;
view.current_closure = {...closure, review_purpose: 'UNSPECIFIED', assessment_scope: unknown};
context.state.closureData.history = [view.current_closure];
context.renderClosure();
assert(roots.closureContent.innerHTML.includes('목적 미확인 보존 기록'));
assert(!roots.closureContent.innerHTML.includes('현재 입력준비 종결'));
context.state.jobDetail = {job: {id: 'job', status: 'AWAITING_REVIEW', freshness: 'CURRENT'}, snapshot: {id: 'snapshot'}, assessment_scope: input, model_run: {validation_status: 'VALID', parsed_output: {action: 'NO_ACTION_REQUIRED'}}};
html = context.renderWorkspaceResult();
assert(html.includes(input.result_scope));
assert(html.includes(input.no_action_required_meaning));
context.state.jobDetail.assessment_scope = unknown;
html = context.renderWorkspaceResult();
assert(/data-review-decision="ACCEPTED" disabled/.test(html));
console.log('PASS: server scope labels, escaping, input closure, performance/legacy boundary and draft acceptance UI');

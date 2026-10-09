// Verify the sealed SC-03 fixture against the original mockup's pure functions.
// This does not execute the current MVP or an alternative process version.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const vm = require('node:vm');

const sourceRoot = process.env.DORILAB_V3_SOURCE_ROOT || '/v3-source';
const fixturePath = process.env.DORILAB_V3_FIXTURE || '/fixtures/sc03_contract.json';
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const fixtureBytes = fs.readFileSync(fixturePath);
const fixture = JSON.parse(fixtureBytes);
const checkedSources = fixture.provenance.sources.map(source => {
  const file = path.join(sourceRoot, source.path);
  const actualHash = hash(fs.readFileSync(file));
  assert.equal(actualHash, source.sha256, `Original source changed: ${source.path}`);
  return { path: source.path, sha256: actualHash, lines: source.lines };
});
const html = fs.readFileSync(path.join(sourceRoot, 'index.html'), 'utf8');

function originalFunction(start, end) {
  const from = html.indexOf(start);
  const to = html.indexOf(end, from + start.length);
  assert(from >= 0 && to > from, `Original function bounds unavailable: ${start}`);
  return html.slice(from, to);
}

// Extract only these existing functions. No DOM, event handlers, storage,
// network access, model calls or comparison metrics execute in this context.
const sourceFunctions = [
  originalFunction('function freshState(){', 'let state = loadState()'),
  originalFunction('function computeFindings(){', 'function findingRuntime('),
  originalFunction('function findingRuntime(', 'function workspaceStatus('),
  originalFunction('function retestGuard(', 'function lifecycleStatus('),
].join('\n');
const context = vm.createContext({});
vm.runInContext(`${sourceFunctions}
  let state = freshState();
  const beforeContext = computeFindings();
  state.contextReconstructed = true;
  const findings = computeFindings();
  globalThis.result = {
    input: state.inputs,
    labels: {
      scenarioVersion: state.scenarioVersion, processVersion: state.processVersion,
      ruleVersion: state.ruleVersion, uiVersion: state.uiVersion
    },
    before_context: beforeContext,
    findings: findings.map(f => ({
      id: f.id, type: f.type, title: f.title,
      ...(f.axes ? { axes: f.axes } : {}),
      evidence_status: findingRuntime(f).evidence
    })),
    finding_runtime: findings.map(f => ({id: f.id, ...findingRuntime(f)})),
    blocked_guards: Object.fromEntries(['run', 'trb', 'evidence', 'vcd'].map(step => [step, retestGuard(step)]))
  };`, context, {timeout: 1000});
const actual = JSON.parse(JSON.stringify(context.result));
assert.deepEqual(actual.input, fixture.original_input, 'Fixture must preserve every original input field');
const {meaning, ...labels} = fixture.original_version_labels;
assert.deepEqual(actual.labels, labels);
assert.deepEqual(actual.before_context, []);
assert.deepEqual(actual.findings, fixture.original_expected.findings);
for (const finding of actual.finding_runtime) {
  assert.equal(finding.ruleVerdict, 'NON_COMPLIANT');
  assert.equal(finding.approval, 'PENDING');
  assert.equal(finding.workflow, 'BLOCKED');
}
for (const [step, [allowed]] of Object.entries(actual.blocked_guards)) {
  assert.equal(allowed, false, `Original prerequisite guard must block ${step}`);
}

process.stdout.write(JSON.stringify({
  schema_id: 'dorilab.v3.source-contract-check.v1',
  case_id: fixture.case_id,
  result: 'PASS',
  execution_kind: 'ORIGINAL_MOCKUP_PURE_FUNCTIONS',
  fixture_sha256: hash(fixtureBytes),
  sources: checkedSources,
  expected: fixture.original_expected,
  actual,
  scope: 'Original SC-03 input/findings and initial prerequisite guards only. Not MVP case completion, engineering correctness or model accuracy.',
  not_executed: ['Human command handlers', 'Full retest episode', 'Current MVP', 'Model calls', 'Process version comparison']
}, null, 2) + '\n');

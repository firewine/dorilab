// Exercise the actual settings handlers with a mock API; no RunPod calls.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('/web/app.js', 'utf8');
new vm.Script(source); // Syntax check the complete browser bundle.
const functions = source.slice(source.indexOf('function updateRunpodSshPreview('), source.indexOf('async function openSourceChapter('));
const submit = source.slice(source.indexOf('$("runpodConnectionForm").addEventListener("submit"'), source.indexOf('$("documentForm").addEventListener("submit"'));
const close = source.slice(source.indexOf('$("runpodDialog").addEventListener("close"'), source.indexOf('$("runpodTrustButton").addEventListener("click"'));

function fixture({available = true, keyState = 'HOST_KEY_VERIFIED', unchanged = false} = {}) {
  const roots = {};
  for (const id of ['runpodSshPreview', 'runpodTrustButton', 'runpodFingerprints', 'runpodConnectionState', 'runpodRuntimeState', 'runpodSaveButton', 'runpodDialog', 'runpodConnectionForm']) {
    roots[id] = {textContent: '', innerHTML: '', disabled: false, hidden: false, handlers: {},
      addEventListener(name, handler) { this.handlers[name] = handler; }, showModal() { this.open = true; }};
  }
  roots.runpodConnectionForm.elements = {host: {value: 'pod.example.test'}, port: {value: '22001'}};
  const calls = [], messages = [], cleared = [];
  const connection = {host: 'pod.example.test', port: 22001, configured: true,
    controller: {available, pending: false, phase: 'IDLE'}, runtime: {mode: 'DEMO', remote: {state: 'LOCAL_ONLY'}}};
  const state = {project: {id: 'project'}, status: {mode: 'DEMO'}};
  const context = vm.createContext({state, $: id => roots[id], csrfHeaders: {'X-DoriLab-CSRF': '1'},
    escapeHtml: value => String(value ?? '').replace(/</g, '&lt;'), Number, Boolean,
    message: (...args) => messages.push(args), refreshStatus: async () => {},
    setInterval: () => 42, clearInterval: value => cleared.push(value),
    FormData: class {constructor(form) {this.form = form;} entries() {return Object.entries(this.form.elements).map(([key, field]) => [key, field.value]);}},
    api: async (url, opts = {}) => {
      calls.push([url, opts.method || 'GET']);
      if (url.endsWith('/scan-host-key')) return {fingerprints: ['SHA256:fixture'], host_key_state: keyState, scan_sha256: 'fixture-hash'};
      if (url.endsWith('/apply')) {
        if (unchanged) return {request_id: 'apply-id', status: 'APPLIED', unchanged: true};
        connection.controller = {...connection.controller, pending: true, phase: 'REQUESTED'};
        return {request_id: 'apply-id', status: 'REQUESTED'};
      }
      return connection;
    }});
  vm.runInContext(functions + '\n' + close + '\n' + submit, context);
  return {context, roots, calls, messages, cleared, connection};
}

(async () => {
  let f = fixture();
  await f.context.openRunpodSettings();
  assert(f.roots.runpodRuntimeState.innerHTML.includes('DEMO'));
  assert(f.roots.runpodRuntimeState.innerHTML.includes('LOCAL_ONLY'));
  assert.equal(f.calls.filter(([url]) => url.endsWith('/apply')).length, 0);
  const event = {preventDefault() {}, currentTarget: f.roots.runpodConnectionForm};
  await Promise.all([f.roots.runpodConnectionForm.handlers.submit(event), f.roots.runpodConnectionForm.handlers.submit(event)]);
  assert.equal(f.calls.filter(([, method]) => method === 'PUT').length, 1);
  assert.equal(f.calls.filter(([url]) => url.endsWith('/apply')).length, 1);
  assert.equal(f.roots.runpodSaveButton.disabled, true);
  assert(f.roots.runpodRuntimeState.innerHTML.includes('연결 적용 요청됨'));
  f.roots.runpodDialog.handlers.close();
  assert(f.cleared.includes(42));

  f = fixture({unchanged: true});
  await f.context.openRunpodSettings();
  await f.roots.runpodConnectionForm.handlers.submit({...event, currentTarget: f.roots.runpodConnectionForm});
  assert(f.roots.runpodConnectionState.textContent.includes('현재 연결을 유지'));
  assert.equal(f.roots.runpodSaveButton.disabled, false);

  f = fixture({available: false});
  await f.context.openRunpodSettings();
  await f.roots.runpodConnectionForm.handlers.submit({...event, currentTarget: f.roots.runpodConnectionForm});
  assert.equal(f.calls.filter(([url]) => url.endsWith('/apply')).length, 0);
  assert(f.roots.runpodConnectionState.textContent.includes('./scripts/dev.sh up'));

  f = fixture({keyState: 'HOST_KEY_CONFIRMATION_REQUIRED'});
  await f.context.openRunpodSettings();
  await f.roots.runpodConnectionForm.handlers.submit({...event, currentTarget: f.roots.runpodConnectionForm});
  assert.equal(f.roots.runpodTrustButton.hidden, false);
  assert.equal(f.calls.filter(([url]) => url.endsWith('/apply')).length, 0);

  f = fixture();
  f.connection.controller = {available: true, phase: 'APPLIED', code: 'SERVICE_NOT_DEPLOYED', applied_host: 'pod.example.test', applied_port: '22001', ssh_state: 'CONNECTED'};
  f.connection.runtime = {mode: 'LIVE', remote: {state: 'SERVICE_NOT_DEPLOYED'}};
  f.context.renderRunpodRuntime(f.connection);
  assert(f.roots.runpodRuntimeState.innerHTML.includes('추론 API가 준비되지 않았습니다'));
  assert(f.roots.runpodRuntimeState.innerHTML.includes('LIVE'));
  assert(f.roots.runpodRuntimeState.innerHTML.includes('CONNECTED'));
  f.connection.runtime.remote.state = 'MODEL_RELEASE_MISMATCH';
  f.context.renderRunpodRuntime(f.connection);
  assert(f.roots.runpodRuntimeState.innerHTML.includes('서버와 인증 연결은 가능'));
  f.connection.controller.phase = 'FAILED'; f.connection.controller.code = 'SSH_AUTH_FAILED';
  f.context.renderRunpodRuntime(f.connection);
  assert(f.roots.runpodRuntimeState.innerHTML.includes('SSH 인증 실패'));
  f.connection.host = 'changed.example.test';
  f.context.renderRunpodRuntime(f.connection);
  assert(f.roots.runpodRuntimeState.innerHTML.includes('적용 필요'));
  assert(!f.calls.some(([url]) => url.includes('generations') || url.includes('reviews')));
  console.log('PASS: settings open, save+apply, duplicate prevention, close, offline, trust gate, failure, separate readiness, changed target; model calls=0');
})().catch(error => {console.error(error); process.exitCode = 1;});

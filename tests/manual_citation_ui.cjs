// Uses the actual form handler and render functions, including async event lifetime.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('/web/app.js', 'utf8');
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const entries = {artifact_id:'artifact',display_id:'CITE-UI',kind:'REFERENCE',locator:'PDF page 2, lines 1-1',quote:'Original full chunk.',scope_unit:'U',scope_configuration:'C',scope_run:'R',cited_edition:'REV-A',page_start:'2',page_end:'2',line_start:'1',line_end:'1'};
let listener, opened, posted, messages = [], calls = 0;
const form = {hidden:false, addEventListener: (type, callback) => {listener=callback;}};
const nodes = {evidenceForm:form,citationChunk:{value:'chunk'},uploadForm:{reset(){}},artifactDialog:{close(){}}};
const receipt = {status:'VALID',freshness:'CURRENT',enforced:true,reason_code:'CITATION_MATCHED',semantic_support:'UNASSESSED'};
const context = vm.createContext({
  state:{project:{id:'project'},evidence:[],selectedEvidenceIds:[]}, $: id => nodes[id], escapeHtml,
  FormData:class {constructor(target){assert.equal(target,form);} entries(){return Object.entries(entries);}},
  csrfHeaders:{'X-DoriLab-CSRF':'1'},
  api:async (path, options) => {calls++; if(options){posted=JSON.parse(options.body);return {id:'evidence',source_verification:receipt};}return [{id:'evidence',source_verification:receipt}];},
  renderEvidence(){},renderOverview(){},renderGates(){},
  message:(text,success)=>messages.push({text,success}),openEvidenceDialog:async id=>{opened=id;},
  workspaceScope:()=>({unit:'U',configuration:'C',run:'R'}),
});
for(const name of ['citationNotice','evidenceEligibility']) {
  const start=source.indexOf(`function ${name}(`);
  const next=source.slice(start+1).search(/\n(?:async )?function /);
  vm.runInContext(source.slice(start,start+1+next),context);
}
const start=source.indexOf('$("evidenceForm").addEventListener("submit"');
const end=source.indexOf('\nasync function saveRequirementPurpose',start);
vm.runInContext(source.slice(start,end),context);
(async()=>{
  const event={currentTarget:form,preventDefault(){}};
  const pending=listener(event);
  event.currentTarget=null; // Browsers clear currentTarget outside synchronous dispatch.
  await pending;
  assert.equal(calls,2);assert.equal(opened,'evidence');assert.equal(form.hidden,true);
  assert.deepEqual(posted.citation,{document_chunk_id:'chunk',cited_edition:'REV-A',source_position:{page_start:2,page_end:2,line_start:1,line_end:1}});
  assert(!('page_start' in posted));assert(!('cited_edition' in posted));
  assert.equal(messages.at(-1).success,true);
  assert(context.citationNotice({source_verification:receipt}).includes('원문 텍스트·위치 일치'));
  const base={kind:'REFERENCE',rights_status:'PUBLIC',edition:'REV-A',adopted:true,applicability_status:'APPLICABLE'};
  assert.equal(context.evidenceEligibility({...base,source_verification:receipt})[0],true);
  for(const check of [{...receipt,status:'REJECTED',reason_code:'CITATION_QUOTE_MISMATCH'}, {...receipt,freshness:'STALE',reason_code:'SOURCE_CHANGED'}]) {
    assert.equal(context.evidenceEligibility({...base,source_verification:check})[0],false);
    assert(!context.citationNotice({source_verification:check}).includes('<b>원문 텍스트·위치 일치</b>'));
  }
  assert(context.citationNotice({}).includes('이전 등록 자료'));
  assert(context.citationNotice({source_verification:{...receipt,reason_code:'<script>bad</script>'}}).includes('&lt;script&gt;'));
  assert(context.citationNotice({source_verification:receipt}).includes('의미적 지지·적용성·제품 적합성'));
  console.log('PASS: actual async Evidence form, citation payload, receipt popup, pending/stale labels and semantic boundary');
})().catch(error=>{console.error(error);process.exitCode=1;});

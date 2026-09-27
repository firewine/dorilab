#!/usr/bin/env python3
"""DoriLab: scoped technical-record / counterfactual diagnostic, no training.

Copy beside dcurr/, data/, runs/ and the already used evidence_probe_v04.py.
New synthetic observations; original local source excerpts are copied, not rewritten.
This is SAME-SOURCE NEW-SCENARIO development evaluation, not a new-program holdout.
Commands: build -> review -> evaluate -> compare. Never calls a training module.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import html
import importlib.util
import json
import random
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

VERSION = 'applicability-probe-v0.6.0'
OUT = 'data/applicability_probe_v06'
PARENT = 'data/physics_candidates40_v02.jsonl'
PARENT_SHA = 'f0a5641a1b4ee64964b2e39b2aafbf779da2fb1cb6cdc1528d62cd115eed83e8'
MODEL = 'Qwen/Qwen3.5-2B'
REVISION = '15852e8c16360a2fea060d615a32b45270f8a8fc'
VIEWS = ('clean', 'first', 'middle', 'last')
POSITION_VIEWS = ('first', 'middle', 'last')
MODELS = {
    'e1': {'adapter': 'runs/evidence_training_v05_position_e1',
           'weight_sha256': '6d05a9efe34b73fb39e04e16715126390d64fe89bf26f748b7e23c4c780a7bf6'},
    'e2': {'adapter': 'runs/evidence_training_v05_position_e2',
           'weight_sha256': 'c16813cc75b33133fbdc4065e991ff0bea9580a75440900eae0fc2be2e4d44c5'},
}
# These are DoriLab-authored synthetic scenarios, NOT new facts attributed to papers.
# Topic order is fixed; A/B state assignment is balanced and outside model input.
TOPICS = (
    {
        'parent': 'PHY-TH01-P07-A', 'title': '열: 센서 위치와 모델 물리량의 대응',
        'negative_action': 'CHALLENGE', 'reason': 'MEASUREMENT_MAPPING_MISMATCH',
        'question': 'Does channel J7 measure the same physical quantity as model output T_case for this comparison?',
        'proposal': 'Use channel J7 as the directly corresponding measurement for the case-average temperature T_case.',
        'positive': 'Channel J7 is the weighted mean of the case-surface sensors. The mapping table uses the same case-surface locations and weights for J7 and model output T_case. J7 is not an internal-heater thermocouple.',
        'negative': 'Channel J7 is a thermocouple on the internal heater. Model output T_case is the mean over the case surface. No spatial mapping or transfer model relates this heater measurement to that case-surface mean.',
        'request_ids': [], 'positive_A': True,
        'rationale': '채널/모델이 나타내는 위치·평균량의 일치 여부만 검토한다. 다른 시험체나 다른 run의 올바른 mapping은 현재 run의 불일치를 해소하지 않는다.',
    },
    {
        'parent': 'PHY-TH01-P05-A', 'title': '열: 부품별 발열량과 위치 자료의 존재',
        'negative_action': 'REQUEST_EVIDENCE', 'reason': 'POWER_DISSIPATION_UNRESOLVED',
        'question': 'What is the next action for the component-power input-completeness check? This is a readiness check, not a final assertion that a model result is valid.',
        'proposal': 'Resolve the component-power input check using the supplied record package before any subsequent thermal correlation.',
        'positive': 'The package lists each component heat source, its dissipated power in the specified operating mode, and its corresponding physical location in the thermal model. The entries are linked to this run and configuration; component totals are reconciled with the measured assembly total.',
        'negative': 'The package contains only the assembly total electrical input. Component-level dissipated powers and the physical locations to assign those heat sources in the thermal model are not included.',
        'request_ids': ['PER_COMPONENT_POWER_AND_LOCATION'], 'positive_A': False,
        'rationale': '최종 결과를 부정하는 문제가 아니라 입력 완결성 확인이다. 부품별 전력·위치가 없으면 요청하고, 해당 목록이 현재 범위에 대해 제공된 경우 이 확인 단계의 추가 조치는 없다.',
    },
    {
        'parent': 'PHY-VBX1-P03-A', 'title': '진동: f0 모드 선정과 유효질량',
        'negative_action': 'CHALLENGE', 'reason': 'MODE_SELECTION_MISMATCH',
        'question': 'Does the proposed turnover mode follow the supplied definition of f0 for the stated load direction?',
        'proposal': 'Use the mode at 47 Hz as f0 for this load direction under the cited force-limiting method.',
        'positive': 'For this load direction, the mode at 47 Hz is the primary load mode with significant modal effective mass. The listed mode at 112 Hz is localized and has negligible modal effective mass in this direction.',
        'negative': 'For this load direction, the mode at 47 Hz is localized and has negligible modal effective mass. The primary load mode with significant modal effective mass in this direction is the listed mode at 112 Hz.',
        'request_ids': [], 'positive_A': False,
        'rationale': '47/112 Hz와 유효질량 분류는 모두 가상 입력이다. 작은 주파수라는 이름이 아니라 현재 방향의 primary load mode라는 주어진 분류에 따라 검토한다.',
    },
    {
        'parent': 'PHY-VBX1-P05-A', 'title': '진동: 잔여질량과 감쇠 입력 누락',
        'negative_action': 'REQUEST_EVIDENCE', 'reason': 'MODAL_INPUTS_MISSING',
        'question': 'What is the next action for input completeness of the cited CSMA model? Only input availability is being checked, not approval of predicted loads.',
        'proposal': 'Complete the CSMA input-completeness review using the supplied data package before evaluating predicted interface loads.',
        'positive': 'The input package contains total mass, fixed-interface natural frequencies, modal effective masses, residual-mass terms, damping assumptions, and the translational apparent-mass information required by the stated model. Each entry is mapped to this configuration.',
        'negative': 'The input package contains total mass, fixed-interface natural frequencies, modal effective masses, and translational apparent-mass information. Residual-mass terms and damping assumptions are absent; they are not recoverable from the supplied package.',
        'request_ids': ['RESIDUAL_MASS_AND_DAMPING'], 'positive_A': True,
        'rationale': '모델의 참·거짓 판정이 아니라 필요한 입력의 완결성을 확인한다. 이 사례에서는 누락 항목을 잔여질량과 감쇠로 한정한다.',
    },
    {
        'parent': 'PHY-EE02-P01-A', 'title': '전기전자: 자극 중 이상과 시험 후 복귀의 구분',
        'negative_action': 'CHALLENGE', 'reason': 'EVIDENCE_INTERPRETATION_ERROR',
        'question': 'Does the time-aligned channel record support the proposed description of this stimulus interval? This is an observation-description check, not an EMC compliance decision.',
        'proposal': 'Describe the monitored channel as showing no excursion during the applied stimulus in this run.',
        'positive': 'The time-aligned channel history covers the complete stimulus interval. It records no channel excursion during the stimulus and a nominal channel value after the stimulus ends.',
        'negative': 'The time-aligned channel history covers the complete stimulus interval. It records a reproducible channel excursion during the stimulus and a return to the nominal value after the stimulus ends.',
        'request_ids': [], 'positive_A': True,
        'rationale': '시험 후 정상 복귀는 두 상태에 공통이다. 가상 time history의 자극 중 excursion 유무만 다르며 EMC 합격 기준은 새로 만들지 않는다.',
    },
    {
        'parent': 'PHY-EE03-P02-A', 'title': '전기전자: 노출 기록과 전기적 구성의 추적성',
        'negative_action': 'REQUEST_EVIDENCE', 'reason': 'EXPOSURE_METADATA_UNRESOLVED',
        'question': 'What is the next action for checking whether this single-event test result has traceable exposure and electrical operating conditions? The question is record completeness, not radiation qualification.',
        'proposal': 'Complete the exposure-and-electrical-configuration traceability check before interpreting the single-event result.',
        'positive': 'The package includes the run-specific exposure log and the tested electrical configuration, including bias and operating mode. Both records are explicitly linked to this test article, configuration and run identifier.',
        'negative': 'The package includes a post-run result summary but not the run-specific exposure log or the tested bias and operating-mode configuration. Neither missing record is available elsewhere in the supplied package.',
        'request_ids': ['EXPOSURE_RECORD', 'ELECTRICAL_CONFIGURATION'], 'positive_A': False,
        'rationale': '노출·전기적 구성의 기록 존재만 판단한다. 기록이 있다고 방사선 내성을 인정하는 것이 아니며, 다른 serial/run의 자료로 현재 기록을 대체하지 않는다.',
    },
)


def now(): return datetime.now(timezone.utc).isoformat()
def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''): h.update(b)
    return h.hexdigest()
def strict(s):
    def pairs(xs):
        d = {}
        for k, v in xs:
            if k in d: raise ValueError('Duplicate JSON key: ' + k)
            d[k] = v
        return d
    def bad(v): raise ValueError('Invalid numeric constant: ' + v)
    return json.loads(s, object_pairs_hook=pairs, parse_constant=bad)
def readj(p): return strict(Path(p).read_text(encoding='utf-8-sig'))
def readl(p):
    xs = [strict(x) for x in Path(p).read_text(encoding='utf-8-sig').splitlines() if x.strip()]
    if any(not isinstance(x, dict) for x in xs): raise ValueError('JSONL object rows required: ' + str(p))
    return xs
def canon(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
def writej(p, x):
    with Path(p).open('x', encoding='utf-8') as f: json.dump(x, f, ensure_ascii=False, indent=2); f.write('\n')
def writel(p, xs):
    with Path(p).open('x', encoding='utf-8') as f:
        for x in xs: f.write(json.dumps(x, ensure_ascii=False) + '\n')
def local(root, rel):
    r = Path(rel)
    if r.is_absolute() or '..' in r.parts: raise ValueError('Project-relative path required: ' + str(rel))
    p = root / r
    if not p.resolve().is_relative_to(root.resolve()): raise ValueError('Path escapes project')
    return p

def helper(root):
    p = root / 'evidence_probe_v04.py'
    if not p.is_file(): raise ValueError('Keep the already used evidence_probe_v04.py at the project root.')
    spec = importlib.util.spec_from_file_location('_existing_dori_v04', p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    if m.VERSION != 'evidence-probe-v0.4.0': raise ValueError('Unexpected v04 scorer version')
    return m

def scope_text(serial, config, run, body):
    return f'Record scope: unit={serial}; configuration={config}; run={run}. {body}'

def make_cases(parents, seed=62026):
    """Copy source excerpts exactly apart from their local reference handles.
    Only the target record's technical body changes within each pair. The proposal,
    scope, metadata and both off-scope technical records are identical within pairs.
    """
    byid = {x['case_id']: x for x in parents}
    if len(byid) != len(parents): raise ValueError('Duplicate original case_id')
    rng = random.Random(seed); used = set(); flat = []; audit = []
    def ident(prefix):
        while True:
            s = prefix + str(rng.randrange(1000, 10000))
            if s not in used: used.add(s); return s
    for i, t in enumerate(TOPICS, 1):
        if t['parent'] not in byid: raise ValueError('Required source case absent: ' + t['parent'])
        parent = byid[t['parent']]; neg = parent['expected']
        if (neg['action'], neg.get('reason')) != (t['negative_action'], t['reason']):
            raise ValueError('Parent action/reason changed: ' + t['parent'])
        if set(neg.get('requested_evidence', [])) != set(t['request_ids']):
            raise ValueError('Parent request IDs changed: ' + t['parent'])
        pid = f'AP06-{i:02d}'
        refs = copy.deepcopy(parent['packet']['reference_context'])
        if len(refs) != 1 or not isinstance(refs[0].get('text'), str):
            raise ValueError('This diagnostic expects one reviewed source excerpt: ' + t['parent'])
        original_ref = refs[0]['reference_id']; refs[0]['reference_id'] = ident('SF-')
        refid = refs[0]['reference_id']; obs, dec1, dec2 = [ident('OBS-') for _ in range(3)]
        claim = ident('CLM-'); serial = f'U-{rng.randrange(110, 980)}'; other = serial + 'X'
        config = f'C-{rng.randrange(10, 90)}'; older = config + '-prev'
        run = f'R-{rng.randrange(100, 999)}'; prior_run = run + '-prior'
        # One different article; one same article but different configuration/run.
        # Both off-scope records keep a fixed polarity within the pair. Their
        # majority therefore cannot solve both target states. Across topics this
        # nuisance polarity alternates; it is not exposed as a label in the packet.
        nuisance_body = t['positive'] if i % 2 else t['negative']
        d1 = {'evidence_id': dec1, 'text': scope_text(other, config, run, nuisance_body)}
        d2 = {'evidence_id': dec2, 'text': scope_text(serial, older, prior_run, nuisance_body)}
        question = (
            f'Review scope: unit={serial}; configuration={config}; run={run}. '
            'Only records matching all three scope identifiers may substantiate this check; '
            'any other supplied records are archival comparisons and no equivalence or carryover evidence is provided. '
            + t['question']
        )
        for variant in ('A', 'B'):
            positive = (variant == 'A') == t['positive_A']
            obs_text = t['positive'] if positive else t['negative']
            answer = {'action': 'NO_ACTION_REQUIRED' if positive else t['negative_action'],
                      'claim_id': claim, 'evidence_refs': [refid, obs]}
            if not positive:
                answer['reason'] = t['reason']
                if t['request_ids']: answer['requested_evidence'] = list(t['request_ids'])
            c = {
                'case_id': f'{pid}-{variant}', 'pair_id': pid, 'variant': variant,
                'role': parent['role'], 'domain': parent['domain'], 'source_id': parent['source_id'],
                'source_fact_ids': copy.deepcopy(parent.get('source_fact_ids', [])),
                'source_program_groups': copy.deepcopy(parent.get('source_program_groups', [])),
                'basis': 'SYNTHETIC_NEW_SCENARIO_FROM_EXISTING_SOURCE_EXCERPT',
                'planned_split': 'DEV_DIAGNOSTIC', 'human_review_status': 'PENDING',
                'scope_of_no_action': 'Only the specified local check; not test approval or qualification.',
                'packet': {'review_question': question, 'claim_id': claim,
                           'reference_context': copy.deepcopy(refs),
                           'case_packet': {'evidence': [{'evidence_id': obs, 'text': scope_text(serial, config, run, obs_text)},
                                                       copy.deepcopy(d1), copy.deepcopy(d2)],
                                           'proposal': t['proposal']},
                           'allowed_request_ids': list(t['request_ids'])},
                'expected': answer, 'acceptable_answers': [copy.deepcopy(answer)],
                'rationale_ko': t['rationale'], 'prompt_version': 'physics-review-v0.2',
                'schema_version': 'physics-review-action-v0.2',
                'authoring': {'parent_case_id': t['parent'], 'original_reference_id': original_ref,
                              'title_ko': t['title'], 'expected_scope_record': obs,
                              'off_scope_record_ids': [dec1, dec2], 'target_scope': [serial, config, run],
                              'numbers_and_records': 'All record scopes, observations and example numbers are synthetic.',
                              'reference_text_status': 'Copied locally; no new full-text verification performed by this tool.',
                              'label_basis': 'DoriLab-authored local-review policy plus copied source principle; human review required.',
                              'pair_change': 'Only technical content of the current-scope record changes.'},
            }
            flat.append(c)
        audit.append({'pair_id': pid, 'title': t['title'], 'parent_case_id': t['parent'],
                      'source_id': parent['source_id'], 'synthetic_case_scope': [serial, config, run],
                      'rationale_ko': t['rationale']})
    rng.shuffle(flat)
    views = {}
    for v in VIEWS:
        views[v] = copy.deepcopy(flat)
        for c in views[v]:
            target, d1, d2 = c['packet']['case_packet']['evidence']
            if v == 'clean':
                ev = [target]
            else:
                ev = [d1, d2]; ev.insert(POSITION_VIEWS.index(v), target)
            c['packet']['case_packet']['evidence'] = ev
    return views, audit


def design_check(views, parents):
    """Structural invariants, not a substitute for engineering label review."""
    if set(views) != set(VIEWS): raise ValueError('Clean plus three position views required')
    parents = {x['case_id']: x for x in parents}; base = {x['case_id']: x for x in views['first']}
    if len(base) != 12 or any(len(views[v]) != 12 for v in VIEWS): raise ValueError('Expected 12 unique scenarios per view')
    groups = defaultdict(list)
    for c in views['first']: groups[c['pair_id']].append(c)
    if len(groups) != 6: raise ValueError('Six paired topics required')
    if Counter(c['expected']['action'] for c in base.values()) != {'NO_ACTION_REQUIRED': 6, 'CHALLENGE': 3, 'REQUEST_EVIDENCE': 3}:
        raise ValueError('Unexpected action distribution')
    for pid, cs in groups.items():
        if len(cs) != 2 or {x['variant'] for x in cs} != {'A', 'B'}: raise ValueError('Incomplete pair')
        p1, p2 = [copy.deepcopy(x['packet']) for x in cs]
        t1 = p1['case_packet']['evidence'][0].pop('text'); t2 = p2['case_packet']['evidence'][0].pop('text')
        if p1 != p2 or t1 == t2: raise ValueError('Pair must change only target technical record text')
        if cs[0]['expected']['action'] == cs[1]['expected']['action']: raise ValueError('Pair must require an action change')
    for v in VIEWS:
        if {x['case_id'] for x in views[v]} != set(base): raise ValueError('View membership changed')
        for c in views[v]:
            b = base[c['case_id']]
            original = parents[c['authoring']['parent_case_id']]['packet']['reference_context'][0]
            ref = copy.deepcopy(c['packet']['reference_context'][0]); ref['reference_id'] = original['reference_id']
            if ref != original: raise ValueError('Source excerpt was rewritten')
            ev = c['packet']['case_packet']['evidence']
            n = 0 if v == 'clean' else POSITION_VIEWS.index(v)
            if len(ev) != (1 if v == 'clean' else 3): raise ValueError('Unexpected observation count')
            if ev[n]['evidence_id'] != c['authoring']['expected_scope_record']: raise ValueError('Target position mismatch')
            c2 = copy.deepcopy(c); b2 = copy.deepcopy(b)
            if v == 'clean': b2['packet']['case_packet']['evidence'] = b2['packet']['case_packet']['evidence'][:1]
            for item in (c2, b2): item['packet']['case_packet']['evidence'].sort(key=lambda e: e['evidence_id'])
            if c2 != b2: raise ValueError('Position variants must contain exactly the same content')
            expected = {c['packet']['reference_context'][0]['reference_id'], c['authoring']['expected_scope_record']}
            if set(c['expected']['evidence_refs']) != expected: raise ValueError('Gold must cite the local source and scoped observation only')
            if expected & set(c['authoring']['off_scope_record_ids']): raise ValueError('Off-scope gold leak')
    return True


def review_html(views, topics):
    def esc(x): return html.escape(str(x))
    def pretty(x): return '<pre>' + esc(json.dumps(x, ensure_ascii=False, indent=2)) + '</pre>'
    parts = ['<!doctype html><html lang="ko"><meta charset="utf-8"><title>적용성·반증 평가 후보 검토</title>',
             '<style>body{font-family:system-ui,sans-serif;max-width:1100px;margin:2em auto;padding:0 1em;line-height:1.6} pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f2f4f6;padding:1em} section{border-top:2px solid #888;margin-top:2em} article{border:1px solid #bbb;padding:1em;margin:1em 0}h1,h2,h3{line-height:1.3}</style>',
             '<h1>v06 적용성·반증 평가 후보</h1><p><b>새 관측과 수치는 전부 가상이다.</b> 원문 근거는 로컬 원본 사례에서 복사했다. 새로운 논문·실제 시험 프로그램의 검증 결과가 아니다. 기존 학습/소스 승인은 변경하지 않는다.</p>',
             '<p>6주제 × A/B = 12개 후보. 평가 때 현재 기록만 주는 대조 조건과, 현재 범위 기록을 처음·중간·끝에 둔 조건을 비교한다(총48개 입력, 독립 문제48개가 아님). 각 쌍은 질문·proposal·범위·비해당 기술기록이 같고, 현재 범위 기록의 내용만 다르다.</p>',
             '<p><b>확인:</b> 원문 원리가 이 새 질문을 지지하는가? 범위 식별자가 명확한가? 긍정 조건이 검토 범위에서 충분한가? 누락 상황에서 REQUEST가 타당한가? 다른 합리적인 action/reason/근거 집합이 있는가? 애매하면 평가 실행 전에 후보를 수정하고 새 버전으로 동결한다.</p>']
    groups = defaultdict(list)
    for c in views['first']: groups[c['pair_id']].append(c)
    for t in topics:
        cs = sorted(groups[t['pair_id']], key=lambda x: x['variant'])
        parts += ['<section><h2>' + esc(t['pair_id'] + ' ' + t['title']) + '</h2>',
                  '<p>원본: ' + esc(t['parent_case_id']) + ' / source ' + esc(t['source_id']) + '</p>',
                  '<h3>그대로 가져온 문헌 근거</h3>' + pretty(cs[0]['packet']['reference_context']),
                  '<h3>두 상황에서 동일한 질문과 제안</h3>' + pretty({k: cs[0]['packet'][k] for k in ('review_question', 'claim_id')}),
                  pretty(cs[0]['packet']['case_packet']['proposal']), '<p>' + esc(t['rationale_ko']) + '</p>']
        for c in cs:
            parts += ['<article><h3>' + esc(c['case_id']) + '</h3><h4>관측 기록(현재 범위 기록이 첫 항목인 보기)</h4>',
                      pretty(c['packet']['case_packet']['evidence']), '<h4>정답 후보</h4>', pretty(c['expected']), '</article>']
        parts += ['</section>']
    parts += ['<p>이 문서는 학습자료가 아닌 평가 후보 검토 화면이다. 승인 명령은 이 bundle의 진단 사용만 승인하며, 문헌 사용권 또는 실제 시험/제품을 승인하지 않는다.</p></html>']
    return '\n'.join(parts)


def build(root, outdir, seed):
    dest = local(root, outdir)
    if dest.exists(): raise ValueError('Output folder exists; preserve it. Do not overwrite a reviewed diagnostic.')
    parfile = root / PARENT
    if sha(parfile) != PARENT_SHA: raise ValueError('Original case corpus hash differs; do not build against an unexamined version.')
    h = helper(root); common = h.runtime_common(root)
    parents = readl(parfile); views, topics = make_cases(parents, seed); design_check(views, parents)
    frozen = {PARENT: sha(parfile), 'evidence_probe_v04.py': sha(root / 'evidence_probe_v04.py'),
              'data/action_schema_v02.json': sha(root / 'data/action_schema_v02.json')}
    for p in sorted((root / 'dcurr').glob('*.py')): frozen[str(p.relative_to(root))] = sha(p)
    for module in ('common.py', 'evaluate.py', 'model_io.py', 'prompts.py', 'prompts_legacy.py'):
        if 'dcurr/' + module not in frozen: raise ValueError('Missing dcurr/' + module)
    for rows in views.values():
        for c in rows:
            h.validate_gold_refs(c); common.validate_answer(c['expected'], c)
            if len(c['packet']['case_packet']['evidence']) > 1:
                h.runtime_contract_check(common, c, c['authoring']['off_scope_record_ids'][0])
    models = copy.deepcopy(MODELS)
    for label, spec in models.items():
        d = local(root, spec['adapter'])
        if sha(d / 'adapter_model.safetensors') != spec['weight_sha256']: raise ValueError('Unexpected ' + label + ' adapter')
        if not (d / 'adapter_config.json').is_file(): raise ValueError('Adapter config missing: ' + str(d))
        cfg = readj(d / 'adapter_config.json')
        if cfg.get('base_model_name_or_path') != MODEL: raise ValueError('Adapter base identity differs')
        # Freeze adapter-local tokenizer/config files as well as the weights.
        for p in d.iterdir():
            if p.is_file(): frozen[str(p.relative_to(root))] = sha(p)
        spec['outputs'] = {v: str(outdir / 'results' / f'{label}_{v}.jsonl') for v in VIEWS}
    dest.mkdir(parents=True); (dest / 'results').mkdir(); (dest / 'logs').mkdir()
    inputs = {}
    for v in VIEWS:
        p = dest / f'cases_{v}.jsonl'; writel(p, views[v]); inputs[str(p.relative_to(root))] = sha(p)
    rev = dest / 'REVIEW.html'; rev.write_text(review_html(views, topics), encoding='utf-8'); inputs[str(rev.relative_to(root))] = sha(rev)
    manifest = {'version': VERSION, 'created_at_utc': now(), 'script_sha256': sha(Path(__file__)),
                'purpose': 'REVIEWED_SAME_SOURCE_NEW_SCENARIO_DIAGNOSTIC_NOT_EXTERNAL_HOLDOUT',
                'unique_scenarios': 12, 'counterfactual_pairs': 6, 'views_are_not_independent_samples': True,
                'model': MODEL, 'base_revision': REVISION, 'generation_budget': 384, 'seed_for_data': seed,
                'case_files': {v: str(outdir / f'cases_{v}.jsonl') for v in VIEWS},
                'frozen_files': frozen, 'generated_files': inputs, 'models': models, 'topics': topics,
                'action_counts_per_view': {'CHALLENGE': 3, 'REQUEST_EVIDENCE': 3, 'NO_ACTION_REQUIRED': 6},
                'source_note': 'New synthetic records; source excerpts are copied verbatim from local parent cases except reference handles. No claim of new-source independence.',
                'intervention_note': 'Within pair: only current-scope technical record body changes. Clean control has no off-scope records; across position views only observation order changes. Roles/prompts/schema unchanged.',
                'report_policy': 'Evidence precision is a diagnostic exact-set criterion, not a new physical acceptance threshold.'}
    writej(dest / 'manifest.json', manifest)
    print('APPLICABILITY BUILD: PASS\nCandidate scenarios: 12 / pairs: 6 / views: 4')
    print('Review:', rev)
    print('No source/case approval, training data, model or existing code was changed.')


def plan(root, outdir, reviewed=False):
    dest = local(root, outdir); m = readj(dest / 'manifest.json')
    if m['version'] != VERSION or m['script_sha256'] != sha(Path(__file__)): raise ValueError('Script/version changed after build')
    h = helper(root)
    h.freeze_check(root, {**m['frozen_files'], **m['generated_files']})
    if reviewed:
        ap = readj(dest / 'review.json')
        if ap.get('decision') != 'ACCEPTED_FOR_DIAGNOSTIC' or not ap.get('reviewer') or not ap.get('notes'):
            raise ValueError('Candidate review acceptance is required')
        if ap.get('manifest_sha256') != sha(dest / 'manifest.json'): raise ValueError('Review applies to another bundle')
    return dest, m, h


def review(root, outdir, reviewer, notes):
    dest, m, h = plan(root, outdir)
    if not reviewer.strip() or not notes.strip(): raise ValueError('Actual reviewer and review notes required')
    writej(dest / 'review.json', {'decision': 'ACCEPTED_FOR_DIAGNOSTIC', 'reviewer': reviewer.strip(),
                                'notes': notes.strip(), 'at_utc': now(), 'manifest_sha256': sha(dest / 'manifest.json'),
                                'scope': 'Only newly authored scenario/gold validity. Not source rights, training approval, or real equipment qualification.'})
    print('DIAGNOSTIC REVIEW SAVED. Original approval CSVs unchanged.')


def checked_results(root, m, label, view, h):
    spec = m['models'][label]; out = local(root, spec['outputs'][view]); casepath = local(root, m['case_files'][view])
    sm = readj(out.with_suffix('.summary.json')); cases = readl(casepath); rows = h.result_ids(readl(out), cases)
    if sm.get('adapter_sha256') != spec['weight_sha256'] or sm.get('case_file_sha256') != sha(casepath):
        raise ValueError('Output adapter/case identity mismatch: ' + str(out))
    if sm.get('model') != m['model'] or sm.get('purpose') != 'CANDIDATE_DIAGNOSTIC': raise ValueError('Output experiment identity mismatch')
    if sm.get('records') != len(cases): raise ValueError('Result count mismatch')
    if sm.get('prompt_sha256') != sha(root / 'dcurr/prompts.py'): raise ValueError('Output prompt mismatch')
    for sk, rk in [('strict_json_valid','strict_json_valid'), ('schema_and_refs_valid','schema_and_refs_valid'),
                   ('action_correct','action_ok'), ('contract_pass','contract_pass')]:
        if sum(bool(r.get(rk)) for r in rows.values()) != sm.get(sk): raise ValueError('Summary/row mismatch: ' + sk)
    return cases, rows


def evaluate(root, outdir, only):
    dest, m, h = plan(root, outdir, True)
    labels = [only] if only else list(m['models'])
    for label in labels:
        for v in VIEWS:
            plan(root, outdir, True)
            output = local(root, m['models'][label]['outputs'][v]); marker = dest / 'results' / f'{label}_{v}.invocation.json'
            command = [sys.executable, '-m', 'dcurr.evaluate', '--cases', m['case_files'][v],
                       '--adapter', m['models'][label]['adapter'], '--out', str(output.relative_to(root)),
                       '--model', m['model'], '--revision', m['base_revision'],
                       '--max-new-tokens', str(m['generation_budget']), '--purpose', 'CANDIDATE_DIAGNOSTIC']
            if output.exists() or output.with_suffix('.summary.json').exists():
                if not marker.exists() or readj(marker)['command'] != command: raise ValueError('Existing result has no matching invocation record; preserve it')
                checked_results(root, m, label, v, h)
                print('SKIP VERIFIED COMPLETE:', label, v); continue
            if marker.exists() and readj(marker)['command'] != command: raise ValueError('Attempt record differs')
            if not marker.exists(): writej(marker, {'command': command, 'at_utc': now(), 'manifest_sha256': sha(dest / 'manifest.json')})
            log = dest / 'logs' / f'{label}_{v}_{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")}.log'
            print('\nRUN:', ' '.join(command), flush=True)
            with log.open('x', encoding='utf-8') as f:
                f.write('COMMAND ' + json.dumps(command) + '\n'); f.flush()
                with subprocess.Popen(command, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                      text=True, encoding='utf-8', errors='replace') as proc:
                    for line in proc.stdout:
                        print(line, end='', flush=True); f.write(line); f.flush()
                    code = proc.wait()
            if code: raise RuntimeError(f'Evaluation stopped ({code}); log preserved: {log}. Do not rerun training.')
            checked_results(root, m, label, v, h)
    print('EVALUATIONS COMPLETE. Next: compare')


def action_of(score):
    value = score.get('parsed')
    return value.get('action') if isinstance(value, dict) else None

def refs_of(score):
    value = score.get('parsed')
    refs = value.get('evidence_refs') if isinstance(value, dict) else None
    return canon(sorted(refs, key=canon)) if isinstance(refs, list) else canon(refs)

def compare(root, outdir):
    dest, m, h = plan(root, outdir, True); common = h.runtime_common(root)
    if (dest / 'comparison.json').exists() or (dest / 'comparison_cases.jsonl').exists(): raise ValueError('Comparison already exists; preserved')
    summaries = {}; details = []; all_scores = {}; raw_hash = {}
    for label in m['models']:
        sv = {}; bycase = defaultdict(dict); combined = []
        for v in VIEWS:
            cases, outputs = checked_results(root, m, label, v, h)
            path = local(root, m['models'][label]['outputs'][v]); raw_hash[f'{label}/{v}'] = sha(path)
            records = []
            for c in cases:
                d = c['authoring']['off_scope_record_ids']; row = outputs[c['case_id']]
                score = h.score(common, c, row, d)
                if not score['stored_score_agrees']: raise ValueError('Current scorer differs from stored score')
                record = {'case_id': c['case_id'], 'pair_id': c['pair_id'], 'domain': c['domain'], 'score': score}
                records.append(record); bycase[c['case_id']][v] = record; combined.append(record)
            s = h.summarise(records)
            s['gold_action_breakdown'] = {}
            for a in ('CHALLENGE','REQUEST_EVIDENCE','NO_ACTION_REQUIRED'):
                part = [r for r in records if r['score']['expected_primary']['action'] == a]
                s['gold_action_breakdown'][a] = {'n': len(part), 'action_correct': sum(r['score']['action_correct'] for r in part),
                    'strict_pass': sum(r['score']['strict_selection_contract_pass'] for r in part)}
            s['wrongly_accepts_refuted_proposal'] = sum(r['score']['expected_primary']['action'] == 'CHALLENGE' and
                     action_of(r['score']) == 'NO_ACTION_REQUIRED' for r in records)
            s['unnecessary_intervention_on_positive'] = sum(r['score']['expected_primary']['action'] == 'NO_ACTION_REQUIRED' and
                     action_of(r['score']) in ('CHALLENGE','REQUEST_EVIDENCE') for r in records)
            sv[v] = s
        bundles = []; groups = defaultdict(list)
        for cid, recs in bycase.items():
            sc = {v: recs[v]['score'] for v in VIEWS}
            consistent_action = len({action_of(sc[v]) for v in POSITION_VIEWS}) == 1
            consistent_refs = len({refs_of(sc[v]) for v in POSITION_VIEWS}) == 1
            d = {'model': label, 'case_id': cid, 'pair_id': recs['first']['pair_id'], 'scores': sc,
                 'order_changed_action': not consistent_action, 'order_changed_refs': not consistent_refs,
                 'all_views_strict_pass': all(s['strict_selection_contract_pass'] for s in sc.values()),
                 'clean_strict_pass_lost': {v: bool(sc['clean']['strict_selection_contract_pass'] and not sc[v]['strict_selection_contract_pass']) for v in POSITION_VIEWS}}
            details.append(d); bundles.append(d); groups[d['pair_id']].append(d)
        summaries[label] = {'views': sv, 'case_denominator': 12, 'pair_denominator': 6,
                            'order_changed_action_cases': sum(x['order_changed_action'] for x in bundles),
                            'order_changed_reference_cases': sum(x['order_changed_refs'] for x in bundles),
                            'all_views_strict_pass_cases': sum(x['all_views_strict_pass'] for x in bundles),
                            'clean_pass_lost_by_position': {v: sum(x['clean_strict_pass_lost'][v] for x in bundles) for v in POSITION_VIEWS},
                            'both_states_all_views_strict_pairs': sum(len(xs)==2 and all(x['all_views_strict_pass'] for x in xs) for xs in groups.values())}
    report = {'version': VERSION, 'created_at_utc': now(), 'manifest_sha256': sha(dest / 'manifest.json'),
              'unique_scenarios': 12, 'counterfactual_pairs': 6, 'models': summaries, 'result_sha256': raw_hash,
              'meaning': 'Same-source newly authored scope/polarity diagnostic. 48 inputs per model are 12 related scenarios from 6 topics, not 48 independent samples. No training or final-holdout claim.',
              'label_note': 'Gold labels and exact allowed evidence set were reviewed before new model outputs. Original public excerpts may already be known to the base/adapter.'}
    writej(dest / 'comparison.json', report); writel(dest / 'comparison_cases.jsonl', details)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    lines = ['# v06 적용성·반증 평가 결과', '', report['meaning'], '',
             '| 모델/위치 | action | 근거 정확선택 | 엄격 통과 | 범위 밖 인용 | 반증을 문제없음으로 수용 |',
             '|---|---:|---:|---:|---:|---:|']
    for label, s in summaries.items():
        for v, a in s['views'].items():
            lines.append(f"| {label}/{v} | {a['action_correct']}/12 | {a['reference_choice_exact']}/12 | {a['strict_selection_contract_pass']}/12 | {a['rows_citing_distractors']} | {a['wrongly_accepts_refuted_proposal']} |")
        lines.append(f"\n{label}: 4조건 모두 통과 {s['all_views_strict_pass_cases']}/12, A/B 두 상태·4조건 모두 통과 {s['both_states_all_views_strict_pairs']}/6쌍, 순서에 따른 action 변경 {s['order_changed_action_cases']}건.\n")
    lines += ['\n평가 결과를 보고 이 자료로 학습하면 이후에는 학습/회귀 자료로 관리한다. 새로운 source family 일반화와 별개다.']
    (dest / 'RESULTS_KO.md').write_text('\n'.join(lines), encoding='utf-8')
    print('\nRESULT FOLDER:', dest)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, default=Path.cwd())
    p.add_argument('--outdir', type=Path, default=Path(OUT))
    sub = p.add_subparsers(dest='cmd', required=True)
    b = sub.add_parser('build'); b.add_argument('--seed', type=int, default=62026)
    r = sub.add_parser('review'); r.add_argument('--reviewer', required=True); r.add_argument('--notes', required=True)
    e = sub.add_parser('evaluate'); e.add_argument('--only', choices=tuple(MODELS))
    sub.add_parser('compare')
    a = p.parse_args(); root = a.root.resolve()
    if a.cmd == 'build': build(root, a.outdir, a.seed)
    elif a.cmd == 'review': review(root, a.outdir, a.reviewer, a.notes)
    elif a.cmd == 'evaluate': evaluate(root, a.outdir, a.only)
    else: compare(root, a.outdir)

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        raise SystemExit('STOP: ' + str(exc) + '\nOriginal data, models and approvals are preserved. Inspect the log; no retraining is requested.')

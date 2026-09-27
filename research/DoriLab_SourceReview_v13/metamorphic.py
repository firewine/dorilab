#!/usr/bin/env python3
"""Deterministic ID/order view. Does not add independent samples or consult gold for input creation."""
import copy,hashlib,random

def rename_input(inp,seed=13):
    x=copy.deepcopy(inp);p=x['packet'];caseid=x['case_id'];mapping={}
    allids=[p['claim_id']]+[r['reference_id'] for r in p['source_refs']]+[o['evidence_id'] for o in p['observations']]
    for old in allids:
        prefix=old.split('-')[0];mapping[old]=prefix+'-'+hashlib.sha256(f'{seed}:{caseid}:{old}'.encode()).hexdigest()[:10]
    p['claim_id']=mapping[p['claim_id']]
    for r in p['source_refs']:r['reference_id']=mapping[r['reference_id']]
    for o in p['observations']:o['evidence_id']=mapping[o['evidence_id']]
    rng=random.Random(f'{seed}:{caseid}');rng.shuffle(p['source_refs']);rng.shuffle(p['observations']);rng.shuffle(p['request_catalog'])
    # scope identity unchanged: renaming a record ID does not change the observed configuration.
    return x,mapping

def remap_gold_for_offline_score(gold,mapping):
    g=copy.deepcopy(gold);e=g['expected'];e['claim_id']=mapping[e['claim_id']]
    e['evidence_refs']=[mapping[x] for x in e['evidence_refs']]
    g['reference_requirement']['required']=[mapping[x] for x in g['reference_requirement']['required']]
    g['review_note']['supporting_observation_ids']=[mapping[x] for x in g['review_note']['supporting_observation_ids']]
    return g

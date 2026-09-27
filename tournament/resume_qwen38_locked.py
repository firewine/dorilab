#!/usr/bin/env python3
"""Resume the failed pre-inference download using the original immutable lock."""
import sys
from pathlib import Path
import dorilab_model_tournament as tournament
from huggingface_hub import HfApi
from transformers import AutoConfig

LOCK_PATH = Path('/workspace/dorilab/tournament/baseline_v1/failed_attempts/qwen38_27b_download_enospc_20260923T1426Z/qwen38_27b/MODEL_LOCK.json')
lock = tournament.read_json(LOCK_PATH)

def resolve_original_revision(model_id):
    tournament.require(model_id == lock['model'], 'retry model changed')
    revision = HfApi().model_info(model_id, revision=lock['revision']).sha
    tournament.require(revision == lock['revision'], 'retry revision changed')
    config = AutoConfig.from_pretrained(model_id, revision=revision, trust_remote_code=False)
    return config, revision

tournament.resolve_revision = resolve_original_revision
sys.argv = [str(Path(tournament.__file__)), 'run', '--models', 'qwen38_27b']
raise SystemExit(tournament.main())

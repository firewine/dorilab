# DoriLab RC3 HTTP API

Bind: `127.0.0.1:8080`, one web process, one resident BF16/SDPA model, one generation, no pending queue. Start loads once; requests never reload. `enable_thinking=false`, greedy, native EOS `<|im_end|>` (248046), pad 248044, native template, request-local KV cache.

| Method/path | Authentication | Meaning |
|---|---|---|
| GET /healthz | none | Process liveness, 200 even during loading |
| GET /readyz | none | 200 only after hashes, GPU load, adapter attach and warmup; otherwise 503 |
| GET /health | none | Identical readiness to /readyz |
| GET /version | Bearer | Boot ID, PID, receipt ID, readiness, contract IDs and limits |
| POST /v1/generations | Bearer | Validate and return 202 + ID and Location |
| GET /v1/generations/{id} | Bearer | running/completed/failed; 404 unknown, expired, or prior boot |

Missing/malformed authorization: 401. Wrong token: 403. Not ready: 503. Busy or boot capacity exhausted: 429. Invalid schema/native input/token budget: 422. Request body >65536 bytes: 413. Same request ID with different payload: 409. Validation errors precede admission; no silent truncation. Under transport overload Uvicorn may return 503 (32 concurrent HTTP connections maximum).

Example body (a newly constructed synthetic input):

```json
{
  "request_id": "client-unique-uuid",
  "contract_id": "0703fba59425b087a4061a1fc9a370f2e6d7a192a2b2ce4b1ad2b1377f89a00b",
  "user": "{\"task\":\"CHECK_AXIS_DURATION\",\"required_s\":17,\"actual_by_axis\":{\"synthetic_x\":19,\"synthetic_y\":13}}",
  "max_new_tokens": 384
}
```

`contract_id` is the exact SHA256 of an approved service-owned system prompt, exposed by authenticated `/version`. The six sealed RC3 systems remain in `contracts/system_allowlist.json`; reviewed service overlays and the fixed memory planner contract are added separately. API supplies that system prompt. Additional fields are forbidden, including system/messages/model/adapter/generation overrides. `user` contains the original native JSON object, optionally preceded by its native `STATE:` prefix. Only one system/user pair per request. Reserved chat delimiters, duplicate JSON keys, nonfinite numbers, gold/expected/rationale/reference-answer metadata are rejected. No history or assistant turns are accepted. Untrusted text inside user content remains model input, not authorization to change system or execute tools.

Actual native input tokens + requested response reservation must be <=4096; response reservation is 1..384 (default 384). The whole input is tokenized without truncation before 202. The output text is never repaired, normalized, parsed into a corrected object, or automatically executed. A valid HTTP completion may contain invalid model JSON.

202 body: `{id,status,boot_id,duplicate}`. GET completed body includes `raw_text` (special tokens included), `text` (ordinary native tokenizer decode), generated token IDs, input/generated token counts, reservation, finish_reason (`eos`/`length`/`other`), elapsed_seconds, input/prompt-token/rendered/output hashes, model receipt ID and boot ID. `execution_mode` is `rc3` or `memory_planner`; `adapter_applied` records whether RC3 was enabled. Hashes use the sealed RC3 canonical JSON digest; raw output hash is SHA256 of UTF-8 raw_text. Each receipt is saved in `run/<boot_id>/model_receipt.json`.

`request_id` is required and scoped to the boot. Identical retries return the same job with 202, even while busy or after completion; different payload under the same retained key returns 409. No request is automatically regenerated. Results/idempotency keys remain available for 24h in the live process. At most 256 jobs are admitted per boot (bounded registry and disk generation artifacts); thereafter 429 until an operator-managed restart. Expired keys can be reused within remaining boot capacity. Restart loses API job lookup but retains local artifacts. Clients must record boot_id and must not blindly replay a job after restart.

Token is read from root-only `/root/.config/dorilab/inference.token`. No token in responses, access logs, arguments, or workspace backup. Input/output evidence is sensitive operational data; files are created with umask 077. The shared `/workspace` mount may impose its own permissions and must not be treated as a secret store.

API lock recovery: `restore_api.py` installs only missing exact pinned API closure entries using `--no-deps`, refuses changes to existing package versions, and records before/after/diff/pip-check. Called on every start; the GPU venv is reused. No reload, quantization, merge, training or base download is performed by serving code.

Optional project memory client: [project_memory/README_KO.md](../project_memory/README_KO.md) provides a local, opt-in evidence-gathering bridge inspired by LongMemEval-V2. It retrieves project/scope-isolated raw observations, state transitions and confirmed notes, then adds them to the existing SourceReview `observations` field. It uses the pinned SourceReview contract; the HTTP body, system allowlist, generation settings and request-local KV behavior above are unchanged. Other clients are not automatically augmented. No memory-management HTTP endpoints are exposed. The bridge records the memory snapshot, selected evidence IDs and source hashes separately from the native request, preserves the raw generation result, and never promotes model answers into confirmed memory. Project authorization for a future multi-user application must be supplied by its trusted authentication layer; the current CLI is for local operators.

Memory planner execution: `memory_controller_qwen_v1` is pinned in `project_memory/planner_contract.py`. Only that exact contract uses the resident base Qwen with the RC3 adapter temporarily disabled in a PEFT context manager. The single executor serializes planner and reviewer jobs; adapter state is checked before, during and after base generation. Both modes retain the same token limits, native template, EOS, authentication and request-local caches. Each planner call consumes one ordinary job admission. See [Qwen controller operation](../project_memory/CONTROLLER_KO.md).

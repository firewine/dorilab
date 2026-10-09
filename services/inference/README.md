# RunPod inference wrapper

This directory is a small authenticated API wrapper. It does not contain a generic
Qwen loader and it never installs or upgrades torch, transformers, PEFT, or model
weights. Deployment remains blocked until the approved RC3 loader/renderer and all
null release hashes are resolved from the actual RunPod release artifacts.

The service binds to `127.0.0.1:8080`, loads once, runs one generation at a time,
and exposes the API contract in the architecture document. `DORILAB_LOADER_MODULE`
must implement `load`, `count_tokens`, `generate`, and `receipt` using the verified
runtime and native template. Its receipt must prove eval mode, disabled gradients,
BF16/SDPA, greedy generation, disabled thinking, and the exact model/adapter/contract
hashes. Generation results must include raw output, raw output with special tokens,
token usage, and finish reason. The wrapper records its real API `boot_id`, PID,
log, and ready version receipt under `run/` and `logs/`.

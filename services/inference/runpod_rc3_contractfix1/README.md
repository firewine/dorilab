# RC3 SourceReview contract fix 1

This package preserves the sealed `v15_rc1` contract and adds one immutable service overlay.
The overlay makes `evidence_refs` mandatory for every action and requires an explicit empty list
when no supplied evidence supports the judgment. It does not repair model output, relax the local
validator, change weights, retrain, merge the adapter, or alter the native renderer.

`contract_conformance.py` sends three new synthetic packets through the authenticated loopback API.
It checks missing-input, sufficient-input, and contradiction paths against the exact SourceReview
shape. These checks establish contract behavior only; they are not engineering accuracy evidence.
`finalize_receipt.py` binds the passing conformance receipt to the current boot and to a stable model
release digest that excludes the per-process `boot_id`; it never reads or writes model input/output.

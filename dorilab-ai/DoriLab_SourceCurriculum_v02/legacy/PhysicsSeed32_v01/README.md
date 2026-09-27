# DoriLab Physics Seed32 v0.1

Start with [README_KO.md](README_KO.md).

This package contains 32 **synthetic, source-grounded engineering review SFT candidates** (16 counterfactual pairs) from two full-text-accessible sources, plus a 13-source bibliography/access/rights register. Human label review remains pending. It is not a raw physical test dataset or an independent benchmark.

Quick check, using Python standard-library utilities:

```bash
python -m tools.validate_pack
python -m unittest discover -v
python -m tools.show_cases --pair TH01-P07
```

Original source binaries are not included. Use `python -m tools.fetch_sources --ids TH-01 VB-X1` on a network-connected machine and preserve the generated acquisition log.

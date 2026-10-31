# Reproduce the IDRiD audit

Run from `D:\DR_Hackathon`:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements-audit.txt
.venv\Scripts\python.exe src\data\audit_idrid.py
```

The driver discovers files recursively under `data/raw/IDRiD`, reads them without writing into raw, and regenerates all audit tables, figures and reports. The final verification stage checks extracted files against the retained archives, traces MA component topology, reopens all output CSVs and decodes every plot. It runs automatically on subsequent full executions; it can also be rerun separately:

```powershell
.venv\Scripts\python.exe src\data\verify_idrid_audit.py
```

The first completed execution is recorded in `outputs/metrics/idrid_execution.log`; supplemental verification is in `idrid_verification.log`. Exact package versions are pinned in `requirements-audit.txt`; environment metadata is in `idrid_environment.json`. Python 3.11 was used. No model framework is required. Sampling uses seed 20261028. Empty result CSVs retain a header and mean no rows met that table's criterion.

Start with `IDRiD_DATASET_AUDIT.md`, then read `IDRiD_LIMITATIONS.md` and `IDRiD_SUITABILITY_MATRIX.md`. The main report distinguishes file observations, documentation facts, interpretations, unknowns and future hypotheses. A PASS is limited to the named check; REVIEW/UNKNOWN need attention. Contact sheets support human inspection and do not constitute medical adjudication.

Raw manifests cover every file under the IDRiD root, including archives, with path/size/mtime_ns/SHA-256 before and after the full audit. Access timestamps are deliberately excluded. Generated images are downscaled audit figures, not copied original fundus images or masks.

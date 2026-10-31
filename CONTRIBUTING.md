# Contributing

Thank you for helping. This is a research prototype for diabetic-retinopathy screening decision support, not a medical device.

## Workflow

1. **Branch** from `main`: `git checkout -b <short-topic>`.
2. **Commit** small, focused changes with clear messages.
3. **Run the tests** before opening a pull request (CPU mode is fine):
   `set RS_DEVICE=cpu` then `.venv\Scripts\python -m pytest -q backend tests`
   For frontend changes also run `cd frontend && npm run build`.
4. **Open a pull request** against `main` and describe what changed and how you checked it.
5. **Review:** at least one teammate reviews the pull request.
6. **Merge** after approval and green tests.

## Never commit

- **Data:** datasets, dataset label files, anything under `data/` (see [DATA.md](DATA.md)).
- **Weights:** model checkpoints or weight files (`*.pt`, `*.pth`, `*.ckpt`, `*.onnx`, `*.safetensors`; see [MODELS.md](MODELS.md)).
- **Patient or fundus images:** including screenshots of the app that show a fundus photograph, uploads and the local case store.
- **Secrets:** API tokens, `kaggle.json`, `.env` files, passwords or keys.

`.gitignore` covers these paths; check `git status` before every commit anyway.

## Results and claims

- Every number in the app or docs must come from a generated file (`results/registry.csv`, `results/KEY_NUMBERS.md`), not be typed by hand.
- Model or threshold changes follow a rule written in `docs/research/ARCHITECTURE_DECISION_LOG.md` **before** the result is known.
- Never describe the system as diagnosing, or as safe to route patients without clinician review.

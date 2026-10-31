# Run RetinaScreen on another laptop

This folder has everything the app needs: the code, the four model files in `models/checkpoints/`, and the web page already built (`frontend/dist/`). The one thing it doesn't include is the Python environment, which you install once with `setup.bat`.

Research prototype, not a medical device. It does not diagnose.

## What you need

- Windows 10 or 11, 64-bit, with at least 8 GB RAM and about 6 GB of free disk.
- **Python 3.11** (64-bit) from https://www.python.org/downloads/windows/. In the installer, tick **Add python.exe to PATH**.
- An internet connection for the setup only (about 3 GB of packages, mostly PyTorch).
- Node.js and Git are **not** needed to run the app.
- An NVIDIA GPU is optional. Without one, the app runs on the CPU automatically and is slower (a few seconds per image).

## Steps

1. Unzip `RetinaScreen_full_project.zip` to a short path, for example `C:\RetinaScreen` (very long paths can break the Python install).
2. Double-click **`setup.bat`**. It finds Python 3.11, creates `.venv`, installs the exact package versions (`requirements-lock.txt`) and runs the preflight check. Run it once.
3. Double-click **`start.bat`**. After 30 to 60 seconds, once the models have loaded, the browser opens http://localhost:8000.
4. To stop the app, close the window that `start.bat` opened.

Uploaded images and reviews are stored in `data/app/` inside this folder. Nothing is sent anywhere.

## Troubleshooting

| Problem | What to do |
|---|---|
| `setup.bat` says Python 3.11 not found | Install Python 3.11 as above, then open a new window and run `setup.bat` again. Other versions (3.12, 3.13) don't match the locked packages. |
| Package installation fails partway | Check the internet connection and run `setup.bat` again; it carries on with the existing `.venv`. |
| Windows SmartScreen blocks `setup.bat` or `start.bat` | Choose **More info → Run anyway**, or right-click the file → Properties → **Unblock**. |
| Preflight FAIL: Frontend build | The page stamp (`frontend/dist/build-info.json`) and `BUILD_COMMIT` must match. Don't edit either. If you changed the frontend code, install Node.js and run `cd frontend`, `npm install`, `npm run build`. |
| Port 8000 in use | Another program is using it. Close it, or run `start.bat -Restart` if it's an older RetinaScreen. |
| Laptop has an NVIDIA GPU but you want to use the CPU | Run `set RS_DEVICE=cpu` in a command window, then `start.bat` from the same window. Don't use `CUDA_VISIBLE_DEVICES=-1` (it crashes with some NVIDIA drivers). |
| PDF opens a print dialog | Microsoft Edge is needed for server-side PDF. Otherwise choose **Save as PDF** in the dialog. |

More details are in `README.md`.

## Not included

- **Datasets** (IDRiD, APTOS, MMRDR, DDR, DeepDRiD). They're needed only for retraining and evaluation, not for running the app. Their licences don't allow redistribution, so download them as described in `DATA.md`.
- **Per-image dataset labels and split files.** `docs/REPRODUCE.md` lists the scripts that regenerate them from the official downloads. Because of this, tests that need dataset files (for example `tests/test_e2e_http.py` and `tests/test_offline.py`) can't run until the datasets and splits are in place.

## Putting this folder into Git later

This copy has no Git history. Its version stamp is in `BUILD_COMMIT`. If you make it a Git repository and commit, the app compares the page with the new commit and rebuilds the page with Node.js (`cd frontend`, `npm install`, `npm run build`). After that, `BUILD_COMMIT` can be deleted. The model files in `models/` and the `.venv` folder are ignored by `.gitignore` and won't be committed.

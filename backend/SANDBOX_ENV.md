# XBots sandbox environment

Learner code runs in the dedicated `xbots-sandbox` Conda environment. The FastAPI
backend remains in its own environment.

## Install or rebuild

From the `backend` directory, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_sandbox_env.ps1
```

The script installs and verifies Python 3.11, Node.js 20, OpenJDK 21, GCC/G++,
NumPy, Pandas, SciPy, scikit-learn, Matplotlib, and CPU PyTorch. It creates
`.sandbox-env-ready` only after every check succeeds. Until that marker exists,
the application keeps using the previously available runtimes.

For a non-default Conda location, set `XBOTS_SANDBOX_ENV_PATH` to the absolute
environment directory before starting the backend.

## Portable definitions

- `environment.sandbox.yml` defines language runtimes and compilers.
- `sandbox-requirements.txt` defines Python libraries available to learner code.

Create the environment manually with:

```powershell
conda env create -f environment.sandbox.yml
```

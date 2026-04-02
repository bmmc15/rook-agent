# Rook Menu Bar

Native macOS shell for the existing Rook Python runtime.

## Run

From the repo root:

```bash
cd macos/RookMenuBar
swift run
```

The app looks for the repo root automatically and starts the backend with:

```bash
.venv/bin/python -m rook.macos.backend
```

If needed, force the repo path with:

```bash
ROOK_REPO_ROOT=/absolute/path/to/rook-agent swift run
```

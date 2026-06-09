# AI-Powered Minutes of Meeting (MoM) Assistant

An open-source FastAPI + frontend project that records or accepts uploaded audio of meetings, transcribes them, and generates structured Minutes of Meeting (summary, key points, decisions, and action items) using an AI engine.

## Features

- Browser recording (client-side) and server-side recording support
- Upload audio files (WAV, MP3, M4A) for transcription
- Background processing of audio to generate transcript and structured summary
- Downloadable PDF of Minutes of Meeting
- Simple web frontend for viewing meetings, transcripts and summaries

## Repository Structure

- `backend/` — FastAPI application and server-side code
- `frontend/` — Static frontend (HTML/CSS/JS)
- `data/` — Local storage for audio files, settings and SQLite DB (ignored from Git)
- `requirements.txt` — Python dependencies
- `run.bat` / `run.sh` — Convenience scripts to start the app

## Prerequisites

- Python 3.10+ (recommended)
- `pip` installed
- Optional: system audio device and `sounddevice` Python package for host recording

## Quick Start (Local)

1. Create and activate a virtual environment:

```bash
python -m venv .venv
# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
# Windows (cmd)
.venv\Scripts\activate.bat
# macOS / Linux
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Configure your AI key (preferred) using an environment variable:

```bash
# Linux / macOS
export GEMINI_API_KEY="your_api_key_here"

# Windows (PowerShell)
$env:GEMINI_API_KEY = "your_api_key_here"
```

Alternatively, you can set `data/settings.json` locally with the `gemini_api_key` field, but DO NOT commit that file to git. This project ships a `.gitignore` which excludes `data/settings.json`.

4. Run the backend (development):

```bash
# From project root
.venv\Scripts\uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
# or use run.bat on Windows
```

5. Open the frontend in your browser at:

```
http://127.0.0.1:8000/
```

## Running Tests

```bash
pytest -q
```

## Configuration

- `GEMINI_API_KEY`: Set as an environment variable or saved to `data/settings.json` (local only). The server uses this key when calling the AI engine (see `backend/ai_engine.py`).
- `ollama_model`: Model name saved in settings.

## Troubleshooting

- No audio when playing recorded files in the browser:
  - Check the browser tab is not muted.
  - Verify the system volume for your browser in the OS volume mixer.
  - Confirm the audio output device (headphones / speakers) is correct.
  - Verify the raw audio file exists at `data/audio/` and is playable locally.

- Host recording not available:
  - Ensure `sounddevice` and its system dependencies are installed.
  - If `sounddevice` is not available, server recording controls are disabled in the UI.

## Security & Secrets

- The repository must never contain API keys or other secrets. Use environment variables for production keys.
- If an API key has been accidentally committed and pushed, rotate/revoke it immediately. To fully remove it from repository history, use `git filter-repo` or BFG and force-push (coordinate with collaborators).

## Contributing

Contributions are welcome. Create an issue first to discuss larger changes, or open a pull request for smaller fixes and improvements.

## License

This project is provided under the repository's chosen license (check the GitHub repo for details). If you want, I can add a `LICENSE` file.

---

If you'd like, I can also:

- Add example `.env` and `.env.example` files (for local development).
- Add a CI workflow for tests and linting.
- Create a short `CONTRIBUTING.md` with guidelines.

File created: README.md

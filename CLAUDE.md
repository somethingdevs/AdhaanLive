# CLAUDE.md — AdhaanLive

## What this is
AdhaanLive detects the live Adhaan (call to prayer) from a mosque's public
livestream and plays it in users' homes around prayer time. Python backend
(FastAPI) + vanilla JS frontend. Currently single-mosque.

## How to run
- Python >= 3.9. Requires `ffmpeg` on PATH.
- Entry point: `python main.py`. This starts, as daemon threads: the FastAPI
  server (port 8000), the stream refresher, the prayer scheduler, and the
  daily prayer-time refresh.
- Frontend is served at http://localhost:8000/ (static files from `frontend/`).
- Configuration lives in `config.yml` (city/country/method for prayer times,
  plus a `livestream` section).
- Runtime dependencies are in `requirements.txt`; development/test dependencies
  are in `requirements-dev.txt`.

## Architecture / module map
- `main.py` — bootstraps and orchestrates all threads; handles startup/shutdown.
- `core/`
  - `runtime_state.py` — `RuntimeState` singleton (`state`), lock-guarded single
    source of truth. Core modules WRITE here; the API layer READS here. Do not
    reintroduce scattered global flags.
  - `detector.py` — pipes stream audio via ffmpeg; RMS-loudness detection of
    adhaan start/end; records WAV snippets to `assets/audio_logs/`.
  - `prayer_scheduler.py` — schedules a wake window before each prayer, then
    starts/stops detection.
  - `stream_refresher.py` — `StreamRefresher`; periodically re-scrapes the
    `.m3u8` URL and defers refresh while an adhaan is active.
- `utils/`
  - `livestream.py` — Selenium-wire headless Chrome scraper that sniffs the
    `.m3u8` URL from click2stream/angelcam.
  - `prayer_api.py` — Aladhan API client.
  - `config_loader.py`, `logger.py`, `adhaan_logger.py` (CSV event log),
    `audio_logger.py` (WAV writer).
- `api/`
  - `app.py` — FastAPI app; mounts routes and the static frontend.
  - `routes/` — `health`, `status`, `schedule`, `control` (start/stop
    detection), `client_logs`.
- `frontend/` — `index.html`, `app.js` (polls `/status` every 2s and plays the
  stream in a browser `<audio>` element; this is the ONLY place audio plays),
  `styles.css`.
- `assets/` — gitignored runtime output: `prayer_times.json`, logs,
  `audio_logs/`, `adhaan_log.csv`.

## Conventions
- Python, 4-space indentation, max line length 100 (see `.pylintrc`).
- Log via the stdlib `logging` module with bracketed tags, e.g. `[DETECT]`,
  `[SCHED]`, `[STREAM]`. Keep that style.
- All runtime state transitions go through `RuntimeState` methods — never mutate
  flags directly from other modules.
- Background work uses daemon threads with stop-events and `join` timeouts.

## Testing
- Install test dependencies with `pip install -r requirements-dev.txt`.
- Run backend tests with `python -m pytest -q`.
- Run browser playback-policy tests with
  `node --test tests/playback_policy.test.js`.
- Run the controlled local smoke test with `python scripts/smoke_test.py`.
  It imports the entry point and briefly serves the API/frontend locally; it
  does not contact the mosque stream or wait for a real Adhaan.
- `tests/sound_test.py` is a manual, live-stream experiment, not an automated
  test. Keep live validation separate from the deterministic suite.

## Current priorities
1. Keep deterministic coverage around runtime state, prayer selection and
   windows, API responses, and client-only playback decisions.
2. Validate the full pipeline against the real configured livestream during a
   prayer window, measuring false positives, detection delay, and browser
   playback reliability.
3. Add authentication before exposing administrative control routes publicly.

## IMPORTANT — playback is client-only (settled)
Audio plays ONLY in the browser, via the `<audio>` element in
`frontend/app.js`. Server-side playback has been removed and must NOT be
reintroduced: no `ffplay`, no `core/playback.py`, no `playback_active` runtime
flag, no `/control/playback/stop` route. The server's job is to detect the
adhaan and publish that state; every client decides for itself whether to play.
The "Silence (this device)" button is purely client-side — it sets a
`dismissedThisAdhaan` flag that suppresses replay until `adhaan_active` goes
false.

## IMPORTANT — do not change without explicit direction
The audio-detection approach (RMS loudness in `core/detector.py`) is under
active strategic review. Do NOT refactor, replace, or "improve" the detection
logic unless explicitly asked to. Small bug fixes within the current design are
fine; architectural changes are not.

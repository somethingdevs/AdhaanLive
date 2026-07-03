# CLAUDE.md — AdhaanLive

## What this is
AdhaanLive detects the live Adhaan (call to prayer) from a mosque's public
livestream and plays it in users' homes around prayer time. Python backend
(FastAPI) + vanilla JS frontend. Currently single-mosque.

## How to run
- Python >= 3.9. Requires `ffmpeg` and `ffplay` on PATH.
- Entry point: `python main.py`. This starts, as daemon threads: the FastAPI
  server (port 8000), the stream refresher, the prayer scheduler, and the
  daily prayer-time refresh.
- Frontend is served at http://localhost:8000/ (static files from `frontend/`).
- Configuration lives in `config.yml` (city/country/method for prayer times,
  plus a `livestream` section).
- Note: there is currently no `requirements.txt` — only `pyproject.toml`.

## Architecture / module map
- `main.py` — bootstraps and orchestrates all threads; handles startup/shutdown.
- `core/`
  - `runtime_state.py` — `RuntimeState` singleton (`state`), lock-guarded single
    source of truth. Core modules WRITE here; the API layer READS here. Do not
    reintroduce scattered global flags.
  - `detector.py` — pipes stream audio via ffmpeg; RMS-loudness detection of
    adhaan start/end; records WAV snippets to `assets/audio_logs/`.
  - `playback.py` — `PlaybackManager` (`PLAYBACK` singleton); server-side
    `ffplay` playback with retry logic.
  - `prayer_scheduler.py` — schedules a wake window before each prayer, then
    starts/stops detection.
  - `stream_refresher.py` — `StreamRefresher`; periodically re-scrapes the
    `.m3u8` URL and defers refresh while adhaan/playback is active.
- `utils/`
  - `livestream.py` — Selenium-wire headless Chrome scraper that sniffs the
    `.m3u8` URL from click2stream/angelcam.
  - `prayer_api.py` — Aladhan API client.
  - `config_loader.py`, `logger.py`, `adhaan_logger.py` (CSV event log),
    `audio_logger.py` (WAV writer).
- `api/`
  - `app.py` — FastAPI app; mounts routes and the static frontend.
  - `routes/` — `health`, `status`, `schedule`, `control` (start/stop
    detection, stop playback), `client_logs`.
- `frontend/` — `index.html`, `app.js` (polls `/status` every 2s and plays the
  stream in a browser `<audio>` element), `styles.css`.
- `assets/` — gitignored runtime output: `prayer_times.json`, logs,
  `audio_logs/`, `adhaan_log.csv`.

## Conventions
- Python, 4-space indentation, max line length 100 (see `.pylintrc`).
- Log via the stdlib `logging` module with bracketed tags, e.g. `[DETECT]`,
  `[SCHED]`, `[PLAY]`, `[STREAM]`. Keep that style.
- All runtime state transitions go through `RuntimeState` methods — never mutate
  flags directly from other modules.
- Background work uses daemon threads with stop-events and `join` timeouts.

## Punch list (safe to work on)
1. **Bug:** `api/routes/control.py` reads `state.stream_url`, which
   `RuntimeState` never defines, so `/control/detection/start` returns a 500.
   Source the URL from the `StreamRefresher` instead.
2. `config.yml`'s `livestream.url` is ignored; `utils/livestream.py` hardcodes
   `PAGE_URL`. Make the page URL config-driven via `config_loader`.
3. No `requirements.txt` exists — generate one from `pyproject.toml`.
4. `README.md` is stale: it references `adhaan_streamer.py`, `util.py`, and
   `environment.yml`, none of which exist. Rewrite it to match the current
   structure and run instructions.
5. `prayer_refresh_loop` in `main.py` writes `assets/prayer_times.json` without
   guaranteeing `assets/` exists (it currently works only as a side effect of
   logging setup). Make it robust.

## IMPORTANT — do not change without explicit direction
The audio-detection approach (RMS loudness in `core/detector.py`) and the
playback architecture (server-side `ffplay` in `core/playback.py` vs. the
browser `<audio>` element in `frontend/app.js`) are under active strategic
review. Do NOT refactor, replace, or "improve" the detection logic or the
playback routing unless explicitly asked to. Small bug fixes within the current
design are fine; architectural changes are not.

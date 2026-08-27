# AdhaanLive

AdhaanLive detects the live Adhaan (call to prayer) from a mosque's public livestream and plays it automatically at prayer time. It scrapes the livestream's `.m3u8` URL, listens to the stream's audio for loudness patterns matching an Adhaan, and — when one is detected — signals the browser frontend, which plays the stream in an `<audio>` element. Audio plays only in the browser; the server never plays audio. It currently supports a single, configured mosque.

## Requirements

- Python >= 3.9
- `ffmpeg` available on your system `PATH` (used to decode the stream for audio detection)
- Google Chrome installed (the livestream URL scraper drives headless Chrome via Selenium)

## Setup

```bash
pip install -r requirements.txt
```

Optional local-audio extras (`sounddevice`, `pyaudio`, `soundfile`) are listed as commented-out lines in `requirements.txt` — uncomment and install them if you need local audio device access.

For development and automated tests:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
node --test tests/playback_policy.test.js
python scripts/smoke_test.py
```

The smoke test checks imports, the local health endpoint, and static frontend serving. It does not connect to the mosque livestream or wait for a real Adhaan.

Configure your mosque and location in `config.yml`:

```yaml
settings:
  city: "Dallas"
  country: "US"
  method: 2  # Calculation method for prayer times (2-ISNA)
  school: 1  # 0 - Shafi, 1 - Hanafi

livestream:
  url: "https://iaccplano.click2stream.com/"  # Mosque click2stream link
  auto_unmute: true
  browser: "chrome"
  wait_time: 3
```

## Running

```bash
python main.py
```

This starts, as daemon threads:
- the FastAPI server on port 8000
- the stream refresher (periodically re-scrapes the `.m3u8` stream URL)
- the prayer scheduler (wakes before each prayer and starts/stops detection)
- a daily prayer-time refresh loop (writes `assets/prayer_times.json`)

The frontend is served at `http://localhost:8000/`.

## Project structure

- `main.py` — bootstraps and orchestrates all threads; handles startup/shutdown.
- `core/`
  - `runtime_state.py` — `RuntimeState` singleton (`state`), the single source of truth for detection/adhaan status.
  - `detector.py` — pipes stream audio through ffmpeg and uses RMS-loudness detection to find Adhaan start/end; records WAV snippets to `assets/audio_logs/`.
  - `prayer_scheduler.py` — schedules a wake window before each prayer, then starts/stops detection around it.
  - `stream_refresher.py` — `StreamRefresher`; periodically re-scrapes the `.m3u8` URL and defers refresh while an Adhaan is active.
- `utils/`
  - `livestream.py` — Selenium-wire headless Chrome scraper that sniffs the `.m3u8` URL from the configured livestream page.
  - `prayer_api.py` — Aladhan API client for prayer times.
  - `config_loader.py` — loads `config.yml`.
  - `logger.py`, `adhaan_logger.py` — logging setup and CSV event log.
  - `audio_logger.py` — WAV snippet writer.
- `api/`
  - `app.py` — FastAPI app; mounts routes and serves the static frontend.
  - `routes/`
    - `health.py` — `GET /health`
    - `status.py` — `GET /status` (detection/adhaan state, current stream URL)
    - `schedule.py` — `GET /schedule` (today's prayer times from `assets/prayer_times.json`)
    - `control.py` — `POST /control/detection/start`, `POST /control/detection/stop`
    - `client_logs.py` — `POST /client-log` (frontend event logging)
- `frontend/` — `index.html`, `app.js` (polls `/status` and `/schedule`, plays the stream in a browser `<audio>` element; "Silence (this device)" dismisses audio locally for the current Adhaan), `styles.css`.
- `assets/` — runtime output (gitignored): `prayer_times.json`, logs, `audio_logs/`, `adhaan_log.csv`.

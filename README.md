# AdhaanLive

AdhaanLive detects the live Adhaan (call to prayer) from a mosque's public livestream and plays it at prayer time when browser autoplay permissions allow. It resolves the livestream's `.m3u8` URL over HTTP, listens for sustained loud audio, and — when detected — signals the browser frontend, which plays the stream in an `<audio>` element. Audio plays only in the browser; the server never plays audio. It currently supports a single, configured mosque and is intended for personal testing. Loudness detection is not an Adhaan classifier.

## Requirements

- Python >= 3.9
- `ffmpeg` available on your system `PATH` (used to decode the stream for audio detection)

No Chrome, Chromium, Selenium, or Selenium Wire is required on the server.

## Setup

```bash
pip install -r requirements.txt
```

Optional local-audio extras (`sounddevice`, `pyaudio`, `soundfile`) are listed as commented-out lines in `requirements.txt` — uncomment and install them if you need local audio device access.

For development and automated tests:

```bash
pip install -r requirements-dev.txt
python -m pytest -q
node --test tests/playback_policy.test.js tests/schedule_time.test.js
python scripts/smoke_test.py
```

The smoke test checks imports, the local health endpoint, and static frontend serving. It does not connect to the mosque livestream or wait for a real Adhaan.

Configure your mosque and location in `config.yml`:

```yaml
settings:
  city: "Dallas"
  country: "US"
  timezone: "America/Chicago"  # IANA timezone; handles CST/CDT automatically
  method: 2  # Calculation method for prayer times (2-ISNA)
  school: 1  # 0 - Shafi, 1 - Hanafi

livestream:
  url: "https://iaccplano.click2stream.com/"  # Mosque click2stream link
```

All five prayer settings are validated at startup and sent to the Aladhan
client where applicable. Prayer timestamps, refreshes, scheduler comparisons,
API responses, and browser countdowns use the configured mosque timezone. This
keeps Dallas scheduling correct when the server or browser runs in another
timezone such as Atlanta or UTC.

Stream discovery uses ordinary HTTPS requests: the public Click2Stream page
provides an Angelcam player ID, and its iframe HTML provides a signed HLS URL.
Each refresh resolves the source again rather than caching a signed URL forever.
This depends on the provider's current public HTML, not a versioned API; markup
changes or an offline camera can prevent discovery. HTTP requests use timeouts
and bounded retries. No browser fallback is used.

`livestream.url` also accepts an Angelcam iframe URL or a direct HTTP(S) `.m3u8`
URL. Direct URLs are used as supplied; an expiring direct URL cannot be renewed
without its source page or another renewal mechanism. Prefer the public page
for the configured masjid. The former `browser`, `auto_unmute`, and `wait_time`
settings are no longer used.

Docker packaging and a private cloud trial are next; deployment files are not
included yet. Keep the API private during personal testing: administrative
routes are not authenticated. See `CLAUDE.md` for the ordered roadmap.

## Running

```bash
python main.py
```

This starts, as daemon threads:
- the FastAPI server on port 8000
- the stream refresher (periodically resolves a fresh `.m3u8` stream URL over HTTP)
- the prayer scheduler (wakes before each prayer and starts/stops detection)
- a daily prayer-time refresh loop (writes `assets/prayer_times.json`)

The frontend is served at `http://localhost:8000/`.

## Project structure

- `main.py` — bootstraps and orchestrates all threads; handles startup/shutdown.
- `core/`
  - `runtime_state.py` — `RuntimeState` singleton (`state`), the single source of truth for detection/adhaan status.
  - `detector.py` — pipes stream audio through ffmpeg and uses RMS-loudness detection to find Adhaan start/end; records WAV snippets to `assets/audio_logs/`.
  - `prayer_scheduler.py` — schedules a wake window before each prayer, then starts/stops detection around it.
  - `stream_refresher.py` — `StreamRefresher`; periodically resolves the `.m3u8` URL and defers refresh while an Adhaan is active.
- `utils/`
  - `livestream.py` — browser-free HTTP resolver for public Click2Stream/Angelcam pages or direct HLS URLs.
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
- `frontend/` — `index.html`, `app.js` (polls `/status` and `/schedule`, displays the schedule in the configured mosque timezone, and plays the stream in a browser `<audio>` element), pure playback/schedule policy modules, and `styles.css`. "Silence (this device)" dismisses audio locally for the current Adhaan.
- `assets/` — runtime output (gitignored): `prayer_times.json`, logs, `audio_logs/`, `adhaan_log.csv`.

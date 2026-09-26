# CLAUDE.md — AdhaanLive

## What this is
AdhaanLive detects the live Adhaan (call to prayer) from a mosque's public
livestream and plays it in users' homes around prayer time. Python backend
(FastAPI) + vanilla JS frontend. Currently single-mosque.

## How to run
- Python >= 3.9. Requires `ffmpeg` on PATH.
- No browser, Selenium, or Selenium Wire is required on the server.
- Entry point: `python main.py`. This starts, as daemon threads: the FastAPI
  server (port 8000), the stream refresher, the prayer scheduler, and the
  daily prayer-time refresh.
- Frontend is served at http://localhost:8000/ (static files from `frontend/`).
- Configuration lives in `config.yml` (city/country/IANA timezone/method/school
  for prayer times, plus a `livestream` section). These prayer settings are
  validated centrally; do not replace them with server-local time assumptions.
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
  - `stream_refresher.py` — `StreamRefresher`; periodically re-resolves the
    `.m3u8` URL and defers refresh while an adhaan is active.
- `utils/`
  - `livestream.py` — HTTP-only resolver: public Click2Stream HTML supplies the
    Angelcam player ID; iframe HTML supplies a fresh signed `.m3u8` URL.
    Also accepts an Angelcam iframe URL or direct HTTP(S) HLS URL. Direct signed
    URLs are not renewable by themselves. Keep browser automation out of this
    path. Provider markup may change; fail clearly rather than guessing a URL.
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
  `node --test tests/playback_policy.test.js tests/schedule_time.test.js`.
- Run the controlled local smoke test with `python scripts/smoke_test.py`.
  It imports the entry point and briefly serves the API/frontend locally; it
  does not contact the mosque stream or wait for a real Adhaan.
- `tests/sound_test.py` is a manual, live-stream experiment, not an automated
  test. Keep live validation separate from the deterministic suite.

## Scope and ordered roadmap (user direction, 2026-09-25)
This is currently a personal, single-masjid experiment. Public rollout and
multi-user requirements are future work. Prioritize making detection run in the
cloud without browser automation; do not let ML training or dashboard polish
block that work. The following order records the next steps, not an instruction
to implement every item in a single task.

1. **Remove Selenium and browser automation from stream discovery.** Implemented
   with HTTP-only public-page/player resolution. Preserve periodic signed-URL
   renewal and existing detector/refresher interfaces. Local validation on
   2026-09-25 resolved the configured feed, fetched its HLS playlist, and decoded
   three seconds of audio with FFmpeg while Selenium imports were blocked.
   The September 25 evening run completed Asr, Maghrib, and Isha detection and
   recording cycles, with 29 successful first-attempt HTTP URL resolutions and
   no logged warnings or errors. On September 26, the user listened to all three
   recordings and confirmed they contain the Adhaan, with a short silent tail.
   Browser playback during those prayers was not verified. Retain offline
   resolver tests; extended operation and access from the eventual cloud host
   still need validation.
2. **Package with Docker and run a private cloud trial.** Include Python and
   FFmpeg, configuration and persistent runtime volumes, and a restart policy.
   Use a single application process initially. Keep the unauthenticated API
   private; Docker does not itself provide access control. No Kubernetes yet.
3. **Make the early scheduling buffer useful.** Recommended change, not yet
   implemented: actually start listening at prayer time minus a configurable
   buffer (initially 10 minutes), instead of waking and waiting until prayer
   time. On restart, resume an eligible uncompleted window. Define completed
   cycles and overlapping-window behavior, and check actual masjid Adhaan times.
   Earlier listening also increases exposure to non-Adhaan audio under RMS.
4. **Choose the unattended home listening client.** The user wants one-time
   opt-in, not repeated clicks. Persist preference separately from actual browser
   playback permission; never treat localStorage as proof of permission. Keep
   the website useful as a schedule/status dashboard. A dedicated home receiver
   connected to a speaker is a candidate, not an implemented or finalized design.
5. **Strengthen recovery before depending on unattended operation.** Add bounded
   stream reads, detector reconnection, reliable worker/process shutdown,
   schedule freshness checks, meaningful health reporting, and outage visibility.
6. **Prepare for external users before any public exposure.** Authenticate admin
   controls, separate household controls, configure HTTPS, bound/rate-limit client
   logging, add recording retention, and automate checks/deployment. This becomes
   a prerequisite immediately if a deployment is publicly reachable, regardless
   of its position in this roadmap.
7. **Evaluate detection accuracy; defer ML.** RMS is an intentional provisional
   solution. The user lacks training resources and has deferred a lightweight
   classifier. Existing recordings can support later measurement without model
   training. Do not redesign detection or require an ML dataset for cloud trials.
8. **Expand only when justified.** Multi-masjid state/workers, shared persistence,
   and Kubernetes are future options after a dependable single-masjid deployment.

Maintain deterministic tests while implementing each step. Keep live stream
checks separate and distinguish successful audio decoding from correct Adhaan
recognition or reliable playback in a household.

## IMPORTANT — playback stays on listening clients
Currently audio plays ONLY in the browser, via the `<audio>` element in
`frontend/app.js`. A future home receiver would be another listening client,
not audio output on the cloud detection server. Its implementation is deferred.
Server-side playback has been removed and must NOT be
reintroduced: no `ffplay`, no `core/playback.py`, no `playback_active` runtime
flag, no `/control/playback/stop` route. The server's job is to detect the
adhaan and publish that state; every client decides for itself whether to play.
The "Silence (this device)" button is purely client-side — it sets a
`dismissedThisAdhaan` flag that suppresses replay until `adhaan_active` goes
false.

## IMPORTANT — do not change without explicit direction
The audio-detection approach (RMS loudness in `core/detector.py`) is deliberately
provisional; ML-based recognition is deferred. Do NOT refactor, replace, or "improve" the detection
logic unless explicitly asked to. Small bug fixes within the current design are
fine; architectural changes are not.

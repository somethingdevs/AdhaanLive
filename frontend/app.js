/*********************************
 * CONFIG
 *********************************/
const API_BASE = "";
const STATUS_POLL_MS = 2000;
const SCHEDULE_POLL_MS = 5 * 60 * 1000;

/*********************************
 * CLIENT LOGGING
 *********************************/
const CLIENT_ID = crypto.randomUUID();

async function clientLog(event, data = {}) {
  const payload = {
    ts: new Date().toISOString(),
    client_id: CLIENT_ID,
    event,
    data,
    userAgent: navigator.userAgent,
    visibility: document.visibilityState,
  };

  console.log("[CLIENT]", payload);

  try {
    await fetch("/client-log", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    });
  } catch (_) {
    // logging must never break UX
  }
}

/*********************************
 * DOM REFERENCES
 *********************************/
const clockEl = document.getElementById("current-time");
const statusBar = document.getElementById("status-bar");
const statusText = document.getElementById("status-text");
const nextPrayerNameEl = document.getElementById("next-prayer-name");
const nextPrayerCountdownEl = document.getElementById("next-prayer-countdown");
const prayerGrid = document.getElementById("prayer-grid");

const audioHint = document.getElementById("audio-hint");
const player = document.getElementById("adhaan-player");
const muteToggle = document.getElementById("mute-toggle");
const themeToggle = document.getElementById("theme-toggle");

/*********************************
 * STATE
 *********************************/
let audioUnlocked = localStorage.getItem("audioUnlocked") === "true";
let muted = false;
let prayerSchedule = {};
let currentPrayer = null;
let nextPrayer = null;
let nextPrayerTime = null;

let isPlaying = false;
let lastStatusSignature = "";

// Set when the user silences audio on this device for the current adhaan.
// Suppresses replay until the adhaan ends, then resets.
let dismissedThisAdhaan = false;

/*********************************
 * LIFECYCLE LOGGING
 *********************************/
document.addEventListener("DOMContentLoaded", () => {
  clientLog("page_loaded");
});

window.addEventListener("beforeunload", () => {
  clientLog("page_unload");
});

window.addEventListener("focus", () => {
  clientLog("window_focus");
});

window.addEventListener("blur", () => {
  clientLog("window_blur");
});

document.addEventListener("visibilitychange", () => {
  clientLog("visibility_change", {
    state: document.visibilityState,
  });
});

/*********************************
 * CLOCK
 *********************************/
function pad(n) {
  return n.toString().padStart(2, "0");
}

function updateClock() {
  const now = new Date();
  clockEl.textContent =
    `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}
setInterval(updateClock, 1000);
updateClock();

/*********************************
 * AUDIO UNLOCK
 *********************************/
if (!audioUnlocked) {
  audioHint.addEventListener("click", unlockAudio);
} else {
  audioHint.style.display = "none";
}

function unlockAudio() {
  clientLog("audio_unlock_attempt");
  player.play().catch(() => {});
  audioUnlocked = true;
  localStorage.setItem("audioUnlocked", "true");
  audioHint.style.display = "none";
  clientLog("audio_unlocked");
}

/*********************************
 * AUDIO EVENT LOGGING (GUARDED)
 *********************************/
player.addEventListener("play", () => {
  isPlaying = true;
  clientLog("audio_play");
});

player.addEventListener("pause", () => {
  if (!isPlaying) return;
  clientLog("audio_pause", { currentTime: Math.floor(player.currentTime) });
});

player.addEventListener("ended", () => {
  isPlaying = false;
  clientLog("audio_ended");
});

player.addEventListener("error", () => {
  if (!player.src) return; // suppress empty-src noise
  clientLog("audio_error", {
    code: player.error?.code,
    message: player.error?.message,
  });
});

/*********************************
 * AUDIO CONTROL (STATE SAFE)
 *********************************/
async function playAdhaan(src) {
  if (isPlaying && player.src === src) return;

  clientLog("audio_play_requested", { src });

  try {
    player.src = src;
    await player.play();
    clientLog("audio_play_success");
  } catch (err) {
    clientLog("audio_play_failed", { error: err.message });
  }
}

function stopAdhaan() {
  if (!isPlaying) return;

  clientLog("audio_stop_requested");
  player.pause();
  player.removeAttribute("src");
  player.load();
  isPlaying = false;
}

/*********************************
 * MUTE
 *********************************/
muteToggle.onclick = () => {
  muted = !muted;
  player.muted = muted;
  muteToggle.textContent = muted ? "🔇" : "🔊";
  clientLog("mute_toggled", { muted });
};

/*********************************
 * THEME
 *********************************/
themeToggle.onclick = () => {
  document.body.classList.toggle("light");
  const theme = document.body.classList.contains("light") ? "light" : "dark";
  localStorage.setItem("theme", theme);
  clientLog("theme_changed", { theme });
};

if (localStorage.getItem("theme") === "light") {
  document.body.classList.add("light");
}

/*********************************
 * FETCH HELPERS
 *********************************/
async function fetchJSON(path) {
  const res = await fetch(API_BASE + path);
  return res.json();
}

/*********************************
 * STATUS POLLING (TRANSITION-BASED)
 *********************************/
async function pollStatus() {
  const s = await fetchJSON("/status");

  const signature =
    `${s.adhaan_active}-${s.detection_active}`;

  if (signature !== lastStatusSignature) {
    clientLog("status_changed", s);
    lastStatusSignature = signature;
  }

  statusBar.className = "status-bar " + (
    s.adhaan_active ? "adhaan" :
    s.detection_active ? "listening" : "idle"
  );

  statusText.textContent = s.adhaan_active
    ? "🔴 Adhaan in Progress"
    : s.detection_active
    ? "🟡 Listening for Adhaan"
    : "Idle";

  // A new adhaan clears any prior dismissal.
  if (!s.adhaan_active) {
    dismissedThisAdhaan = false;
  }

  if (
    s.adhaan_active &&
    s.stream_url &&
    audioUnlocked &&
    !muted &&
    !dismissedThisAdhaan
  ) {
    playAdhaan(s.stream_url);
  } else {
    stopAdhaan();
  }
}
setInterval(pollStatus, STATUS_POLL_MS);
pollStatus();

/*********************************
 * SCHEDULE
 *********************************/
async function loadSchedule() {
  prayerSchedule = await fetchJSON("/schedule");
  computePrayerState();
  renderGrid();
}
setInterval(loadSchedule, SCHEDULE_POLL_MS);
loadSchedule();

function computePrayerState() {
  const now = new Date();
  const entries = Object.entries(prayerSchedule)
    .map(([n, t]) => {
      const [h, m] = t.split(":");
      const d = new Date();
      d.setHours(h, m, 0, 0);
      return { name: n, time: d };
    })
    .sort((a, b) => a.time - b.time);

  for (let i = 0; i < entries.length; i++) {
    if (now < entries[i].time) {
      nextPrayer = entries[i].name;
      nextPrayerTime = entries[i].time;
      currentPrayer = entries[i - 1]?.name ?? null;
      break;
    }
  }

  if (!nextPrayer && prayerSchedule.Fajr) {
    const [h, m] = prayerSchedule.Fajr.split(":");
    const d = new Date();
    d.setDate(d.getDate() + 1);
    d.setHours(h, m, 0, 0);
    nextPrayer = "Fajr";
    nextPrayerTime = d;
    currentPrayer = "Isha";
  }

  nextPrayerNameEl.textContent = nextPrayer ?? "—";
}

setInterval(() => {
  if (!nextPrayerTime) return;
  const diff = Math.max(
    0,
    Math.floor((nextPrayerTime - new Date()) / 1000)
  );
  nextPrayerCountdownEl.textContent =
    `${pad(Math.floor(diff / 3600))}:${pad(Math.floor(diff / 60) % 60)}:${pad(diff % 60)}`;
}, 1000);

function renderGrid() {
  prayerGrid.innerHTML = "";
  for (const [name, time] of Object.entries(prayerSchedule)) {
    const d = document.createElement("div");
    d.className = "prayer";
    if (name === currentPrayer) d.classList.add("current");
    if (name === nextPrayer) d.classList.add("upcoming");
    d.innerHTML = `<div>${name}</div><div>${time.slice(0, 5)}</div>`;
    prayerGrid.appendChild(d);
  }
}

/*********************************
 * HEARTBEAT
 *********************************/
setInterval(() => {
  clientLog("heartbeat");
}, 30_000);

/*********************************
 * ADMIN
 *********************************/
function post(path) {
  return fetch(API_BASE + path, { method: "POST" });
}
window.startDetection = () => post("/control/detection/start");
window.stopDetection = () => post("/control/detection/stop");

// Client-only: silence audio on THIS device for the current adhaan.
// Playback is browser-side, so nothing is sent to the server.
window.stopPlayback = () => {
  dismissedThisAdhaan = true;
  clientLog("playback_dismissed");
  stopAdhaan();
};

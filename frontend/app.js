const API_BASE = "http://localhost:8000";
const STATUS_POLL_MS = 2000;
const SCHEDULE_POLL_MS = 5 * 60 * 1000;

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

let audioUnlocked = localStorage.getItem("audioUnlocked") === "true";
let muted = false;
let prayerSchedule = {};
let currentPrayer = null;
let nextPrayer = null;
let nextPrayerTime = null;

function pad(n) { return n.toString().padStart(2, "0"); }

function updateClock() {
  const now = new Date();
  clockEl.textContent = `${pad(now.getHours())}:${pad(now.getMinutes())}:${pad(now.getSeconds())}`;
}
setInterval(updateClock, 1000);
updateClock();

/* AUDIO UNLOCK */
if (!audioUnlocked) {
  audioHint.addEventListener("click", unlockAudio);
} else {
  audioHint.style.display = "none";
}

function unlockAudio() {
  player.play().catch(() => {});
  audioUnlocked = true;
  localStorage.setItem("audioUnlocked", "true");
  audioHint.style.display = "none";
}

/* MUTE */
muteToggle.onclick = () => {
  muted = !muted;
  player.muted = muted;
  muteToggle.textContent = muted ? "🔇" : "🔊";
};

/* THEME */
themeToggle.onclick = () => {
  document.body.classList.toggle("light");
  localStorage.setItem("theme", document.body.classList.contains("light") ? "light" : "dark");
};

if (localStorage.getItem("theme") === "light") {
  document.body.classList.add("light");
}

/* FETCH */
async function fetchJSON(path) {
  const res = await fetch(API_BASE + path);
  return res.json();
}

/* STATUS */
async function pollStatus() {
  const s = await fetchJSON("/status");

  statusBar.className = "status-bar " + (
    s.adhaan_active ? "adhaan" :
    s.detection_active ? "listening" : "idle"
  );

  statusText.textContent = s.adhaan_active
    ? "🔴 Adhaan in Progress"
    : s.detection_active
    ? "🟡 Listening for Adhaan"
    : "Idle";

  if (s.adhaan_active && s.stream_url && audioUnlocked && !muted) {
    if (player.src !== s.stream_url) {
      player.src = s.stream_url;
      player.play().catch(() => {});
    }
  } else {
    player.pause();
    player.src = "";
  }
}
setInterval(pollStatus, STATUS_POLL_MS);
pollStatus();

/* SCHEDULE */
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
    .map(([n,t]) => {
      const [h,m] = t.split(":");
      const d = new Date();
      d.setHours(h, m, 0, 0);
      return { name:n, time:d };
    })
    .sort((a,b)=>a.time-b.time);

  for (let i=0;i<entries.length;i++) {
    if (now < entries[i].time) {
      nextPrayer = entries[i].name;
      nextPrayerTime = entries[i].time;
      currentPrayer = entries[i-1]?.name ?? null;
      break;
    }
  }

  if (!nextPrayer && prayerSchedule.Fajr) {
    const [h,m] = prayerSchedule.Fajr.split(":");
    const d = new Date();
    d.setDate(d.getDate()+1);
    d.setHours(h,m,0,0);
    nextPrayer = "Fajr";
    nextPrayerTime = d;
    currentPrayer = "Isha";
  }

  nextPrayerNameEl.textContent = nextPrayer ?? "—";
}

setInterval(() => {
  if (!nextPrayerTime) return;
  const diff = Math.max(0, Math.floor((nextPrayerTime - new Date())/1000));
  nextPrayerCountdownEl.textContent =
    `${pad(Math.floor(diff/3600))}:${pad(Math.floor(diff/60)%60)}:${pad(diff%60)}`;
}, 1000);

function renderGrid() {
  prayerGrid.innerHTML = "";
  for (const [name,time] of Object.entries(prayerSchedule)) {
    const d = document.createElement("div");
    d.className = "prayer";
    if (name === currentPrayer) d.classList.add("current");
    if (name === nextPrayer) d.classList.add("upcoming");
    d.innerHTML = `<div>${name}</div><div>${time.slice(0,5)}</div>`;
    prayerGrid.appendChild(d);
  }
}

/* ADMIN */
function post(path) { return fetch(API_BASE + path, {method:"POST"}); }
window.startDetection = ()=>post("/control/detection/start");
window.stopDetection = ()=>post("/control/detection/stop");
window.stopPlayback = ()=>post("/control/playback/stop");

const API_BASE = "http://localhost:8000";
const STATUS_POLL_MS = 2000;
const SCHEDULE_POLL_MS = 5 * 60 * 1000;

// DOM ELEMENTS
const clockEl = document.getElementById("current-time");

const statusBar = document.getElementById("status-bar");
const statusText = document.getElementById("status-text");

const nextPrayerNameEl = document.getElementById("next-prayer-name");
const nextPrayerCountdownEl = document.getElementById("next-prayer-countdown");

const hijriDateEl = document.getElementById("hijri-date");

const prayerGrid = document.getElementById("prayer-grid");


let prayerSchedule = {};
let nextPrayer = null;
let nextPrayerTime = null;
let currentPrayer = null;



function pad(n) {
  return n.toString().padStart(2, "0");
}

function formatTime(date) {
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function secondsToHHMMSS(seconds) {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  return `${pad(h)}:${pad(m)}:${pad(s)}`;
}


function updateClock() {
  const now = new Date();
  clockEl.textContent = formatTime(now);
}

setInterval(updateClock, 1000);
updateClock();


async function fetchJSON(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`Failed to fetch ${path}`);
  return res.json();
}


async function pollStatus() {
  try {
    const status = await fetchJSON("/status");

    if (status.adhaan_active) {
      statusBar.className = "status-bar adhaan";
      statusText.textContent = "🔴 Adhaan in Progress";
    } else if (status.detection_active) {
      statusBar.className = "status-bar listening";
      statusText.textContent = "🟡 Listening for Adhaan";
    } else {
      statusBar.className = "status-bar idle";
      statusText.textContent = "Idle";
    }

  } catch (err) {
    console.error("Status poll failed:", err);
  }
}

setInterval(pollStatus, STATUS_POLL_MS);
pollStatus();


async function loadSchedule() {
  try {
    prayerSchedule = await fetchJSON("/schedule");
    updatePrayerGrid();
    computePrayerState();
  } catch (err) {
    console.error("Failed to load schedule:", err);
  }
}



setInterval(loadSchedule, SCHEDULE_POLL_MS);
loadSchedule();


function computePrayerState() {
  if (!prayerSchedule || Object.keys(prayerSchedule).length === 0) return;

  const now = new Date();
  const entries = Object.entries(prayerSchedule);

  const times = entries.map(([name, timeStr]) => {
    const [h, m, s] = timeStr.split(":").map(Number);
    const t = new Date();
    t.setHours(h, m, s ?? 0, 0);
    return { name, time: t };
  });

  // Sort just in case
  times.sort((a, b) => a.time - b.time);

  currentPrayer = null;
  nextPrayer = null;
  nextPrayerTime = null;

  for (let i = 0; i < times.length; i++) {
    const curr = times[i];
    const next = times[i + 1];

    if (now >= curr.time && (!next || now < next.time)) {
      currentPrayer = curr.name;
      nextPrayer = next?.name ?? "Fajr";
      nextPrayerTime = next?.time ?? new Date(curr.time.getTime() + 24 * 3600 * 1000);
      break;
    }
  }

  // After Isha → before Fajr
  if (!currentPrayer && prayerSchedule["Fajr"]) {
    const [h, m, s] = prayerSchedule["Fajr"].split(":").map(Number);
    const t = new Date();
    t.setDate(t.getDate() + 1);
    t.setHours(h, m, s ?? 0, 0);

    currentPrayer = "Isha";
    nextPrayer = "Fajr";
    nextPrayerTime = t;
  }

  nextPrayerNameEl.textContent = nextPrayer ?? "—";
  updatePrayerGrid();
}





function updateCountdown() {
  if (!nextPrayerTime) return;

  const now = new Date();
  const diffSec = Math.floor((nextPrayerTime - now) / 1000);

  if (diffSec >= 0) {
    nextPrayerCountdownEl.textContent = secondsToHHMMSS(diffSec);
  } else {
    nextPrayerCountdownEl.textContent = "00:00:00";
  }
}

setInterval(updateCountdown, 1000);

function stripSeconds(timeStr) {
  if (!timeStr) return "--:--";
  const [h, m] = timeStr.split(":");
  return `${h}:${m}`;
}



function updatePrayerGrid() {
  prayerGrid.innerHTML = "";

  Object.entries(prayerSchedule).forEach(([name, time]) => {
    const div = document.createElement("div");
    div.className = "prayer";

    if (name === currentPrayer) {
      div.classList.add("current");
    } else if (name === nextPrayer) {
      div.classList.add("upcoming");
    }

    div.innerHTML = `
      <div class="name">${name}</div>
      <div class="time">${stripSeconds(time)}</div>
    `;

    prayerGrid.appendChild(div);
  });
}

function toggleTheme() {
  document.body.classList.toggle("light");
  localStorage.setItem(
    "theme",
    document.body.classList.contains("light") ? "light" : "dark"
  );
}

// Restore theme on load
(function () {
  const saved = localStorage.getItem("theme");
  if (saved === "light") {
    document.body.classList.add("light");
  }
})();





async function postControl(path) {
  const res = await fetch(`${API_BASE}${path}`, { method: "POST" });
  return res.json();
}

// Expose for buttons if added later
window.startDetection = () => postControl("/control/detection/start");
window.stopDetection = () => postControl("/control/detection/stop");
window.stopPlayback = () => postControl("/control/playback/stop");

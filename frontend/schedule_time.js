/**
 * Pure timezone-aware schedule helpers shared by the browser and Node tests.
 */
function prayerEntries(schedule) {
  if (!schedule || typeof schedule.prayers !== "object") return [];

  return Object.entries(schedule.prayers)
    .map(([name, timestamp]) => ({
      name,
      timestamp,
      time: new Date(timestamp),
    }))
    .filter((entry) => !Number.isNaN(entry.time.getTime()))
    .sort((a, b) => a.time - b.time);
}

function getPrayerState(schedule, now = new Date()) {
  const entries = prayerEntries(schedule);
  const nextIndex = entries.findIndex((entry) => now < entry.time);

  if (nextIndex === -1) {
    return {
      currentPrayer: entries.at(-1)?.name ?? null,
      nextPrayer: null,
      nextPrayerTime: null,
    };
  }

  return {
    currentPrayer: entries[nextIndex - 1]?.name ?? null,
    nextPrayer: entries[nextIndex].name,
    nextPrayerTime: entries[nextIndex].time,
  };
}

function countdownSeconds(target, now = new Date()) {
  if (!target) return null;
  return Math.max(0, Math.floor((target - now) / 1000));
}

function formatPrayerTime(timestamp, timezoneName) {
  const prayerTime = new Date(timestamp);
  if (Number.isNaN(prayerTime.getTime())) return "—";

  return new Intl.DateTimeFormat("en-US", {
    timeZone: timezoneName,
    hour: "numeric",
    minute: "2-digit",
  }).format(prayerTime);
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = {
    prayerEntries,
    getPrayerState,
    countdownSeconds,
    formatPrayerTime,
  };
}

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  getPrayerState,
  countdownSeconds,
  formatPrayerTime,
} = require("../frontend/schedule_time.js");


const schedule = {
  date: "2026-08-27",
  timezone: "America/Chicago",
  prayers: {
    Fajr: "2026-08-27T05:30:00-05:00",
    Dhuhr: "2026-08-27T13:30:00-05:00",
    Asr: "2026-08-27T17:00:00-05:00",
  },
};


test("Atlanta and UTC clients select the same Dallas prayer", () => {
  const atlantaNow = new Date("2026-08-27T14:29:00-04:00");
  const utcNow = new Date("2026-08-27T18:29:00Z");

  const atlantaState = getPrayerState(schedule, atlantaNow);
  const utcState = getPrayerState(schedule, utcNow);

  assert.equal(atlantaNow.getTime(), utcNow.getTime());
  assert.equal(atlantaState.nextPrayer, "Dhuhr");
  assert.equal(utcState.nextPrayer, "Dhuhr");
  assert.equal(
    atlantaState.nextPrayerTime.getTime(),
    utcState.nextPrayerTime.getTime()
  );
});


test("countdown is based on the absolute instant", () => {
  const target = new Date("2026-08-27T13:30:00-05:00");
  const atlantaNow = new Date("2026-08-27T14:29:00-04:00");
  const utcNow = new Date("2026-08-27T18:29:00Z");

  assert.equal(countdownSeconds(target, atlantaNow), 60);
  assert.equal(countdownSeconds(target, utcNow), 60);
});


test("prayer time is displayed in the configured mosque timezone", () => {
  const displayed = formatPrayerTime(
    "2026-08-27T13:30:00-05:00",
    "America/Chicago"
  );

  assert.match(displayed, /1:30 PM/);
});


test("there is no fabricated next prayer after the final daily prayer", () => {
  const state = getPrayerState(
    schedule,
    new Date("2026-08-28T04:00:00Z")
  );

  assert.equal(state.currentPrayer, "Asr");
  assert.equal(state.nextPrayer, null);
  assert.equal(state.nextPrayerTime, null);
});

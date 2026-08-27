const test = require("node:test");
const assert = require("node:assert/strict");

const {
  shouldPlayAdhaan,
  dismissalForStatus,
} = require("../frontend/playback_policy.js");


const ready = {
  adhaanActive: true,
  streamUrl: "https://example.test/live.m3u8",
  audioUnlocked: true,
  muted: false,
  dismissedThisAdhaan: false,
};


test("plays when every client-side requirement is satisfied", () => {
  assert.equal(shouldPlayAdhaan(ready), true);
});


test("does not play before the server detects an Adhaan", () => {
  assert.equal(shouldPlayAdhaan({ ...ready, adhaanActive: false }), false);
});


test("does not play without a stream URL", () => {
  assert.equal(shouldPlayAdhaan({ ...ready, streamUrl: null }), false);
});


test("does not play before browser audio is unlocked", () => {
  assert.equal(shouldPlayAdhaan({ ...ready, audioUnlocked: false }), false);
});


test("does not play while this device is muted or dismissed", () => {
  assert.equal(shouldPlayAdhaan({ ...ready, muted: true }), false);
  assert.equal(
    shouldPlayAdhaan({ ...ready, dismissedThisAdhaan: true }),
    false
  );
});


test("dismissal persists during one Adhaan and clears after it ends", () => {
  assert.equal(dismissalForStatus(true, true), true);
  assert.equal(dismissalForStatus(false, true), false);
});

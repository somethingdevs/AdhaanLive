/**
 * Pure playback decisions shared by the browser UI and the Node test suite.
 * Keeping these functions free of DOM access makes the client-only behavior
 * deterministic and easy to verify.
 */
function shouldPlayAdhaan({
  adhaanActive,
  streamUrl,
  audioUnlocked,
  muted,
  dismissedThisAdhaan,
}) {
  return Boolean(
    adhaanActive &&
    streamUrl &&
    audioUnlocked &&
    !muted &&
    !dismissedThisAdhaan
  );
}

function dismissalForStatus(adhaanActive, dismissedThisAdhaan) {
  return adhaanActive ? dismissedThisAdhaan : false;
}

if (typeof module !== "undefined" && module.exports) {
  module.exports = { shouldPlayAdhaan, dismissalForStatus };
}

/**
 * proctor.js — AI Interview Coach
 * ================================
 * Client-side proctoring panel using MediaPipe Face Detection (WASM/JS).
 * All processing happens in the browser — no video is ever sent to a server.
 *
 * What it does:
 *   1. Requests webcam access and streams video into #proctorVideo.
 *   2. Runs MediaPipe FaceDetection on every animation frame.
 *   3. If no face is detected for > ABSENT_THRESHOLD_MS (3 s), it:
 *        - Pauses the interview timers (global + per-question).
 *        - Disables the Submit Answer button.
 *        - Shows the #proctorWarning overlay.
 *        - Speaks a TTS warning (rate-limited to once every 6 s).
 *   4. When a face is detected again it immediately:
 *        - Resumes timers.
 *        - Re-enables Submit.
 *        - Hides the overlay.
 *   5. Draws a subtle detection box on #proctorCanvas while a face is present.
 *
 * Integration contract (functions called on interview.js):
 *   window._proctor_pauseTimers()   — defined below, called internally
 *   window._proctor_resumeTimers()  — defined below, called internally
 *   interview.js exposes nothing extra; proctor patches the timer ticks.
 *
 * Dependencies (CDN, no install):
 *   @mediapipe/face_detection  0.4.x  (loaded via script tags in interview.html)
 */

'use strict';

/* ─── Config ────────────────────────────────────────────────────────────── */
const ABSENT_THRESHOLD_MS = 3000;   // ms before warning triggers
const TTS_COOLDOWN_MS = 6000;   // ms between repeated TTS warnings
const DETECTION_CONFIDENCE = 0.6;    // MediaPipe minimum confidence
const WARNING_MESSAGE = 'Please remain in front of the camera to continue the interview.';

/* ─── State ─────────────────────────────────────────────────────────────── */
let _faceDetector = null;
let _camera = null;
let _stream = null;
let _lastSeenFaceAt = Date.now();   // timestamp of last successful detection
let _isAbsent = false;        // true while no face present > threshold
let _lastTtsAt = 0;            // timestamp of last TTS warning
let _rafId = null;         // requestAnimationFrame handle
let _initialized = false;

/* ─── Presence confidence tracking ─────────────────────────────────────── */
// We sample every PRESENCE_SAMPLE_MS ms whether a face is present.
// presenceScore = (samplesWithFace / totalSamples) * 100
const PRESENCE_SAMPLE_MS = 500;     // sample every 500 ms
let _presenceTotalSamples = 0;
let _presenceFaceSamples = 0;
let _presenceSampleTick = null;   // setInterval handle
let _absenceLog = [];     // array of { start, end, durationMs }
let _currentAbsenceStart = null;   // timestamp when current absence began

/** Return presence confidence as a 0-100 number (one decimal place). */
function getPresenceScore() {
  if (_presenceTotalSamples === 0) return 100;
  return parseFloat(
    ((_presenceFaceSamples / _presenceTotalSamples) * 100).toFixed(1)
  );
}

/** Return a copy of the absence log entries. */
function getAbsenceLog() {
  return [..._absenceLog];
}

function _startPresenceSampler() {
  if (_presenceSampleTick) return;
  _presenceSampleTick = setInterval(() => {
    _presenceTotalSamples++;
    if (!_isAbsent) {
      _presenceFaceSamples++;
    }
    // Update the sidebar display
    _updatePresenceDisplay();
  }, PRESENCE_SAMPLE_MS);
}

function _stopPresenceSampler() {
  if (_presenceSampleTick) {
    clearInterval(_presenceSampleTick);
    _presenceSampleTick = null;
  }
}

function _updatePresenceDisplay() {
  const el = document.getElementById('proctorPresenceScore');
  if (el) el.textContent = getPresenceScore() + '%';
  const bar = document.getElementById('proctorPresenceBar');
  if (bar) bar.style.width = getPresenceScore() + '%';
}

/* ─── DOM refs (resolved after DOMContentLoaded) ─────────────────────── */
let $video, $canvas, $ctx, $statusDot, $statusText, $warningBanner, $submitBtn;

/* ─── Timer pause hooks ─────────────────────────────────────────────────── */
// interview.js owns _globalTick and _qTick as module-scoped lets.
// We cannot import them directly, so we patch via a shared API exposed on
// window by interview.js at boot time. If the API is absent we fall back
// to disabling submission only (timers still run — graceful degradation).
function _pauseTimers() {
  if (typeof window._interviewPauseTimers === 'function') {
    window._interviewPauseTimers();
  }
}
function _resumeTimers() {
  if (typeof window._interviewResumeTimers === 'function') {
    window._interviewResumeTimers();
  }
}

/* ─── TTS helper ────────────────────────────────────────────────────────── */
function _speakWarning() {
  const now = Date.now();
  if (now - _lastTtsAt < TTS_COOLDOWN_MS) return;
  _lastTtsAt = now;

  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();

  const utt = new SpeechSynthesisUtterance(WARNING_MESSAGE);
  utt.rate = 0.9;
  utt.pitch = 1.0;
  utt.volume = 1;

  const voices = speechSynthesis.getVoices();
  const preferred = voices.find(v => v.name.includes('Google') && v.lang.startsWith('en'))
    || voices.find(v => v.lang === 'en-US')
    || voices[0];
  if (preferred) utt.voice = preferred;

  speechSynthesis.speak(utt);
}

/* ─── UI helpers ─────────────────────────────────────────────────────────── */
function _setAbsent(absent) {
  if (_isAbsent === absent) return;   // no change — skip DOM work
  _isAbsent = absent;

  if (absent) {
    // Log absence start
    _currentAbsenceStart = Date.now();

    // Pause interview
    _pauseTimers();
    if ($submitBtn) $submitBtn.disabled = true;
    if ($warningBanner) $warningBanner.style.display = 'flex';
    const ao = document.getElementById('proctorAbsentOverlay');
    if (ao) ao.classList.add('visible');
    if ($statusDot) { $statusDot.style.background = 'var(--danger)'; $statusDot.style.boxShadow = '0 0 8px var(--danger)'; }
    if ($statusText) { $statusText.textContent = 'No face detected'; $statusText.style.color = 'var(--danger)'; }
    _speakWarning();
    console.warn('[proctor] Face absent — interview paused. Total absences:', _absenceLog.length + 1);
  } else {
    // Log absence end
    if (_currentAbsenceStart !== null) {
      const end = Date.now();
      _absenceLog.push({
        start: new Date(_currentAbsenceStart).toISOString(),
        end: new Date(end).toISOString(),
        durationMs: end - _currentAbsenceStart,
      });
      _currentAbsenceStart = null;
    }

    // Resume interview
    _resumeTimers();
    // Only re-enable submit if the answer card is actually visible
    const answerCard = document.getElementById('answerCard');
    if ($submitBtn && answerCard && answerCard.style.display !== 'none') {
      $submitBtn.disabled = false;
    }
    if ($warningBanner) $warningBanner.style.display = 'none';
    const ao2 = document.getElementById('proctorAbsentOverlay');
    if (ao2) ao2.classList.remove('visible');
    if ($statusDot) { $statusDot.style.background = 'var(--success)'; $statusDot.style.boxShadow = '0 0 8px var(--success)'; }
    if ($statusText) { $statusText.textContent = 'Face detected'; $statusText.style.color = 'var(--success)'; }
    console.info('[proctor] Face resumed — interview active. Presence score:', getPresenceScore() + '%');
  }
}

/* ─── Canvas drawing ─────────────────────────────────────────────────────── */
function _drawDetections(detections) {
  if (!$canvas || !$ctx || !$video) return;

  $canvas.width = $video.videoWidth || $canvas.offsetWidth;
  $canvas.height = $video.videoHeight || $canvas.offsetHeight;
  $ctx.clearRect(0, 0, $canvas.width, $canvas.height);

  if (!detections || detections.length === 0) return;

  const vw = $canvas.width;
  const vh = $canvas.height;

  detections.forEach(det => {
    const box = det.boundingBox;
    if (!box) return;

    const x = box.xCenter * vw - (box.width * vw) / 2;
    const y = box.yCenter * vh - (box.height * vh) / 2;
    const w = box.width * vw;
    const h = box.height * vh;
    const r = 8;

    // Rounded rect in accent colour
    $ctx.strokeStyle = 'rgba(99,102,241,0.85)';
    $ctx.lineWidth = 2;
    $ctx.beginPath();
    $ctx.moveTo(x + r, y);
    $ctx.lineTo(x + w - r, y);
    $ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    $ctx.lineTo(x + w, y + h - r);
    $ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    $ctx.lineTo(x + r, y + h);
    $ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    $ctx.lineTo(x, y + r);
    $ctx.quadraticCurveTo(x, y, x + r, y);
    $ctx.closePath();
    $ctx.stroke();

    // Corner accent marks
    const cl = 10;
    $ctx.strokeStyle = '#6366f1';
    $ctx.lineWidth = 3;
    [[x, y, 1, 1], [x + w, y, -1, 1], [x, y + h, 1, -1], [x + w, y + h, -1, -1]].forEach(([cx, cy, dx, dy]) => {
      $ctx.beginPath();
      $ctx.moveTo(cx + dx * cl, cy); $ctx.lineTo(cx, cy); $ctx.lineTo(cx, cy + dy * cl);
      $ctx.stroke();
    });
  });
}

/* ─── MediaPipe result handler ──────────────────────────────────────────── */
function _onResults(results) {
  const detections = results.detections || [];
  const now = Date.now();

  _drawDetections(detections);

  if (detections.length > 0) {
    _lastSeenFaceAt = now;
    _setAbsent(false);
  } else {
    // Only trigger absent state after threshold has elapsed
    if (!_isAbsent && (now - _lastSeenFaceAt) >= ABSENT_THRESHOLD_MS) {
      _setAbsent(true);
    }
    // If already absent, keep speaking reminder on cooldown
    if (_isAbsent) {
      _speakWarning();
    }
  }
}

/* ─── MediaPipe initialisation ──────────────────────────────────────────── */
async function _initMediaPipe() {
  if (typeof FaceDetection === 'undefined') {
    console.warn('[proctor] MediaPipe FaceDetection not loaded. Proctoring disabled.');
    _showUnavailable('MediaPipe not loaded. Refresh the page.');
    return false;
  }

  _faceDetector = new FaceDetection({
    locateFile: (file) =>
      `https://cdn.jsdelivr.net/npm/@mediapipe/face_detection@0.4/${file}`,
  });

  _faceDetector.setOptions({
    model: 'short',          // fast short-range model
    minDetectionConfidence: DETECTION_CONFIDENCE,
  });

  _faceDetector.onResults(_onResults);

  await _faceDetector.initialize();
  return true;
}

/* ─── Webcam access ─────────────────────────────────────────────────────── */
async function _startCamera() {
  try {
    _stream = await navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 320 }, height: { ideal: 240 }, facingMode: 'user' },
      audio: false,
    });
    $video.srcObject = _stream;
    await new Promise(resolve => { $video.onloadedmetadata = resolve; });
    await $video.play();
    return true;
  } catch (err) {
    console.warn('[proctor] Camera error:', err.name, err.message);
    const msgs = {
      NotAllowedError: 'Camera access denied. Allow camera in browser settings.',
      NotFoundError: 'No camera found. Connect a webcam to enable proctoring.',
      NotReadableError: 'Camera is in use by another app.',
    };
    _showUnavailable(msgs[err.name] || `Camera error: ${err.message}`);
    return false;
  }
}

/* ─── Detection loop ────────────────────────────────────────────────────── */
async function _detectionLoop() {
  if (!_faceDetector || !$video || $video.readyState < 2) {
    _rafId = requestAnimationFrame(_detectionLoop);
    return;
  }
  try {
    await _faceDetector.send({ image: $video });
  } catch (_) {
    /* ignore single-frame errors */
  }
  _rafId = requestAnimationFrame(_detectionLoop);
}

/* ─── Unavailable state ─────────────────────────────────────────────────── */
function _showUnavailable(msg) {
  const panel = document.getElementById('proctorPanel');
  if (!panel) return;

  const body = panel.querySelector('.proctor-body');
  if (body) {
    body.innerHTML = `
      <div style="text-align:center;padding:1.2rem 0.5rem">
        <div style="font-size:2rem;margin-bottom:0.6rem">📵</div>
        <div style="font-size:0.8rem;color:var(--muted);line-height:1.5">${msg}</div>
        <div style="font-size:0.72rem;color:var(--muted);margin-top:0.5rem;opacity:0.6">Interview continues without proctoring.</div>
      </div>`;
  }
  if ($statusDot) { $statusDot.style.background = 'var(--muted)'; $statusDot.style.boxShadow = 'none'; }
  if ($statusText) { $statusText.textContent = 'Unavailable'; }
}

/* ─── Public init ───────────────────────────────────────────────────────── */
async function initProctor() {
  if (_initialized) return;
  _initialized = true;

  // Resolve DOM refs
  $video = document.getElementById('proctorVideo');
  $canvas = document.getElementById('proctorCanvas');
  $statusDot = document.getElementById('proctorStatusDot');
  $statusText = document.getElementById('proctorStatusText');
  $warningBanner = document.getElementById('proctorWarning');
  $submitBtn = document.getElementById('submitBtn');
  $ctx = $canvas ? $canvas.getContext('2d') : null;

  if (!$video || !$canvas) {
    console.warn('[proctor] Proctor DOM elements not found.');
    return;
  }

  // Check mediaDevices API
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    _showUnavailable('Your browser does not support camera access. Use Chrome or Edge on localhost/HTTPS.');
    return;
  }

  // Status: initialising
  if ($statusText) $statusText.textContent = 'Starting camera…';

  const cameraOk = await _startCamera();
  if (!cameraOk) return;

  if ($statusText) $statusText.textContent = 'Loading detector…';

  const mpOk = await _initMediaPipe();
  if (!mpOk) return;

  // Pre-load voices
  if (window.speechSynthesis) {
    speechSynthesis.getVoices();
    speechSynthesis.addEventListener('voiceschanged', () => speechSynthesis.getVoices());
  }

  // Mark active
  if ($statusDot) { $statusDot.style.background = 'var(--success)'; $statusDot.style.boxShadow = '0 0 8px var(--success)'; }
  if ($statusText) { $statusText.textContent = 'Proctoring active'; $statusText.style.color = 'var(--success)'; }

  _lastSeenFaceAt = Date.now();
  _startPresenceSampler();
  _detectionLoop();
}

/* ─── Cleanup (called by finishInterview / confirmExit in interview.js) ── */
function stopProctor() {
  // Close out any in-progress absence
  if (_isAbsent && _currentAbsenceStart !== null) {
    const end = Date.now();
    _absenceLog.push({
      start: new Date(_currentAbsenceStart).toISOString(),
      end: new Date(end).toISOString(),
      durationMs: end - _currentAbsenceStart,
    });
    _currentAbsenceStart = null;
  }

  _stopPresenceSampler();
  if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null; }
  if (_stream) { _stream.getTracks().forEach(t => t.stop()); _stream = null; }
  if (_faceDetector) { _faceDetector.close(); _faceDetector = null; }

  console.info(
    '[proctor] Stopped. Final presence score:', getPresenceScore() + '%',
    '| Absences:', _absenceLog.length,
    '| Log:', _absenceLog
  );
}

/* ─── Expose on window for interview.js integration ─────────────────────── */
window.initProctor = initProctor;
window.stopProctor = stopProctor;
window.getPresenceScore = getPresenceScore;
window.getAbsenceLog = getAbsenceLog;

/* ─── Boot ──────────────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  // Small delay so interview.js finishes its own DOMContentLoaded first
  setTimeout(initProctor, 400);
});

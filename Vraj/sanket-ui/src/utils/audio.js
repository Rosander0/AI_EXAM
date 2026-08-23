/**
 * Formal Acoustic Audio Synthesizer for SANKET.
 * Provides subtle, enterprise-grade auditory feedback using soft harmonic sine waves.
 */

let audioCtx = null;

function getAudioContext() {
  if (!audioCtx && typeof window !== 'undefined') {
    const AudioContextClass = window.AudioContext || window.webkitAudioContext;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  if (audioCtx && audioCtx.state === 'suspended') {
    audioCtx.resume();
  }
  return audioCtx;
}

/**
 * Plays a formal, warm acoustic chime with harmonic overtone.
 */
function playTone(freq, startTime, duration, gainValue = 0.08, ctx) {
  const osc = ctx.createOscillator();
  const harmonic = ctx.createOscillator();
  const gain = ctx.createGain();
  const harmonicGain = ctx.createGain();

  osc.type = 'sine';
  osc.frequency.setValueAtTime(freq, startTime);

  // Soft overtone at 2x frequency for warm timbre
  harmonic.type = 'sine';
  harmonic.frequency.setValueAtTime(freq * 2, startTime);

  // Envelopes: soft attack, natural exponential decay
  gain.gain.setValueAtTime(0.0001, startTime);
  gain.gain.linearRampToValueAtTime(gainValue, startTime + 0.015);
  gain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration);

  harmonicGain.gain.setValueAtTime(0.0001, startTime);
  harmonicGain.gain.linearRampToValueAtTime(gainValue * 0.25, startTime + 0.015);
  harmonicGain.gain.exponentialRampToValueAtTime(0.0001, startTime + duration * 0.7);

  osc.connect(gain);
  harmonic.connect(harmonicGain);
  gain.connect(ctx.destination);
  harmonicGain.connect(ctx.destination);

  osc.start(startTime);
  harmonic.start(startTime);
  osc.stop(startTime + duration);
  harmonic.stop(startTime + duration);
}

export const playAudioChime = (type = 'warning') => {
  try {
    const ctx = getAudioContext();
    if (!ctx) return;

    const now = ctx.currentTime;

    if (type === 'critical') {
      // Deep, formal authoritative two-tone (E4 -> C4)
      playTone(329.63, now, 0.40, 0.08, ctx);
      playTone(261.63, now + 0.20, 0.60, 0.10, ctx);
    } else if (type === 'warning') {
      // Deep, resonant acoustic ping (A4)
      playTone(440.00, now, 0.40, 0.06, ctx);
    } else if (type === 'success') {
      // Professional ascending sequence (C4 -> E4 -> G4)
      playTone(261.63, now, 0.25, 0.05, ctx);
      playTone(329.63, now + 0.12, 0.30, 0.05, ctx);
      playTone(392.00, now + 0.24, 0.40, 0.06, ctx);
    } else if (type === 'halt') {
      // Deep descending tone signaling system standby (G4 -> C4)
      playTone(392.00, now, 0.30, 0.06, ctx);
      playTone(261.63, now + 0.15, 0.50, 0.08, ctx);
    }
  } catch (err) {
    console.debug('Audio feedback unavailable:', err);
  }
};

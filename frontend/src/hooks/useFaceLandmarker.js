import { useEffect, useState } from "react";

const VERSION = "0.10.14";
const WASM = `https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@${VERSION}/wasm`;
const MODEL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task";

// Loads MediaPipe FaceLandmarker (GPU first, automatic CPU fallback for mobile browsers).
// status: loading | ready | failed (→ manual button mode, NEVER blind auto-snap)
export function useFaceLandmarker() {
  const [state, setState] = useState({ status: "loading", landmarker: null });

  useEffect(() => {
    let cancelled = false;
    let instance;
    const timeout = setTimeout(
      () => !cancelled && setState((s) => (s.status === "loading" ? { status: "failed", landmarker: null } : s)),
      20000
    );
    (async () => {
      try {
        if (new URLSearchParams(window.location.search).has("guided")) throw new Error("forced manual mode");
        const { FilesetResolver, FaceLandmarker } = await import("@mediapipe/tasks-vision");
        const fileset = await FilesetResolver.forVisionTasks(WASM);

        // Try GPU first; on many Android/iOS browsers WebGL delegate fails -> fallback to CPU
        try {
          instance = await FaceLandmarker.createFromOptions(fileset, {
            baseOptions: { modelAssetPath: MODEL, delegate: "GPU" },
            runningMode: "VIDEO",
            numFaces: 2,
          });
        } catch {
          instance = await FaceLandmarker.createFromOptions(fileset, {
            baseOptions: { modelAssetPath: MODEL, delegate: "CPU" },
            runningMode: "VIDEO",
            numFaces: 2,
          });
        }

        if (!cancelled) setState({ status: "ready", landmarker: instance });
      } catch {
        if (!cancelled) setState({ status: "failed", landmarker: null });
      } finally {
        clearTimeout(timeout);
      }
    })();
    return () => {
      cancelled = true;
      clearTimeout(timeout);
      instance?.close();
    };
  }, []);

  return state;
}

// Nose-tip x relative to the two cheek edges (landmarks 1, 234, 454).
// Facing front: ~0.50 | Turning own right: < 0.33 | Turning own left: > 0.67
export function yawRatio(lm) {
  if (!lm || lm.length < 455) return 0.5;
  const nose = lm[1], a = lm[234], b = lm[454];
  const span = b.x - a.x;
  return Math.abs(span) < 1e-6 ? 0.5 : (nose.x - a.x) / span;
}

// Eye openness ratio for Liveness Detection (blink verification)
// Left eye top: 159, bottom: 145, corners: 33, 133
// Right eye top: 386, bottom: 374, corners: 362, 263
export function eyeOpenRatio(lm) {
  if (!lm || lm.length < 468) return 0.3;
  const dLeft = Math.hypot(lm[159].x - lm[145].x, lm[159].y - lm[145].y);
  const wLeft = Math.hypot(lm[33].x - lm[133].x, lm[33].y - lm[133].y);
  const leftRatio = dLeft / (wLeft + 1e-6);

  const dRight = Math.hypot(lm[386].x - lm[374].x, lm[386].y - lm[374].y);
  const wRight = Math.hypot(lm[362].x - lm[263].x, lm[362].y - lm[263].y);
  const rightRatio = dRight / (wRight + 1e-6);

  return (leftRatio + rightRatio) / 2;
}

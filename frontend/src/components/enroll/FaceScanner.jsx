import { useCallback, useEffect, useRef, useState } from "react";
import { VideoOff, Loader2, Camera, ShieldCheck, Eye, AlertCircle } from "lucide-react";
import { POSES } from "./poses";
import { PoseBadges } from "./PoseBadges";
import { useFaceLandmarker, yawRatio, eyeOpenRatio } from "@/hooks/useFaceLandmarker";

const HOLD_MS = 1500; // Tahan posisi 1.5 detik setelah pose benar agar foto tajam
const TRANSITION_COOLDOWN_MS = 1300; // Jeda 1.3 detik antar pose agar sempat menoleh

export const FaceScanner = ({ onComplete, busy, failed, errorMessage }) => {
  const videoRef = useRef(null);
  const shotsRef = useRef({});
  const stageRef = useRef(0);
  const holdRef = useRef(null);
  const cooldownUntilRef = useRef(0);
  const lastVideoTsRef = useRef(0);
  const eyeClosedRef = useRef(false);
  const blinkVerifiedRef = useRef(false);

  const { status: lmStatus, landmarker } = useFaceLandmarker();
  const [camError, setCamError] = useState("");
  const [camReady, setCamReady] = useState(false);
  const [distanceStatus, setDistanceStatus] = useState("ok"); // "too_far" | "too_close" | "ok"
  const [ui, setUi] = useState({ stage: 0, hold: 0, status: "noface", shots: {}, blinkDone: false });
  const [flash, setFlash] = useState(false);

  useEffect(() => {
    let stream;
    navigator.mediaDevices?.getUserMedia({ video: { facingMode: "user", width: { ideal: 960 }, height: { ideal: 720 } }, audio: false })
      .then((s) => {
        stream = s;
        if (videoRef.current) {
          videoRef.current.srcObject = s;
        }
      })
      .catch(() => setCamError("Kamera tidak dapat diakses. Mohon izinkan akses kamera perangkat untuk melanjutkan registrasi."));
    return () => stream?.getTracks().forEach((t) => t.stop());
  }, []);

  const capture = useCallback(() => {
    const v = videoRef.current;
    if (!v || v.videoWidth === 0 || v.videoHeight === 0) return;
    if (stageRef.current >= POSES.length) return;

    const c = document.createElement("canvas");
    c.width = v.videoWidth;
    c.height = v.videoHeight;
    c.getContext("2d").drawImage(v, 0, 0);
    const pose = POSES[stageRef.current];
    stageRef.current += 1;
    holdRef.current = null;
    eyeClosedRef.current = false;
    blinkVerifiedRef.current = false;
    cooldownUntilRef.current = performance.now() + TRANSITION_COOLDOWN_MS;
    setFlash(true);
    setTimeout(() => setFlash(false), 240);

    c.toBlob((blob) => {
      shotsRef.current = { ...shotsRef.current, [pose.angle]: { blob, url: URL.createObjectURL(blob) } };
      setUi((u) => ({ ...u, shots: shotsRef.current, stage: stageRef.current, hold: 0, status: "cooldown", blinkDone: false }));
      if (stageRef.current >= POSES.length) {
        onComplete(shotsRef.current);
      }
    }, "image/jpeg", 0.95);
  }, [onComplete]);

  useEffect(() => {
    if (!camReady || lmStatus === "loading") return;
    let raf;
    const manualOnly = lmStatus !== "ready";

    const tick = () => {
      const stage = stageRef.current;
      const v = videoRef.current;
      const now = performance.now();

      if (stage < POSES.length && v?.readyState >= 2 && v.videoWidth > 0) {
        if (manualOnly) {
          // Jangan auto-jepret buta jika MediaPipe gagal dimuat! User ambil manual setelah menoleh.
          holdRef.current = null;
          setUi((u) => (u.status === "manual" && u.stage === stage ? u : { ...u, stage, hold: 0, status: "manual" }));
        } else if (now < cooldownUntilRef.current) {
          // Jeda antar pose agar user punya waktu membaca instruksi dan mulai menoleh
          holdRef.current = null;
          setUi((u) => ({ ...u, stage, hold: 0, status: "cooldown", blinkDone: false }));
        } else if (now > lastVideoTsRef.current + 30) {
          lastVideoTsRef.current = now;
          let status = "noface";
          const currentPose = POSES[stage];

          try {
            const faces = landmarker.detectForVideo(v, now).faceLandmarks || [];
            if (faces.length === 0) {
              status = "noface";
              setDistanceStatus("ok");
            } else if (faces.length > 1) {
              status = "multi";
              setDistanceStatus("ok");
            } else {
              const lm = faces[0];
              const yaw = yawRatio(lm);
              const poseMatched = currentPose.match(yaw);

              // Periksa jarak wajah relatif terhadap frame
              const xs = lm.map((p) => p.x);
              const ys = lm.map((p) => p.y);
              const faceW = Math.max(...xs) - Math.min(...xs);
              const faceH = Math.max(...ys) - Math.min(...ys);

              let dist = "ok";
              if (faceW < 0.22 || faceH < 0.25) {
                dist = "too_far";
              } else if (faceW > 0.78 || faceH > 0.82) {
                dist = "too_close";
              }
              setDistanceStatus(dist);

              if (dist !== "ok") {
                status = "distance";
              } else if (currentPose.requiresBlink) {
                const eyeOpen = eyeOpenRatio(lm);
                if (eyeOpen < 0.17) {
                  eyeClosedRef.current = true;
                } else if (eyeClosedRef.current && eyeOpen >= 0.21) {
                  blinkVerifiedRef.current = true;
                }
                if (!blinkVerifiedRef.current) {
                  status = "need_blink";
                } else {
                  status = poseMatched ? "hold" : "adjust";
                }
              } else {
                status = poseMatched ? "hold" : "adjust";
              }
            }
          } catch {
            // Skip frame jika MediaPipe sedang sibuk
            status = "adjust";
          }

          const ok = status === "hold";
          if (ok && holdRef.current == null) holdRef.current = now;
          if (!ok) holdRef.current = null;
          const hold = ok ? Math.min(1, (now - holdRef.current) / HOLD_MS) : 0;
          setUi((u) => ({ ...u, stage, hold, status, blinkDone: blinkVerifiedRef.current }));
          if (hold >= 1) capture();
        }
      }
      raf = requestAnimationFrame(tick);
    };

    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [camReady, lmStatus, landmarker, capture]);

  if (camError) {
    return (
      <div data-testid="camera-error" className="text-center text-white/80 py-16">
        <VideoOff className="w-10 h-10 mx-auto mb-4 text-red-400" />
        <p className="font-mono text-xs max-w-sm mx-auto">{camError}</p>
      </div>
    );
  }

  const done = ui.stage >= POSES.length;
  const pose = POSES[Math.min(ui.stage, POSES.length - 1)];
  const progress = (Object.keys(ui.shots).length + (done ? 0 : ui.hold)) / POSES.length;

  const getInstruction = () => {
    if (busy) return "Memvalidasi & Menyimpan Profil Wajah…";
    if (failed) return "Pemeriksaan Kualitas Gagal";
    if (done) return "3 Pose Selesai Diambil";
    if (ui.status === "cooldown") return `Pose Berikutnya: ${pose.short}`;
    if (distanceStatus === "too_far") return "Dekatkan Wajah ke Kamera";
    if (distanceStatus === "too_close") return "Mundurkan Wajah Sedikit";
    if (ui.status === "need_blink") return "Kedipkan Mata Anda Sekali";
    return pose.instruction;
  };

  const getSubtext = () => {
    if (busy) return "Memeriksa resolusi >=60px, ketajaman, kecerahan CIELAB, dan 5 landmark…";
    if (failed) return errorMessage || "Pastikan wajah cukup terang, tidak buram, dan hanya ada 1 orang di depan kamera.";
    if (done) return "Menyimpan 3 pose profil wajah Anda ke database aman…";
    if (lmStatus === "loading") return "Memuat modul pendeteksi wajah dan arah kepala…";
    if (ui.status === "manual") return `Mode tombol manual: ${pose.hint} Lalu tekan tombol "Ambil Foto" di bawah.`;
    if (ui.status === "cooldown") return `Bagus! Sekarang bersiap: ${pose.hint}`;
    if (ui.status === "noface") return "Posisikan wajah Anda tepat di dalam bingkai oval panduan.";
    if (ui.status === "multi") return "Terdeteksi lebih dari satu orang. Pastikan hanya Anda di depan kamera.";
    if (distanceStatus === "too_far") return "Wajah terlalu jauh (minimal 60 piksel). Majukan wajah agar proporsional di bingkai.";
    if (distanceStatus === "too_close") return "Wajah terlalu dekat. Mundurkan sedikit agar seluruh fitur wajah muat di bingkai.";
    if (ui.status === "need_blink") return "Deteksi keaktifan (Liveness): Kedipkan mata Anda sekali untuk membuka pose depan.";
    if (ui.status === "adjust") {
      if (pose.angle === "right") return "Belum cukup menoleh — putar kepala ke KANAN sekitar 25°-30° sampai bingkai hijau…";
      if (pose.angle === "left") return "Belum cukup menoleh — putar kepala ke KIRI sekitar 25°-30° sampai bingkai hijau…";
      return "Hadapkan wajah lurus menghadap kamera…";
    }
    if (ui.status === "hold") return "Posisi tepat! Tahan sebentar jangan bergerak…";
    return "Posisikan wajah di dalam bingkai oval dan ikuti petunjuk pose.";
  };

  return (
    <div className="w-full flex flex-col items-center gap-4 sm:gap-6" data-testid="face-scanner">
      {/* Live Distance & Biometric Status Badge */}
      <div className="inline-flex max-w-full flex-wrap items-center justify-center gap-1.5 sm:gap-2 rounded-full bg-slate-800/90 border border-slate-700 px-3 sm:px-4 py-1.5 text-center backdrop-blur-md shadow-xs">
        <ShieldCheck className="size-3.5 sm:size-4 text-emerald-400 shrink-0" />
        <span className="font-mono text-[10.5px] sm:text-[11px] text-slate-300">
          Jarak:{" "}
          <span
            className={
              distanceStatus === "too_far" || distanceStatus === "too_close"
                ? "text-amber-400 font-bold"
                : "text-emerald-400 font-bold"
            }
          >
            {distanceStatus === "too_far"
              ? "Terlalu Jauh (Dekatkan)"
              : distanceStatus === "too_close"
              ? "Terlalu Dekat (Mundurkan)"
              : "Optimal"}
          </span>
        </span>
      </div>

      {/* Camera Container with Clean KYC Guide Frame — no protruding outer circle */}
      <div className="w-full max-w-[300px] sm:max-w-[380px] flex flex-col items-center gap-3">
        <div
          className={`relative w-full aspect-[4/5] rounded-[24px] overflow-hidden bg-neutral-900 border-2 transition-all duration-300 shadow-2xl ${
            ui.status === "hold" || done
              ? "border-emerald-400 shadow-[0_0_24px_rgba(52,211,153,0.35)]"
              : failed
              ? "border-red-500/80 shadow-[0_0_20px_rgba(239,68,68,0.25)]"
              : distanceStatus !== "ok"
              ? "border-amber-400/80"
              : "border-white/20"
          }`}
        >
          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            onLoadedData={() => setCamReady(true)}
            className="w-full h-full object-cover -scale-x-100"
            data-testid="scanner-video"
          />

          {/* Shutter flash effect */}
          <div
            className={`absolute inset-0 bg-white pointer-events-none transition-opacity duration-200 ${
              flash ? "opacity-80" : "opacity-0"
            }`}
            data-testid="shutter-flash"
          />

          {/* Loading spinner */}
          {(lmStatus === "loading" || !camReady) && (
            <div className="absolute inset-0 grid place-items-center bg-black/60 text-white">
              <Loader2 className="w-8 h-8 animate-spin" />
            </div>
          )}

          {/* OVERLAY BINGKAI PANDUAN WAJAH (OVAL / FRAME) — proportional % so it fits every phone */}
          <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
            <div
              className={`w-[64%] h-[68%] rounded-[50%] border-2 transition-colors duration-300 ${
                ui.status === "hold" || done
                  ? "border-emerald-400 shadow-[0_0_20px_rgba(52,211,153,0.45)] bg-emerald-500/5"
                  : distanceStatus !== "ok"
                  ? "border-amber-400/85 border-dashed"
                  : "border-sky-400/80 border-dashed shadow-[0_0_15px_rgba(56,189,248,0.2)]"
              }`}
            >
              <div className="relative w-full h-full">
                <div className="absolute top-2 left-1/2 -translate-x-1/2 w-7 sm:w-8 h-1 bg-white/50 rounded-full" />
                <div className="absolute bottom-2 left-1/2 -translate-x-1/2 w-7 sm:w-8 h-1 bg-white/50 rounded-full" />
                <div className="absolute top-1/2 left-2 -translate-y-1/2 w-1 h-7 sm:h-8 bg-white/50 rounded-full" />
                <div className="absolute top-1/2 right-2 -translate-y-1/2 w-1 h-7 sm:h-8 bg-white/50 rounded-full" />
              </div>
            </div>
          </div>

          {/* Bottom inside pill */}
          <div className="absolute inset-x-0 bottom-3 flex justify-center pointer-events-none">
            <div
              className="whitespace-nowrap font-mono text-[11px] sm:text-xs text-emerald-300 bg-black/75 backdrop-blur-md px-3.5 py-1 rounded-full border border-emerald-500/40 shadow-lg"
              data-testid="scanner-percent"
            >
              Pose {Math.min(ui.stage + 1, 3)} dari 3 ({Math.round(progress * 100)}%)
            </div>
          </div>
        </div>

        {/* Sleek Linear Progress Bar directly below camera */}
        <div className="w-full h-2 rounded-full bg-white/10 overflow-hidden" data-testid="scanner-progress-bar">
          <div
            className="h-full rounded-full bg-emerald-400 transition-all duration-150"
            style={{ width: `${Math.min(100, Math.round(progress * 100))}%` }}
          />
        </div>
      </div>

      {/* Instructions & Quality Feedback */}
      <div className="text-center min-h-[76px] w-full max-w-lg px-1 sm:px-4 pt-1">
        <h2
          className="font-display text-[19px] sm:text-3xl font-bold sm:font-black leading-snug tracking-tight text-white flex flex-wrap items-center justify-center gap-2"
          data-testid="scanner-instruction"
        >
          {ui.status === "need_blink" && <Eye className="size-5 sm:size-6 text-sky-400 animate-pulse inline shrink-0" />}
          {failed && <AlertCircle className="size-5 sm:size-6 text-red-400 inline shrink-0" />}
          <span>{getInstruction()}</span>
        </h2>
        <p
          className={`mt-2 text-[11.5px] sm:text-sm font-mono leading-relaxed break-words ${
            failed ? "text-red-200 font-semibold bg-red-950/70 p-3 rounded-xl border border-red-800/80" : "text-slate-300"
          }`}
          data-testid="scanner-status"
        >
          {getSubtext()}
        </p>
      </div>

      {/* Manual Snap Trigger for current pose */}
      {!done && !busy && camReady && (
        <button
          type="button"
          onClick={capture}
          data-testid="manual-snap-button"
          className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 sm:py-2.5 rounded-full bg-sky-600 hover:bg-sky-500 text-white text-[13px] sm:text-xs font-semibold shadow-lg transition-all active:scale-95 cursor-pointer"
        >
          <Camera className="size-4" />
          <span>Ambil Foto Pose {pose.short}</span>
        </button>
      )}

      {/* Pose indicators */}
      <PoseBadges shots={ui.shots} stage={ui.stage} />
    </div>
  );
};

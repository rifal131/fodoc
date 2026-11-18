import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  RotateCcw,
  ShieldAlert,
  CheckCircle2,
  Camera,
  Upload,
  Loader2,
  AlertTriangle,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { POSES } from "@/components/enroll/poses";
import { FaceScanner } from "@/components/enroll/FaceScanner";
import { UploadSlots } from "@/components/enroll/UploadSlots";
import { StackedCard } from "@/components/StackedCard";

const SLOT_TAGS = [
  { angle: "front", label: "Tampak Depan", tag: "[Tampak Depan]" },
  { angle: "right", label: "Menoleh ke Kanan", tag: "[Menoleh ke Kanan]" },
  { angle: "left", label: "Menoleh ke Kiri", tag: "[Menoleh ke Kiri]" },
];

/** Pecah pesan error backend bertag [Tampak Depan] / [Menoleh ke Kanan] / [Menoleh ke Kiri] menjadi error per slot */
function parseSlotErrors(msg) {
  if (!msg || typeof msg !== "string") return {};
  const result = {};
  const cleaned = msg.replace(/^Verifikasi gagal pada \d+ pose:\s*/i, "");
  const segments = cleaned.split(/\s*\|\s*/);

  for (const seg of segments) {
    const matched = SLOT_TAGS.filter((s) => seg.includes(s.tag));
    if (matched.length > 0) {
      let text = seg;
      matched.forEach((m) => {
        text = text.replace(m.tag, "");
      });
      text = text.trim();
      matched.forEach((m) => {
        result[m.angle] = text || seg.trim();
      });
    }
  }
  return result;
}

/** Perkecil foto galeri HP beresolusi besar (mis. 4000x3000) agar unggah cepat & bebas timeout 504 */
function resizeImageForUpload(fileOrBlob, maxDim = 1280) {
  return new Promise((resolve) => {
    if (!fileOrBlob || fileOrBlob.size <= 650 * 1024) {
      resolve(fileOrBlob);
      return;
    }
    const url = URL.createObjectURL(fileOrBlob);
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(url);
      const { naturalWidth: w, naturalHeight: h } = img;
      const scale = Math.min(1, maxDim / Math.max(w, h));
      const tw = Math.max(1, Math.round(w * scale));
      const th = Math.max(1, Math.round(h * scale));
      const canvas = document.createElement("canvas");
      canvas.width = tw;
      canvas.height = th;
      const ctx = canvas.getContext("2d");
      if (!ctx) {
        resolve(fileOrBlob);
        return;
      }
      ctx.drawImage(img, 0, 0, tw, th);
      canvas.toBlob(
        (out) => resolve(out || fileOrBlob),
        "image/jpeg",
        0.9
      );
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      resolve(fileOrBlob);
    };
    img.src = url;
  });
}

export default function Enroll() {
  const { refresh } = useAuth();
  const nav = useNavigate();
  const [mode, setMode] = useState("camera"); // "camera" | "upload"
  const [enrolled, setEnrolled] = useState(false);
  const [needsReEnroll, setNeedsReEnroll] = useState(false);
  const [busy, setBusy] = useState(false);
  const [scanKey, setScanKey] = useState(0);
  const [failed, setFailed] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [slotErrors, setSlotErrors] = useState({});
  const [uploadShots, setUploadShots] = useState({ front: null, right: null, left: null });
  const uploadShotsRef = useRef(uploadShots);
  uploadShotsRef.current = uploadShots;
  const uploadCardRef = useRef(null);

  const loadStatus = async () => {
    try {
      const { data } = await api.get("/enrollment/status");
      setEnrolled(data.enrolled);
      setNeedsReEnroll(data.needs_re_enrollment);
    } catch {}
  };

  useEffect(() => {
    loadStatus();
    return () => {
      Object.values(uploadShotsRef.current).forEach((s) => {
        if (s?.url) URL.revokeObjectURL(s.url);
      });
    };
  }, []);

  const switchMode = (nextMode) => {
    if (busy || nextMode === mode) return;
    setMode(nextMode);
    setFailed(false);
    setErrorMessage("");
    setSlotErrors({});
  };

  const handlePickUpload = (angle, file) => {
    if (!file.type.startsWith("image/")) {
      toast.error("Format file harus berupa gambar (JPG, PNG, atau WebP).");
      return;
    }
    if (file.size > 20 * 1024 * 1024) {
      toast.error("Ukuran foto maksimal 20 MB per slot.");
      return;
    }
    // Hapus error khusus slot ini saja supaya slot lain yang masih salah tetap terlihat jelas
    setSlotErrors((prev) => {
      const next = { ...prev };
      delete next[angle];
      if (Object.keys(next).length === 0) {
        setFailed(false);
        setErrorMessage("");
      }
      return next;
    });
    setUploadShots((prev) => {
      if (prev[angle]?.url) URL.revokeObjectURL(prev[angle].url);
      return {
        ...prev,
        [angle]: {
          blob: file,
          url: URL.createObjectURL(file),
          name: file.name,
        },
      };
    });
  };

  const handleRemoveUpload = (angle) => {
    setSlotErrors((prev) => {
      const next = { ...prev };
      delete next[angle];
      if (Object.keys(next).length === 0) {
        setFailed(false);
        setErrorMessage("");
      }
      return next;
    });
    setUploadShots((prev) => {
      if (prev[angle]?.url) URL.revokeObjectURL(prev[angle].url);
      return { ...prev, [angle]: null };
    });
  };

  const handleClearUploads = () => {
    setFailed(false);
    setErrorMessage("");
    setSlotErrors({});
    setUploadShots((prev) => {
      Object.values(prev).forEach((s) => {
        if (s?.url) URL.revokeObjectURL(s.url);
      });
      return { front: null, right: null, left: null };
    });
  };

  const submit = async (shots) => {
    setBusy(true);
    setFailed(false);
    setErrorMessage("");
    setSlotErrors({});
    try {
      const fd = new FormData();
      for (const p of POSES) {
        const entry = shots[p.angle];
        if (entry?.blob) {
          const optimized = await resizeImageForUpload(entry.blob, 1280);
          const filename = entry.name ? `${p.angle}.jpg` : `${p.angle}.jpg`;
          fd.append(p.angle, optimized, filename);
        }
      }

      await api.post("/auth/enroll-face", fd, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 90000,
      });

      await refresh();
      toast.success("Verifikasi 3 pose profil wajah berhasil!");
      nav("/");
    } catch (err) {
      const status = err.response?.status;
      let msg = err.response?.data?.detail || "";
      if (!msg) {
        if (status === 504 || status === 502 || err.code === "ECONNABORTED") {
          msg = "Server membutuhkan waktu terlalu lama saat memproses foto (timeout). Silakan coba tekan tombol verifikasi sekali lagi.";
        } else {
          msg = err.message || "Verifikasi wajah gagal";
        }
      }
      const parsedSlots = parseSlotErrors(msg);
      setErrorMessage(msg);
      setSlotErrors(parsedSlots);
      toast.error(msg, { duration: 7000 });
      setFailed(true);
      if (mode === "upload" && uploadCardRef.current) {
        setTimeout(() => {
          uploadCardRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 50);
      }
    } finally {
      setBusy(false);
    }
  };

  const uploadReadyCount = POSES.filter((p) => !!uploadShots[p.angle]).length;
  const canSubmitUpload = uploadReadyCount === 3 && !busy;
  const slotErrorEntries = SLOT_TAGS.filter((s) => slotErrors[s.angle]);

  return (
    <div className="bg-[#F5F5F2] min-h-[calc(100vh-4rem)] py-6 sm:py-12" data-testid="enroll-page">
      <div className="max-w-[780px] mx-auto px-3.5 sm:px-8">
        <div className="text-center mb-6 sm:mb-7">
          <div className="font-mono text-[11px] sm:text-[12px] text-[#8F8E8B] mb-2">
            Verifikasi Wajah Terstandar · 3 Pose (Depan, Kanan, Kiri)
          </div>
          <h1 className="text-[26px] sm:text-[38px] font-normal leading-[1.15] tracking-[-0.025em] text-[#171717]">
            Verifikasi <span className="text-[#8F8E8B]">Profil Wajah</span>
          </h1>
          <p className="text-[#6E6D6A] text-[13.5px] sm:text-[14px] mt-2 max-w-lg mx-auto">
            Rekam langsung lewat kamera atau unggah 3 foto wajah berbeda:{" "}
            <span className="text-[#171717] font-medium">(1) Depan</span>,{" "}
            <span className="text-[#171717] font-medium">(2) Kanan</span>, dan{" "}
            <span className="text-[#171717] font-medium">(3) Kiri</span>.
          </p>
        </div>

        {/* Mode Switcher: Kamera Langsung vs Unggah 3 Foto */}
        <div className="flex justify-center mb-5 sm:mb-6">
          <div
            className="grid grid-cols-2 sm:inline-flex w-full sm:w-auto items-center p-1 rounded-full bg-white border border-black/10 shadow-xs"
            role="tablist"
            aria-label="Metode Verifikasi Wajah"
          >
            <button
              type="button"
              role="tab"
              aria-selected={mode === "camera"}
              onClick={() => switchMode("camera")}
              disabled={busy}
              data-testid="enroll-mode-camera"
              className={`inline-flex items-center justify-center gap-1.5 sm:gap-2 rounded-full px-3 sm:px-4 py-2 text-[12.5px] sm:text-[13px] font-medium transition-all cursor-pointer ${
                mode === "camera"
                  ? "bg-[#171717] text-white shadow-xs"
                  : "text-[#6E6D6A] hover:text-[#171717]"
              }`}
            >
              <Camera className="size-3.5 shrink-0" />
              <span>Kamera Langsung</span>
            </button>
            <button
              type="button"
              role="tab"
              aria-selected={mode === "upload"}
              onClick={() => switchMode("upload")}
              disabled={busy}
              data-testid="enroll-mode-upload"
              className={`inline-flex items-center justify-center gap-1.5 sm:gap-2 rounded-full px-3 sm:px-4 py-2 text-[12.5px] sm:text-[13px] font-medium transition-all cursor-pointer ${
                mode === "upload"
                  ? "bg-[#171717] text-white shadow-xs"
                  : "text-[#6E6D6A] hover:text-[#171717]"
              }`}
            >
              <Upload className="size-3.5 shrink-0" />
              <span>Unggah 3 Foto</span>
            </button>
          </div>
        </div>

        {needsReEnroll && !busy && (
          <div
            className="mb-6 rounded-[14px] bg-amber-50 border border-amber-200 p-4 text-amber-900 text-[13px] flex items-start gap-3"
            data-testid="needs-re-enrollment-banner"
          >
            <ShieldAlert className="size-5 text-amber-700 shrink-0 mt-0.5" />
            <div>
              <div className="font-medium mb-0.5">Perlu Registrasi Ulang Wajah</div>
              <p className="text-[12.5px] text-amber-800/90 leading-relaxed">
                Profil acuan wajib memiliki tepat 3 pose seimbang (Depan, Kanan, dan Kiri). Silakan lengkapi melalui kamera langsung atau unggah 3 foto di bawah ini.
              </p>
            </div>
          </div>
        )}

        {enrolled && !needsReEnroll && !busy && (
          <div className="mb-6 flex justify-center">
            <div
              className="inline-flex items-center gap-2 rounded-full bg-emerald-50 border border-emerald-200 text-emerald-800 font-mono text-[12px] px-4 py-1.5"
              data-testid="already-enrolled-badge"
            >
              <CheckCircle2 className="size-3.5 shrink-0" /> 3 Pose Terdaftar — Anda dapat memperbarui kapan saja
            </div>
          </div>
        )}

        {mode === "camera" ? (
          <StackedCard
            accent="cyan"
            category="Kamera Verifikasi"
            meta="3 Pose"
            bodyClassName="p-4 sm:p-8 bg-[#171717] text-white border-black/20"
          >
            <div className="flex flex-col items-center">
              <FaceScanner
                key={scanKey}
                onComplete={submit}
                busy={busy}
                failed={failed}
                errorMessage={errorMessage}
              />

              {failed && (
                <button
                  onClick={() => {
                    setFailed(false);
                    setErrorMessage("");
                    setSlotErrors({});
                    setScanKey((k) => k + 1);
                  }}
                  data-testid="rescan-button"
                  className="mt-6 sm:mt-8 w-full sm:w-auto inline-flex items-center justify-center gap-2 rounded-[10px] bg-white text-[#171717] hover:bg-[#F5F5F2] font-medium text-[13px] px-5 py-2.5 transition-colors shadow-md cursor-pointer"
                >
                  <RotateCcw className="size-4" /> Ambil Ulang Pose Kamera
                </button>
              )}
            </div>
          </StackedCard>
        ) : (
          <div ref={uploadCardRef} className="scroll-mt-20">
            <StackedCard
              accent="emerald"
              category="Unggah Foto Verifikasi"
              meta="Depan · Kanan · Kiri"
              bodyClassName="p-4 sm:p-7 bg-[#FCFCFA]"
            >
              <div className="space-y-6">
                {failed && errorMessage && (
                  <div
                    className="rounded-[12px] bg-red-50 border border-red-200 p-4 text-red-900 flex items-start gap-3"
                    data-testid="upload-error-banner"
                  >
                    <AlertTriangle className="size-5 text-red-600 shrink-0 mt-0.5" />
                    <div className="min-w-0 flex-1">
                      <div className="text-[13.5px] font-semibold text-red-800 mb-1">
                        Verifikasi Gagal — Silakan Upload Ulang Foto yang Salah
                      </div>
                      {slotErrorEntries.length > 0 ? (
                        <ul className="space-y-1.5 text-[12.5px] text-red-800/95 leading-relaxed list-disc pl-4">
                          {slotErrorEntries.map((s) => (
                            <li key={s.angle}>
                              <span className="font-semibold">Slot {s.label}:</span> {slotErrors[s.angle]}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="text-[12.5px] text-red-800/90 leading-relaxed break-words">
                          {errorMessage}
                        </p>
                      )}
                    </div>
                  </div>
                )}

                <UploadSlots
                  shots={uploadShots}
                  onPick={handlePickUpload}
                  onRemove={handleRemoveUpload}
                  slotErrors={slotErrors}
                  disabled={busy}
                />

                <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-3 pt-4 border-t border-black/[0.07]">
                  <button
                    type="button"
                    onClick={handleClearUploads}
                    disabled={busy || uploadReadyCount === 0}
                    data-testid="upload-reset-button"
                    className="inline-flex items-center justify-center gap-2 rounded-[10px] border border-black/15 bg-white hover:bg-[#F5F5F2] text-[#52524E] font-medium text-[13px] px-4 py-2.5 transition-colors disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                  >
                    <Trash2 className="size-4" />
                    Hapus Semua Pilihan
                  </button>

                  <button
                    type="button"
                    onClick={() => submit(uploadShots)}
                    disabled={!canSubmitUpload}
                    data-testid="upload-submit-button"
                    className="cta-btn-dark inline-flex items-center justify-center gap-2 px-6 py-2.5 text-[13.5px] disabled:opacity-45 disabled:cursor-not-allowed disabled:transform-none"
                  >
                    {busy ? (
                      <>
                        <Loader2 className="size-4 animate-spin" />
                        Memeriksa Arah &amp; Kualitas Foto…
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="size-4" />
                        Verifikasi &amp; Simpan 3 Pose
                      </>
                    )}
                  </button>
                </div>
              </div>
            </StackedCard>
          </div>
        )}
      </div>
    </div>
  );
}

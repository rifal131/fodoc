import { ScanFace, ArrowRight, ArrowLeft } from "lucide-react";

// 3 Pose Registrasi Terstandar (non-overlapping yaw ranges agar wajib menoleh dulu):
// - Depan : 0.40 <= yaw <= 0.60 (+ kedip mata)
// - Kanan : yaw <= 0.33 (menoleh jelas ke kanan ~20°-35°)
// - Kiri  : yaw >= 0.67 (menoleh jelas ke kiri ~20°-35°)
export const POSES = [
  {
    angle: "front",
    label: "Hadap Depan (Kedip Mata)",
    short: "Depan",
    instruction: "Hadap Lurus ke Kamera & Kedipkan Mata",
    hint: "Posisikan wajah lurus di dalam bingkai oval, lalu kedipkan mata sekali.",
    Icon: ScanFace,
    requiresBlink: true,
    match: (y) => y >= 0.40 && y <= 0.60,
  },
  {
    angle: "right",
    label: "Hadap Kanan",
    short: "Kanan",
    instruction: "Tengok ke Kanan & Tahan",
    hint: "Putar kepala Anda ke arah kanan (sekitar 20°-30°), lalu tahan sebentar.",
    Icon: ArrowRight,
    requiresBlink: false,
    match: (y) => y <= 0.33,
  },
  {
    angle: "left",
    label: "Hadap Kiri",
    short: "Kiri",
    instruction: "Tengok ke Kiri & Tahan",
    hint: "Putar kepala Anda ke arah kiri (sekitar 20°-30°), lalu tahan sebentar.",
    Icon: ArrowLeft,
    requiresBlink: false,
    match: (y) => y >= 0.67,
  },
];

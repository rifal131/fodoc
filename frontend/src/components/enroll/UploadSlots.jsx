import { ImagePlus, CheckCircle2, AlertCircle, X, Info, RefreshCw } from "lucide-react";
import { POSES } from "./poses";

const UPLOAD_META = {
  front: {
    title: "Tampak Depan",
    direction: "Menghadap lurus ke kamera",
    errorMatch: "[Tampak Depan]",
  },
  right: {
    title: "Menoleh ke Kanan",
    direction: "Kepala menoleh jelas ke kanan (20°–35°)",
    errorMatch: "[Menoleh ke Kanan]",
  },
  left: {
    title: "Menoleh ke Kiri",
    direction: "Kepala menoleh jelas ke kiri (20°–35°)",
    errorMatch: "[Menoleh ke Kiri]",
  },
};

export const UploadSlots = ({
  shots,
  onPick,
  onRemove,
  slotErrors = {},
  disabled = false,
}) => {
  const filledCount = POSES.filter((p) => !!shots[p.angle]).length;

  return (
    <div className="w-full space-y-5" data-testid="upload-slots">
      {/* Header status */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-[12px] text-[#6E6D6A]">
          Kelengkapan 3 Pose Wajah
        </span>
        <span
          className={`font-mono text-[11px] font-medium px-3 py-1 rounded-full border ${
            filledCount === 3
              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
              : "bg-[#F5F5F2] text-[#6E6D6A] border-black/10"
          }`}
        >
          {filledCount} dari 3 Foto Siap
        </span>
      </div>

      {/* Rules banner */}
      <div className="rounded-[12px] bg-[#F5F5F2] border border-black/[0.08] px-3.5 py-3 flex items-start gap-2.5 text-[12.5px] text-[#52524E] leading-relaxed">
        <Info className="size-4 text-[#171717] shrink-0 mt-0.5" />
        <div>
          Unggah <span className="font-semibold text-[#171717]">3 foto berbeda</span> yang sesuai arah masing-masing slot:{" "}
          <span className="font-medium text-[#171717]">Depan</span> (lurus),{" "}
          <span className="font-medium text-[#171717]">Kanan</span> (menoleh ke kanan), dan{" "}
          <span className="font-medium text-[#171717]">Kiri</span> (menoleh ke kiri). Jika ada slot yang salah arah atau duplikat, kartu tersebut akan ditandai merah agar langsung bisa diunggah ulang.
        </div>
      </div>

      {/* 3 Upload Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {POSES.map((p, idx) => {
          const shot = shots[p.angle];
          const isFilled = !!shot;
          const meta = UPLOAD_META[p.angle];
          const slotErrorText = slotErrors[p.angle] || "";
          const hasSlotError = Boolean(slotErrorText);
          const Icon = p.Icon;

          return (
            <div
              key={p.angle}
              data-testid={`upload-slot-${p.angle}`}
              className={`group relative rounded-[14px] border overflow-hidden transition-all flex flex-col bg-white ${
                hasSlotError
                  ? "border-red-500 ring-2 ring-red-100"
                  : isFilled
                  ? "border-emerald-400/80 ring-1 ring-emerald-200/70"
                  : "border-dashed border-black/20 hover:border-[#171717]"
              }`}
            >
              {isFilled && !disabled && onRemove && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    onRemove(p.angle);
                  }}
                  title={`Hapus foto ${meta.title}`}
                  data-testid={`upload-remove-${p.angle}`}
                  className="absolute top-2 left-2 z-20 size-7 rounded-full bg-[#171717]/80 hover:bg-[#171717] text-white grid place-items-center transition-colors cursor-pointer shadow-sm"
                >
                  <X className="size-3.5" />
                </button>
              )}

              <label
                className={`block flex-1 flex flex-col ${
                  disabled ? "pointer-events-none opacity-70" : "cursor-pointer"
                }`}
              >
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  disabled={disabled}
                  className="hidden"
                  data-testid={`upload-input-${p.angle}`}
                  onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) onPick(p.angle, file);
                    e.target.value = "";
                  }}
                />

                <div className="aspect-[4/3] w-full bg-[#ECECE8] grid place-items-center overflow-hidden relative">
                  {isFilled ? (
                    <>
                      <img
                        src={shot.url}
                        alt={meta.title}
                        className="w-full h-full object-contain"
                      />
                      <div
                        className={`absolute top-2 right-2 px-2.5 py-0.5 rounded-full font-mono text-[10.5px] font-medium flex items-center gap-1 shadow-sm ${
                          hasSlotError
                            ? "bg-red-600 text-white"
                            : "bg-emerald-600 text-white"
                        }`}
                      >
                        {hasSlotError ? (
                          <>
                            <AlertCircle className="size-3" />
                            <span>Salah · Upload Ulang</span>
                          </>
                        ) : (
                          <>
                            <CheckCircle2 className="size-3" />
                            <span>Siap</span>
                          </>
                        )}
                      </div>
                    </>
                  ) : (
                    <div className="text-center px-4 py-5">
                      <div className="size-10 rounded-[10px] bg-white border border-black/10 text-[#171717] grid place-items-center mx-auto mb-2.5 shadow-xs group-hover:bg-[#171717] group-hover:text-white transition-colors">
                        <Icon className="size-4" />
                      </div>
                      <div className="text-[13px] font-semibold text-[#171717] mb-1">
                        {idx + 1}. {meta.title}
                      </div>
                      <p className="text-[11.5px] text-[#6E6D6A] leading-snug">
                        {meta.direction}
                      </p>
                      <span className="inline-flex items-center gap-1.5 text-[11.5px] text-[#171717] font-medium mt-3 px-2.5 py-1 rounded-full bg-white border border-black/15 shadow-xs">
                        <ImagePlus className="size-3.5" /> Pilih Foto
                      </span>
                    </div>
                  )}
                </div>

                {/* Alasan spesifik error langsung di dalam kartu slot yang salah */}
                {hasSlotError && (
                  <div className="px-3 py-2.5 bg-red-50 border-t border-red-200 text-red-800 space-y-2">
                    <p className="text-[11.5px] leading-snug font-medium">
                      {slotErrorText}
                    </p>
                    <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-[8px] bg-red-600 text-white text-[11px] font-semibold shadow-xs">
                      <RefreshCw className="size-3" />
                      <span>Upload Ulang Foto {p.short}</span>
                    </div>
                  </div>
                )}

                <div
                  className={`border-t px-3 py-2.5 flex items-center justify-between text-[11.5px] mt-auto ${
                    hasSlotError
                      ? "bg-red-50/70 border-red-200 text-red-900"
                      : "bg-[#FCFCFA] border-black/[0.06] text-[#171717]"
                  }`}
                >
                  <span className="font-semibold">
                    {idx + 1}. {meta.title}
                  </span>
                  <span className="font-mono text-[11px] text-[#6E6D6A]">
                    {hasSlotError ? "Perlu ganti" : isFilled ? "Ganti foto" : "Wajib"}
                  </span>
                </div>
              </label>
            </div>
          );
        })}
      </div>

      {/* Tips kecil tentang selfie mirror */}
      <p className="text-[11.5px] text-[#8F8E8B] leading-relaxed">
        Catatan: Pastikan pencahayaan terang, wajah terlihat jelas (tidak buram), hanya 1 orang di dalam foto, dan arah menoleh sesuai perintah. Jika memakai kamera depan HP dengan fitur cermin (mirror) aktif, arah kanan/kiri pada galeri bisa terbalik.
      </p>
    </div>
  );
};

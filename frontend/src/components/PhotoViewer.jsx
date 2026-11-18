import { useEffect, useRef, useState } from "react";
import api, { fileSrc } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { X, UserX, Download, Eye, EyeOff } from "lucide-react";
import { toast } from "sonner";

export default function PhotoViewer({ photoId, onClose, onNotMyPhoto }) {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [reporting, setReporting] = useState(false);
  const [showBoxes, setShowBoxes] = useState(true);
  const imgRef = useRef(null);
  const [imgSize, setImgSize] = useState({ w: 0, h: 0, nw: 1, nh: 1 });

  useEffect(() => {
    api.get(`/photos/${photoId}`).then(({ data }) => setData(data));
  }, [photoId]);

  const onImgLoad = () => {
    if (!imgRef.current) return;
    const el = imgRef.current;
    setImgSize({
      w: el.clientWidth,
      h: el.clientHeight,
      nw: el.naturalWidth || 1,
      nh: el.naturalHeight || 1,
    });
  };

  const handleNotMe = async () => {
    if (
      !window.confirm(
        "Tandai foto ini sebagai BUKAN FOTO ANDA? Foto ini akan dikeluarkan dari galeri pribadi Anda dan dicatat untuk evaluasi false acceptance sistem."
      )
    ) {
      return;
    }
    setReporting(true);
    try {
      await api.post(`/photos/${photoId}/not-me`);
      toast.success("Foto ditandai bukan milik Anda dan dikeluarkan dari galeri.");
      if (onNotMyPhoto) onNotMyPhoto(photoId);
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || "Gagal menandai foto");
    } finally {
      setReporting(false);
    }
  };

  const handleDownload = async () => {
    if (!data?.url) return;
    try {
      const src = fileSrc(data.url);
      const res = await fetch(src);
      const blob = await res.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = blobUrl;
      link.download = data.original_filename || `foto_fodoc_${photoId.slice(0, 8)}.jpg`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(blobUrl);
      toast.success("Foto resolusi asli berhasil diunduh");
    } catch {
      const link = document.createElement("a");
      link.href = fileSrc(data.url);
      link.download = data.original_filename || `foto_fodoc_${photoId.slice(0, 8)}.jpg`;
      link.target = "_blank";
      link.click();
    }
  };

  const nw = data?.image_width || imgSize.nw || 1;
  const nh = data?.image_height || imgSize.nh || 1;

  const matchByFaceId = {};
  (data?.matches || []).forEach((m) => {
    matchByFaceId[m.face_id] = m;
  });

  const isStudent = user?.role === "mahasiswa";

  // PRIVASI MAHASISWA: Mahasiswa HANYA boleh melihat kecocokan dirinya sendiri!
  const displayMatches = (data?.matches || []).filter((m) => {
    if (isStudent) {
      return (
        m.status === "COCOK" &&
        (m.user_id === user?.id || m.name === user?.name)
      );
    }
    return true;
  });

  return (
    <div
      className="fixed inset-0 z-50 bg-black/75 backdrop-blur-md flex items-center justify-center p-2 sm:p-6"
      data-testid="photo-viewer"
    >
      <div className="relative max-w-[1160px] w-full max-h-[94vh] sm:max-h-[90vh] bg-[#FCFCFA] rounded-[16px] sm:rounded-[20px] border border-black/[0.12] shadow-2xl overflow-y-auto lg:overflow-hidden flex flex-col lg:grid lg:grid-cols-[1fr_340px]">
        {/* Left: Dark Charcoal Image Stage */}
        <div className="relative bg-[#141413] flex flex-col min-h-0">
          {/* Clean Top Toolbar (never overlaps photo or close button on mobile) */}
          <div className="flex items-center justify-between gap-2 px-3 py-2.5 sm:px-4 sm:py-3 bg-[#141413] border-b border-white/10 shrink-0">
            <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 min-w-0">
              <button
                onClick={() => setShowBoxes((v) => !v)}
                className="inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-[9px] bg-white/10 hover:bg-white/15 text-white text-[11.5px] sm:text-[12px] font-medium border border-white/15 transition-colors cursor-pointer"
              >
                {showBoxes ? (
                  <>
                    <EyeOff className="size-3.5 text-amber-300 shrink-0" />
                    <span className="hidden sm:inline">Sembunyikan Kotak</span>
                    <span className="sm:hidden">Sembunyikan</span>
                  </>
                ) : (
                  <>
                    <Eye className="size-3.5 text-emerald-400 shrink-0" />
                    <span className="hidden sm:inline">Tampilkan Kotak</span>
                    <span className="sm:hidden">Tampilkan</span>
                  </>
                )}
              </button>

              <button
                onClick={handleDownload}
                className="inline-flex items-center gap-1.5 px-2.5 sm:px-3 py-1.5 rounded-[9px] bg-white hover:bg-[#F5F5F2] text-[#171717] text-[11.5px] sm:text-[12px] font-medium transition-colors shadow-sm cursor-pointer"
              >
                <Download className="size-3.5 shrink-0" />
                <span>Unduh Asli</span>
              </button>
            </div>

            <button
              onClick={onClose}
              data-testid="photo-viewer-close"
              aria-label="Tutup pratinjau"
              className="size-8 rounded-full bg-white/15 hover:bg-white/25 text-white grid place-items-center transition-colors cursor-pointer shrink-0"
            >
              <X className="size-4" />
            </button>
          </div>

          <div className="flex-1 flex items-center justify-center p-3 sm:p-4 min-h-[240px] sm:min-h-[320px] overflow-hidden">
            {data && (
              <div className="relative inline-block max-h-[52vh] lg:max-h-[78vh] max-w-full">
                <img
                  ref={imgRef}
                  src={fileSrc(data.url)}
                  onLoad={onImgLoad}
                  alt=""
                  className="max-h-[52vh] lg:max-h-[78vh] max-w-full w-auto h-auto block select-none rounded-[10px]"
                />

                {showBoxes &&
                  (data.faces || []).map((f) => {
                    const [x1, y1, x2, y2] = f.box;
                    const left = `${(x1 / nw) * 100}%`;
                    const top = `${(y1 / nh) * 100}%`;
                    const width = `${((x2 - x1) / nw) * 100}%`;
                    const height = `${((y2 - y1) / nh) * 100}%`;

                    const match = matchByFaceId[f.face_id];
                    const isHighlighted = isStudent
                      ? f.is_me === true || (match && (match.user_id === user?.id || match.name === user?.name))
                      : f.status === "COCOK" || (match && match.status === "COCOK");

                    const displayName = isStudent
                      ? user?.name || "Anda"
                      : match?.name || f.top1_name || "Mahasiswa";
                    const labelAbove = y1 / nh >= 0.06;

                    return (
                      <div
                        key={f.face_id}
                        className="group absolute pointer-events-auto rounded-[2px]"
                        style={{
                          left,
                          top,
                          width,
                          height,
                          borderWidth: 2,
                          borderStyle: "solid",
                          borderColor: isHighlighted ? "#16A34A" : "#EF4444",
                          boxShadow: isHighlighted ? "0 0 10px rgba(22, 163, 74, 0.55)" : "none",
                        }}
                        data-testid={`face-box-${f.face_id}`}
                      >
                        {isHighlighted && (
                          <div
                            className={`absolute left-0 font-mono text-[9.5px] sm:text-[10px] font-medium px-1.5 sm:px-2 py-0.5 whitespace-nowrap shadow-md pointer-events-none z-10 rounded-[3px] bg-emerald-600 text-white ${
                              labelAbove ? "-top-6" : "top-0"
                            }`}
                          >
                            {displayName}
                          </div>
                        )}
                      </div>
                    );
                  })}
              </div>
            )}
          </div>
        </div>

        {/* Right: Warm Paper Metadata Sidebar */}
        <aside className="p-4 sm:p-6 bg-[#F5F5F2] border-t lg:border-t-0 lg:border-l border-black/[0.08] lg:overflow-y-auto flex flex-col justify-between">
          <div className="space-y-6">
            <div>
              <span className="font-mono text-[11px] uppercase tracking-wider text-[#8F8E8B]">
                Informasi Citra
              </span>
              <h3 className="text-[20px] font-medium tracking-[-0.015em] text-[#171717] mt-1">
                Detail Pengenalan
              </h3>
            </div>

            <div className="space-y-2.5 bg-[#FCFCFA] p-4 rounded-[14px] border border-black/[0.08] text-[12.5px]">
              <div className="flex justify-between items-center">
                <span className="text-[#6E6D6A]">Status</span>
                <span className="font-mono text-[11px] text-emerald-800 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded-[6px] uppercase">
                  {data?.status || "DONE"}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-[#6E6D6A]">Total Wajah Terdeteksi</span>
                <span className="font-mono font-medium text-[#171717]">{data?.face_count ?? 0}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-[#6E6D6A]">
                  {isStudent ? "Verifikasi Wajah Anda" : "Mahasiswa Cocok"}
                </span>
                <span className="font-mono font-medium text-emerald-700">
                  {isStudent
                    ? displayMatches.length > 0
                      ? "COCOK (1)"
                      : "0"
                    : data?.match_count ?? 0}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-[#6E6D6A]">Kondisi Cahaya</span>
                <span className="capitalize text-[#171717]">{data?.condition || "Normal"}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-[#6E6D6A]">Restorasi Adaptif</span>
                <span className="text-[#171717]">{data?.used_restoration ? "Aktif" : "Tidak"}</span>
              </div>
            </div>

            <div>
              <div className="font-mono text-[11px] uppercase tracking-wider text-[#8F8E8B] mb-2.5">
                {isStudent ? "Identitas Anda Terverifikasi" : "Mahasiswa Teridentifikasi"}
              </div>
              <div className="space-y-2">
                {displayMatches.map((m) => (
                  <div
                    key={m.face_id}
                    className="bg-[#FCFCFA] rounded-[12px] border border-black/[0.08] p-3 flex items-center justify-between text-[13px]"
                  >
                    <div>
                      <div className="font-medium text-[#171717]">{m.name}</div>
                      {m.nim && <div className="font-mono text-[11px] text-[#8F8E8B] mt-0.5">{m.nim}</div>}
                    </div>
                    <div className="rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 font-mono text-[11.5px] font-medium px-2.5 py-0.5">
                      {(m.similarity * 100).toFixed(1)}% Cocok
                    </div>
                  </div>
                ))}
                {displayMatches.length === 0 && (
                  <div className="text-[12.5px] text-[#8F8E8B] italic">Belum ada kecocokan terverifikasi.</div>
                )}
              </div>
            </div>
          </div>

          {isStudent && (
            <div className="mt-8 pt-4 border-t border-black/[0.08]">
              <button
                onClick={handleNotMe}
                disabled={reporting}
                data-testid="not-my-photo-button"
                className="w-full py-2.5 px-4 rounded-[10px] border border-red-200 bg-red-50/80 text-red-700 hover:bg-red-100 font-medium text-[13px] transition-colors flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
              >
                <UserX className="size-4 text-red-600" />
                {reporting ? "Memproses..." : "Bukan Foto Saya"}
              </button>
              <p className="mt-2 text-[11px] text-[#8F8E8B] text-center leading-relaxed">
                Tandai jika sistem salah mengenali Anda. Foto akan dikeluarkan dari galeri dan dicatat untuk evaluasi.
              </p>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}

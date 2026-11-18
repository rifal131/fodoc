import { useEffect, useState } from "react";
import api, { fileSrc } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";
import { Check, X, AlertTriangle, UserCheck, ImageIcon, Eye } from "lucide-react";
import PhotoViewer from "@/components/PhotoViewer";
import { StackedCard } from "@/components/StackedCard";

export default function VerificationQueue() {
  const { user } = useAuth();
  const isStudent = user?.role === "mahasiswa";
  const [queue, setQueue] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activePhotoModal, setActivePhotoModal] = useState(null);
  const [processingId, setProcessingId] = useState(null);

  const loadQueue = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/verification/queue");
      setQueue(data);
    } catch {
      toast.error("Gagal memuat daftar konfirmasi foto");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadQueue();
  }, []);

  const handleConfirm = async (faceId, candidateName) => {
    setProcessingId(faceId);
    try {
      await api.post(`/verification/${faceId}/confirm`);
      toast.success(
        isStudent
          ? "Foto dikonfirmasi milik Anda dan langsung masuk ke Galeri Pribadi!"
          : `Wajah dikonfirmasi sebagai ${candidateName} dan didistribusikan ke galeri!`
      );
      setQueue((prev) => prev.filter((item) => item.face_id !== faceId));
    } catch (err) {
      toast.error(err.response?.data?.detail || "Gagal mengonfirmasi wajah");
    } finally {
      setProcessingId(null);
    }
  };

  const handleReject = async (faceId) => {
    setProcessingId(faceId);
    try {
      await api.post(`/verification/${faceId}/reject`);
      toast.success(isStudent ? "Foto ditandai bukan Anda dan dihapus dari daftar." : "Wajah ditolak (UNKNOWN).");
      setQueue((prev) => prev.filter((item) => item.face_id !== faceId));
    } catch (err) {
      toast.error(err.response?.data?.detail || "Gagal menolak wajah");
    } finally {
      setProcessingId(null);
    }
  };

  return (
    <div className="max-w-[1100px] mx-auto px-4 sm:px-8 py-7 sm:py-12" data-testid="verification-page">
      {/* Header */}
      <div className="mb-7 sm:mb-10 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="font-mono text-[11px] sm:text-[12px] text-[#8F8E8B] mb-2">
            {isStudent ? "Konfirmasi Mandiri Mahasiswa" : "Panel Evaluasi Admin"}
          </div>
          <h1 className="text-[26px] sm:text-[40px] font-normal leading-[1.15] tracking-[-0.025em] text-[#171717]">
            {isStudent ? (
              <>
                Konfirmasi <span className="text-[#8F8E8B]">Foto Anda</span>
              </>
            ) : (
              <>
                Antrean <span className="text-[#8F8E8B]">Verifikasi</span>
              </>
            )}
          </h1>
          <p className="text-[#6E6D6A] text-[13.5px] sm:text-[14px] mt-2 max-w-2xl">
            {isStudent ? (
              <>
                Sistem mendeteksi wajah yang mirip dengan Anda namun belum otomatis masuk galeri (<span className="font-mono text-[#171717] font-medium">PERLU_CEK</span>). Hanya Anda yang melihat daftar ini — pilih <strong>Ya, Ini Saya</strong> untuk memasukkannya ke Galeri Pribadi.
              </>
            ) : (
              <>
                Daftar seluruh wajah berstatus <span className="font-mono text-[#171717] font-medium">PERLU_CEK</span> yang sedang menunggu konfirmasi.
              </>
            )}
          </p>
        </div>

        <div className="self-start md:self-auto font-mono text-[11.5px] sm:text-[12px] text-[#6E6D6A] border border-black/[0.08] rounded-[10px] px-3.5 py-2 bg-[#FCFCFA]">
          {queue.length} {isStudent ? "foto perlu konfirmasi Anda" : "wajah menunggu tinjauan"}
        </div>
      </div>

      {/* Queue Grid */}
      {loading ? (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5 sm:gap-6">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="h-64 rounded-[16px] bg-black/[0.05] animate-pulse" />
          ))}
        </div>
      ) : queue.length === 0 ? (
        <StackedCard accent="green" category="Semua Terkonfirmasi" meta="0 menunggu" bodyClassName="p-8 sm:p-14 text-center items-center">
          <div className="size-12 rounded-[12px] bg-[#F5F5F2] border border-black/[0.08] text-emerald-700 grid place-items-center mb-4">
            <UserCheck className="size-5" />
          </div>
          <h3 className="text-[18px] sm:text-[19px] font-medium text-[#171717]">Tidak Ada Foto Menunggu Konfirmasi</h3>
          <p className="text-[13.5px] text-[#6E6D6A] mt-1 max-w-sm">
            {isStudent
              ? "Semua foto yang cocok sudah otomatis berada di Galeri Pribadi Anda."
              : "Tidak ada wajah dengan status PERLU_CEK saat ini."}
          </p>
        </StackedCard>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-7 sm:gap-y-10">
          {queue.map((item) => (
            <StackedCard
              key={item.face_id}
              data-testid={`verification-item-${item.face_id}`}
              accent="amber"
              category={item.event_name || "Acara Kampus"}
              meta={`${(item.score * 100).toFixed(1)}%`}
              bodyClassName="p-4 sm:p-5 flex flex-col justify-between"
            >
              <div>
                <div className="flex items-center gap-4 mb-4">
                  <div className="relative size-20 rounded-[12px] overflow-hidden bg-[#F5F5F2] border border-black/[0.1] shrink-0">
                    {item.crop_url ? (
                      <img src={fileSrc(item.crop_url)} alt="Potongan Wajah" className="w-full h-full object-cover" />
                    ) : (
                      <div className="w-full h-full grid place-items-center text-[#8F8E8B]">
                        <ImageIcon className="size-5" />
                      </div>
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <h3 className="text-[15px] font-medium leading-snug text-[#171717]">
                      {isStudent ? "Apakah ini wajah Anda?" : item.candidate_name}
                    </h3>
                    {!isStudent && item.candidate_nim && (
                      <div className="text-[12px] font-mono text-[#8F8E8B]">{item.candidate_nim}</div>
                    )}
                    <div className="mt-2 flex items-center gap-1.5 flex-wrap font-mono text-[11px]">
                      <span className="rounded-[6px] bg-amber-50 text-amber-800 border border-amber-200 px-2 py-0.5">
                        Kemiripan {(item.score * 100).toFixed(1)}%
                      </span>
                      {!isStudent && (
                        <span className="rounded-[6px] bg-black/[0.04] text-[#6E6D6A] px-2 py-0.5">
                          Gap {(item.selisih * 100).toFixed(1)}%
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {item.data_leakage && !isStudent && (
                  <div className="mb-3 p-2.5 rounded-[10px] bg-red-50 border border-red-200 text-red-700 text-[11.5px] flex items-center gap-2">
                    <AlertTriangle className="size-3.5 shrink-0" />
                    <span>Kemiripan ≥ 95% ke foto acuan (Indikasi Kebocoran Data).</span>
                  </div>
                )}

                <div className="grid grid-cols-2 gap-2 text-[11.5px] font-mono text-[#8F8E8B] bg-[#F5F5F2] border border-black/[0.06] p-2.5 rounded-[10px] mb-3">
                  <div>
                    Sisi: <span className="text-[#171717] font-medium">{item.min_side} px</span>
                  </div>
                  <div>
                    Tajam: <span className="text-[#171717] font-medium">{item.sharpness?.toFixed(1) || "—"}</span>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => setActivePhotoModal(item.photo_id)}
                  className="w-full font-mono text-[12px] text-[#6E6D6A] hover:text-[#171717] flex items-center justify-center gap-1.5 py-1.5 transition-colors cursor-pointer"
                >
                  <Eye className="size-3.5" />
                  <span>Lihat foto lengkap</span>
                </button>
              </div>

              <div className="mt-4 pt-4 border-t border-black/[0.06] flex items-center gap-2">
                <button
                  onClick={() => handleConfirm(item.face_id, item.candidate_name)}
                  disabled={processingId === item.face_id}
                  data-testid={`confirm-face-${item.face_id}`}
                  className="cta-btn-dark flex-1 py-2 px-3 text-[12.5px] flex items-center justify-center gap-1.5 disabled:opacity-50 cursor-pointer"
                >
                  <Check className="size-3.5" />
                  <span>{isStudent ? "Ya, Ini Saya" : "Konfirmasi"}</span>
                </button>

                <button
                  onClick={() => handleReject(item.face_id)}
                  disabled={processingId === item.face_id}
                  data-testid={`reject-face-${item.face_id}`}
                  className="cta-btn-light flex-1 py-2 px-3 text-[12.5px] flex items-center justify-center gap-1.5 hover:text-red-600 hover:border-red-200 disabled:opacity-50 cursor-pointer"
                >
                  <X className="size-3.5" />
                  <span>{isStudent ? "Bukan Saya" : "Tolak"}</span>
                </button>
              </div>
            </StackedCard>
          ))}
        </div>
      )}

      {activePhotoModal && (
        <PhotoViewer photoId={activePhotoModal} onClose={() => setActivePhotoModal(null)} />
      )}
    </div>
  );
}

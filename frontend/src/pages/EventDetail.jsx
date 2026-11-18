import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import api, { fileSrc, formatApiError } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Upload, CheckCircle2, Clock, AlertTriangle, Loader2, MapPin, Calendar, Image as ImageIcon } from "lucide-react";
import { toast } from "sonner";
import PhotoViewer from "@/components/PhotoViewer";
import { StackedCard } from "@/components/StackedCard";

export default function EventDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const [event, setEvent] = useState(null);
  const [photos, setPhotos] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState(null);
  const [filter, setFilter] = useState("all");
  const pollRef = useRef(null);
  const canUpload = user?.role === "panitia" || user?.role === "admin";

  const load = async () => {
    const [e, p] = await Promise.all([
      api.get(`/events/${id}`),
      api.get(`/events/${id}/photos`),
    ]);
    setEvent(e.data);
    setPhotos(p.data);
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  // Hanya polling ketika masih ada foto berstatus antrean / diproses agar hemat jaringan di HP
  const hasPending = photos.some((p) => p.status === "queued" || p.status === "processing");
  useEffect(() => {
    if (!hasPending) return;
    pollRef.current = setInterval(() => {
      if (document.hidden) return;
      api.get(`/events/${id}/photos`).then(({ data }) => setPhotos(data)).catch(() => {});
    }, 5000);
    return () => clearInterval(pollRef.current);
  }, [id, hasPending]);

  const upload = async (files) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    try {
      const fd = new FormData();
      for (const f of files) fd.append("files", f);
      const { data } = await api.post(`/events/${id}/photos`, fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(`${data.count} foto berhasil diunggah dan masuk antrean pemrosesan`);
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setUploading(false);
    }
  };

  const stats = {
    queued: photos.filter((p) => p.status === "queued").length,
    processing: photos.filter((p) => p.status === "processing").length,
    done: photos.filter((p) => p.status === "done").length,
    failed: photos.filter((p) => p.status === "failed").length,
  };

  const filteredPhotos = photos.filter((p) => {
    if (filter === "matched") return p.match_count > 0;
    if (filter === "unmatched") return p.status === "done" && (!p.match_count || p.match_count === 0);
    if (filter === "processing") return p.status === "processing" || p.status === "queued";
    return true;
  });

  return (
    <div className="max-w-[1100px] mx-auto px-4 sm:px-8 py-7 sm:py-12">
      {/* Event Header */}
      {event && (
        <div className="mb-6 sm:mb-8">
          <StackedCard accent="green" category="Dokumentasi Acara Kampus" meta={`${photos.length} foto`} bodyClassName="p-4 sm:p-8">
            <h1 className="text-[24px] sm:text-[36px] font-normal leading-[1.15] tracking-[-0.025em] text-[#171717] break-words">
              {event.name}
            </h1>
            {event.description && (
              <p className="mt-2.5 text-[#6E6D6A] text-[13.5px] sm:text-[14.5px] max-w-2xl leading-relaxed">
                {event.description}
              </p>
            )}
            <div className="mt-4 sm:mt-5 pt-4 border-t border-black/[0.06] flex flex-wrap items-center gap-x-4 gap-y-2 text-[11.5px] sm:text-[12px] text-[#8F8E8B] font-mono">
              {event.location && (
                <span className="flex items-center gap-1.5">
                  <MapPin className="size-3.5 shrink-0" />
                  {event.location}
                </span>
              )}
              {event.date && (
                <span className="flex items-center gap-1.5">
                  <Calendar className="size-3.5 shrink-0" />
                  {event.date}
                </span>
              )}
              <span className="text-[#171717] font-medium">{photos.length} Total Foto</span>
            </div>
          </StackedCard>
        </div>
      )}

      {/* Upload Dropzone */}
      {canUpload && (
        <label
          data-testid="bulk-upload-dropzone"
          className="block rounded-[16px] border border-dashed border-black/[0.2] bg-[#FCFCFA] hover:bg-white hover:border-[#171717] p-5 sm:p-8 text-center cursor-pointer transition-all mb-6 sm:mb-8"
        >
          <input
            type="file"
            multiple
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => upload(e.target.files)}
            className="hidden"
            data-testid="bulk-upload-input"
          />
          <div className="flex flex-col items-center gap-2">
            <div className="size-11 sm:size-12 rounded-[12px] bg-[#F5F5F2] border border-black/[0.08] text-[#171717] grid place-items-center mb-1">
              {uploading ? <Loader2 className="size-5 animate-spin" /> : <Upload className="size-5" />}
            </div>
            <div className="text-[14px] sm:text-[15px] font-medium text-[#171717]">
              {uploading ? "Mengunggah dan memproses foto..." : "Pilih atau Seret Foto Dokumentasi ke Sini"}
            </div>
            <p className="text-[12.5px] sm:text-[13px] text-[#6E6D6A] max-w-md">
              Mendukung JPG, JPEG, PNG, WebP sekaligus. Foto otomatis diproses dan didistribusikan ke galeri mahasiswa.
            </p>
          </div>
        </label>
      )}

      {/* Pipeline Status Counters */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 sm:gap-4 mb-6 sm:mb-8" data-testid="pipeline-status-bar">
        {[
          { label: "Dalam Antrean", v: stats.queued, Icon: Clock, tint: "text-[#6E6D6A]" },
          { label: "Sedang Diproses", v: stats.processing, Icon: Loader2, tint: "text-amber-700" },
          { label: "Selesai Diproses", v: stats.done, Icon: CheckCircle2, tint: "text-emerald-700" },
          { label: "Gagal", v: stats.failed, Icon: AlertTriangle, tint: "text-red-600" },
        ].map((s) => (
          <div key={s.label} className="bg-[#FCFCFA] rounded-[14px] border border-black/[0.08] p-3.5 sm:p-4 shadow-[0_1px_4px_rgba(0,0,0,0.02)]">
            <div className="flex items-center justify-between gap-1 text-[11.5px] sm:text-[12px] text-[#8F8E8B] mb-2">
              <span className="truncate">{s.label}</span>
              <s.Icon className={`size-3.5 shrink-0 ${s.tint}`} />
            </div>
            <div className="font-mono text-[22px] sm:text-[26px] font-medium text-[#171717] leading-none">{s.v}</div>
          </div>
        ))}
      </div>

      {/* Photo Filter Tabs */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-5 pb-4 border-b border-black/[0.08]">
        <div className="flex flex-wrap items-center gap-1.5 text-[12.5px] sm:text-[13px]">
          {[
            { key: "all", label: `Semua (${photos.length})` },
            { key: "matched", label: `Cocok (${photos.filter((p) => p.match_count > 0).length})` },
            { key: "unmatched", label: `Wajah Lain (${photos.filter((p) => p.status === "done" && (!p.match_count || p.match_count === 0)).length})` },
          ].map((tab) => (
            <button
              key={tab.key}
              onClick={() => setFilter(tab.key)}
              className={`px-3 py-1.5 rounded-[8px] transition-colors cursor-pointer ${
                filter === tab.key
                  ? "bg-black/[0.08] text-[#171717] font-medium"
                  : "text-[#6E6D6A] hover:text-[#171717] hover:bg-black/[0.04]"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="text-[11.5px] sm:text-[12px] font-mono text-[#8F8E8B]">
          Menampilkan {filteredPhotos.length} foto
        </div>
      </div>

      {/* Photo Grid */}
      {filteredPhotos.length === 0 ? (
        <div className="bg-[#FCFCFA] rounded-[16px] border border-dashed border-black/[0.15] p-8 sm:p-12 text-center text-[#6E6D6A]">
          <ImageIcon className="size-8 text-[#8F8E8B] mx-auto mb-3" />
          <div className="text-[15px] font-medium text-[#171717]">Tidak ada foto dalam kategori ini</div>
          <p className="text-[13px] text-[#8F8E8B] mt-1">Silakan pilih kategori lain atau unggah foto baru.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 sm:gap-4" data-testid="event-photos-grid">
          {filteredPhotos.map((p) => (
            <div
              key={p.id}
              onClick={() => setSelected(p.id)}
              className="group relative aspect-square rounded-[14px] overflow-hidden border border-black/[0.08] bg-[#ECECE8] cursor-pointer shadow-[0_2px_6px_rgba(0,0,0,0.03)] hover:border-black/[0.18] transition-all"
              data-testid={`photo-item-${p.id}`}
            >
              <img
                src={fileSrc(`/api/files/${p.stored_filename}`, 420)}
                alt=""
                loading="lazy"
                decoding="async"
                className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-300"
              />

              <div className="absolute top-2 right-2 flex flex-col items-end gap-1 font-mono text-[9.5px]">
                <span
                  className={`px-2 py-0.5 rounded-full backdrop-blur-md ${
                    p.status === "done"
                      ? "bg-[#171717]/80 text-white"
                      : p.status === "processing"
                      ? "bg-amber-600/90 text-white animate-pulse"
                      : "bg-black/60 text-white"
                  }`}
                >
                  {p.status === "done" ? "Selesai" : p.status === "processing" ? "Memproses" : p.status}
                </span>
                {p.match_count > 0 && (
                  <span className="rounded-full bg-emerald-600/95 text-white px-2 py-0.5 font-medium">
                    {p.match_count} cocok
                  </span>
                )}
              </div>

              <div className="absolute inset-x-0 bottom-0 p-2 sm:p-2.5 bg-gradient-to-t from-black/75 via-black/30 to-transparent text-white opacity-100 sm:opacity-0 sm:group-hover:opacity-100 transition-opacity text-[10.5px] sm:text-[11px] font-mono flex items-center justify-between">
                <span>{p.face_count} wajah</span>
                {p.match_count > 0 && <span className="text-emerald-300">{p.match_count} cocok</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {selected && <PhotoViewer photoId={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

import { useEffect, useState, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import api, { fileSrc } from "@/lib/api";
import PhotoViewer from "@/components/PhotoViewer";
import { Image as ImageIcon, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { StackedCard } from "@/components/StackedCard";

export default function Gallery() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [photos, setPhotos] = useState([]);
  const [selected, setSelected] = useState(null);
  const [selectedEvent, setSelectedEvent] = useState("all");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const pid = searchParams.get("photoId");
    if (pid) setSelected(pid);
  }, [searchParams]);

  const loadGallery = async () => {
    setLoading(true);
    try {
      const { data } = await api.get("/me/gallery");
      setPhotos(data);
    } catch {
      toast.error("Gagal memuat galeri pribadi");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGallery();
  }, []);

  const albums = useMemo(() => {
    const map = {};
    photos.forEach((p) => {
      const eid = p.event_id || "general";
      if (!map[eid]) {
        map[eid] = {
          id: eid,
          name: p.event_name || "Acara Kampus",
          count: 0,
          coverUrl: p.url,
        };
      }
      map[eid].count += 1;
    });
    return Object.values(map);
  }, [photos]);

  const displayedPhotos = useMemo(() => {
    if (selectedEvent === "all") return photos;
    return photos.filter((p) => (p.event_id || "general") === selectedEvent);
  }, [photos, selectedEvent]);

  const handleNotMyPhoto = (photoId) => {
    setPhotos((prev) => prev.filter((p) => p.id !== photoId));
  };

  const handleCloseViewer = () => {
    setSelected(null);
    if (searchParams.get("photoId")) {
      const newParams = new URLSearchParams(searchParams);
      newParams.delete("photoId");
      setSearchParams(newParams, { replace: true });
    }
  };

  return (
    <div className="max-w-[1100px] mx-auto px-4 sm:px-8 py-7 sm:py-12" data-testid="gallery-page">
      {/* Header */}
      <div className="mb-6 sm:mb-8 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="font-mono text-[11px] sm:text-[12px] text-[#8F8E8B] mb-2">
            Distribusi Otomatis · Galeri Pribadi
          </div>
          <h1 className="text-[26px] sm:text-[40px] font-normal leading-[1.15] tracking-[-0.025em] text-[#171717]">
            Galeri <span className="text-[#8F8E8B]">Foto Anda</span>
          </h1>
          <p className="text-[#6E6D6A] text-[13.5px] sm:text-[14px] mt-2 max-w-xl">
            Semua foto dokumentasi acara kampus yang memuat wajah Anda (berstatus <span className="font-mono text-[#171717] font-medium">COCOK</span>) tersaji otomatis di sini.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <div className="inline-flex items-center gap-1.5 rounded-[10px] border border-black/[0.08] bg-[#FCFCFA] px-3 py-1.5 sm:px-3.5 sm:py-2 font-mono text-[11.5px] sm:text-[12px] text-[#171717]">
            <ShieldCheck className="size-3.5 text-emerald-700 shrink-0" />
            <span>Terverifikasi Cocok</span>
          </div>

          <div
            className="font-mono text-[11.5px] sm:text-[12px] text-[#6E6D6A] border border-black/[0.08] rounded-[10px] px-3 py-1.5 sm:px-3.5 sm:py-2 bg-[#FCFCFA]"
            data-testid="gallery-count"
          >
            {displayedPhotos.length} foto
          </div>
        </div>
      </div>

      {/* Album Filter Tabs (Cofounder soft gray pills) */}
      <div className="mb-8 pb-5 border-b border-black/[0.08]">
        <div className="font-mono text-[11px] uppercase tracking-wider text-[#8F8E8B] mb-3">
          Koleksi Album Acara
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => setSelectedEvent("all")}
            className={`px-3.5 py-1.5 text-[13px] rounded-[8px] transition-colors cursor-pointer ${
              selectedEvent === "all"
                ? "bg-black/[0.08] text-[#171717] font-medium"
                : "text-[#6E6D6A] hover:text-[#171717] hover:bg-black/[0.04]"
            }`}
          >
            Semua Foto <span className="font-mono text-[11px] text-[#8F8E8B] ml-1">({photos.length})</span>
          </button>

          {albums.map((album) => {
            const isSelected = selectedEvent === album.id;
            return (
              <button
                key={album.id}
                onClick={() => setSelectedEvent(album.id)}
                className={`px-3.5 py-1.5 text-[13px] rounded-[8px] transition-colors cursor-pointer ${
                  isSelected
                    ? "bg-black/[0.08] text-[#171717] font-medium"
                    : "text-[#6E6D6A] hover:text-[#171717] hover:bg-black/[0.04]"
                }`}
              >
                {album.name} <span className="font-mono text-[11px] text-[#8F8E8B] ml-1">({album.count})</span>
              </button>
            );
          })}
        </div>
      </div>

      {/* Photo Grid */}
      {loading ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-5">
          {[...Array(8)].map((_, i) => (
            <div key={i} className="aspect-square rounded-[14px] sm:rounded-[16px] bg-black/[0.05] animate-pulse" />
          ))}
        </div>
      ) : displayedPhotos.length === 0 ? (
        <StackedCard accent="ink" category="Galeri Kosong" meta="0 foto" bodyClassName="p-8 sm:p-12 text-center items-center">
          <div className="size-12 rounded-[12px] bg-[#F5F5F2] border border-black/[0.08] text-[#6E6D6A] grid place-items-center mb-4">
            <ImageIcon className="size-5" />
          </div>
          <h3 className="text-[18px] sm:text-[19px] font-medium text-[#171717]">Belum Ada Foto Cocok</h3>
          <p className="text-[13.5px] text-[#6E6D6A] mt-2 max-w-sm leading-relaxed">
            Foto dokumentasi berstatus COCOK akan otomatis muncul di sini setelah panitia mengunggah foto acara kampus.
          </p>
        </StackedCard>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3 sm:gap-5" data-testid="gallery-grid">
          {displayedPhotos.map((photo) => (
            <div
              key={photo.id}
              onClick={() => setSelected(photo.id)}
              className="group relative rounded-[14px] sm:rounded-[16px] overflow-hidden bg-[#FCFCFA] border border-black/[0.08] shadow-[0_2px_8px_rgba(0,0,0,0.03)] hover:border-black/[0.16] hover:shadow-[0_10px_24px_rgba(0,0,0,0.07)] transition-all cursor-pointer flex flex-col"
              data-testid={`gallery-photo-${photo.id}`}
            >
              <div className="aspect-square overflow-hidden bg-[#ECECE8]">
                <img
                  src={photo.url?.startsWith("http") ? photo.url : fileSrc(photo.url, 420)}
                  alt=""
                  className="w-full h-full object-cover group-hover:scale-[1.03] transition-transform duration-300"
                  loading="lazy"
                  decoding="async"
                />
              </div>

              <div className="px-2.5 sm:px-3.5 py-2 sm:py-2.5 flex items-center justify-between gap-1.5 sm:gap-2 bg-[#FCFCFA] border-t border-black/[0.06]">
                <span className="text-[11.5px] sm:text-[12px] text-[#171717] font-medium truncate">
                  {photo.event_name || "Acara Kampus"}
                </span>
                <span className="font-mono text-[10.5px] sm:text-[11px] text-[#8F8E8B] shrink-0">
                  {(photo.similarity * 100).toFixed(0)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {selected && (
        <PhotoViewer
          photoId={selected}
          onClose={handleCloseViewer}
          onNotMyPhoto={handleNotMyPhoto}
        />
      )}
    </div>
  );
}

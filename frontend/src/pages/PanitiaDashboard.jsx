import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api from "@/lib/api";
import { Plus } from "lucide-react";
import { StackedCard } from "@/components/StackedCard";

const ACCENTS = ["green", "cyan", "purple", "amber", "coral"];

export default function PanitiaDashboard() {
  const [events, setEvents] = useState([]);

  useEffect(() => {
    api.get("/events").then(({ data }) => setEvents(data));
  }, []);

  const totalPhotos = events.reduce((a, e) => a + (e.photo_count || 0), 0);

  return (
    <div className="max-w-[1100px] mx-auto px-4 sm:px-8 py-7 sm:py-12">
      {/* Header */}
      <div className="mb-7 sm:mb-10 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="font-mono text-[11px] sm:text-[12px] text-[#8F8E8B] mb-2">Studio Dokumentasi Panitia</div>
          <h1 className="text-[26px] sm:text-[40px] font-normal leading-[1.15] tracking-[-0.025em] text-[#171717]">
            Manajemen <span className="text-[#8F8E8B]">Dokumentasi</span>
          </h1>
          <p className="text-[13.5px] sm:text-[14px] text-[#6E6D6A] mt-2">
            Unggah foto acara kampus dan pantau distribusi otomatis ke mahasiswa.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Link
            to="/events"
            className="cta-btn-dark w-full sm:w-auto justify-center px-4 py-2.5 sm:py-2 text-[13px] inline-flex items-center gap-1.5"
          >
            <Plus className="size-3.5" />
            Kelola Acara
          </Link>
        </div>
      </div>

      {/* Stats Stacked Cards */}
      <div className="grid md:grid-cols-3 gap-x-6 gap-y-6 sm:gap-y-10 mb-10 sm:mb-14">
        <StackedCard accent="green" category="Total Acara Aktif" meta="AGENDA">
          <div className="font-mono text-[42px] font-medium leading-none text-[#171717] mt-1">
            {events.length}
          </div>
          <p className="text-[13px] text-[#6E6D6A] mt-3">album dokumentasi terdaftar</p>
        </StackedCard>

        <StackedCard accent="cyan" category="Total Foto Terunggah" meta="ARSIP">
          <div className="font-mono text-[42px] font-medium leading-none text-[#171717] mt-1">
            {totalPhotos}
          </div>
          <p className="text-[13px] text-[#6E6D6A] mt-3">citra dokumentasi acara diproses</p>
        </StackedCard>

        <StackedCard accent="purple" category="Status Sistem" meta="AKTIF">
          <div className="font-mono text-[28px] font-medium leading-none text-emerald-700 mt-2">
            SIAP (LIVE)
          </div>
          <p className="text-[13px] text-[#6E6D6A] mt-3">Pemrosesan foto dokumentasi otomatis aktif</p>
        </StackedCard>
      </div>

      {/* Recent Events */}
      <div className="flex items-center justify-between mb-6 pb-3 border-b border-black/[0.08]">
        <h2 className="text-[20px] font-medium tracking-[-0.015em] text-[#171717]">Acara Terbaru</h2>
        <Link to="/events" className="font-mono text-[12px] text-[#8F8E8B] hover:text-[#171717] transition-colors">
          Lihat semua ({events.length})
        </Link>
      </div>

      <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-10">
        {events.slice(0, 6).map((e, i) => (
          <StackedCard
            key={e.id}
            to={`/events/${e.id}`}
            accent={ACCENTS[i % ACCENTS.length]}
            category={e.location || "Kampus"}
            meta={`${e.photo_count} foto`}
            title={e.name}
            description={e.description || "Dokumentasi kegiatan kampus terhubung dengan distribusi wajah otomatis."}
            footerText="Buka album acara"
          />
        ))}
      </div>
    </div>
  );
}

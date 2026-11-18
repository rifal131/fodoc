import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { Calendar, MapPin, Plus, FolderKanban } from "lucide-react";
import { toast } from "sonner";
import { useAuth } from "@/context/AuthContext";
import { StackedCard } from "@/components/StackedCard";

const ACCENTS = ["green", "cyan", "purple", "amber", "coral"];

export default function Events() {
  const { user } = useAuth();
  const [events, setEvents] = useState([]);
  const [form, setForm] = useState({ name: "", description: "", date: "", location: "" });
  const [open, setOpen] = useState(false);
  const canCreate = user?.role === "panitia" || user?.role === "admin";

  const load = async () => {
    const { data } = await api.get("/events");
    setEvents(data);
  };

  useEffect(() => {
    load();
  }, []);

  const create = async (e) => {
    e.preventDefault();
    try {
      await api.post("/events", form);
      toast.success("Acara baru berhasil dibuat");
      setForm({ name: "", description: "", date: "", location: "" });
      setOpen(false);
      load();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    }
  };

  return (
    <div className="max-w-[1100px] mx-auto px-4 sm:px-8 py-7 sm:py-12">
      {/* Header */}
      <div className="mb-7 sm:mb-10 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="font-mono text-[11px] sm:text-[12px] text-[#8F8E8B] mb-2">Katalog Acara Kampus</div>
          <h1 className="text-[26px] sm:text-[40px] font-normal leading-[1.15] tracking-[-0.025em] text-[#171717]">
            Daftar <span className="text-[#8F8E8B]">Acara</span>
          </h1>
          <p className="text-[13.5px] sm:text-[14px] text-[#6E6D6A] mt-2">
            Daftar dokumentasi kegiatan, wisuda, seminar, dan agenda universitas.
          </p>
        </div>

        {canCreate && (
          <button
            onClick={() => setOpen(!open)}
            data-testid="toggle-create-event"
            className="cta-btn-dark w-full sm:w-auto inline-flex items-center justify-center gap-2 px-4 py-2.5 text-[13.5px] cursor-pointer"
          >
            <Plus className="size-4" />
            {open ? "Tutup Form" : "Buat Acara Baru"}
          </button>
        )}
      </div>

      {/* Form Tambah Acara */}
      {open && canCreate && (
        <div className="mb-10">
          <StackedCard accent="amber" category="Buat Agenda" meta="BARU" bodyClassName="p-6 sm:p-7">
            <form onSubmit={create} className="space-y-4" data-testid="create-event-form">
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="font-mono text-[11px] uppercase tracking-wider text-[#6E6D6A] block mb-1.5">
                    Nama Acara
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="misal: Wisuda Sarjana Angkatan 2026"
                    value={form.name}
                    onChange={(e) => setForm({ ...form, name: e.target.value })}
                    className="w-full px-3.5 py-2 text-[14px]"
                    data-testid="event-name-input"
                  />
                </div>

                <div>
                  <label className="font-mono text-[11px] uppercase tracking-wider text-[#6E6D6A] block mb-1.5">
                    Lokasi
                  </label>
                  <input
                    type="text"
                    placeholder="misal: Auditorium Gedung Rektorat"
                    value={form.location}
                    onChange={(e) => setForm({ ...form, location: e.target.value })}
                    className="w-full px-3.5 py-2 text-[14px]"
                    data-testid="event-location-input"
                  />
                </div>

                <div>
                  <label className="font-mono text-[11px] uppercase tracking-wider text-[#6E6D6A] block mb-1.5">
                    Tanggal Pelaksanaan
                  </label>
                  <input
                    type="date"
                    value={form.date}
                    onChange={(e) => setForm({ ...form, date: e.target.value })}
                    className="w-full px-3.5 py-2 text-[14px]"
                    data-testid="event-date-input"
                  />
                </div>

                <div>
                  <label className="font-mono text-[11px] uppercase tracking-wider text-[#6E6D6A] block mb-1.5">
                    Deskripsi Singkat
                  </label>
                  <input
                    type="text"
                    placeholder="misal: Dokumentasi foto resmi & candid"
                    value={form.description}
                    onChange={(e) => setForm({ ...form, description: e.target.value })}
                    className="w-full px-3.5 py-2 text-[14px]"
                    data-testid="event-desc-input"
                  />
                </div>
              </div>

              <div className="flex justify-end pt-2">
                <button
                  type="submit"
                  data-testid="submit-create-event"
                  className="cta-btn-dark px-5 py-2 text-[13.5px] cursor-pointer"
                >
                  Simpan Acara
                </button>
              </div>
            </form>
          </StackedCard>
        </div>
      )}

      {/* Grid Acara (Cofounder 3-column Stacked Paper Cards) */}
      {events.length === 0 ? (
        <StackedCard accent="ink" category="Agenda Kosong" meta="0 acara" bodyClassName="p-14 text-center items-center">
          <FolderKanban className="size-8 text-[#8F8E8B] mb-3" />
          <div className="text-[18px] font-medium text-[#171717]">Belum ada acara</div>
          <p className="text-[13.5px] text-[#6E6D6A] mt-1">
            {canCreate ? "Klik tombol 'Buat Acara Baru' untuk menambahkan agenda." : "Belum ada agenda acara yang dipublikasikan."}
          </p>
        </StackedCard>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-10" data-testid="events-grid">
          {events.map((e, i) => (
            <StackedCard
              key={e.id}
              to={`/events/${e.id}`}
              data-testid={`event-card-${e.id}`}
              accent={ACCENTS[i % ACCENTS.length]}
              category="Agenda Kampus"
              meta={`${e.photo_count} foto`}
              title={e.name}
              description={e.description || "Dokumentasi kegiatan resmi dan candid kampus."}
              footerText="Buka acara"
            >
              <div className="mt-5 pt-4 border-t border-black/[0.06] text-[12px] font-mono text-[#8F8E8B] space-y-1.5">
                {e.location && (
                  <div className="flex items-center gap-2">
                    <MapPin className="size-3.5 shrink-0" />
                    <span className="truncate">{e.location}</span>
                  </div>
                )}
                {e.date && (
                  <div className="flex items-center gap-2">
                    <Calendar className="size-3.5 shrink-0" />
                    <span>{e.date}</span>
                  </div>
                )}
              </div>
            </StackedCard>
          ))}
        </div>
      )}
    </div>
  );
}

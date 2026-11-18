import { useEffect, useState } from "react";
import api, { fileSrc } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { Link } from "react-router-dom";
import { CheckCircle2, AlertTriangle } from "lucide-react";
import { useNotifications } from "@/context/NotificationContext";
import { StackedCard } from "@/components/StackedCard";

export default function Dashboard() {
  const { user } = useAuth();
  const { unread } = useNotifications();
  const [status, setStatus] = useState(null);
  const [gallery, setGallery] = useState([]);
  const [pendingCount, setPendingCount] = useState(0);

  useEffect(() => {
    (async () => {
      try {
        const [s, g, q] = await Promise.all([
          api.get("/enrollment/status"),
          api.get("/me/gallery"),
          api.get("/verification/queue").catch(() => ({ data: [] })),
        ]);
        setStatus(s.data);
        setGallery(g.data);
        setPendingCount(Array.isArray(q.data) ? q.data.length : 0);
      } catch {}
    })();
  }, [unread]);

  return (
    <div className="max-w-[1100px] mx-auto px-4 sm:px-8 py-7 sm:py-12">
      {/* Two-tone Editorial Welcome Header */}
      <div className="mb-7 sm:mb-10">
        <div className="font-mono text-[11px] sm:text-[12px] text-[#8F8E8B] mb-2">
          Dashboard Mahasiswa · NIM {user?.nim || "-"}
        </div>
        <h1 className="text-[26px] sm:text-[40px] font-normal leading-[1.15] tracking-[-0.025em] text-[#171717] break-words">
          Selamat datang, <span className="text-[#8F8E8B]">{user?.name}</span>
        </h1>
      </div>

      {/* Stacked Paper Cards Grid */}
      <div className="grid md:grid-cols-3 gap-x-6 gap-y-6 sm:gap-y-10" data-testid="student-dashboard">
        {/* Biometric Enrollment Status */}
        <div className="md:col-span-2">
          <StackedCard
            to="/enroll"
            accent={status?.enrolled && !status?.needs_re_enrollment ? "green" : "amber"}
            category="Status Biometrik"
            meta={status?.needs_re_enrollment ? "PERLU ULANG" : status?.enrolled ? "3 POSE AKTIF" : "BELUM VERIFIKASI"}
            title={status?.enrolled && !status?.needs_re_enrollment ? "Verifikasi Wajah Aktif" : "Daftarkan Wajah Sekarang"}
            description={
              status?.needs_re_enrollment
                ? "Akun Anda perlu registrasi ulang 3 pose wajah terstandar (Depan, Kanan, Kiri) via kamera langsung."
                : status?.enrolled
                ? "Wajah Anda telah terdaftar dengan 3 pose acuan. Setiap foto dokumentasi baru dari panitia otomatis dicocokkan."
                : "Rekam 3 pose wajah Anda langsung melalui kamera aplikasi agar foto dokumentasi acara kampus otomatis masuk ke akun Anda."
            }
            footerText={status?.enrolled ? "Perbarui 3 pose wajah" : "Mulai perekaman kamera"}
          >
            <div className="mt-4">
              {status?.needs_re_enrollment ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200 font-mono text-[11px] px-2.5 py-0.5">
                  <AlertTriangle className="size-3" /> Perlu Registrasi Ulang 3 Pose
                </span>
              ) : status?.enrolled ? (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 font-mono text-[11px] px-2.5 py-0.5">
                  <CheckCircle2 className="size-3" /> 3 Pose Terdaftar
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 text-amber-800 border border-amber-200 font-mono text-[11px] px-2.5 py-0.5">
                  <AlertTriangle className="size-3" /> Belum Verifikasi Wajah
                </span>
              )}
            </div>
          </StackedCard>
        </div>

        {/* Gallery Count Card */}
        <StackedCard
          to="/gallery"
          accent="cyan"
          category="Galeri Pribadi"
          meta="COCOK"
          footerText="Buka galeri foto"
        >
          <div className="font-mono text-[44px] font-medium leading-none text-[#171717] mt-1">
            {gallery.length}
          </div>
          <p className="text-[14px] text-[#6E6D6A] mt-3">
            foto dokumentasi terverifikasi memuat wajah Anda
          </p>
        </StackedCard>

        {/* Notifications / Konfirmasi Foto Card */}
        <StackedCard
          to={pendingCount > 0 ? "/verification" : "/notifications"}
          accent={pendingCount > 0 ? "amber" : "purple"}
          category={pendingCount > 0 ? "Konfirmasi Foto" : "Notifikasi"}
          meta={pendingCount > 0 ? "PERLU CEK" : unread > 0 ? "BARU" : "TERBACA"}
          footerText={pendingCount > 0 ? "Konfirmasi foto Anda" : "Buka kotak masuk"}
        >
          <div className="font-mono text-[44px] font-medium leading-none text-[#171717] mt-1 flex items-center gap-3">
            {pendingCount > 0 ? pendingCount : unread}
            {(pendingCount > 0 || unread > 0) && (
              <span className={`size-2.5 rounded-full ${pendingCount > 0 ? "bg-amber-500" : "bg-[#22C55E]"}`} />
            )}
          </div>
          <p className="text-[14px] text-[#6E6D6A] mt-3">
            {pendingCount > 0
              ? "foto mirip wajah Anda menunggu konfirmasi (Ya/Bukan)"
              : "pemberitahuan foto acara baru belum dibaca"}
          </p>
        </StackedCard>

        {/* Gallery Preview Stacked Card */}
        <div className="md:col-span-2">
          <StackedCard
            accent="ink"
            category="Pratinjau Koleksi Terkini"
            meta={`${gallery.length} foto`}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-[18px] font-medium tracking-[-0.015em] text-[#171717]">
                Foto Terbaru Anda
              </h3>
              {gallery.length > 0 && (
                <Link
                  to="/gallery"
                  className="font-mono text-[12px] text-[#8F8E8B] hover:text-[#171717] transition-colors"
                >
                  Lihat semua ({gallery.length})
                </Link>
              )}
            </div>

            <div className="grid grid-cols-3 sm:grid-cols-6 gap-2.5">
              {gallery.slice(0, 6).map((p) => (
                <Link
                  key={p.id}
                  to={`/gallery?photoId=${p.id}`}
                  className="group relative aspect-square rounded-[10px] overflow-hidden border border-black/[0.08] bg-[#F5F5F2]"
                >
                  <img
                    src={fileSrc(p.url, 240)}
                    alt=""
                    loading="lazy"
                    decoding="async"
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  />
                </Link>
              ))}
              {gallery.length === 0 && (
                <div className="col-span-3 sm:col-span-6 py-10 text-center font-mono text-[12px] text-[#8F8E8B]">
                  Belum ada foto yang masuk ke galeri pribadi Anda.
                </div>
              )}
            </div>
          </StackedCard>
        </div>
      </div>
    </div>
  );
}

import { Link } from "react-router-dom";
import { ScanFace } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

const FLOATING_TASKS = [
  { label: "Album Acara", title: "Wisuda & Kegiatan Kampus" },
  { label: "Distribusi Otomatis", title: "Langsung ke Galeri Pribadi" },
  { label: "Privasi Terjaga", title: "Khusus Pemilik Akun" },
];

/** Pixel-dither transition strip bridging the full-bleed pixel hero into #F5F5F2 paper below */
function HeroPixelFadeBottom() {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[34px] overflow-hidden select-none">
      <svg className="w-full h-full block" preserveAspectRatio="none" viewBox="0 0 1200 34" fill="none" aria-hidden="true">
        {Array.from({ length: 120 }).map((_, i) => {
          const x = i * 10;
          const h1 = (i * 7) % 3 === 0 ? 18 : (i * 5) % 2 === 0 ? 12 : 8;
          return (
            <g key={i}>
              <rect x={x} y={34 - h1} width="10" height={h1} fill="#F5F5F2" />
              {i % 2 === 0 && <rect x={x + 2} y={34 - h1 - 6} width="6" height="6" fill="#F5F5F2" opacity="0.85" />}
            </g>
          );
        })}
        <rect x="0" y="26" width="1200" height="8" fill="#F5F5F2" />
      </svg>
    </div>
  );
}

export default function Landing() {
  const { user } = useAuth();

  const primaryCta = !user
    ? { to: "/register", label: "Daftar & Verifikasi" }
    : user.role === "admin"
    ? { to: "/admin", label: "Buka Admin Panel" }
    : user.role === "panitia"
    ? { to: "/events", label: "Kelola Acara" }
    : { to: "/gallery", label: "Buka Galeri Saya" };

  const secondaryCta = !user
    ? { to: "/login", label: "Masuk ke Akun" }
    : user.role === "admin"
    ? { to: "/events", label: "Daftar Acara" }
    : user.role === "panitia"
    ? { to: "/panitia", label: "Panel Panitia" }
    : { to: "/enroll", label: "Verifikasi 3 Pose" };

  return (
    <div className="bg-[#F5F5F2] text-[#171717]">
      {/* FULL-BLEED COFOUNDER.CO HOMEPAGE HERO — Universitas Mercu Buana Pixel-Art */}
      <section className="relative w-full min-h-[560px] sm:min-h-[680px] lg:min-h-[740px] -mt-[64px] sm:-mt-[72px] pt-[96px] sm:pt-[148px] pb-20 sm:pb-24 overflow-hidden">
        {/* Edge-to-edge Pixel-Art Background */}
        <img
          src="/images/umb-hero.jpg"
          alt="Universitas Mercu Buana — FODOC Foto Dokumentasi"
          className="absolute inset-0 w-full h-full object-cover object-center select-none pointer-events-none"
        />

        {/* Gentle left sky readability veil (extra contrast on narrow mobile viewports) */}
        <div
          className="absolute inset-0 pointer-events-none hidden sm:block"
          style={{
            background:
              "linear-gradient(105deg, rgba(14, 116, 214, 0.72) 0%, rgba(14, 116, 214, 0.42) 38%, rgba(14, 116, 214, 0.08) 68%, rgba(0, 0, 0, 0.12) 100%)",
          }}
        />
        <div
          className="absolute inset-0 pointer-events-none sm:hidden"
          style={{
            background:
              "linear-gradient(180deg, rgba(12, 84, 168, 0.78) 0%, rgba(14, 96, 186, 0.62) 55%, rgba(14, 34, 48, 0.68) 100%)",
          }}
        />
        <div className="absolute inset-x-0 top-0 h-28 bg-gradient-to-b from-black/30 to-transparent pointer-events-none" />

        {/* Foreground Content */}
        <div className="relative z-10 max-w-[1180px] mx-auto px-4 sm:px-8 grid lg:grid-cols-12 gap-8 lg:gap-10 items-center">
          {/* Left Editorial Headline & Buttons directly over sky */}
          <div className="lg:col-span-7 min-w-0">
            {user && (
              <div className="inline-flex max-w-full items-center gap-2 rounded-full bg-black/30 backdrop-blur-md border border-white/25 px-3 py-1 font-mono text-[11px] text-white/95 mb-3.5">
                <span className="size-1.5 rounded-full bg-[#4ADE80] shrink-0" />
                <span className="truncate">Halo, {user.name} · {user.role}</span>
              </div>
            )}

            <h1 className="text-[30px] sm:text-[48px] lg:text-[54px] font-semibold leading-[1.12] sm:leading-[1.09] tracking-[-0.025em] text-white drop-shadow-[0_2px_14px_rgba(0,0,0,0.45)]">
              FODOC temukan foto{" "}
              <br className="hidden sm:block" />
              dokumentasi Anda otomatis
            </h1>

            <p className="mt-3.5 sm:mt-4 text-[14.5px] sm:text-[17px] font-semibold leading-[1.55] text-white max-w-[500px] drop-shadow-[0_2px_8px_rgba(0,0,0,0.65)]">
              Rekam 3 pose wajah lewat kamera atau unggah 3 foto, lalu biarkan FODOC mengumpulkan foto dokumentasi kegiatan Universitas Mercu Buana ke galeri pribadi Anda secara otomatis dan privat.
            </p>

            {/* Exact 2-button pair: Solid White CTA + Frosted Glass Secondary */}
            <div className="mt-6 sm:mt-7 grid grid-cols-1 sm:flex sm:flex-wrap items-stretch sm:items-center gap-2.5 sm:gap-3">
              <Link
                to={primaryCta.to}
                data-testid="hero-cta-primary"
                className="inline-flex items-center justify-center rounded-[10px] bg-white text-[#171717] hover:bg-[#F5F5F2] text-[14px] sm:text-[14.5px] font-medium px-5 py-3 sm:py-2.5 shadow-[0_4px_14px_rgba(0,0,0,0.16)] transition-all hover:-translate-y-[1px]"
              >
                {primaryCta.label}
              </Link>

              <Link
                to={secondaryCta.to}
                data-testid="hero-cta-login"
                className="inline-flex items-center justify-center gap-2 rounded-[10px] bg-black/30 hover:bg-black/40 backdrop-blur-md border border-white/30 text-white text-[14px] sm:text-[14.5px] font-medium px-5 py-3 sm:py-2.5 shadow-[0_4px_14px_rgba(0,0,0,0.12)] transition-all"
              >
                <ScanFace className="size-4 text-white/90 shrink-0" />
                <span>{secondaryCta.label}</span>
              </Link>
            </div>
          </div>

          {/* Right: 3 Stacked Dark-Glass Floating Status Pills */}
          <div className="lg:col-span-5 flex flex-col items-stretch sm:items-start lg:items-end gap-2 sm:gap-2.5 lg:pt-16 min-w-0">
            {FLOATING_TASKS.map((t, idx) => (
              <div
                key={t.title}
                className={`flex sm:inline-flex items-center gap-2 sm:gap-2.5 rounded-[10px] bg-[#14261E]/70 backdrop-blur-md border border-white/20 px-3.5 sm:px-4 py-2.5 text-[12px] sm:text-[13px] shadow-[0_8px_24px_rgba(0,0,0,0.18)] ${
                  idx === 1 ? "lg:-translate-x-3" : ""
                }`}
              >
                <span className="size-2 rounded-full bg-[#4ADE80] shadow-[0_0_8px_#4ADE80] shrink-0" />
                <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 min-w-0">
                  <span className="text-white/70 shrink-0">{t.label}</span>
                  <span className="text-white font-medium">{t.title}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Pixel-dithered bottom edge melting cleanly into #F5F5F2 paper */}
        <HeroPixelFadeBottom />
      </section>
    </div>
  );
}

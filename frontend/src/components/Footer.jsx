import { Link } from "react-router-dom";
import { ShieldCheck } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

/** Retro 8-bit green pixel grass strip along the very bottom edge (matches cofounder.co footer) */
function PixelGrassStrip() {
  return (
    <div className="relative w-full h-[54px] overflow-hidden select-none mt-12">
      <svg
        className="w-full h-full block"
        preserveAspectRatio="none"
        viewBox="0 0 1200 54"
        fill="none"
        aria-hidden="true"
      >
        {[24, 58, 92, 134, 180, 224, 270, 326, 378, 430, 488, 540, 602, 668, 720, 774, 830, 890, 948, 1004, 1068, 1126, 1172].map((x, i) => (
          <g key={`top-${x}`}>
            <rect x={x} y={i % 2 === 0 ? 4 : 10} width="8" height="8" fill={i % 3 === 0 ? "#86EFAC" : "#A3E635"} opacity="0.85" />
            <rect x={x + 12} y={i % 2 === 0 ? 12 : 6} width="8" height="8" fill="#BBF7D0" opacity="0.8" />
          </g>
        ))}
        {Array.from({ length: 75 }).map((_, i) => (
          <rect
            key={`mid-${i}`}
            x={i * 16}
            y={i % 3 === 0 ? 18 : i % 2 === 0 ? 22 : 26}
            width="16"
            height="14"
            fill={i % 4 === 0 ? "#A3E635" : i % 2 === 0 ? "#84CC16" : "#BEF264"}
            opacity="0.92"
          />
        ))}
        <rect x="0" y="30" width="1200" height="24" fill="#9AE630" />
        {Array.from({ length: 40 }).map((_, i) => (
          <rect
            key={`base-${i}`}
            x={i * 30 + (i % 2) * 8}
            y={32 + (i % 3) * 6}
            width="10"
            height="6"
            fill={i % 2 === 0 ? "#84CC16" : "#BEF264"}
          />
        ))}
      </svg>
      <div className="absolute inset-x-0 bottom-1.5 px-3 text-center font-mono text-[9px] sm:text-[10px] text-[#365314]/85 pointer-events-none truncate">
        Made with ♡ by Rifal, Vikry &amp; Harari • Universitas Mercu Buana
      </div>
    </div>
  );
}

/** Framed Universitas Mercu Buana Campus Card (clean edge-to-edge art + clickable button) */
function CampusFeatureCard({ ctaTo, ctaLabel }) {
  return (
    <div className="cofounder-holo-card p-2.5 sm:p-3 rounded-[18px] sm:rounded-[20px] border border-black/[0.08] w-full max-w-[340px] mx-auto lg:mx-0">
      <div className="relative h-[320px] sm:h-[390px] rounded-[13px] sm:rounded-[14px] overflow-hidden border border-black/[0.06] bg-[#3B82F6]">
        <img
          src="/images/umb-card.jpg"
          alt="Universitas Mercu Buana"
          className="absolute inset-0 w-full h-full object-cover object-center select-none pointer-events-none"
        />

        {/* Frosted glass overlay panel at bottom — z-20 & pointer-events-auto so button always clicks cleanly */}
        <div className="absolute inset-x-3 sm:inset-x-3.5 bottom-3 sm:bottom-3.5 z-20 pointer-events-auto rounded-[12px] sm:rounded-[14px] bg-[#171717]/75 backdrop-blur-md border border-white/20 p-3.5 sm:p-4 text-white shadow-lg">
          <p className="text-[14.5px] sm:text-[16px] leading-[1.35] font-normal tracking-[-0.01em]">
            <span className="font-medium text-white">FODOC Universitas Mercu Buana</span>{" "}
            <span className="text-white/85">— distribusi foto dokumentasi acara kampus otomatis &amp; privat.</span>
          </p>
          <Link
            to={ctaTo}
            className="mt-3 sm:mt-3.5 inline-flex items-center justify-center rounded-[10px] bg-white text-[#171717] hover:bg-[#F5F5F2] active:scale-[0.98] text-[13px] sm:text-[13.5px] font-medium px-4 py-2 shadow-sm transition-all cursor-pointer"
          >
            {ctaLabel}
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function Footer() {
  const { user } = useAuth();
  const ctaTo = !user
    ? "/register"
    : user.role === "admin"
    ? "/admin"
    : user.role === "panitia"
    ? "/events"
    : "/gallery";
  const ctaLabel = !user
    ? "Daftar akun"
    : user.role === "admin"
    ? "Buka Admin Panel"
    : user.role === "panitia"
    ? "Kelola acara"
    : "Buka galeri";

  return (
    <footer className="cofounder-grid-bg border-t border-black/[0.06] pt-12 sm:pt-20 text-[#171717]">
      <div className="max-w-[1100px] mx-auto px-4 sm:px-8">
        <div className="grid lg:grid-cols-12 gap-8 sm:gap-12 items-center">
          {/* Left Editorial Column */}
          <div className="lg:col-span-7 space-y-5 sm:space-y-7">
            <div className="flex items-center">
              <img
                src="/images/fodoc-logo-full.png"
                alt="FODOC Foto Dokumentasi Kampus"
                className="h-10 sm:h-12 w-auto object-contain"
              />
            </div>

            <h2 className="text-[26px] sm:text-[40px] font-normal leading-[1.15] sm:leading-[1.12] tracking-[-0.025em]">
              <span className="block text-[#171717]">Foto dokumentasi kampus</span>
              <span className="block text-[#8F8E8B]">Universitas Mercu Buana</span>
            </h2>

            <div className="flex flex-wrap items-center gap-x-4 gap-y-2 text-[13.5px]">
              <span className="text-[#8F8E8B]">Alur kerja</span>
              <Link to={user ? "/enroll" : "/register"} className="text-[#171717] hover:text-[#6E6D6A] transition-colors">
                Rekam 3 pose
              </Link>
              <Link to={user ? "/events" : "/login"} className="text-[#171717] hover:text-[#6E6D6A] transition-colors">
                Unggah acara
              </Link>
              <Link to={user ? "/verification" : "/login"} className="text-[#171717] hover:text-[#6E6D6A] transition-colors">
                Konfirmasi foto
              </Link>
              <Link to={user ? "/gallery" : "/login"} className="text-[#171717] hover:text-[#6E6D6A] transition-colors">
                Galeri otomatis
              </Link>
            </div>

            <div className="grid grid-cols-2 max-w-[340px] gap-y-2.5 gap-x-8 text-[13.5px] text-[#4A4946] pt-1">
              <Link to="/" className="hover:text-[#171717] transition-colors">
                Beranda
              </Link>
              <Link to="/team" className="hover:text-[#171717] transition-colors">
                Tim Kami
              </Link>
              <Link to={user ? "/gallery" : "/login"} className="hover:text-[#171717] transition-colors">
                Galeri Pribadi
              </Link>
              <Link to={user ? "/events" : "/login"} className="hover:text-[#171717] transition-colors">
                Daftar Acara
              </Link>
              <Link to={user ? "/enroll" : "/register"} className="hover:text-[#171717] transition-colors">
                Verifikasi 3 Pose
              </Link>
              <Link to="/login" className="hover:text-[#171717] transition-colors">
                Masuk Akun
              </Link>
            </div>

            <div className="space-y-2 pt-2 text-[12px] text-[#8F8E8B]">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-md bg-black/[0.05] border border-black/[0.06] font-mono text-[11px] text-[#171717]">
                  <ShieldCheck className="size-3 text-emerald-700" />
                  Privasi Terjaga
                </span>
              </div>
              <p className="text-[11.5px] text-[#8F8E8B]">
                Copyright © 2026 FODOC — Foto Dokumentasi Universitas Mercu Buana
              </p>
              <p className="text-[12px] text-[#8F8E8B]">
                Capstone Project •{" "}
                <span className="text-[#171717] font-medium">Rifal, Vikry &amp; Harari</span> — Universitas Mercu Buana
              </p>
            </div>
          </div>

          {/* Right Universitas Mercu Buana Framed Card */}
          <div className="lg:col-span-5 flex lg:justify-end">
            <CampusFeatureCard ctaTo={ctaTo} ctaLabel={ctaLabel} />
          </div>
        </div>
      </div>

      <PixelGrassStrip />
    </footer>
  );
}

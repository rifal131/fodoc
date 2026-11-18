import { useEffect, useState } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { LogOut, Bell, Menu, X } from "lucide-react";
import { ExportSourceButton } from "@/components/ExportSourceButton";
import { useNotifications } from "@/context/NotificationContext";

export default function Navbar() {
  const { user, logout } = useAuth();
  const { unread } = useNotifications();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const { pathname } = useLocation();
  const nav = useNavigate();

  // Transparent glass overlay mode over the full-bleed blue-sky pixel hero on Beranda Awal ("/")
  const isHeroOverlay = pathname === "/" && !scrolled && !mobileOpen;

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const linkClass = ({ isActive }) =>
    isHeroOverlay
      ? `px-3 py-1.5 text-[14px] rounded-[8px] transition-colors duration-150 ${
          isActive
            ? "bg-white/25 text-white font-medium"
            : "text-white/85 hover:text-white hover:bg-white/10"
        }`
      : `px-3 py-1.5 text-[14px] rounded-[8px] transition-colors duration-150 ${
          isActive
            ? "bg-black/[0.06] text-[#171717] font-medium"
            : "text-[#6E6D6A] hover:text-[#171717]"
        }`;

  const mobileLinkClass = ({ isActive }) =>
    `block px-3.5 py-2.5 text-[14px] rounded-[10px] transition-colors ${
      isActive
        ? "bg-black/[0.06] text-[#171717] font-medium"
        : "text-[#6E6D6A] hover:text-[#171717] hover:bg-black/[0.03]"
    }`;

  const handleLogout = async () => {
    setMobileOpen(false);
    await logout();
    nav("/");
  };

  const sepClass = isHeroOverlay ? "text-white/30 select-none text-xs" : "text-black/15 select-none text-xs";

  return (
    <header
      className={`sticky top-0 z-40 transition-all duration-200 ${
        isHeroOverlay
          ? "bg-transparent border-b border-transparent"
          : "bg-[#F5F5F2]/95 backdrop-blur-md border-b border-black/[0.06]"
      }`}
    >
      <div className="max-w-[1180px] mx-auto px-4 sm:px-8 h-[64px] sm:h-[72px] flex items-center justify-between gap-2 sm:gap-4">
        {/* FODOC — Foto Dokumentasi Logo */}
        <Link
          to="/"
          data-testid="brand-link"
          onClick={() => setMobileOpen(false)}
          className="flex items-center gap-2 sm:gap-2.5 group shrink-0 min-w-0"
        >
          <img
            src="/images/fodoc-logo.png"
            alt="FODOC Foto Dokumentasi"
            className="h-8 sm:h-10 w-auto object-contain drop-shadow-[0_1px_4px_rgba(0,0,0,0.2)] group-hover:scale-105 transition-transform shrink-0"
          />
          <span className="leading-none">
            <span
              className={`block font-serif-brand text-[20px] sm:text-[24px] tracking-[-0.02em] transition-colors ${
                isHeroOverlay ? "text-white drop-shadow-[0_1px_6px_rgba(0,0,0,0.28)]" : "text-[#171717]"
              }`}
            >
              FODOC
            </span>
            <span
              className={`block font-mono text-[8.5px] sm:text-[9.5px] uppercase tracking-[0.12em] sm:tracking-[0.14em] mt-0.5 ${
                isHeroOverlay ? "text-white/85" : "text-[#8F8E8B]"
              }`}
            >
              Foto Dokumentasi
            </span>
          </span>
        </Link>

        {/* Right Desktop Navigation + CTA */}
        <div className="hidden md:flex items-center gap-2.5">
          {!user ? (
            <>
              {/* Clean Nav Group */}
              <NavLink
                to="/"
                end
                className={({ isActive }) =>
                  isHeroOverlay
                    ? `px-3.5 py-2 text-[14px] rounded-[10px] backdrop-blur-md border transition-colors ${
                        isActive
                          ? "bg-black/25 border-white/25 text-white font-medium"
                          : "bg-white/15 border-white/25 text-white/90 hover:bg-white/25"
                      }`
                    : linkClass({ isActive })
                }
              >
                Beranda
              </NavLink>

              <NavLink
                to="/team"
                data-testid="nav-team-anon"
                className={({ isActive }) =>
                  isHeroOverlay
                    ? `px-3.5 py-2 text-[14px] rounded-[10px] backdrop-blur-md border transition-colors ${
                        isActive
                          ? "bg-black/25 border-white/25 text-white font-medium"
                          : "bg-white/15 border-white/25 text-white/90 hover:bg-white/25"
                      }`
                    : linkClass({ isActive })
                }
              >
                Tim Kami
              </NavLink>

              <Link
                to="/login"
                data-testid="nav-login"
                className={
                  isHeroOverlay
                    ? "px-3.5 py-2 text-[14px] rounded-[10px] bg-white/15 hover:bg-white/25 backdrop-blur-md border border-white/25 text-white transition-colors"
                    : "px-3 py-1.5 text-[14px] text-[#6E6D6A] hover:text-[#171717] transition-colors"
                }
              >
                Masuk
              </Link>

              <Link
                to="/register"
                data-testid="nav-register"
                className={
                  isHeroOverlay
                    ? "px-4 py-2 text-[14px] font-medium rounded-[10px] bg-white text-[#171717] hover:bg-[#F5F5F2] shadow-md transition-colors inline-flex items-center"
                    : "cta-btn-dark px-4 py-2 text-[14px] inline-flex items-center"
                }
              >
                Daftar Akun
              </Link>
            </>
          ) : (
            <>
              <nav
                className={`flex items-center gap-1 px-2 py-1 rounded-[12px] transition-all ${
                  isHeroOverlay
                    ? "bg-black/25 backdrop-blur-md border border-white/20 shadow-[0_2px_12px_rgba(0,0,0,0.12)]"
                    : ""
                }`}
              >
                <NavLink to="/" end className={linkClass} data-testid="nav-home">
                  Beranda
                </NavLink>
                <span className={sepClass}>|</span>
                <NavLink to="/team" className={linkClass} data-testid="nav-team">
                  Tim Kami
                </NavLink>
                <span className={sepClass}>|</span>

                {user.role === "mahasiswa" && (
                  <>
                    <NavLink to="/dashboard" className={linkClass} data-testid="nav-dashboard">
                      Dashboard
                    </NavLink>
                    <span className={sepClass}>|</span>
                    <NavLink to="/enroll" className={linkClass} data-testid="nav-enroll">
                      Verifikasi Wajah
                    </NavLink>
                    <span className={sepClass}>|</span>
                    <NavLink to="/gallery" className={linkClass} data-testid="nav-gallery">
                      Galeri Pribadi
                    </NavLink>
                    <span className={sepClass}>|</span>
                    <NavLink to="/verification" className={linkClass} data-testid="nav-verification">
                      Konfirmasi Foto
                    </NavLink>
                  </>
                )}

                {user.role === "panitia" && (
                  <>
                    <NavLink to="/panitia" className={linkClass} data-testid="nav-panitia">
                      Panel Panitia
                    </NavLink>
                    <span className={sepClass}>|</span>
                    <NavLink to="/events" className={linkClass} data-testid="nav-events">
                      Daftar Acara
                    </NavLink>
                  </>
                )}

                {user.role === "admin" && (
                  <>
                    <NavLink to="/admin" className={linkClass} data-testid="nav-admin">
                      Admin Panel
                    </NavLink>
                    <span className={sepClass}>|</span>
                    <NavLink to="/verification" className={linkClass} data-testid="nav-verification">
                      Antrean Verifikasi
                    </NavLink>
                    <span className={sepClass}>|</span>
                    <NavLink to="/events" className={linkClass} data-testid="nav-events">
                      Kelola Acara
                    </NavLink>
                  </>
                )}
              </nav>

              <ExportSourceButton className="hidden lg:inline-flex" />

              {user.role === "mahasiswa" && (
                <button
                  onClick={() => nav("/notifications")}
                  data-testid="notifications-bell"
                  className={`relative size-9 rounded-[10px] border grid place-items-center transition-colors cursor-pointer ${
                    isHeroOverlay
                      ? "bg-white/20 backdrop-blur-md border-white/30 text-white hover:bg-white/30"
                      : "border-black/[0.08] bg-white hover:border-black/[0.18] text-[#171717]"
                  }`}
                  title="Notifikasi Foto Baru"
                >
                  <Bell className="size-4" />
                  {unread > 0 && (
                    <span
                      data-testid="notifications-unread-badge"
                      className="absolute -top-1.5 -right-1.5 min-w-[18px] h-[18px] px-1 grid place-items-center rounded-full bg-[#171717] text-white font-mono text-[10px] font-medium"
                    >
                      {unread > 9 ? "9+" : unread}
                    </span>
                  )}
                </button>
              )}

              <div
                className={`flex items-center gap-2.5 pl-3 ml-1 border-l ${
                  isHeroOverlay ? "border-white/25" : "border-black/[0.08]"
                }`}
              >
                <div className="flex flex-col items-end">
                  <span
                    className={`text-[13px] font-medium leading-tight ${
                      isHeroOverlay ? "text-white drop-shadow-xs" : "text-[#171717]"
                    }`}
                  >
                    {user.name}
                  </span>
                  <span
                    className={`font-mono text-[10px] uppercase tracking-wider ${
                      isHeroOverlay ? "text-white/75" : "text-[#8F8E8B]"
                    }`}
                  >
                    {user.role}
                  </span>
                </div>
                <button
                  onClick={handleLogout}
                  data-testid="logout-button"
                  className={`size-9 rounded-[10px] border grid place-items-center transition-colors cursor-pointer ${
                    isHeroOverlay
                      ? "bg-white/95 border-white text-[#171717] hover:bg-red-50 hover:text-red-600 shadow-sm"
                      : "border-black/[0.08] bg-white hover:bg-red-50 hover:text-red-600 hover:border-red-200 text-[#6E6D6A]"
                  }`}
                  title="Keluar dari akun"
                >
                  <LogOut className="size-4" />
                </button>
              </div>
            </>
          )}
        </div>

        {/* Mobile Right Controls */}
        <div className="flex md:hidden items-center gap-1.5 sm:gap-2 shrink-0">
          {!user ? (
            <Link
              to="/register"
              data-testid="nav-register-mobile"
              className={
                isHeroOverlay
                  ? "px-3 py-1.5 text-[12.5px] font-medium rounded-[9px] bg-white text-[#171717] shadow-md whitespace-nowrap"
                  : "cta-btn-dark px-3 py-1.5 text-[12.5px] whitespace-nowrap"
              }
            >
              Daftar Akun
            </Link>
          ) : (
            user.role === "mahasiswa" && (
              <button
                onClick={() => nav("/notifications")}
                className={`relative size-9 rounded-[9px] border grid place-items-center ${
                  isHeroOverlay
                    ? "bg-white/20 backdrop-blur-md border-white/30 text-white"
                    : "border-black/[0.1] bg-white text-[#171717]"
                }`}
                title="Notifikasi"
              >
                <Bell className="size-4" />
                {unread > 0 && (
                  <span className="absolute -top-1 -right-1 min-w-[17px] h-[17px] px-1 grid place-items-center rounded-full bg-[#171717] text-white font-mono text-[10px]">
                    {unread > 9 ? "9+" : unread}
                  </span>
                )}
              </button>
            )
          )}

          <button
            type="button"
            onClick={() => setMobileOpen((v) => !v)}
            aria-label="Toggle menu"
            className={`size-9 rounded-[9px] border grid place-items-center cursor-pointer ${
              isHeroOverlay
                ? "bg-white/95 border-white text-[#171717] shadow-sm"
                : "border-black/[0.1] bg-white text-[#171717] shadow-[0_1px_2px_rgba(0,0,0,0.04)]"
            }`}
          >
            {mobileOpen ? <X className="size-4" /> : <Menu className="size-4" />}
          </button>
        </div>
      </div>

      {/* Mobile Dropdown Drawer */}
      {mobileOpen && (
        <div className="md:hidden border-t border-black/[0.06] bg-[#FCFCFA] px-4 py-4 space-y-1 shadow-xl max-h-[calc(100vh-64px)] overflow-y-auto">
          {!user ? (
            <>
              <NavLink to="/" end onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                Beranda
              </NavLink>
              <NavLink to="/team" onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                Tim Kami
              </NavLink>
              <NavLink to="/login" onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                Masuk
              </NavLink>
              <NavLink to="/register" onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                Daftar Akun Baru
              </NavLink>
            </>
          ) : (
            <>
              <div className="px-3.5 py-2 mb-2 border-b border-black/[0.06] flex items-center justify-between">
                <div>
                  <div className="text-sm font-medium text-[#171717]">{user.name}</div>
                  <div className="font-mono text-[11px] text-[#8F8E8B] uppercase">{user.role}</div>
                </div>
              </div>

              <NavLink to="/" end onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                Beranda
              </NavLink>
              <NavLink to="/team" onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                Tim Kami
              </NavLink>

              {user.role === "mahasiswa" && (
                <>
                  <NavLink to="/dashboard" onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                    Dashboard
                  </NavLink>
                  <NavLink to="/enroll" onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                    Verifikasi Wajah (3 Pose)
                  </NavLink>
                  <NavLink to="/gallery" onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                    Galeri Pribadi
                  </NavLink>
                  <NavLink to="/verification" onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                    Konfirmasi Foto
                  </NavLink>
                  <NavLink to="/notifications" onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                    Notifikasi {unread > 0 ? `(${unread})` : ""}
                  </NavLink>
                </>
              )}

              {user.role === "panitia" && (
                <>
                  <NavLink to="/panitia" onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                    Panel Panitia
                  </NavLink>
                  <NavLink to="/events" onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                    Daftar Acara
                  </NavLink>
                </>
              )}

              {user.role === "admin" && (
                <>
                  <NavLink to="/admin" onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                    Admin Panel
                  </NavLink>
                  <NavLink to="/verification" onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                    Antrean Verifikasi
                  </NavLink>
                  <NavLink to="/events" onClick={() => setMobileOpen(false)} className={mobileLinkClass}>
                    Kelola Acara
                  </NavLink>
                </>
              )}

              <button
                onClick={handleLogout}
                className="w-full mt-2 px-3.5 py-2.5 text-left text-[14px] text-red-600 hover:bg-red-50 rounded-[10px] flex items-center gap-2"
              >
                <LogOut className="size-4" />
                Keluar dari Akun
              </button>
            </>
          )}
        </div>
      )}
    </header>
  );
}

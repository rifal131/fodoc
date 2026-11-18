import { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { StackedCard } from "@/components/StackedCard";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const u = await login(email, password);
      toast.success(`Selamat datang, ${u.name}`);
      nav("/");
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[76vh] max-w-[1100px] mx-auto px-4 sm:px-8 py-8 sm:py-14 flex items-center justify-center">
      <div className="w-full max-w-[430px]">
        <div className="mb-6 sm:mb-8 flex flex-col items-center text-center">
          <img
            src="/images/fodoc-logo.png"
            alt="FODOC Foto Dokumentasi"
            className="h-16 sm:h-20 w-auto object-contain mb-3"
          />
          <h1 className="text-[26px] sm:text-[30px] font-normal leading-[1.15] tracking-[-0.025em] text-[#171717]">
            Masuk ke <span className="font-serif-brand">FODOC</span>
          </h1>
          <p className="text-[13.5px] sm:text-[14px] text-[#6E6D6A] mt-1.5">
            Foto Dokumentasi — Mahasiswa, Panitia Acara, &amp; Admin
          </p>
        </div>

        <StackedCard
          accent="green"
          category="Portal Masuk"
          meta="JWT · RBAC"
          bodyClassName="p-5 sm:p-7"
        >
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="font-mono text-[11px] uppercase tracking-wider text-[#6E6D6A] block mb-1.5">
                Alamat Email
              </label>
              <input
                data-testid="login-email-input"
                type="email"
                required
                placeholder="41523010007@student.mercubuana.ac.id"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-3.5 py-2.5 text-[14px] placeholder:text-[#8F8E8B]"
              />
              <p className="mt-1 text-[11px] text-[#8F8E8B]">
                Mahasiswa gunakan email <span className="font-mono text-[#52524E]">&lt;NIM&gt;@student.mercubuana.ac.id</span>. Panitia dapat masuk setelah di-ACC Admin.
              </p>
            </div>

            <div>
              <label className="font-mono text-[11px] uppercase tracking-wider text-[#6E6D6A] block mb-1.5">
                Kata Sandi
              </label>
              <input
                data-testid="login-password-input"
                type="password"
                required
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-3.5 py-2.5 text-[14px] placeholder:text-[#8F8E8B]"
              />
            </div>

            {error && (
              <div
                data-testid="login-error"
                className="rounded-[10px] border border-red-200 bg-red-50/80 text-[12.5px] text-red-700 p-3 leading-relaxed"
              >
                {error}
              </div>
            )}

            <button
              data-testid="login-submit-button"
              type="submit"
              disabled={loading}
              className="cta-btn-dark w-full mt-2 text-[14px] py-2.5 flex items-center justify-center gap-2 disabled:opacity-60 cursor-pointer"
            >
              <span>{loading ? "Memverifikasi..." : "Masuk ke Sistem"}</span>
              <ArrowRight className="size-4" />
            </button>
          </form>

          <div className="mt-6 pt-5 border-t border-black/[0.06] text-center text-[13px] text-[#6E6D6A]">
            Belum memiliki akun mahasiswa?{" "}
            <Link to="/register" className="text-[#171717] font-medium underline underline-offset-4 hover:text-[#6E6D6A]">
              Daftar Sekarang
            </Link>
          </div>
        </StackedCard>

        <div className="mt-6 text-center">
          <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-[#8F8E8B]">
            <ShieldCheck className="size-3.5 text-emerald-700" />
            Keamanan Data Wajah Kampus Terproteksi
          </span>
        </div>
      </div>
    </div>
  );
}

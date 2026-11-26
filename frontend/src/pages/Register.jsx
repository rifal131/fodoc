import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import {
  UserCheck,
  Camera,
  ArrowRight,
  ShieldCheck,
  Users,
  CheckCircle2,
  Clock,
  Search,
  AlertTriangle,
  Building2,
  Loader2,
  Mail,
  KeyRound,
  ArrowLeft,
} from "lucide-react";
import { StackedCard } from "@/components/StackedCard";

const STUDENT_DOMAIN = "student.mercubuana.ac.id";

export default function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [role, setRole] = useState("mahasiswa"); // "mahasiswa" | "panitia"
  const [name, setName] = useState("");
  const [nim, setNim] = useState("");
  const [committeeReason, setCommitteeReason] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // Status cek data mahasiswa
  const [checkingStudent, setCheckingStudent] = useState(false);
  const [studentCheck, setStudentCheck] = useState(null);

  // OTP Email 2-step state (khusus mahasiswa)
  const [otpStep, setOtpStep] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [sendingOtp, setSendingOtp] = useState(false);
  const [otpCooldown, setOtpCooldown] = useState(0);
  const [otpDevMode, setOtpDevMode] = useState(false);
  const [otpNotice, setOtpNotice] = useState("");

  // Status menunggu ACC Admin untuk Panitia
  const [pendingInfo, setPendingInfo] = useState(null);

  const cleanNim = nim.replace(/\s+/g, "");
  const expectedEmail = cleanNim ? `${cleanNim}@${STUDENT_DOMAIN}` : "";

  useEffect(() => {
    if (otpCooldown <= 0) return;
    const t = setInterval(() => {
      setOtpCooldown((prev) => (prev <= 1 ? 0 : prev - 1));
    }, 1000);
    return () => clearInterval(t);
  }, [otpCooldown]);

  const handleRoleSwitch = (nextRole) => {
    setRole(nextRole);
    setError("");
    setStudentCheck(null);
    setOtpStep(false);
    setOtpCode("");
    setOtpNotice("");
    setOtpDevMode(false);
    setNim("");
    setCommitteeReason("");
    setEmail("");
  };

  const handleCheckStudentData = async () => {
    if (!cleanNim || !name.trim()) {
      toast.error("Isi Nama Lengkap dan NIM terlebih dahulu untuk cek data mahasiswa.");
      return;
    }
    setCheckingStudent(true);
    setError("");
    try {
      const { data } = await api.post("/pddikti/verify", {
        nim: cleanNim,
        name: name.trim(),
      });
      setStudentCheck(data);
      if (data.valid) {
        if (!email.trim() && data.expected_email) {
          setEmail(data.expected_email);
        }
        toast.success("Data mahasiswa Universitas Mercu Buana cocok!");
      } else {
        toast.error(data.message);
      }
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || "Gagal memeriksa data mahasiswa");
    } finally {
      setCheckingStudent(false);
    }
  };

  const handleRequestOtp = async () => {
    setError("");
    if (name.trim().length < 2) {
      setError("Nama lengkap wajib diisi.");
      return;
    }
    if (!/^\d{6,15}$/.test(cleanNim)) {
      setError("Format NIM tidak valid. NIM harus berupa angka 6 sampai 15 digit.");
      return;
    }
    const lowerEmail = email.trim().toLowerCase();
    if (lowerEmail !== expectedEmail) {
      setError(
        `Email mahasiswa wajib berformat <NIM>@${STUDENT_DOMAIN}. Untuk NIM ${cleanNim}, gunakan ${expectedEmail}.`
      );
      return;
    }
    if (password.length < 6) {
      setError("Kata sandi minimal 6 karakter.");
      return;
    }

    setSendingOtp(true);
    try {
      const { data } = await api.post("/auth/send-otp", {
        name: name.trim(),
        nim: cleanNim,
        email: lowerEmail,
      });
      setOtpStep(true);
      setOtpCode("");
      setOtpCooldown(data.cooldown_seconds || 45);
      setOtpDevMode(Boolean(data.dev_mode));
      setOtpNotice(data.message || `Kode verifikasi 6 digit telah dikirim ke ${lowerEmail}.`);
      toast.success(data.dev_mode ? "Kode OTP dicetak di terminal backend (mode uji coba)." : `Kode OTP dikirim ke ${lowerEmail}!`);
    } catch (err) {
      const msg = formatApiError(err.response?.data?.detail) || err.message;
      setError(msg);
      toast.error(msg);
    } finally {
      setSendingOtp(false);
    }
  };

  const submit = async (e) => {
    e.preventDefault();
    setError("");

    // Mahasiswa: langkah 1 -> kirim OTP ke email terlebih dahulu
    if (role === "mahasiswa" && !otpStep) {
      await handleRequestOtp();
      return;
    }

    if (role === "mahasiswa") {
      if (otpCode.trim().length !== 6) {
        setError("Masukkan 6 digit kode verifikasi OTP yang dikirim ke email Anda.");
        return;
      }
    } else {
      if (nim.trim().length < 2) {
        setError("Wajib mengisi nama Unit / Organisasi / Kepanitiaan Anda agar Admin dapat memverifikasi.");
        return;
      }
    }

    setLoading(true);
    try {
      const res = await register({
        name: name.trim(),
        nim: role === "mahasiswa" ? cleanNim : nim.trim(),
        committee_reason: role === "panitia" ? committeeReason.trim() : null,
        email: email.trim().toLowerCase(),
        password,
        role,
        otp_code: role === "mahasiswa" ? otpCode.trim() : null,
      });

      if (res?.pending_approval) {
        setPendingInfo({
          name: name.trim(),
          email: email.trim().toLowerCase(),
          organization: nim.trim(),
          message: res.message,
        });
        toast.success("Permohonan akun Panitia berhasil dikirim! Menunggu ACC Admin.");
      } else {
        toast.success("Verifikasi email & pendaftaran berhasil! Lanjutkan verifikasi wajah.");
        nav("/enroll");
      }
    } catch (err) {
      setError(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setLoading(false);
    }
  };

  if (pendingInfo) {
    return (
      <div className="min-h-[80vh] max-w-[1100px] mx-auto px-4 sm:px-8 py-10 sm:py-14 flex items-center justify-center">
        <div className="w-full max-w-[460px]">
          <StackedCard
            accent="amber"
            category="Permohonan Panitia Terkirim"
            meta="MENUNGGU ACC ADMIN"
            bodyClassName="p-6 sm:p-8 text-center"
          >
            <div className="size-14 rounded-2xl bg-amber-50 border border-amber-200 text-amber-700 grid place-items-center mx-auto mb-4">
              <Clock className="size-7" />
            </div>
            <h1 className="text-[22px] sm:text-[25px] font-medium tracking-[-0.02em] text-[#171717]">
              Menunggu Persetujuan Admin
            </h1>
            <p className="text-[13.5px] text-[#6E6D6A] mt-2 leading-relaxed">
              {pendingInfo.message}
            </p>

            <div className="mt-5 rounded-[12px] bg-[#F5F5F2] border border-black/[0.08] p-4 text-left space-y-2 text-[12.5px]">
              <div className="flex justify-between gap-2">
                <span className="text-[#8F8E8B]">Nama</span>
                <span className="font-medium text-[#171717] text-right">{pendingInfo.name}</span>
              </div>
              <div className="flex justify-between gap-2">
                <span className="text-[#8F8E8B]">Email</span>
                <span className="font-mono text-[#171717] text-right break-all">{pendingInfo.email}</span>
              </div>
              <div className="flex justify-between gap-2">
                <span className="text-[#8F8E8B]">Kepanitiaan / Unit</span>
                <span className="font-medium text-[#171717] text-right">{pendingInfo.organization}</span>
              </div>
            </div>

            <div className="mt-6 flex flex-col sm:flex-row gap-2.5">
              <Link
                to="/login"
                className="cta-btn-dark flex-1 py-2.5 text-[13.5px] inline-flex items-center justify-center"
              >
                Ke Halaman Masuk
              </Link>
              <Link
                to="/"
                className="cta-btn-light flex-1 py-2.5 text-[13.5px] inline-flex items-center justify-center"
              >
                Kembali ke Beranda
              </Link>
            </div>
          </StackedCard>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-[80vh] max-w-[1100px] mx-auto px-4 sm:px-8 py-7 sm:py-12 flex items-center justify-center">
      <div className="w-full max-w-[460px]">
        <div className="mb-5 sm:mb-6 flex flex-col items-center text-center">
          <img
            src="/images/fodoc-logo-full.png"
            alt="FODOC Foto Dokumentasi Kampus"
            className="h-12 sm:h-14 w-auto object-contain mb-3"
          />
          <h1 className="text-[26px] sm:text-[30px] font-normal leading-[1.15] tracking-[-0.025em] text-[#171717]">
            Daftar Akun Baru
          </h1>
          <p className="text-[13.5px] sm:text-[14px] text-[#6E6D6A] mt-1.5">
            {role === "mahasiswa"
              ? "Khusus mahasiswa aktif Universitas Mercu Buana yang terdaftar pada data kampus."
              : "Ajukan akun Panitia Acara (memerlukan verifikasi & ACC dari Admin)."}
          </p>
        </div>

        {/* Cofounder Soft Pill Role Switcher */}
        <div className="mb-5 grid grid-cols-2 gap-1.5 p-1 bg-black/[0.05] rounded-[12px] border border-black/[0.06]">
          <button
            type="button"
            onClick={() => handleRoleSwitch("mahasiswa")}
            className={`flex items-center justify-center gap-2 py-2 px-3 rounded-[9px] text-[13px] transition-all cursor-pointer ${
              role === "mahasiswa"
                ? "bg-white text-[#171717] font-medium shadow-[0_1px_2px_rgba(0,0,0,0.06)] border border-black/[0.06]"
                : "text-[#6E6D6A] hover:text-[#171717]"
            }`}
          >
            <Users className="size-3.5" />
            Mahasiswa
          </button>
          <button
            type="button"
            onClick={() => handleRoleSwitch("panitia")}
            className={`flex items-center justify-center gap-2 py-2 px-3 rounded-[9px] text-[13px] transition-all cursor-pointer ${
              role === "panitia"
                ? "bg-white text-[#171717] font-medium shadow-[0_1px_2px_rgba(0,0,0,0.06)] border border-black/[0.06]"
                : "text-[#6E6D6A] hover:text-[#171717]"
            }`}
          >
            <Camera className="size-3.5" />
            Panitia Acara
          </button>
        </div>

        <StackedCard
          accent={role === "mahasiswa" ? "cyan" : "amber"}
          category={
            role === "mahasiswa"
              ? otpStep
                ? "Verifikasi Kode OTP Email"
                : "Pendaftaran Mahasiswa UMB"
              : "Pengajuan Akun Panitia"
          }
          meta={
            role === "mahasiswa"
              ? otpStep
                ? "LANGKAH 2/2 · OTP"
                : "LANGKAH 1/2 · DATA"
              : "PERLU ACC ADMIN"
          }
          bodyClassName="p-5 sm:p-7"
        >
          {/* STEP 2 MAHASISWA: INPUT KODE OTP 6 DIGIT */}
          {role === "mahasiswa" && otpStep ? (
            <form onSubmit={submit} className="space-y-4">
              <div
                className={`rounded-[12px] border p-3.5 text-[12.5px] flex items-start gap-2.5 leading-relaxed ${
                  otpDevMode
                    ? "bg-amber-50 border-amber-200 text-amber-900"
                    : "bg-emerald-50 border-emerald-200 text-emerald-900"
                }`}
              >
                <Mail className="size-4 shrink-0 mt-0.5" />
                <div>
                  <div className="font-semibold mb-0.5">
                    {otpDevMode ? "Mode Uji Coba Email (SMTP Belum Diisi)" : "Kode Verifikasi Terkirim"}
                  </div>
                  <p>{otpNotice}</p>
                </div>
              </div>

              <div>
                <label className="font-mono text-[11px] uppercase tracking-wider text-[#6E6D6A] block mb-2">
                  Masukkan 6 Digit Kode OTP
                </label>
                <div className="relative">
                  <KeyRound className="size-4 text-[#8F8E8B] absolute left-3.5 top-1/2 -translate-y-1/2" />
                  <input
                    data-testid="register-otp-input"
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    maxLength={6}
                    required
                    autoFocus
                    placeholder="000000"
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value.replace(/[^\d]/g, "").slice(0, 6))}
                    className="w-full pl-10 pr-4 py-3 text-center font-mono text-[22px] font-semibold tracking-[0.35em] placeholder:tracking-[0.25em] placeholder:text-[#C5C4C0]"
                  />
                </div>
                <p className="mt-1.5 text-[11.5px] text-[#8F8E8B] text-center">
                  Dikirim ke <span className="font-mono text-[#171717]">{email}</span> (berlaku 5 menit)
                </p>
              </div>

              {error && (
                <div
                  data-testid="register-error"
                  className="rounded-[10px] border border-red-200 bg-red-50/80 text-[12.5px] text-red-700 p-3 leading-relaxed"
                >
                  {error}
                </div>
              )}

              <button
                data-testid="register-verify-otp-button"
                type="submit"
                disabled={loading || otpCode.length !== 6}
                className="cta-btn-dark w-full text-[14px] py-2.5 flex items-center justify-center gap-2 disabled:opacity-50 cursor-pointer"
              >
                {loading ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    <span>Memverifikasi Kode OTP...</span>
                  </>
                ) : (
                  <>
                    <span>Verifikasi OTP &amp; Selesaikan Daftar</span>
                    <ArrowRight className="size-4" />
                  </>
                )}
              </button>

              <div className="flex items-center justify-between gap-2 pt-2 text-[12.5px]">
                <button
                  type="button"
                  onClick={() => {
                    setOtpStep(false);
                    setError("");
                  }}
                  className="inline-flex items-center gap-1 text-[#6E6D6A] hover:text-[#171717] cursor-pointer"
                >
                  <ArrowLeft className="size-3.5" />
                  Ubah data
                </button>

                <button
                  type="button"
                  disabled={otpCooldown > 0 || sendingOtp}
                  onClick={handleRequestOtp}
                  className="font-medium text-[#171717] hover:underline disabled:text-[#8F8E8B] disabled:no-underline cursor-pointer disabled:cursor-not-allowed"
                >
                  {sendingOtp
                    ? "Mengirim..."
                    : otpCooldown > 0
                    ? `Kirim ulang (${otpCooldown}d)`
                    : "Kirim Ulang OTP"}
                </button>
              </div>
            </form>
          ) : (
            <>
              {role === "mahasiswa" ? (
                <div className="mb-4 rounded-[11px] bg-[#F5F5F2] border border-black/[0.08] p-3 text-[12px] text-[#52524E] flex items-start gap-2.5 leading-relaxed">
                  <Building2 className="size-4 text-[#171717] shrink-0 mt-0.5" />
                  <div>
                    Wajib terdaftar sebagai mahasiswa aktif <strong className="text-[#171717]">UNIVERSITAS MERCU BUANA</strong>, menggunakan email{" "}
                    <span className="font-mono text-[#171717] font-medium">&lt;NIM&gt;@{STUDENT_DOMAIN}</span>, dan memverifikasi kode OTP 6 digit di email.
                  </div>
                </div>
              ) : (
                <div className="mb-4 rounded-[11px] bg-amber-50 border border-amber-200 p-3 text-[12px] text-amber-900 flex items-start gap-2.5 leading-relaxed">
                  <AlertTriangle className="size-4 text-amber-700 shrink-0 mt-0.5" />
                  <div>
                    Untuk menjaga keamanan dokumentasi kampus, pendaftaran Panitia akan dikirim ke <strong>Admin untuk ditinjau &amp; di-ACC</strong> terlebih dahulu sebelum bisa login dan mengunggah foto.
                  </div>
                </div>
              )}

              <form onSubmit={submit} className="space-y-4">
                <div>
                  <label className="font-mono text-[11px] uppercase tracking-wider text-[#6E6D6A] block mb-1.5">
                    {role === "mahasiswa" ? "Nama Lengkap Mahasiswa" : "Nama Lengkap Penanggung Jawab"}
                  </label>
                  <input
                    data-testid="register-name-input"
                    type="text"
                    required
                    placeholder={role === "mahasiswa" ? "misal: Nur Rifal" : "misal: Agil Pratama"}
                    value={name}
                    onChange={(e) => {
                      setName(e.target.value);
                      setStudentCheck(null);
                    }}
                    className="w-full px-3.5 py-2.5 text-[14px] placeholder:text-[#8F8E8B]"
                  />
                </div>

                {role === "mahasiswa" ? (
                  <div className="space-y-2">
                    <label className="font-mono text-[11px] uppercase tracking-wider text-[#6E6D6A] block">
                      NIM (Nomor Induk Mahasiswa)
                    </label>
                    <div className="flex flex-col sm:flex-row gap-2">
                      <input
                        data-testid="register-nim-input"
                        type="text"
                        inputMode="numeric"
                        required
                        placeholder="misal: 41523010007"
                        value={nim}
                        onChange={(e) => {
                          const val = e.target.value.replace(/[^\d]/g, "");
                          setNim(val);
                          setStudentCheck(null);
                          if (val) {
                            setEmail(`${val}@${STUDENT_DOMAIN}`);
                          } else {
                            setEmail("");
                          }
                        }}
                        className="flex-1 px-3.5 py-2.5 text-[14px] font-mono placeholder:text-[#8F8E8B]"
                      />
                      <button
                        type="button"
                        onClick={handleCheckStudentData}
                        disabled={checkingStudent || !cleanNim || !name.trim()}
                        data-testid="check-pddikti-button"
                        className="cta-btn-light px-3.5 py-2.5 text-[12.5px] inline-flex items-center justify-center gap-1.5 whitespace-nowrap disabled:opacity-45 cursor-pointer"
                      >
                        {checkingStudent ? (
                          <Loader2 className="size-3.5 animate-spin" />
                        ) : (
                          <Search className="size-3.5" />
                        )}
                        <span>Cek Data Mahasiswa</span>
                      </button>
                    </div>

                    {studentCheck && (
                      <div
                        className={`rounded-[10px] border p-2.5 text-[12px] flex items-start gap-2 leading-snug ${
                          studentCheck.valid
                            ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                            : "bg-red-50 border-red-200 text-red-700"
                        }`}
                      >
                        {studentCheck.valid ? (
                          <CheckCircle2 className="size-4 text-emerald-600 shrink-0 mt-0.5" />
                        ) : (
                          <AlertTriangle className="size-4 text-red-600 shrink-0 mt-0.5" />
                        )}
                        <div>
                          <div className="font-medium">{studentCheck.message}</div>
                          {studentCheck.valid && studentCheck.prodi && (
                            <div className="font-mono text-[11px] mt-0.5 text-emerald-700">
                              {studentCheck.kampus} · {studentCheck.prodi} ({studentCheck.status})
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <>
                    <div>
                      <label className="font-mono text-[11px] uppercase tracking-wider text-[#6E6D6A] block mb-1.5">
                        Asal Kepanitiaan / Unit / Organisasi *
                      </label>
                      <input
                        data-testid="register-nim-input"
                        type="text"
                        required
                        placeholder="misal: Panitia Wisuda 2026 / BEM Fasilkom / Humas UMB"
                        value={nim}
                        onChange={(e) => setNim(e.target.value)}
                        className="w-full px-3.5 py-2.5 text-[14px] placeholder:text-[#8F8E8B]"
                      />
                    </div>

                    <div>
                      <label className="font-mono text-[11px] uppercase tracking-wider text-[#6E6D6A] block mb-1.5">
                        Keterangan / Acara yang Didokumentasikan
                      </label>
                      <textarea
                        rows={2}
                        placeholder="misal: Dokumentasi Seminar Nasional & Wisuda Fakultas Ilmu Komputer UMB"
                        value={committeeReason}
                        onChange={(e) => setCommitteeReason(e.target.value)}
                        className="w-full px-3.5 py-2 text-[13.5px] placeholder:text-[#8F8E8B]"
                      />
                    </div>
                  </>
                )}

                <div>
                  <label className="font-mono text-[11px] uppercase tracking-wider text-[#6E6D6A] block mb-1.5">
                    {role === "mahasiswa" ? `Email Mahasiswa (@${STUDENT_DOMAIN})` : "Alamat Email Panitia"}
                  </label>
                  <input
                    data-testid="register-email-input"
                    type="email"
                    required
                    placeholder={
                      role === "mahasiswa"
                        ? expectedEmail || `41523010007@${STUDENT_DOMAIN}`
                        : "panitia@mercubuana.ac.id"
                    }
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className="w-full px-3.5 py-2.5 text-[14px] font-mono placeholder:text-[#8F8E8B]"
                  />
                  {role === "mahasiswa" && (
                    <p className="mt-1 text-[11px] text-[#8F8E8B]">
                      Otomatis mengikuti format{" "}
                      <span className="font-mono text-[#171717]">
                        {expectedEmail || `<NIM>@${STUDENT_DOMAIN}`}
                      </span>
                    </p>
                  )}
                </div>

                <div>
                  <label className="font-mono text-[11px] uppercase tracking-wider text-[#6E6D6A] block mb-1.5">
                    Kata Sandi (Minimal 6 Karakter)
                  </label>
                  <input
                    data-testid="register-password-input"
                    type="password"
                    required
                    minLength={6}
                    placeholder="••••••••"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="w-full px-3.5 py-2.5 text-[14px] placeholder:text-[#8F8E8B]"
                  />
                </div>

                {error && (
                  <div
                    data-testid="register-error"
                    className="rounded-[10px] border border-red-200 bg-red-50/80 text-[12.5px] text-red-700 p-3 leading-relaxed"
                  >
                    {error}
                  </div>
                )}

                <button
                  data-testid="register-submit-button"
                  type="submit"
                  disabled={loading || sendingOtp}
                  className="cta-btn-dark w-full mt-2 text-[14px] py-2.5 flex items-center justify-center gap-2 disabled:opacity-60 cursor-pointer"
                >
                  {sendingOtp || loading ? (
                    <>
                      <Loader2 className="size-4 animate-spin" />
                      <span>
                        {role === "mahasiswa" ? "Mengirim Kode OTP..." : "Mengirim Permohonan..."}
                      </span>
                    </>
                  ) : (
                    <>
                      {role === "mahasiswa" ? (
                        <Mail className="size-4" />
                      ) : null}
                      <span>
                        {role === "panitia"
                          ? "Ajukan Akun Panitia (Minta ACC Admin)"
                          : "Kirim Kode OTP ke Email"}
                      </span>
                      <ArrowRight className="size-4" />
                    </>
                  )}
                </button>
              </form>
            </>
          )}

          <div className="mt-6 pt-5 border-t border-black/[0.06] text-center text-[13px] text-[#6E6D6A]">
            Sudah memiliki akun?{" "}
            <Link to="/login" className="text-[#171717] font-medium underline underline-offset-4 hover:text-[#6E6D6A]">
              Masuk
            </Link>
          </div>
        </StackedCard>

        <div className="mt-6 text-center">
          <span className="inline-flex items-center gap-1.5 font-mono text-[11px] text-[#8F8E8B]">
            {role === "mahasiswa" ? (
              <>
                <ShieldCheck className="size-3.5 text-emerald-700 shrink-0" />
                Verifikasi Email OTP 6 Digit · Universitas Mercu Buana
              </>
            ) : (
              <>
                <UserCheck className="size-3.5 text-[#171717] shrink-0" />
                Akses unggah foto panitia aktif setelah disetujui (ACC) Admin
              </>
            )}
          </span>
        </div>
      </div>
    </div>
  );
}

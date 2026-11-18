import { useEffect, useState } from "react";
import api, { formatApiError } from "@/lib/api";
import { toast } from "sonner";
import {
  CheckCircle2,
  Trash2,
  RefreshCw,
  AlertTriangle,
  Check,
  X,
  UserCheck,
  Upload,
  Download,
  Search,
  Plus,
  Building2,
} from "lucide-react";
import { StackedCard } from "@/components/StackedCard";

export default function Admin() {
  const [stats, setStats] = useState(null);
  const [users, setUsers] = useState([]);
  const [pendingPanitia, setPendingPanitia] = useState([]);
  const [pddiktiList, setPddiktiList] = useState([]);
  const [pddiktiQuery, setPddiktiQuery] = useState("");
  const [feedbackSummary, setFeedbackSummary] = useState(null);
  const [reprocessing, setReprocessing] = useState(false);
  const [savingSettings, setSavingSettings] = useState(false);
  const [busyPanitiaId, setBusyPanitiaId] = useState(null);
  const [savingPddikti, setSavingPddikti] = useState(false);
  const [importingCsv, setImportingCsv] = useState(false);

  const [pddiktiForm, setPddiktiForm] = useState({
    nim: "",
    nama: "",
    kampus: "UNIVERSITAS MERCU BUANA",
    prodi: "Teknik Informatika",
    status: "Aktif",
  });

  const [settings, setSettings] = useState({
    ambang_cocok: 0.55,
    ambang_perlu_cek: 0.40,
    ambang_selisih: 0.10,
    min_wajah_px: 28,
    min_wajah_acuan_px: 60,
    ambang_ketajaman: 15.0,
    confidence_deteksi: 0.4639,
  });

  const loadPddikti = async (q = pddiktiQuery) => {
    try {
      const { data } = await api.get("/admin/pddikti", { params: q ? { q } : {} });
      setPddiktiList(data);
    } catch {}
  };

  const loadData = async () => {
    try {
      const [s, cfg, u, fb, pp, pd] = await Promise.all([
        api.get("/admin/stats"),
        api.get("/admin/settings"),
        api.get("/admin/users"),
        api.get("/admin/feedback-summary"),
        api.get("/admin/panitia/pending").catch(() => ({ data: [] })),
        api.get("/admin/pddikti", { params: pddiktiQuery ? { q: pddiktiQuery } : {} }).catch(() => ({ data: [] })),
      ]);
      setStats(s.data);
      if (cfg.data?.settings) setSettings(cfg.data.settings);
      setUsers(u.data);
      setFeedbackSummary(fb.data);
      setPendingPanitia(pp.data || []);
      setPddiktiList(pd.data || []);
    } catch {
      toast.error("Gagal memuat data admin dashboard");
    }
  };

  useEffect(() => {
    loadData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSettingChange = (field, value) => {
    setSettings((prev) => ({
      ...prev,
      [field]: typeof value === "string" ? parseFloat(value) || 0 : value,
    }));
  };

  const saveSettings = async (e) => {
    e?.preventDefault();
    if (Number(settings.ambang_perlu_cek) >= Number(settings.ambang_cocok)) {
      toast.error("Validasi Gagal: ambang_perlu_cek harus lebih kecil dari ambang_cocok.");
      return;
    }

    setSavingSettings(true);
    try {
      await api.put("/admin/settings", settings);
      toast.success("Konfigurasi ambang batas berhasil disimpan!");
      loadData();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setSavingSettings(false);
    }
  };

  const handleReprocessDecisions = async () => {
    if (
      !window.confirm(
        "Jalankan 'Proses Ulang Keputusan'? Sistem akan menghitung ulang status (COCOK, PERLU_CEK, UNKNOWN) pada seluruh wajah dokumentasi yang tersimpan menggunakan ambang terbaru tanpa ekstraksi ulang."
      )
    ) {
      return;
    }

    setReprocessing(true);
    try {
      const { data } = await api.post("/admin/reprocess-decisions");
      toast.success(
        `Proses ulang selesai! ${data.photos_processed} foto diproses. Hasil: ${data.total_cocok} COCOK, ${data.total_perlu_cek} PERLU_CEK, ${data.total_unknown} UNKNOWN.`
      );
      loadData();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setReprocessing(false);
    }
  };

  const handleApprovePanitia = async (uid) => {
    setBusyPanitiaId(uid);
    try {
      const { data } = await api.post(`/admin/panitia/${uid}/approve`);
      toast.success(data.message || "Akun panitia disetujui (ACC)!");
      loadData();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setBusyPanitiaId(null);
    }
  };

  const handleRejectPanitia = async (uid) => {
    if (!window.confirm("Tolak permohonan akun Panitia ini?")) return;
    setBusyPanitiaId(uid);
    try {
      const { data } = await api.post(`/admin/panitia/${uid}/reject`);
      toast.success(data.message || "Permohonan panitia ditolak.");
      loadData();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setBusyPanitiaId(null);
    }
  };

  const handleSavePddikti = async (e) => {
    e.preventDefault();
    setSavingPddikti(true);
    try {
      const { data } = await api.post("/admin/pddikti", pddiktiForm);
      toast.success(data.message || "Data mahasiswa PDDIKTI disimpan!");
      setPddiktiForm({
        nim: "",
        nama: "",
        kampus: "UNIVERSITAS MERCU BUANA",
        prodi: "Teknik Informatika",
        status: "Aktif",
      });
      loadData();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setSavingPddikti(false);
    }
  };

  const handleImportCsv = async (file) => {
    if (!file) return;
    setImportingCsv(true);
    try {
      const fd = new FormData();
      fd.append("file", file);
      const { data } = await api.post("/admin/pddikti/import-csv", fd, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      toast.success(data.message || "Import CSV berhasil!");
      loadData();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    } finally {
      setImportingCsv(false);
    }
  };

  const handleDownloadCsvTemplate = () => {
    const csvContent =
      "nim,nama,kampus,prodi,status\n" +
      "41523010007,Nur Rifal,UNIVERSITAS MERCU BUANA,Teknik Informatika,Aktif\n" +
      "41523010012,Harari Zuhdi,UNIVERSITAS MERCU BUANA,Teknik Informatika,Aktif\n" +
      "41523010006,Vikry Aldiansyah,UNIVERSITAS MERCU BUANA,Teknik Informatika,Aktif\n";
    const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "template_pddikti_umb.csv";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const handleDeletePddikti = async (nim) => {
    if (!window.confirm(`Hapus data PDDIKTI NIM ${nim}?`)) return;
    try {
      await api.delete(`/admin/pddikti/${nim}`);
      toast.success(`Data NIM ${nim} dihapus`);
      loadData();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    }
  };

  const updateRole = async (uid, role) => {
    try {
      await api.patch(`/admin/users/${uid}/role`, { role });
      toast.success("Peran akun pengguna berhasil diperbarui");
      loadData();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    }
  };

  const deleteUser = async (uid) => {
    if (!window.confirm("Hapus user ini secara permanen dari sistem?")) return;
    try {
      await api.delete(`/admin/users/${uid}`);
      toast.success("Pengguna berhasil dihapus");
      loadData();
    } catch (err) {
      toast.error(formatApiError(err.response?.data?.detail) || err.message);
    }
  };

  if (!stats) {
    return (
      <div className="p-16 text-center text-[#8F8E8B] font-mono text-[12px] animate-pulse">
        Memuat Panel Administrasi FODOC...
      </div>
    );
  }

  return (
    <div className="max-w-[1100px] mx-auto px-4 sm:px-8 py-7 sm:py-12" data-testid="admin-panel">
      {/* Header */}
      <div className="mb-7 sm:mb-10 flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="font-mono text-[11px] sm:text-[12px] text-[#8F8E8B] mb-2">
            Pusat Kontrol Sistem, ACC Panitia &amp; Data PDDIKTI
          </div>
          <h1 className="text-[26px] sm:text-[40px] font-normal leading-[1.15] tracking-[-0.025em] text-[#171717]">
            Admin <span className="text-[#8F8E8B]">Dashboard</span>
          </h1>
          <p className="text-[13.5px] sm:text-[14px] text-[#6E6D6A] mt-2">
            Kelola persetujuan panitia acara, data master PDDIKTI Universitas Mercu Buana, dan konfigurasi sistem.
          </p>
        </div>

        <button
          onClick={handleReprocessDecisions}
          disabled={reprocessing}
          data-testid="reprocess-decisions-button"
          className="cta-btn-dark w-full sm:w-auto inline-flex items-center justify-center gap-2 text-[13.5px] px-4 py-2.5 disabled:opacity-50 cursor-pointer self-start md:self-auto"
        >
          <RefreshCw className={`size-4 ${reprocessing ? "animate-spin" : ""}`} />
          <span>{reprocessing ? "Memproses Ulang..." : "Proses Ulang Keputusan"}</span>
        </button>
      </div>

      {/* METRIC STATS */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-5 mb-8 sm:mb-12" data-testid="admin-stats-grid">
        <StackedCard accent="ink" category="Total Pengguna" meta="AKUN" bodyClassName="p-3.5 sm:p-5">
          <div className="font-mono text-[26px] sm:text-[32px] font-medium text-[#171717] leading-none">{stats.users_total}</div>
          <div className="text-[10.5px] sm:text-[11px] text-[#8F8E8B] font-mono mt-2">
            {stats.mahasiswa} Mhs · {stats.panitia} Panitia
          </div>
        </StackedCard>

        <StackedCard accent="amber" category="Panitia Menunggu ACC" meta="PERSETUJUAN" bodyClassName="p-3.5 sm:p-5">
          <div className="font-mono text-[26px] sm:text-[32px] font-medium text-amber-700 leading-none">
            {stats.pending_panitia ?? pendingPanitia.length}
          </div>
          <div className="text-[10.5px] sm:text-[11px] text-[#8F8E8B] font-mono mt-2">Perlu tinjauan Admin</div>
        </StackedCard>

        <StackedCard accent="cyan" category="Master PDDIKTI UMB" meta="VERIFIKASI" bodyClassName="p-3.5 sm:p-5">
          <div className="font-mono text-[26px] sm:text-[32px] font-medium text-[#171717] leading-none">
            {stats.pddikti_count ?? pddiktiList.length}
          </div>
          <div className="text-[10.5px] sm:text-[11px] text-[#8F8E8B] font-mono mt-2">Data NIM &amp; Nama terdaftar</div>
        </StackedCard>

        <StackedCard accent="green" category="Status COCOK" meta="TERDISTRIBUSI" bodyClassName="p-3.5 sm:p-5">
          <div className="font-mono text-[26px] sm:text-[32px] font-medium text-emerald-700 leading-none">
            {stats.faces_cocok ?? stats.matches_total}
          </div>
          <div className="text-[10.5px] sm:text-[11px] text-[#8F8E8B] font-mono mt-2">
            {stats.enrolled_students} Mhs 3 Pose · {stats.faces_perlu_cek ?? 0} Cek
          </div>
        </StackedCard>
      </div>

      {/* PERSETUJUAN (ACC) AKUN PANITIA */}
      <div className="mb-10 sm:mb-12" data-testid="panitia-approval-section">
        <StackedCard
          accent="amber"
          category="Keamanan Akses Panitia"
          meta={`${pendingPanitia.length} MENUNGGU ACC`}
          bodyClassName="p-4 sm:p-7"
        >
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-5 pb-4 border-b border-black/[0.06]">
            <div>
              <h2 className="text-[19px] sm:text-[22px] font-medium tracking-[-0.02em] text-[#171717] flex items-center gap-2">
                <UserCheck className="size-5 text-amber-700 shrink-0" />
                <span>Persetujuan Akun Panitia (ACC Admin)</span>
              </h2>
              <p className="text-[13px] sm:text-[13.5px] text-[#6E6D6A] mt-1">
                Periksa asal kepanitiaan &amp; email pendaftar sebelum memberi izin mengunggah foto dokumentasi acara kampus.
              </p>
            </div>
          </div>

          {pendingPanitia.length === 0 ? (
            <div className="rounded-[12px] bg-[#F5F5F2] border border-black/[0.06] p-5 text-center text-[13px] font-mono text-[#8F8E8B]">
              Tidak ada permohonan akun Panitia yang menunggu persetujuan saat ini.
            </div>
          ) : (
            <div className="grid md:grid-cols-2 gap-4">
              {pendingPanitia.map((p) => (
                <div
                  key={p.id}
                  data-testid={`pending-panitia-${p.id}`}
                  className="rounded-[14px] border border-amber-200 bg-amber-50/40 p-4 flex flex-col justify-between gap-4"
                >
                  <div className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <div className="text-[15px] font-semibold text-[#171717]">{p.name}</div>
                        <div className="font-mono text-[12px] text-[#6E6D6A] break-all">{p.email}</div>
                      </div>
                      <span className="shrink-0 font-mono text-[10px] uppercase px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-200">
                        PENDING ACC
                      </span>
                    </div>

                    <div className="rounded-[10px] bg-white border border-black/[0.07] p-3 space-y-1.5 text-[12.5px]">
                      <div>
                        <span className="font-mono text-[10.5px] uppercase text-[#8F8E8B] block">
                          Asal Kepanitiaan / Unit
                        </span>
                        <span className="font-medium text-[#171717]">{p.organization || p.nim || "—"}</span>
                      </div>
                      {p.committee_reason && (
                        <div className="pt-1 border-t border-black/[0.05]">
                          <span className="font-mono text-[10.5px] uppercase text-[#8F8E8B] block">
                            Keterangan / Acara
                          </span>
                          <span className="text-[#52524E] leading-snug">{p.committee_reason}</span>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    <button
                      type="button"
                      disabled={busyPanitiaId === p.id}
                      onClick={() => handleApprovePanitia(p.id)}
                      data-testid={`approve-panitia-${p.id}`}
                      className="cta-btn-dark flex-1 py-2 px-3 text-[12.5px] inline-flex items-center justify-center gap-1.5 disabled:opacity-50 cursor-pointer"
                    >
                      <Check className="size-3.5" />
                      <span>Setujui (ACC)</span>
                    </button>
                    <button
                      type="button"
                      disabled={busyPanitiaId === p.id}
                      onClick={() => handleRejectPanitia(p.id)}
                      data-testid={`reject-panitia-${p.id}`}
                      className="cta-btn-light flex-1 py-2 px-3 text-[12.5px] inline-flex items-center justify-center gap-1.5 hover:text-red-600 hover:border-red-200 disabled:opacity-50 cursor-pointer"
                    >
                      <X className="size-3.5" />
                      <span>Tolak</span>
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </StackedCard>
      </div>

      {/* DATABASE MASTER PDDIKTI — UNIVERSITAS MERCU BUANA */}
      <div className="mb-10 sm:mb-12" data-testid="pddikti-master-section">
        <StackedCard
          accent="cyan"
          category="Database Master PDDIKTI"
          meta="UNIVERSITAS MERCU BUANA"
          bodyClassName="p-4 sm:p-7"
        >
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-5 pb-4 border-b border-black/[0.06]">
            <div>
              <h2 className="text-[19px] sm:text-[22px] font-medium tracking-[-0.02em] text-[#171717] flex items-center gap-2">
                <Building2 className="size-5 text-[#171717] shrink-0" />
                <span>Data Mahasiswa PDDIKTI (UMB)</span>
              </h2>
              <p className="text-[13px] sm:text-[13.5px] text-[#6E6D6A] mt-1">
                Hanya mahasiswa dengan NIM, Nama Lengkap, dan Kampus <strong>UNIVERSITAS MERCU BUANA</strong> yang cocok di daftar ini serta email <span className="font-mono text-[#171717]">&lt;NIM&gt;@student.mercubuana.ac.id</span> yang dapat mendaftar &amp; masuk.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={handleDownloadCsvTemplate}
                className="cta-btn-light px-3 py-2 text-[12px] inline-flex items-center gap-1.5 cursor-pointer"
              >
                <Download className="size-3.5" />
                <span>Contoh CSV</span>
              </button>

              <label className="cta-btn-dark px-3.5 py-2 text-[12px] inline-flex items-center gap-1.5 cursor-pointer">
                <Upload className="size-3.5" />
                <span>{importingCsv ? "Mengimpor..." : "Import CSV"}</span>
                <input
                  type="file"
                  accept=".csv,text/csv"
                  disabled={importingCsv}
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) handleImportCsv(f);
                    e.target.value = "";
                  }}
                />
              </label>
            </div>
          </div>

          {/* Form Tambah 1 Data Mahasiswa PDDIKTI */}
          <form onSubmit={handleSavePddikti} className="mb-6 p-4 rounded-[12px] bg-[#F5F5F2] border border-black/[0.07] space-y-3">
            <div className="font-mono text-[11px] uppercase tracking-wider text-[#6E6D6A]">
              Tambah / Perbarui Data Mahasiswa PDDIKTI
            </div>
            <div className="grid sm:grid-cols-2 lg:grid-cols-5 gap-3">
              <input
                type="text"
                required
                placeholder="NIM (mis. 41523010007)"
                value={pddiktiForm.nim}
                onChange={(e) => setPddiktiForm({ ...pddiktiForm, nim: e.target.value.replace(/[^\d]/g, "") })}
                className="px-3 py-2 text-[13px] font-mono"
              />
              <input
                type="text"
                required
                placeholder="Nama Lengkap sesuai PDDIKTI"
                value={pddiktiForm.nama}
                onChange={(e) => setPddiktiForm({ ...pddiktiForm, nama: e.target.value })}
                className="px-3 py-2 text-[13px]"
              />
              <input
                type="text"
                required
                placeholder="Kampus"
                value={pddiktiForm.kampus}
                onChange={(e) => setPddiktiForm({ ...pddiktiForm, kampus: e.target.value })}
                className="px-3 py-2 text-[13px]"
              />
              <input
                type="text"
                placeholder="Program Studi"
                value={pddiktiForm.prodi}
                onChange={(e) => setPddiktiForm({ ...pddiktiForm, prodi: e.target.value })}
                className="px-3 py-2 text-[13px]"
              />
              <button
                type="submit"
                disabled={savingPddikti}
                className="cta-btn-dark px-4 py-2 text-[13px] inline-flex items-center justify-center gap-1.5 disabled:opacity-50 cursor-pointer"
              >
                <Plus className="size-3.5" />
                <span>{savingPddikti ? "Menyimpan..." : "Simpan"}</span>
              </button>
            </div>
          </form>

          {/* Search Bar PDDIKTI */}
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 mb-4">
            <div className="relative flex-1 max-w-sm">
              <Search className="size-3.5 text-[#8F8E8B] absolute left-3 top-1/2 -translate-y-1/2" />
              <input
                type="text"
                placeholder="Cari NIM, Nama, atau Prodi..."
                value={pddiktiQuery}
                onChange={(e) => {
                  setPddiktiQuery(e.target.value);
                  loadPddikti(e.target.value);
                }}
                className="w-full pl-9 pr-3 py-2 text-[13px]"
              />
            </div>
            <span className="font-mono text-[11.5px] text-[#8F8E8B]">
              Menampilkan {pddiktiList.length} data mahasiswa
            </span>
          </div>

          <div className="overflow-x-auto rounded-[12px] border border-black/[0.08]">
            <table className="w-full min-w-[620px] text-left text-[12.5px]">
              <thead className="bg-[#F5F5F2] text-[#8F8E8B] border-b border-black/[0.08] font-mono text-[10.5px] uppercase tracking-wider">
                <tr>
                  <th className="px-4 py-2.5 font-medium">NIM</th>
                  <th className="px-4 py-2.5 font-medium">Nama Lengkap</th>
                  <th className="px-4 py-2.5 font-medium">Perguruan Tinggi</th>
                  <th className="px-4 py-2.5 font-medium">Prodi</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
                  <th className="px-4 py-2.5 font-medium text-right">Hapus</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-black/[0.06] bg-white">
                {pddiktiList.map((st) => (
                  <tr key={st.nim} className="hover:bg-[#F5F5F2]/60">
                    <td className="px-4 py-2.5 font-mono font-medium text-[#171717] whitespace-nowrap">{st.nim}</td>
                    <td className="px-4 py-2.5 font-medium text-[#171717] whitespace-nowrap">{st.nama}</td>
                    <td className="px-4 py-2.5 text-[#52524E] whitespace-nowrap">{st.kampus}</td>
                    <td className="px-4 py-2.5 text-[#6E6D6A] whitespace-nowrap">{st.prodi || "—"}</td>
                    <td className="px-4 py-2.5 whitespace-nowrap">
                      <span className="inline-flex rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 px-2 py-0.5 font-mono text-[10.5px]">
                        {st.status || "Aktif"}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        type="button"
                        onClick={() => handleDeletePddikti(st.nim)}
                        className="size-7 rounded-[7px] border border-black/[0.1] bg-white text-[#6E6D6A] hover:bg-red-50 hover:text-red-600 hover:border-red-200 inline-grid place-items-center cursor-pointer"
                        title="Hapus data PDDIKTI"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
                {pddiktiList.length === 0 && (
                  <tr>
                    <td colSpan={6} className="px-4 py-6 text-center font-mono text-[12px] text-[#8F8E8B]">
                      Belum ada data mahasiswa PDDIKTI yang cocok.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </StackedCard>
      </div>

      {/* KONFIGURASI AMBANG BATAS */}
      <div className="mb-10 sm:mb-12" data-testid="settings-section">
        <StackedCard accent="purple" category="Koleksi MongoDB · settings" meta="PARAMETER" bodyClassName="p-4 sm:p-8">
          <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 mb-6 pb-5 border-b border-black/[0.06]">
            <div>
              <h2 className="text-[19px] sm:text-[22px] font-medium tracking-[-0.02em] text-[#171717]">
                Konfigurasi Ambang Batas
              </h2>
              <p className="text-[13px] sm:text-[13.5px] text-[#6E6D6A] mt-1">
                Ubah ambang secara dinamis tanpa mengubah kode. Klik &quot;Proses Ulang Keputusan&quot; setelah menyimpan.
              </p>
            </div>

            <div className="bg-[#F5F5F2] border border-black/[0.08] text-[#6E6D6A] text-[12px] p-3 rounded-[12px] max-w-sm">
              <span className="font-medium text-[#171717]">Rekomendasi:</span>{" "}
              <span className="font-mono text-[#171717]">ambang_cocok ≥ 0.55</span> dan{" "}
              <span className="font-mono text-[#171717]">ambang_perlu_cek 0.40–0.45</span>.
            </div>
          </div>

          <form onSubmit={saveSettings} className="space-y-6">
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {[
                { key: "ambang_cocok", label: "ambang_cocok", desc: "Skor minimal untuk status COCOK otomatis.", step: "0.01", min: "0.10", max: "0.95" },
                { key: "ambang_perlu_cek", label: "ambang_perlu_cek", desc: "Batas bawah skor untuk Antrean Verifikasi.", step: "0.01", min: "0.10", max: "0.95" },
                { key: "ambang_selisih", label: "ambang_selisih (Margin)", desc: "Selisih minimal kandidat top-1 dan top-2.", step: "0.01", min: "0.01", max: "0.50" },
                { key: "min_wajah_px", label: "min_wajah_px (Acara)", desc: "Ukuran sisi minimal wajah (px) untuk COCOK.", step: "1", min: "14", max: "120", isInt: true },
                { key: "min_wajah_acuan_px", label: "min_wajah_acuan_px", desc: "Ukuran sisi minimal wajah saat registrasi.", step: "1", min: "30", max: "200", isInt: true },
                { key: "ambang_ketajaman", label: "ambang_ketajaman", desc: "Batas ketajaman wajah (anti-blur).", step: "0.5", min: "1.0", max: "100.0" },
                { key: "confidence_deteksi", label: "confidence_deteksi", desc: "Ambang keyakinan deteksi wajah.", step: "0.0001", min: "0.10", max: "0.90" },
              ].map((f) => (
                <div key={f.key} className="bg-[#F5F5F2] p-4 rounded-[12px] border border-black/[0.06]">
                  <label className="block font-mono text-[12px] font-medium text-[#171717] mb-1">
                    {f.label}
                  </label>
                  <p className="text-[11.5px] text-[#8F8E8B] mb-2.5">{f.desc}</p>
                  <input
                    type="number"
                    step={f.step}
                    min={f.min}
                    max={f.max}
                    value={settings[f.key]}
                    onChange={(e) =>
                      handleSettingChange(f.key, f.isInt ? parseInt(e.target.value, 10) || 0 : e.target.value)
                    }
                    className="w-full px-3 py-2 text-[14px] font-mono font-medium"
                    required
                  />
                </div>
              ))}
            </div>

            {Number(settings.ambang_perlu_cek) >= Number(settings.ambang_cocok) && (
              <div className="flex items-center gap-2 p-3 rounded-[10px] bg-red-50 text-red-700 text-[12.5px] border border-red-200">
                <AlertTriangle className="size-4 shrink-0" />
                <span>
                  Peringatan Validasi: <strong>ambang_perlu_cek</strong> ({settings.ambang_perlu_cek}) harus lebih kecil dari <strong>ambang_cocok</strong> ({settings.ambang_cocok}).
                </span>
              </div>
            )}

            <div className="flex flex-wrap items-center gap-4 pt-1">
              <button
                type="submit"
                disabled={savingSettings || Number(settings.ambang_perlu_cek) >= Number(settings.ambang_cocok)}
                data-testid="save-settings-button"
                className="cta-btn-dark text-[13.5px] px-5 py-2.5 disabled:opacity-50 cursor-pointer"
              >
                {savingSettings ? "Menyimpan..." : "Simpan Konfigurasi Ambang"}
              </button>

              <span className="text-[11.5px] text-[#8F8E8B] font-mono">
                Setelah menyimpan, klik &quot;Proses Ulang Keputusan&quot; di kanan atas.
              </span>
            </div>
          </form>
        </StackedCard>
      </div>

      {/* EVALUASI FALSE ACCEPTANCE */}
      <div className="mb-10 sm:mb-12" data-testid="feedback-section">
        <StackedCard accent="coral" category="Evaluasi False Acceptance" meta="FEEDBACK" bodyClassName="p-4 sm:p-8">
          <h2 className="text-[19px] sm:text-[20px] font-medium tracking-[-0.015em] text-[#171717]">
            Umpan Balik &quot;Bukan Foto Saya&quot;
          </h2>
          <p className="text-[13px] sm:text-[13.5px] text-[#6E6D6A] mt-1 mb-6">
            Rekapitulasi jumlah penolakan foto oleh mahasiswa per acara kampus.
          </p>

          {!feedbackSummary || feedbackSummary.per_event?.length === 0 ? (
            <div className="text-[13px] font-mono text-[#8F8E8B] p-6 bg-[#F5F5F2] rounded-[12px] border border-black/[0.06] text-center">
              Belum ada laporan umpan balik &quot;Bukan Foto Saya&quot; dari mahasiswa.
            </div>
          ) : (
            <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {feedbackSummary.per_event.map((ev) => (
                <div
                  key={ev.event_id}
                  className="p-4 rounded-[12px] border border-black/[0.08] bg-[#F5F5F2] flex items-center justify-between"
                >
                  <div>
                    <div className="font-medium text-[#171717] text-[14px]">{ev.event_name}</div>
                    <div className="text-[11.5px] text-[#8F8E8B] mt-0.5">Penolakan dilaporkan</div>
                  </div>
                  <div className="font-mono text-[22px] font-medium text-red-700 bg-red-50 border border-red-200 px-3 py-1 rounded-[10px]">
                    {ev.count}
                  </div>
                </div>
              ))}
            </div>
          )}
        </StackedCard>
      </div>

      {/* USERS TABLE */}
      <div data-testid="users-table">
        <StackedCard accent="ink" category="Manajemen Pengguna & Peran" meta={`${users.length} akun`} bodyClassName="p-0 overflow-hidden">
          <div className="px-4 sm:px-6 py-4 border-b border-black/[0.06] flex flex-wrap items-center justify-between gap-2">
            <h3 className="font-medium text-[#171717] text-[15px] sm:text-[16px]">Daftar Akun Terdaftar</h3>
            <span className="text-[11.5px] sm:text-[12px] font-mono text-[#8F8E8B]">{users.length} Total Akun</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[740px] text-left text-[13px]">
              <thead className="bg-[#F5F5F2] text-[#8F8E8B] border-b border-black/[0.08] font-mono text-[11px] uppercase tracking-wider">
                <tr>
                  <th className="px-4 sm:px-6 py-3 font-medium">Nama</th>
                  <th className="px-4 sm:px-6 py-3 font-medium">Email</th>
                  <th className="px-4 sm:px-6 py-3 font-medium">NIM / Unit</th>
                  <th className="px-4 sm:px-6 py-3 font-medium">Status</th>
                  <th className="px-4 sm:px-6 py-3 font-medium">Peran</th>
                  <th className="px-4 sm:px-6 py-3 font-medium text-right">Aksi</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-black/[0.06] text-[#171717]">
                {users.map((u) => (
                  <tr key={u.id} className="hover:bg-[#F5F5F2]/60 transition-colors">
                    <td className="px-4 sm:px-6 py-3.5 font-medium whitespace-nowrap">{u.name}</td>
                    <td className="px-4 sm:px-6 py-3.5 font-mono text-[12px] text-[#6E6D6A]">{u.email}</td>
                    <td className="px-4 sm:px-6 py-3.5 font-mono text-[12px] text-[#6E6D6A] whitespace-nowrap">
                      {u.nim || u.organization || "—"}
                    </td>
                    <td className="px-4 sm:px-6 py-3.5 whitespace-nowrap">
                      {u.role === "panitia" ? (
                        u.approval_status === "pending" ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 text-amber-800 border border-amber-200 px-2.5 py-0.5 text-[10.5px] font-mono">
                            MENUNGGU ACC
                          </span>
                        ) : u.approval_status === "rejected" ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-red-50 text-red-700 border border-red-200 px-2.5 py-0.5 text-[10.5px] font-mono">
                            DITOLAK
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 px-2.5 py-0.5 text-[10.5px] font-mono">
                            <CheckCircle2 className="size-3" /> DISETUJUI
                          </span>
                        )
                      ) : u.role !== "mahasiswa" ? (
                        <span className="text-[#8F8E8B] font-mono text-[11px]">ADMIN</span>
                      ) : u.needs_re_enrollment ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 text-amber-800 border border-amber-200 px-2.5 py-0.5 text-[10.5px] font-mono">
                          <AlertTriangle className="size-3" /> PERLU 3 POSE
                        </span>
                      ) : u.has_enrollment ? (
                        <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 text-emerald-800 border border-emerald-200 px-2.5 py-0.5 text-[10.5px] font-mono">
                          <CheckCircle2 className="size-3" /> 3 POSE LENGKAP
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 rounded-full bg-black/[0.05] text-[#6E6D6A] px-2.5 py-0.5 text-[10.5px] font-mono">
                          BELUM VERIFIKASI
                        </span>
                      )}
                    </td>
                    <td className="px-4 sm:px-6 py-3.5 whitespace-nowrap">
                      <select
                        value={u.role}
                        onChange={(e) => updateRole(u.id, e.target.value)}
                        data-testid={`role-select-${u.id}`}
                        className="px-2.5 py-1 text-[12px] bg-white"
                      >
                        <option value="mahasiswa">Mahasiswa</option>
                        <option value="panitia">Panitia</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="px-4 sm:px-6 py-3.5 text-right whitespace-nowrap space-x-1.5">
                      {u.role === "panitia" && u.approval_status !== "approved" && (
                        <button
                          onClick={() => handleApprovePanitia(u.id)}
                          className="px-2.5 py-1 rounded-[8px] bg-emerald-600 hover:bg-emerald-700 text-white text-[11.5px] font-medium cursor-pointer"
                          title="ACC Panitia"
                        >
                          ACC
                        </button>
                      )}
                      <button
                        onClick={() => deleteUser(u.id)}
                        data-testid={`delete-user-${u.id}`}
                        className="size-8 rounded-[8px] border border-black/[0.1] bg-white text-[#6E6D6A] hover:bg-red-50 hover:text-red-600 hover:border-red-200 grid place-items-center transition-colors inline-flex cursor-pointer align-middle"
                        title="Hapus User"
                      >
                        <Trash2 className="size-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </StackedCard>
      </div>
    </div>
  );
}

import { Code2, ScanFace, Focus, CheckCircle2, ArrowRight, GraduationCap } from "lucide-react";
import { StackedCard } from "@/components/StackedCard";

const TEAM_MEMBERS = [
  {
    name: "Nur Rifal",
    nim: "41523010007",
    role: "Web Developer",
    category: "Web & Integrasi Sistem",
    accent: "green",
    photo: "/images/team-rifal.jpg",
    photoBg: "bg-[#EAEAE5]",
    photoFit: "object-cover object-top",
    Icon: Code2,
    summary:
      "Bertanggung jawab penuh atas arsitektur aplikasi web, pengalaman pengguna (UI/UX), keamanan akses, serta integrasi seluruh pipeline AI ke dalam sistem FODOC.",
    tasks: [
      "Merancang antarmuka web responsif (desktop & mobile) untuk Mahasiswa, Panitia Acara, dan Admin.",
      "Membangun backend API (FastAPI & MongoDB), autentikasi JWT, verifikasi email OTP, validasi data mahasiswa Universitas Mercu Buana, dan persetujuan (ACC) akun Panitia.",
      "Mengembangkan alur verifikasi 3 pose wajah (Kamera Langsung & Unggah 3 Foto) dengan validasi arah pose dan anti-duplikat.",
      "Mengintegrasikan model deteksi & pengenalan wajah ke pemrosesan foto acara, distribusi galeri pribadi terisolasi, konfirmasi mandiri foto, serta optimasi kecepatan akses.",
    ],
  },
  {
    name: "Vikry Aldiansyah",
    nim: "41523010006",
    role: "Face Recognition",
    category: "Pengenalan Wajah",
    accent: "cyan",
    photo: "/images/team-vikry.jpg",
    photoBg: "bg-[#2C2C30]",
    photoFit: "object-cover object-top",
    Icon: ScanFace,
    summary:
      "Berfokus pada pemodelan, evaluasi, dan akurasi sistem pengenalan identitas wajah agar setiap foto dokumentasi terdistribusi tepat ke mahasiswa yang bersangkutan.",
    tasks: [
      "Mengembangkan modul ekstraksi fitur biometrik wajah berbasis AdaFace IR-50 WebFace4M (vektor 512-dimensi L2-normalized dengan Flip-TTA).",
      "Merancang pembentukan template centroid dari 3 pose acuan (Depan, Kanan, Kiri) untuk menjaga akurasi di berbagai sudut wajah.",
      "Menentukan kalibrasi ambang keputusan berlapis (COCOK, PERLU_CEK, UNKNOWN) dan selisih margin antar-kandidat.",
      "Melakukan pengujian presisi, evaluasi false acceptance, dan penyetelan skor kemiripan pada foto kegiatan kampus.",
    ],
  },
  {
    name: "Harari Zuhdi",
    nim: "41523010012",
    role: "Face Detection",
    category: "Deteksi Wajah",
    accent: "amber",
    photo: "/images/team-harari.png",
    photoBg: "bg-gradient-to-b from-[#F1F1EC] to-[#E2E2DC]",
    photoFit: "object-contain object-bottom",
    Icon: Focus,
    summary:
      "Berfokus pada deteksi banyak wajah secara presisi dalam foto rombongan maupun candid acara kampus di berbagai ukuran wajah dan kondisi pencahayaan.",
    tasks: [
      "Melatih dan melakukan fine-tuning model deteksi multi-wajah YOLOv11n-face (ONNX & PyTorch, resolusi 1088px) untuk foto acara kampus.",
      "Merancang saringan kotak-di-dalam-kotak (nested box filtering) dan pengurutan deteksi wajah untuk mengurangi deteksi ganda.",
      "Mengembangkan integrasi deteksi 5 landmark wajah (mata, hidung, mulut) dan penjajaran wajah (alignment) sebelum tahap pengenalan.",
      "Melakukan kalibrasi ambang kepercayaan deteksi serta analisis kualitas ketajaman dan pencahayaan citra (CIELAB).",
    ],
  },
];

export default function Team() {
  return (
    <div className="bg-[#F5F5F2] min-h-[calc(100vh-4rem)] py-8 sm:py-14" data-testid="team-page">
      <div className="max-w-[1120px] mx-auto px-4 sm:px-8">
        {/* Editorial Header */}
        <div className="max-w-2xl mb-9 sm:mb-12">
          <div className="inline-flex items-center gap-2 font-mono text-[11px] sm:text-[12px] text-[#8F8E8B] mb-2.5">
            <GraduationCap className="size-3.5 text-[#171717]" />
            <span>Capstone Project · Universitas Mercu Buana</span>
          </div>
          <h1 className="text-[28px] sm:text-[42px] font-normal leading-[1.13] tracking-[-0.025em] text-[#171717]">
            Tim <span className="text-[#8F8E8B]">Pengembang FODOC</span>
          </h1>
          <p className="mt-3 text-[14px] sm:text-[15.5px] text-[#6E6D6A] leading-relaxed">
            Kenali tim di balik <strong className="text-[#171717] font-medium">FODOC — Foto Dokumentasi</strong>, sistem distribusi foto acara kampus otomatis dan privat yang memadukan pengembangan web, deteksi wajah, dan pengenalan wajah.
          </p>
        </div>

        {/* 3 Member Stacked Paper Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 sm:gap-7 mb-10 sm:mb-14">
          {TEAM_MEMBERS.map((member) => {
            const RoleIcon = member.Icon;
            return (
              <StackedCard
                key={member.nim}
                accent={member.accent}
                category={member.category}
                meta={`NIM ${member.nim}`}
                bodyClassName="p-4 sm:p-6 flex flex-col"
              >
                {/* Portrait Frame */}
                <div
                  className={`relative w-full aspect-[4/5] rounded-[13px] overflow-hidden border border-black/[0.08] mb-5 ${member.photoBg}`}
                >
                  <img
                    src={member.photo}
                    alt={`${member.name} — ${member.role}`}
                    loading="lazy"
                    decoding="async"
                    className={`w-full h-full ${member.photoFit} select-none`}
                  />
                  <div className="absolute bottom-2.5 left-2.5 inline-flex items-center gap-1.5 rounded-full bg-[#171717]/85 backdrop-blur-md text-white px-3 py-1 font-mono text-[11px] shadow-sm">
                    <RoleIcon className="size-3.5 text-emerald-300 shrink-0" />
                    <span>{member.role}</span>
                  </div>
                </div>

                {/* Identity */}
                <div className="mb-3">
                  <h2 className="text-[21px] sm:text-[22px] font-medium tracking-[-0.02em] text-[#171717] leading-tight">
                    {member.name}
                  </h2>
                  <div className="font-mono text-[12px] text-[#8F8E8B] mt-1">
                    NIM {member.nim} · Universitas Mercu Buana
                  </div>
                </div>

                {/* Summary */}
                <p className="text-[13px] sm:text-[13.5px] text-[#52524E] leading-relaxed mb-4">
                  {member.summary}
                </p>

                {/* Detailed Responsibilities */}
                <div className="mt-auto pt-4 border-t border-black/[0.07]">
                  <div className="font-mono text-[10.5px] uppercase tracking-[0.12em] text-[#8F8E8B] mb-2.5">
                    Kontribusi &amp; Tugas Utama
                  </div>
                  <ul className="space-y-2">
                    {member.tasks.map((task, idx) => (
                      <li key={idx} className="flex items-start gap-2 text-[12.5px] text-[#4A4946] leading-snug">
                        <CheckCircle2 className="size-3.5 text-emerald-700 shrink-0 mt-0.5" />
                        <span>{task}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </StackedCard>
            );
          })}
        </div>

        {/* Kolaborasi Pipeline Card */}
        <StackedCard
          accent="ink"
          category="Kolaborasi Tim"
          meta="END-TO-END"
          bodyClassName="p-5 sm:p-7"
        >
          <div className="mb-4">
            <h2 className="text-[19px] sm:text-[22px] font-medium tracking-[-0.02em] text-[#171717]">
              Bagaimana Sistem FODOC Bekerja Bersama
            </h2>
            <p className="text-[13px] sm:text-[14px] text-[#6E6D6A] mt-1">
              Setiap anggota bertanggung jawab pada satu pilar utama yang saling terintegrasi secara otomatis.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 sm:gap-4 items-stretch">
            <div className="rounded-[12px] bg-[#F5F5F2] border border-black/[0.07] p-4 flex flex-col justify-between">
              <div>
                <div className="font-mono text-[11px] text-amber-800 mb-1">01 · FACE DETECTION</div>
                <div className="text-[15px] font-semibold text-[#171717]">Harari Zuhdi</div>
                <p className="text-[12.5px] text-[#6E6D6A] mt-1.5 leading-relaxed">
                  Mendeteksi seluruh wajah dalam foto acara kampus, menyaring kotak ganda, dan menemukan 5 titik landmark untuk penjajaran.
                </p>
              </div>
              <div className="hidden md:flex justify-end mt-3 text-[#8F8E8B]">
                <ArrowRight className="size-4" />
              </div>
            </div>

            <div className="rounded-[12px] bg-[#F5F5F2] border border-black/[0.07] p-4 flex flex-col justify-between">
              <div>
                <div className="font-mono text-[11px] text-cyan-800 mb-1">02 · FACE RECOGNITION</div>
                <div className="text-[15px] font-semibold text-[#171717]">Vikry Aldiansyah</div>
                <p className="text-[12.5px] text-[#6E6D6A] mt-1.5 leading-relaxed">
                  Mengekstrak ciri biometrik wajah terstandar dan mencocokkannya ke profil 3 pose mahasiswa untuk menentukan status COCOK atau PERLU_CEK.
                </p>
              </div>
              <div className="hidden md:flex justify-end mt-3 text-[#8F8E8B]">
                <ArrowRight className="size-4" />
              </div>
            </div>

            <div className="rounded-[12px] bg-[#F5F5F2] border border-black/[0.07] p-4 flex flex-col justify-between">
              <div>
                <div className="font-mono text-[11px] text-emerald-800 mb-1">03 · WEB &amp; INTEGRASI</div>
                <div className="text-[15px] font-semibold text-[#171717]">Nur Rifal</div>
                <p className="text-[12.5px] text-[#6E6D6A] mt-1.5 leading-relaxed">
                  Menyatukan semuanya ke aplikasi web yang aman, responsif di HP/desktop, tervalidasi email kampus &amp; OTP, hingga distribusi privat ke galeri mahasiswa.
                </p>
              </div>
            </div>
          </div>
        </StackedCard>
      </div>
    </div>
  );
}

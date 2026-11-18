import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { fileSrc } from "@/lib/api";
import { useNotifications } from "@/context/NotificationContext";
import { CheckCheck, Image as ImageIcon } from "lucide-react";
import { StackedCard } from "@/components/StackedCard";

export default function Notifications() {
  const [items, setItems] = useState([]);
  const { reload } = useNotifications();

  const load = async () => {
    const { data } = await api.get("/me/notifications");
    setItems(data);
  };

  useEffect(() => {
    load();
  }, []);

  const markRead = async () => {
    await api.post("/me/notifications/read-all");
    load();
    reload();
  };

  return (
    <div className="max-w-[860px] mx-auto px-4 sm:px-8 py-7 sm:py-12">
      <div className="mb-6 sm:mb-8 flex flex-col sm:flex-row sm:items-end justify-between gap-4">
        <div>
          <div className="font-mono text-[11px] sm:text-[12px] text-[#8F8E8B] mb-2">Kotak Masuk</div>
          <h1 className="text-[26px] sm:text-[38px] font-normal leading-[1.15] tracking-[-0.025em] text-[#171717]">
            Notifikasi <span className="text-[#8F8E8B]">Foto</span>
          </h1>
          <p className="text-[13.5px] sm:text-[14px] text-[#6E6D6A] mt-2">
            Pemberitahuan otomatis saat sistem mendeteksi wajah Anda pada dokumentasi acara baru.
          </p>
        </div>

        <button
          onClick={markRead}
          data-testid="mark-read-button"
          className="cta-btn-light w-full sm:w-auto justify-center text-[13px] px-4 py-2.5 sm:py-2 flex items-center gap-1.5 cursor-pointer self-start sm:self-auto"
        >
          <CheckCheck className="size-4 text-[#6E6D6A]" />
          Tandai semua dibaca
        </button>
      </div>

      <div className="space-y-3" data-testid="notifications-list">
        {items.length === 0 && (
          <StackedCard accent="ink" category="Kotak Masuk Kosong" meta="0 baru" bodyClassName="p-12 text-center items-center">
            <div className="text-[17px] font-medium text-[#171717]">Belum ada notifikasi</div>
            <p className="text-[13.5px] text-[#6E6D6A] mt-1 max-w-sm">
              Saat panitia mengunggah foto acara yang memuat wajah Anda, notifikasi akan muncul di sini.
            </p>
          </StackedCard>
        )}

        {items.map((n) => (
          <Link
            to={n.photo_id ? `/gallery?photoId=${n.photo_id}` : "/gallery"}
            key={n.id}
            data-testid={`notification-item-${n.id}`}
            className={`rounded-[14px] border border-black/[0.08] p-4 flex items-center gap-4 transition-all hover:border-black/[0.16] hover:bg-white ${
              n.read ? "bg-[#F9F9F7] opacity-75" : "bg-[#FCFCFA] shadow-[0_2px_8px_rgba(0,0,0,0.03)]"
            }`}
          >
            {n.photo_url ? (
              <img
                src={fileSrc(n.photo_url, 160)}
                alt=""
                loading="lazy"
                decoding="async"
                className="size-14 rounded-[10px] object-cover border border-black/[0.08] shrink-0"
              />
            ) : (
              <div className="size-14 rounded-[10px] bg-[#F5F5F2] border border-black/[0.08] grid place-items-center text-[#8F8E8B] shrink-0">
                <ImageIcon className="size-5" />
              </div>
            )}

            <div className="flex-1 min-w-0">
              <div className="font-medium text-[#171717] text-[14px]">{n.message}</div>
              <div className="font-mono text-[11px] text-[#8F8E8B] mt-1.5 flex items-center gap-2 flex-wrap">
                {n.event_name && (
                  <span className="text-[#171717] bg-black/[0.05] px-2 py-0.5 rounded-[6px]">
                    {n.event_name}
                  </span>
                )}
                <span>{n.created_at?.slice(0, 19).replace("T", " ")}</span>
              </div>
            </div>

            {!n.read && <span className="size-2.5 rounded-full bg-[#22C55E] shrink-0" title="Belum dibaca" />}
          </Link>
        ))}
      </div>
    </div>
  );
}

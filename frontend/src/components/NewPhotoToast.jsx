import { X, ScanFace, ArrowRight } from "lucide-react";
import { fileSrc } from "@/lib/api";

export const NewPhotoToast = ({ n, onOpen, onClose }) => (
  <div
    data-testid="new-photo-toast"
    className="w-[360px] bg-white rounded-2xl border border-slate-200 shadow-xl overflow-hidden flex animate-[pop_300ms_ease-out]"
  >
    <div className="w-24 shrink-0 bg-slate-900 relative">
      {n.photo_url ? (
        <img src={fileSrc(n.photo_url)} alt="" className="w-full h-full object-cover" />
      ) : (
        <div className="w-full h-full grid place-items-center text-sky-400">
          <ScanFace className="size-8" />
        </div>
      )}
    </div>
    <div className="flex-1 p-4 min-w-0 flex flex-col justify-between">
      <div>
        <div className="flex items-start justify-between gap-2">
          <span className="rounded-full bg-blue-50 text-blue-700 font-mono text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 border border-blue-200">
            Foto Baru
          </span>
          <button
            onClick={onClose}
            data-testid="new-photo-toast-close"
            className="text-slate-400 hover:text-slate-700"
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="mt-2 text-xs font-bold text-slate-900 leading-snug line-clamp-2" data-testid="new-photo-toast-message">
          {n.message}
        </div>
        {n.event_name && (
          <div className="font-mono text-[10px] uppercase tracking-wider text-slate-500 mt-1 truncate">
            {n.event_name}
          </div>
        )}
      </div>

      <button
        onClick={onOpen}
        data-testid="new-photo-toast-open"
        className="mt-3 rounded-lg bg-blue-700 hover:bg-blue-800 text-white font-semibold text-xs py-1.5 px-3 transition-colors shadow-xs flex items-center justify-center gap-1.5"
      >
        <span>Lihat di Galeri</span>
        <ArrowRight className="size-3.5" />
      </button>
    </div>
  </div>
);

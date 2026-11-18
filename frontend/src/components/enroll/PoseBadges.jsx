import { Check } from "lucide-react";
import { POSES } from "./poses";

export const PoseBadges = ({ shots, stage }) => (
  <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3 w-full" data-testid="pose-badges">
    {POSES.map((p, i) => {
      const done = !!shots[p.angle];
      return (
        <div
          key={p.angle}
          data-testid={`pose-badge-${p.angle}`}
          className={`flex items-center gap-1.5 sm:gap-2 px-2.5 sm:px-3 py-1.5 rounded-full border text-[10.5px] sm:text-[11px] font-mono uppercase tracking-[0.08em] sm:tracking-[0.15em] transition-colors duration-300 ${
            done
              ? "border-emerald-500 bg-emerald-500/15 text-emerald-300"
              : i === stage
              ? "border-white text-white"
              : "border-white/20 text-white/40"
          }`}
        >
          {done ? (
            <span className="w-4 h-4 rounded-full bg-emerald-500 grid place-items-center animate-[pop_300ms_ease-out] shrink-0">
              <Check className="w-3 h-3 text-black" strokeWidth={3} />
            </span>
          ) : (
            <p.Icon className="w-3.5 h-3.5 shrink-0" />
          )}
          {p.short}
        </div>
      );
    })}
  </div>
);

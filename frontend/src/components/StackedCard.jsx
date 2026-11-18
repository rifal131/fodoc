import { Link } from "react-router-dom";

const PIXEL_COLORS = {
  green: ["#22C55E", "#86EFAC", "#15803D"],
  cyan: ["#06B6D4", "#67E8F9", "#0E7490"],
  purple: ["#A855F7", "#D8B4FE", "#7E22CE"],
  amber: ["#F59E0B", "#FDE68A", "#B45309"],
  coral: ["#EF4444", "#FCA5A5", "#B91C1C"],
  ink: ["#171717", "#6E6D6A", "#A3A3A0"],
};

/** Tiny pixel-art sprite peeking from the left edge of each card, matching cofounder.co/resources */
export function PixelEdgeSprite({ color = "green" }) {
  const [c1, c2, c3] = PIXEL_COLORS[color] || PIXEL_COLORS.green;
  return (
    <svg
      width="8"
      height="16"
      viewBox="0 0 2 4"
      fill="none"
      className="absolute left-0 top-[20px] pointer-events-none select-none"
      aria-hidden="true"
    >
      <rect x="0" y="0" width="1" height="1" fill={c1} />
      <rect x="1" y="1" width="1" height="1" fill={c2} />
      <rect x="0" y="1" width="1" height="1" fill={c3} />
      <rect x="0" y="2" width="1" height="1" fill={c1} />
      <rect x="1" y="2" width="1" height="1" fill={c1} />
      <rect x="0" y="3" width="1" height="1" fill={c2} />
    </svg>
  );
}

/**
 * Signature Cofounder.co Stacked Paper Card:
 * - Two subtle stacked paper edges peeking out at the top
 * - Crisp off-white front sheet (#FCFCFA) with ultra-thin hairline border
 * - Optional left-edge pixel sprite, top meta row (category + right tag/date), and monospace bottom link
 */
export function StackedCard({
  to,
  onClick,
  accent = "green",
  category,
  meta,
  title,
  description,
  footerText,
  children,
  className = "",
  bodyClassName = "",
  ...rest
}) {
  const hasCustomBg = /\bbg-/.test(bodyClassName);

  const inner = (
    <div className={`group relative flex flex-col h-full min-w-0 ${className}`} {...rest}>
      {/* Stacked back paper sheet 1 (topmost) */}
      <div className="mx-3 h-[5px] rounded-t-[12px] border-t border-x border-black/[0.06] bg-[#F7F7F4] transition-transform duration-200 group-hover:-translate-y-[1px]" />
      {/* Stacked back paper sheet 2 */}
      <div className="mx-1.5 h-[5px] rounded-t-[12px] border-t border-x border-black/[0.07] bg-[#FAFAF8]" />

      {/* Front paper sheet */}
      <div
        className={`relative flex-1 flex flex-col min-w-0 rounded-[16px] ${
          hasCustomBg ? "" : "bg-[#FCFCFA]"
        } border border-black/[0.08] shadow-[0_2px_10px_rgba(0,0,0,0.03)] transition-all duration-200 overflow-hidden ${
          to || onClick
            ? "group-hover:bg-white group-hover:border-black/[0.14] group-hover:shadow-[0_10px_28px_rgba(0,0,0,0.06)] group-hover:-translate-y-[1px]"
            : ""
        } ${bodyClassName || "p-4 sm:p-6"}`}
      >
        {accent && <PixelEdgeSprite color={accent} />}

        {(category || meta) && (
          <div className="flex items-center justify-between gap-2 sm:gap-3 text-[11.5px] sm:text-[12px] text-[#8F8E8B] mb-4 sm:mb-5">
            <span className="truncate">{category}</span>
            {meta && <span className="font-mono text-[10.5px] sm:text-[11px] shrink-0">{meta}</span>}
          </div>
        )}

        {title && (
          <h3 className="text-[19px] sm:text-[22px] font-medium leading-[1.24] tracking-[-0.02em] text-[#171717] break-words">
            {title}
          </h3>
        )}

        {description && (
          <p className="mt-2.5 sm:mt-3 text-[13.5px] sm:text-[15px] leading-[1.45] text-[#6E6D6A]">
            {description}
          </p>
        )}

        {children}

        {footerText && (
          <div className="mt-auto pt-6 sm:pt-8 font-mono text-[12px] sm:text-[12.5px] text-[#8F8E8B] group-hover:text-[#171717] transition-colors">
            {footerText}
          </div>
        )}
      </div>
    </div>
  );

  if (to) {
    return (
      <Link to={to} className="block h-full focus:outline-none">
        {inner}
      </Link>
    );
  }
  if (onClick) {
    return (
      <div onClick={onClick} className="block h-full cursor-pointer">
        {inner}
      </div>
    );
  }
  return inner;
}

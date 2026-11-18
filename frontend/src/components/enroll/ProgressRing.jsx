const R = 47;
const C = 2 * Math.PI * R;

// Circular progress ring with 3 segment ticks; progress in 0..1
export const ProgressRing = ({ progress, active }) => (
  <svg viewBox="0 0 100 100" className="absolute inset-0 w-full h-full -rotate-90" data-testid="scanner-progress-ring">
    <circle cx="50" cy="50" r={R} fill="none" stroke="rgba(255,255,255,0.12)" strokeWidth="2.2" />
    <circle
      cx="50" cy="50" r={R} fill="none" stroke="#10B981" strokeWidth="2.6" strokeLinecap="round"
      strokeDasharray={C} strokeDashoffset={C * (1 - Math.min(1, progress))}
      style={{ transition: "stroke-dashoffset 120ms linear", filter: "drop-shadow(0 0 4px rgba(16,185,129,0.8))" }}
    />
    {[0, 1, 2].map((i) => {
      const a = (i / 3) * 2 * Math.PI;
      return <circle key={i} cx={50 + R * Math.cos(a)} cy={50 + R * Math.sin(a)} r="1.6"
        fill={progress >= (i + 1) / 3 - 0.001 ? "#10B981" : active ? "#fff" : "rgba(255,255,255,0.4)"} />;
    })}
  </svg>
);

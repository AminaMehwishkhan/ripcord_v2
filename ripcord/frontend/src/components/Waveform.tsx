import { useEffect, useRef } from "react";

const BAR_COUNT = 36;

/** Bar waveform driven by a 0-1 level; keeps its own rolling history so React doesn't re-render per frame. */
export function Waveform({ level, active }: { level: number; active: boolean }) {
  const history = useRef<number[]>(new Array(BAR_COUNT).fill(0.04));
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const h = history.current;
    h.shift();
    h.push(active ? Math.max(0.04, level) : 0.04);
    box.current?.querySelectorAll<HTMLDivElement>("[data-bar]").forEach((bar, i) => {
      bar.style.height = `${Math.round(h[i] * 100)}%`;
    });
  }, [level, active]);

  return (
    <div ref={box} className="flex items-end gap-[3px] h-10" aria-hidden="true">
      {Array.from({ length: BAR_COUNT }).map((_, i) => (
        <div key={i} data-bar className={`w-1 rounded-full transition-[height] duration-150 ${active ? "bg-cyan-400/70" : "bg-white/10"}`} style={{ height: "4%" }} />
      ))}
    </div>
  );
}

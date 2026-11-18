import { useEffect, useRef, useState } from "react";
import confetti from "canvas-confetti";
import { PartyPopper } from "lucide-react";
import type { useCourse } from "../api/queries";

type Course = NonNullable<ReturnType<typeof useCourse>["data"]>;
type Module = Course["modules"][number];

const isDone = (m: Module) =>
  m.steps.length > 0 && m.steps.every((s) => s.progress !== "open");

function popperBurst() {
  const base = { zIndex: 100 };
  // The pop in the middle...
  confetti({ ...base, particleCount: 120, spread: 360, startVelocity: 35, ticks: 120, origin: { x: 0.5, y: 0.5 } });
  // ...then two cannons from the lower corners, aimed at the middle.
  setTimeout(() => {
    confetti({ ...base, particleCount: 80, angle: 60, spread: 70, startVelocity: 60, origin: { x: 0, y: 0.9 } });
    confetti({ ...base, particleCount: 80, angle: 120, spread: 70, startVelocity: 60, origin: { x: 1, y: 0.9 } });
  }, 300);
}

export default function ModuleCelebration({ course }: { course: Course }) {
  // Modules that were already done the last time we looked. null = first load.
  const before = useRef<Set<number> | null>(null);
  const [toast, setToast] = useState<{ title: string; next?: string } | null>(null);

  useEffect(() => {
    const done = new Set(course.modules.filter(isDone).map((m) => m.index));
    const previous = before.current;
    before.current = done;
    if (previous === null) return; // first load: nothing newly completed

    const fresh = course.modules.find((m) => done.has(m.index) && !previous.has(m.index));
    if (!fresh) return;

    const next = course.modules.find((m) => m.index === fresh.index + 1);
    setToast({
      title: `Module ${fresh.index + 1} complete!`,
      next: next ? `Module ${next.index + 1} is unlocked.` : "You finished the course.",
    });
    popperBurst();
  }, [course]);

  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 5000);
    return () => clearTimeout(timer);
  }, [toast]);

  if (!toast) return null;
  return (
  <div
    role="status"
    onClick={() => setToast(null)}
    className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 backdrop-blur-[2px] transition duration-300 starting:opacity-0"
  >
    <div className="flex flex-col items-center rounded-3xl bg-white px-12 py-10 text-center shadow-2xl transition duration-500 ease-[cubic-bezier(0.34,1.56,0.64,1)] starting:scale-50 starting:opacity-0">
      <div className="mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-emerald-50">
        <PartyPopper className="h-10 w-10 text-emerald-600" />
      </div>
      <div className="text-3xl font-bold text-slate-900">{toast.title}</div>
      <div className="mt-2 text-lg text-slate-600">{toast.next}</div>
      <button
        type="button"
        onClick={() => setToast(null)}
        className="mt-6 rounded-xl bg-blue-600 px-6 py-2.5 font-semibold text-white shadow-sm hover:bg-blue-700"
      >
        Continue
      </button>
    </div>
  </div>
  );
}
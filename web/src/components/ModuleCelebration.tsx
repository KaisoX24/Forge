import { useEffect, useRef, useState } from "react";
import confetti from "canvas-confetti";
import { PartyPopper } from "lucide-react";
import type { useCourse } from "../api/queries";

type Course = NonNullable<ReturnType<typeof useCourse>["data"]>;
type Module = Course["modules"][number];

const isDone = (m: Module) =>
  m.steps.length > 0 && m.steps.every((s) => s.progress !== "open");

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
    confetti({
      particleCount: 90,
      spread: 70,
      origin: { y: 0.25 },
      disableForReducedMotion: true,
    });
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
      className="fixed bottom-6 right-6 z-50 flex items-center gap-3 rounded-xl border border-emerald-200 bg-white px-5 py-4 shadow-lg transition duration-300 starting:translate-y-3 starting:opacity-0"
    >
      <PartyPopper className="h-6 w-6 text-emerald-600" />
      <div>
        <div className="font-semibold text-slate-900">{toast.title}</div>
        <div className="text-sm text-slate-600">{toast.next}</div>
      </div>
    </div>
  );
}
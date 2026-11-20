import { useState } from "react";
import { ChevronDown, Layers, Lock } from "lucide-react";
import { matchesQuery } from "../lib/search";
import SearchBox from "./SearchBox";
import { useCourse, useCourses } from "../api/queries";
import type { components } from "../api/schema";
import ErrorScreen from "./ErrorScreen";

type Module = components["schemas"]["ModuleSummary"];
type CourseSummary = components["schemas"]["CourseSummary"];

function countSteps(module: Module) {
  const total = module.steps.length;
  const solved = module.steps.filter(
    (s) => s.progress === "solved" || s.progress === "completed",
  ).length;
  const gaveUp = module.steps.filter((s) => s.progress === "gave_up").length;
  return { total, solved, gaveUp };
}

function ModuleRow({ module }: { module: Module }) {
  const { total, solved, gaveUp } = countSteps(module);
  const pct = (n: number) => (total ? (n / total) * 100 : 0);

  return (
    <div className={`flex items-center gap-4 ${module.unlocked ? "" : "opacity-50"}`}>
      <div className="flex w-56 min-w-0 shrink-0 items-center gap-2">
        {!module.unlocked && <Lock className="h-4 w-4 shrink-0 text-slate-400" />}
        <div className="min-w-0">
          <div className="text-sm font-semibold text-slate-900">Module {module.index + 1}</div>
          <div className="truncate text-xs text-slate-500">{module.title}</div>
        </div>
      </div>
      <div className="flex h-2.5 flex-1 overflow-hidden rounded-full bg-slate-200">
        <div className="bg-emerald-500" style={{ width: `${pct(solved)}%` }} />
        <div className="bg-amber-400" style={{ width: `${pct(gaveUp)}%` }} />
      </div>
      <span className="w-12 shrink-0 text-right text-sm tabular-nums text-slate-600">
        {solved + gaveUp}/{total}
      </span>
    </div>
  );
}

function CourseProgress({
  summary,
  defaultOpen,
}: {
  summary: CourseSummary;
  defaultOpen: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const { data: course, isPending } = useCourse(summary.key);

  const totals = (course?.modules ?? []).reduce(
    (acc, m) => {
      const c = countSteps(m);
      return {
        total: acc.total + c.total,
        solved: acc.solved + c.solved,
        gaveUp: acc.gaveUp + c.gaveUp,
      };
    },
    { total: 0, solved: 0, gaveUp: 0 },
  );

  return (
    <section className="rounded-2xl border border-slate-200 bg-white shadow-sm">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="block w-full rounded-2xl p-6 text-left hover:bg-slate-50"
      >
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-blue-50">
            <Layers className="h-6 w-6 text-blue-600" />
          </div>
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-xl font-bold text-slate-900">{summary.title}</h2>
            <p className="text-sm text-slate-500">
              {isPending
                ? "Loading…"
                : `${totals.solved + totals.gaveUp} of ${totals.total} steps done` +
                  (totals.gaveUp ? ` · ${totals.gaveUp} given up` : "")}
            </p>
          </div>
          <div className="text-3xl font-bold text-blue-600">{summary.progress_percent}%</div>
          <ChevronDown
            className={`h-5 w-5 shrink-0 text-slate-500 transition-transform duration-200 ${
              open ? "rotate-180" : ""
            }`}
          />
        </div>

        {/* A slim overall bar stays visible even when the card is collapsed. */}
        <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-blue-600"
            style={{ width: `${summary.progress_percent}%` }}
          />
        </div>
      </button>

      <div
        className={`grid transition-[grid-template-rows] duration-200 ${
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        }`}
      >
        <div className="min-h-0 overflow-hidden">
          <div className="space-y-4 px-6 pb-6 pt-2">
            {course?.modules.map((m) => <ModuleRow key={m.index} module={m} />)}
          </div>
        </div>
      </div>
    </section>
  );
}

export default function ProgressPage() {
  const [query, setQuery] = useState("");
  const { data: courses, isPending, error, refetch } = useCourses();

  if (isPending) return <p className="p-8 text-slate-500">Loading progress…</p>;
  if (error) return <ErrorScreen error={error} onRetry={() => refetch()} />;

  const visible = courses.filter((c) => matchesQuery(c, query));

  return (
    <div className="h-full overflow-y-auto rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Progress</h1>
          <div className="mt-2 flex items-center gap-4 text-sm text-slate-600">
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> Solved
            </span>
            <span className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-amber-400" /> Given up
            </span>
          </div>
        </div>
        <SearchBox value={query} onChange={setQuery} />
      </div>

      <div className="mt-6 space-y-4">
        {visible.length === 0 ? (
          <p className="text-slate-500">
            {courses.length === 0 ? "No courses yet." : `No courses match “${query.trim()}”.`}
          </p>
        ) : (
          visible.map((c) => (
            <CourseProgress key={c.key} summary={c} defaultOpen={courses.length === 1} />
          ))
        )}
      </div>
    </div>
  );
}
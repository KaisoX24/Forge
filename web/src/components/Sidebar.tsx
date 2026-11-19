import { useEffect, useState } from "react";
import { NavLink } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { BookOpen, ChevronRight, CircleCheck, Circle, Flame, Lock, Layers, Sparkles } from "lucide-react";
import type { useCourse } from "../api/queries";
import {useActiveJobs, useJob} from "../api/queries";
import { useGenerateModule } from "../api/mutations";
import type { components } from "../api/schema";

type Course = NonNullable<ReturnType<typeof useCourse>["data"]>;
type Module = components["schemas"]["ModuleSummary"];

function StepIcon({ progress }: { progress: string }) {
  if (progress === "solved" || progress === "completed")
    return <CircleCheck className="h-4 w-4 shrink-0 text-emerald-500" />;
  if (progress === "gave_up")
    return <CircleCheck className="h-4 w-4 shrink-0 text-amber-500" />;
  return <Circle className="h-4 w-4 shrink-0 text-slate-300" />;
}

export default function Sidebar({ course }: { course: Course }) {
  // Only the modules the learner has clicked are stored here.
  // Everything else falls back to "open if unlocked".
  const [overrides, setOverrides] = useState<Record<number, boolean>>({});

  return (
    <aside className="flex h-full w-80 shrink-0 flex-col border-r border-slate-200 bg-[#F3F9FE]">
      <div className="flex items-center gap-2 px-5 py-4">
        <Flame className="h-7 w-7 text-orange-500" />
        <div>
          <div className="text-lg font-bold leading-none">Forge</div>
          <div className="text-xs text-slate-500">Learn by Building</div>
        </div>
      </div>

      <div className="px-4 py-3">
        <div className="mb-2 px-1 text-xs font-medium text-slate-500">Current course</div>
        <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-sm">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-50">
              <Layers className="h-5 w-5 text-blue-600" />
            </div>
            <div className="min-w-0">
              <div className="truncate font-semibold text-slate-900">{course.title}</div>
              <div className="truncate text-xs text-slate-500">{course.framework}</div>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-3">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full rounded-full bg-blue-600 transition-all duration-500"
                style={{ width: `${course.progress_percent}%` }}
              />
            </div>
            <span className="text-xs font-semibold text-slate-600">
              {course.progress_percent}%
            </span>
          </div>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-3">
        {course.modules.map((module) => {
          const open = overrides[module.index] ?? module.unlocked;
          
          return (
            <section key={module.index} className="mb-1">
              {module.unlocked ? (
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() =>
                    setOverrides((prev) => ({ ...prev, [module.index]: !open }))
                  }
                  className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left hover:bg-slate-100"
                >
                  <BookOpen className="h-6 w-6 shrink-0 text-blue-600" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-base font-bold text-slate-900">
                      Module {module.index + 1}
                    </span>
                    <span className="line-clamp-2 block text-sm text-slate-600">{module.title}</span>
                  </span>
                  <ChevronRight
                    className={`h-5 w-5 shrink-0 text-slate-600 transition-transform duration-200 ${
                      open ? "-rotate-90" : ""
                    }`}
                  />
                </button>
              ) : (
                <div className="flex items-center gap-3 px-2 py-2 text-slate-400">
                  <Lock className="h-5 w-5 shrink-0" />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-semibold">Module {module.index + 1}</span>
                    <span className="line-clamp-2 block text-xs">{module.title}</span>
                  </span>
                </div>
              )}
              

              {module.unlocked && (
                // Animating height: a grid row goes from 0fr to 1fr.
                <div
                  className={`grid transition-[grid-template-rows] duration-200 ${
                    open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
                  }`}
                >
                  <div className="min-h-0 overflow-hidden">
                  <ModuleGenerate courseKey={course.key} module={module} />
                  <ul className="ml-5 min-h-0 space-y-1 overflow-hidden border-l border-slate-200">
                    {module.steps.map((step, i) => (
                      <li key={step.id}>
                        <NavLink
                          to={`/course/${course.key}/step/${step.id}`}
                          className={({ isActive }) =>
                            `-ml-px flex items-start gap-2 rounded-r-lg border-l-2 py-2 pl-4 pr-2 text-[15px] ${
                                isActive
                                  ? "border-blue-600 bg-blue-100 font-semibold text-blue-700"
                                  : "border-transparent font-medium text-slate-700 hover:bg-slate-100"
                            }`
                          }
                        >
                          <span className="mt-0.5">
                            <StepIcon progress={step.progress} />
                          </span>
                          <span className="line-clamp-2 flex-1">
                            <span className="mr-1.5 inline-block w-7 text-slate-400 tabular-nums">
                              {module.index + 1}.{i + 1}
                            </span>
                            {step.title}
                          </span>
                          {step.lesson !== "ready" && (
                            <span className="rounded bg-slate-200 px-1.5 text-[10px] text-slate-600">
                              {step.lesson}
                            </span>
                          )}
                        </NavLink>
                      </li>
                    ))}
                  </ul>
                  </div>
                </div>
              )}
            </section>
          );
        })}
      </nav>
    </aside>
  );
}

function ModuleGenerate({ courseKey, module }: { courseKey: string; module: Module }) {
  const qc = useQueryClient();
  const generate = useGenerateModule(courseKey);
  const [jobId, setJobId] = useState<string | null>(null);

  // After a refresh, pick up a job that is still running for this module.
  const active = useActiveJobs(courseKey);
  const resumed = active.data?.find(
    (j) => j.kind === "module" && j.module_index === module.index,
  );
  const job = useJob(jobId ?? resumed?.id ?? null);
  const status = job.data?.status;

  // When a job ends, reload the course so step statuses update.
  useEffect(() => {
    if (status === "done" || status === "failed") {
      qc.invalidateQueries({ queryKey: ["course", courseKey] });
      qc.invalidateQueries({ queryKey: ["jobs", courseKey] });
    }
  }, [status]);

  const needsGeneration = module.steps.some((s) => s.lesson !== "ready");

  if (status === "queued" || status === "running") {
  const { done_steps, total_steps, current_step, current_stage } = job.data!;
  const pct = total_steps ? Math.round((done_steps / total_steps) * 100) : 0;
  return (
    <div className="ml-5 space-y-2 px-3 py-2 text-sm">
      <div className="flex items-center gap-2 text-slate-700">
        Step {Math.min(done_steps + 1, total_steps)} of {total_steps}
        <span className="ml-auto text-xs text-slate-500">
          <Elapsed />
        </span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-slate-200">
        <div
          className="h-full rounded-full bg-blue-600 transition-all duration-500"
          style={{ width: `${Math.max(pct, 4)}%` }}
        />
      </div>
      <div className="text-xs text-slate-500">
        {current_stage ?? "queued"}
        {current_step ? ` · ${current_step}` : ""}
      </div>
    </div>
  );
  }
  if (!needsGeneration) return null;

  return (
    <div className="ml-5 px-3 py-2">
      <button
        type="button"
        disabled={generate.isPending}
        onClick={() => generate.mutate(module.index, { onSuccess: (j) => setJobId(j.id) })}
        className="flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-1.5 text-sm font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-50"
      >
        <Sparkles className="h-4 w-4" />
        Generate lessons
      </button>
      {status === "failed" && (
        <p className="mt-1.5 text-xs text-red-600">
          {job.data?.error ?? "Some steps failed. You can try again."}
        </p>
      )}
      {generate.error && (
        <p className="mt-1.5 text-xs text-red-600">{generate.error.message}</p>
      )}
    </div>
  );
}

function Elapsed() {
  const [start] = useState(() => Date.now());
  const [now, setNow] = useState(start);
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const s = Math.floor((now - start) / 1000);
  return (
    <span className="tabular-nums">
      {Math.floor(s / 60)}:{String(s % 60).padStart(2, "0")}
    </span>
  );
}
import { useState } from "react";
import { NavLink } from "react-router";
import { ChevronRight, CircleCheck, Circle, Flame, Lock } from "lucide-react";
import type { useCourse } from "../api/queries";

type Course = NonNullable<ReturnType<typeof useCourse>["data"]>;

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
    <aside className="flex h-full w-80 shrink-0 flex-col border-r border-slate-200 bg-slate-50">
      <div className="flex items-center gap-2 px-5 py-4">
        <Flame className="h-7 w-7 text-orange-500" />
        <div>
          <div className="text-lg font-bold leading-none">Forge</div>
          <div className="text-xs text-slate-500">Learn by Building</div>
        </div>
      </div>

      <div className="border-y border-slate-200 px-5 py-4">
        <div className="text-xs font-medium uppercase tracking-wide text-slate-500">
          Current course
        </div>
        <div className="mt-1 font-semibold">{course.title}</div>
        <div className="mt-2 flex items-center gap-3">
          <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
            <div
              className="h-full rounded-full bg-blue-600 transition-all duration-500"
              style={{ width: `${course.progress_percent}%` }}
            />
          </div>
          <span className="text-xs font-medium text-slate-600">
            {course.progress_percent}%
          </span>
        </div>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-3">
        {course.modules.map((module) => {
          const open = overrides[module.index] ?? module.unlocked;
          const title = `Module ${module.index + 1}: ${module.title}`;

          return (
            <section key={module.index} className="mb-1">
              {module.unlocked ? (
                <button
                  type="button"
                  aria-expanded={open}
                  onClick={() =>
                    setOverrides((prev) => ({ ...prev, [module.index]: !open }))
                  }
                  className="flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-sm font-semibold text-slate-900 hover:bg-slate-100"
                >
                  <ChevronRight
                    className={`mt-0.5 h-4 w-4 shrink-0 text-slate-400 transition-transform duration-200 ${
                      open ? "rotate-90" : ""
                    }`}
                  />
                  <span>{title}</span>
                </button>
              ) : (
                <div className="flex items-start gap-2 px-2 py-1.5 text-sm font-semibold text-slate-400">
                  <Lock className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>{title}</span>
                </div>
              )}

              {module.unlocked && (
                // Animating height: a grid row goes from 0fr to 1fr.
                <div
                  className={`grid transition-[grid-template-rows] duration-200 ${
                    open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
                  }`}
                >
                  <ul className="min-h-0 space-y-0.5 overflow-hidden">
                    {module.steps.map((step, i) => (
                      <li key={step.id}>
                        <NavLink
                          to={`/course/${course.key}/step/${step.id}`}
                          className={({ isActive }) =>
                            `flex items-start gap-2 rounded-md py-1.5 pl-8 pr-2 text-sm ${
                              isActive
                                ? "bg-blue-100 text-blue-800"
                                : "text-slate-700 hover:bg-slate-100"
                            }`
                          }
                        >
                          <span className="mt-0.5">
                            <StepIcon progress={step.progress} />
                          </span>
                          <span className="line-clamp-2 flex-1">
                            <span className="mr-1.5 text-slate-400">
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
              )}
            </section>
          );
        })}
      </nav>
    </aside>
  );
}
import type { ReactNode } from "react";
import { Link, useParams } from "react-router";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useCourse, useStep } from "../api/queries";
import { useComplete } from "../api/mutations";
import LessonView from "../components/LessonView";
import ExercisePanel from "./ExercisePanel";

export default function StepPage() {
  const { courseKey = "", stepId = "" } = useParams();
  const { data: step, isPending, error } = useStep(courseKey, stepId);
  const { data: course } = useCourse(courseKey); // already cached by the layout
  const complete = useComplete(courseKey, stepId);

  if (isPending) return <p className="p-8 text-slate-500">Loading step…</p>;
  if (error) return <p className="p-8 text-red-600">{error.message}</p>;

  const hasExercise = step.exercise != null;
  const done = step.progress.status !== "open";

  // A step is reachable only if its module is unlocked. The API already says so.
  const link = (id: string | null | undefined) =>
    id && course?.modules.some((m) => m.unlocked && m.steps.some((s) => s.id === id))
      ? `/course/${courseKey}/step/${id}`
      : null;

  const number = `${step.module_index + 1}.${step.step_index + 1}`;

  return (
    <div className="flex h-full">
      <article className="min-w-0 flex-1 overflow-y-auto px-8 py-6">
        <div className="mb-4 text-sm text-slate-500">
          {course?.title} › Module {step.module_index + 1} › {number}
        </div>

        <div className="mb-6 flex items-start justify-between gap-4">
          <h1 className="text-3xl font-bold">
            {number} {step.lesson?.title ?? step.objective}
          </h1>
          <div className="flex shrink-0 gap-2">
            <Arrow to={link(step.previous_step_id)} label="Previous step">
              <ChevronLeft className="h-5 w-5" />
            </Arrow>
            <Arrow to={link(step.next_step_id)} label="Next step">
              <ChevronRight className="h-5 w-5" />
            </Arrow>
          </div>
        </div>

        {step.lesson ? (
          <LessonView lesson={step.lesson} />
        ) : (
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-6 text-slate-600">
            This lesson is not ready yet (status: {step.lesson_status}).
          </div>
        )}

        {!hasExercise && (
          <div className="mt-8 border-t border-slate-200 pt-6">
            <button
              type="button"
              disabled={done || complete.isPending}
              onClick={() => complete.mutate()}
              className="rounded-lg bg-blue-600 px-5 py-2.5 font-medium text-white hover:bg-blue-700 disabled:bg-slate-200 disabled:text-slate-500"
            >
              {done ? "Completed" : "Mark as read"}
            </button>
            {complete.error && (
              <p className="mt-2 text-sm text-red-600">{complete.error.message}</p>
            )}
          </div>
        )}
      </article>

      {step.exercise && (
        <aside className="hidden w-[44%] shrink-0 overflow-y-auto border-l border-slate-200 bg-slate-50 p-6 lg:block">
          <ExercisePanel
            key={step.step_id}
            courseKey={courseKey}
            stepId={stepId}
            exercise={step.exercise}
            progress={step.progress}
          />
        </aside>
      )}
    </div>
  );
}

function Arrow({
  to,
  label,
  children,
}: {
  to: string | null;
  label: string;
  children: ReactNode;
}) {
  const base = "flex h-9 w-9 items-center justify-center rounded-md border border-slate-200";
  return to ? (
    <Link to={to} aria-label={label} className={`${base} hover:bg-slate-100`}>
      {children}
    </Link>
  ) : (
    <span aria-label={label} className={`${base} cursor-not-allowed text-slate-300`}>
      {children}
    </span>
  );
}
import type { ReactNode } from "react";
import { Link, useParams } from "react-router";
import { ArrowLeft, ArrowRight, ChevronLeft, ChevronRight } from "lucide-react";
import { useCourse, useStep } from "../api/queries";
import { useComplete } from "../api/mutations";
import LessonView from "../components/LessonView";
import ExercisePanel from "./ExercisePanel";
import ErrorScreen from "./ErrorScreen";

export default function StepPage() {
  const { courseKey = "", stepId = "" } = useParams();
  const { data: step, isPending, error, refetch } = useStep(courseKey, stepId);
  const { data: course } = useCourse(courseKey); // already cached by the layout
  const complete = useComplete(courseKey, stepId);

  if (isPending) return <p className="p-8 text-slate-500">Loading step…</p>;
  if (error) return <ErrorScreen error={error} onRetry={() => refetch()} />;

  const hasExercise = step.exercise != null;
  const done = step.progress.status !== "open";

  // A step is reachable only if its module is unlocked. The API already says so.
  const link = (id: string | null | undefined) =>
    id && course?.modules.some((m) => m.unlocked && m.steps.some((s) => s.id === id))
      ? `/course/${courseKey}/step/${id}`
      : null;

  const number = `${step.module_index + 1}.${step.step_index + 1}`;

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto lg:flex-row lg:overflow-hidden">
      <article className="min-w-0 shrink-0 rounded-2xl border border-slate-200 bg-white px-8 py-6 shadow-sm lg:flex-1 lg:shrink lg:overflow-y-auto">
        <div className="mb-3 flex items-center gap-1.5 text-sm text-slate-400">
          <span className="text-blue-500">{course?.title}</span>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="text-blue-500">Module {step.module_index + 1}</span>
          <ChevronRight className="h-3.5 w-3.5" />
          <span className="font-medium text-slate-800">{number}</span>
        </div>

        <div className="mb-6 flex items-start justify-between gap-4">
          <h1 className="text-3xl font-bold leading-tight tracking-tight text-slate-900">
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
          <LessonView lesson={step.lesson}/>
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
        <aside className="w-full shrink-0 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm lg:w-[44%] lg:min-w-[380px] lg:max-w-[760px] lg:overflow-y-auto">
          <ExercisePanel
            key={step.step_id}
            courseKey={courseKey}
            stepId={stepId}
            exercise={step.exercise}
            progress={step.progress}
          />
          <div className="mt-6 flex gap-3">
            <NavButton to={link(step.previous_step_id)} direction="prev" />
            <NavButton to={link(step.next_step_id)} direction="next" />
          </div>
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
  const base = "flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 bg-white shadow-sm";
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

function NavButton({ to, direction }: { to: string | null; direction: "prev" | "next" }) {
  const isNext = direction === "next";
  const label = isNext ? "Next Lesson" : "Previous Lesson";
  const Icon = isNext ? ArrowRight : ArrowLeft;
  const content = isNext ? (
    <>
      {label}
      <Icon className="h-4 w-4" />
    </>
  ) : (
    <>
      <Icon className="h-4 w-4" />
      {label}
    </>
  );
  const base =
    "flex flex-1 items-center justify-center gap-2 rounded-xl border px-5 py-2.5 font-semibold shadow-sm";

  if (!to) {
    return (
      <span className={`${base} cursor-not-allowed border-slate-200 bg-slate-50 text-slate-300`}>
        {content}
      </span>
    );
  }
  return (
    <Link
      to={to}
      className={`${base} ${
        isNext
          ? "border-blue-600 bg-blue-600 text-white hover:bg-blue-700"
          : "border-blue-200 bg-white text-blue-700 hover:bg-blue-50"
      }`}
    >
      {content}
    </Link>
  );
}
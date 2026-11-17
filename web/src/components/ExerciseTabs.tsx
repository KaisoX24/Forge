import { lazy, Suspense, useState } from "react";
import { Lock } from "lucide-react";
import { useSolution, type useStep } from "../api/queries";
import { useGiveUp, useNextHint } from "../api/mutations";

type Step = NonNullable<ReturnType<typeof useStep>["data"]>;
type Exercise = NonNullable<Step["exercise"]>;
type Progress = Step["progress"];

export const CodeEditor = lazy(() => import("./CodeEditor"));

export function FileTabs({
  names,
  active,
  onSelect,
}: {
  names: string[];
  active: string;
  onSelect: (name: string) => void;
}) {
  return (
    <div className="flex">
      {names.map((name) => (
        <button
          key={name}
          type="button"
          onClick={() => onSelect(name)}
          className={`border-b-2 px-3 py-2 text-sm font-medium ${
            name === active
              ? "border-blue-600 text-blue-700"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          {name}
        </button>
      ))}
    </div>
  );
}

type TabProps = {
  courseKey: string;
  stepId: string;
  exercise: Exercise;
  progress: Progress;
};

export function HintsTab({ courseKey, stepId, exercise, progress }: TabProps) {
  const next = useNextHint(courseKey, stepId);
  const total = exercise.hint_count;

  if (total === 0) {
    return <p className="text-sm text-slate-500">This exercise has no hints.</p>;
  }

  return (
    <div className="space-y-4">
      {exercise.hints.length === 0 && (
        <p className="text-sm text-slate-500">
          No hints revealed yet. Give the exercise a try first.
        </p>
      )}

      <ol className="space-y-3">
        {exercise.hints.map((hint, i) => (
          <li key={i} className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm">
            <div className="mb-1 font-semibold text-amber-800">Hint {i + 1}</div>
            <p className="text-slate-700">{hint}</p>
          </li>
        ))}
      </ol>

      {progress.hints_revealed < total ? (
        <button
          type="button"
          disabled={next.isPending}
          onClick={() => next.mutate()}
          className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-medium hover:bg-slate-100 disabled:opacity-50"
        >
          Reveal hint {progress.hints_revealed + 1} of {total}
        </button>
      ) : (
        <p className="text-sm text-slate-500">All hints revealed.</p>
      )}
      {next.error && <p className="text-sm text-red-600">{next.error.message}</p>}
    </div>
  );
}

export function SolutionTab({ courseKey, stepId, exercise, progress }: TabProps) {
  const unlocked = progress.solution_unlocked;
  const solution = useSolution(courseKey, stepId, unlocked);
  const giveUp = useGiveUp(courseKey, stepId);
  const [confirming, setConfirming] = useState(false);
  const [selected, setSelected] = useState<string>();

  if (!unlocked) {
    return (
      <div className="rounded-lg border border-slate-200 bg-white p-6 text-center">
        <Lock className="mx-auto mb-2 h-6 w-6 text-slate-400" />
        <p className="text-slate-600">Solve the exercise to see the solution.</p>

        {progress.give_up_available ? (
          confirming ? (
            <div className="mt-4 space-y-3">
              <p className="text-sm text-slate-600">
                This marks the step as given up and shows the solution.
              </p>
              <div className="flex justify-center gap-2">
                <button
                  type="button"
                  disabled={giveUp.isPending}
                  onClick={() => giveUp.mutate()}
                  className="rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:opacity-50"
                >
                  Yes, show the solution
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(false)}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm hover:bg-slate-100"
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => setConfirming(true)}
              className="mt-4 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-medium text-amber-800 hover:bg-amber-100"
            >
              Give up
            </button>
          )
        ) : (
          <p className="mt-3 text-xs text-slate-400">
            Giving up unlocks after a few failed submits.
          </p>
        )}
        {giveUp.error && <p className="mt-3 text-sm text-red-600">{giveUp.error.message}</p>}
      </div>
    );
  }

  if (solution.isPending) return <p className="text-sm text-slate-500">Loading solution…</p>;
  if (solution.error) return <p className="text-sm text-red-600">{solution.error.message}</p>;

  const files = solution.data.files;
  const names = Object.keys(files);
  const current = selected && selected in files ? selected : names[0];

  return (
    <div className="space-y-4">
      <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
        <div className="border-b border-slate-200 bg-slate-50 px-2">
          <FileTabs names={names} active={current} onSelect={setSelected} />
        </div>
        <div className="h-80">
          <Suspense fallback={<p className="p-4 text-sm text-slate-500">Loading editor…</p>}>
            <CodeEditor path={`solution/${current}`} value={files[current]} onChange={() => {}} readOnly />
          </Suspense>
        </div>
      </div>
      {exercise.explanation && (
        <p className="text-sm leading-6 text-slate-700">{exercise.explanation}</p>
      )}
    </div>
  );
}
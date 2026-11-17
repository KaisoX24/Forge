import { Suspense, useState, useRef, useEffect } from "react";
import { Play, RotateCcw, Send } from "lucide-react";
import type { useStep } from "../api/queries";
import { useRun, useSubmit, useSaveDraft } from "../api/mutations";
import TestResults from "./TestResults";
import { CodeEditor, FileTabs, HintsTab, SolutionTab } from "./ExerciseTabs";

type Step = NonNullable<ReturnType<typeof useStep>["data"]>;
type Exercise = NonNullable<Step["exercise"]>;
type Progress = Step["progress"];

const difficultyStyle: Record<string, string> = {
  easy: "bg-emerald-100 text-emerald-700",
  medium: "bg-amber-100 text-amber-700",
  hard: "bg-red-100 text-red-700",
};

type Props = {
  courseKey: string;
  stepId: string;
  exercise: Exercise;
  progress: Progress;
};

type Tab = "exercise" | "solution" | "hints";

export default function ExercisePanel({ courseKey, stepId, exercise, progress }: Props) {
  const [tab, setTab] = useState<Tab>("exercise");
  const [files, setFiles] = useState<Record<string, string>>(exercise.files);
  const names = Object.keys(files);
  const [active, setActive] = useState(names[0]);
  const run = useRun(courseKey, stepId);
  const submit = useSubmit(courseKey, stepId);
  const saveDraft = useSaveDraft(courseKey, stepId);
  const lastSaved = useRef(exercise.files);

  useEffect(() => {
    if (files === lastSaved.current) return;
    const timer = setTimeout(() => {
      lastSaved.current = files;
      saveDraft.mutate(files);
    }, 800);
    return () => clearTimeout(timer);
  }, [files, saveDraft.mutate]);

  const filesRef = useRef(files);
  filesRef.current = files;

  useEffect(() => {
    return () => {
      if (filesRef.current !== lastSaved.current) {
        lastSaved.current = filesRef.current;
        saveDraft.mutate(filesRef.current);
      }
    };
  }, []);

  const latest = submit.submittedAt > run.submittedAt ? submit : run;
  const busy = run.isPending || submit.isPending;

  const tabs: { id: Tab; label: string }[] = [
    { id: "exercise", label: "Exercise" },
    { id: "solution", label: progress.solution_unlocked ? "Solution" : "Solution (Hidden)" },
    { id: "hints", label: `Hints (${progress.hints_revealed}/${exercise.hint_count})` },
  ];

  const tabProps = { courseKey, stepId, exercise, progress };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between border-b border-slate-200">
        <div className="flex gap-1">
          {tabs.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTab(t.id)}
              className={`border-b-2 px-3 py-2 text-sm font-medium ${
                tab === t.id
                  ? "border-blue-600 text-blue-700"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              {t.label}
            </button>
          ))}
        </div>
        <span
          className={`mb-1 rounded-full capitalize px-3 py-0.5 text-sm font-medium ${
            difficultyStyle[exercise.difficulty] ?? "bg-slate-100 text-slate-600"
          }`}
        >
          {exercise.difficulty}
        </span>
      </div>

      {/* Hidden, not removed, so the editor keeps its text and the results stay put. */}
      <div className={tab === "exercise" ? "space-y-5" : "hidden"}>
        <h2 className="text-xl font-bold">{exercise.title}</h2>
        <p className="text-slate-600">{exercise.description}</p>

        <ol className="space-y-2 rounded-lg border border-slate-200 bg-white p-4 text-sm">
          {exercise.instructions.map((line, i) => (
            <li key={i} className="flex gap-3">
              <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-slate-300 text-xs text-slate-500">
                {i + 1}
              </span>
              <span className="text-slate-700">{line}</span>
            </li>
          ))}
        </ol>

        <div className="overflow-hidden rounded-lg border border-slate-200 bg-white">
          <div className="flex items-center justify-between border-b border-slate-200 bg-slate-50 px-2">
            <FileTabs names={names} active={active} onSelect={setActive} />
            <button
              type="button"
              onClick={() => setFiles(exercise.starter_files)}
              className="flex items-center gap-1 px-2 text-sm text-blue-700 hover:underline"
            >
              <RotateCcw className="h-3.5 w-3.5" />
              Reset
            </button>
          </div>

          <div className="h-80">
            <Suspense fallback={<p className="p-4 text-sm text-slate-500">Loading editor…</p>}>
              <CodeEditor
                path={active}
                value={files[active]}
                onChange={(value) => setFiles((prev) => ({ ...prev, [active]: value }))}
              />
            </Suspense>
          </div>
        </div>

        <div className="flex justify-end gap-3">
          <button
            type="button"
            disabled={busy}
            onClick={() => run.mutate(files)}
            className="flex items-center gap-2 rounded-lg border border-slate-300 bg-white px-4 py-2 font-medium text-slate-800 hover:bg-slate-100 disabled:opacity-50"
          >
            <Play className="h-4 w-4" />
            Run Tests
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => submit.mutate(files)}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            Submit
          </button>
        </div>

        <TestResults result={latest.data} pending={latest.isPending} error={latest.error} />
      </div>

      {tab === "solution" && <SolutionTab {...tabProps} />}
      {tab === "hints" && <HintsTab {...tabProps} />}
    </div>
  );
}
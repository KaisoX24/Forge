import { CircleCheck, CircleX, EyeOff, LoaderCircle } from "lucide-react";
import type { useRun, useSubmit } from "../api/mutations";

type Result =
  | NonNullable<ReturnType<typeof useRun>["data"]>
  | NonNullable<ReturnType<typeof useSubmit>["data"]>;
type CaseResult = Result["cases"][number];

type Props = {
  result?: Result;
  pending: boolean;
  error?: Error | null;
};

function Detail({ label, value }: { label: string; value?: string | null }) {
  if (value == null) return null;
  return (
    <div className="flex gap-2">
      <span className="w-16 shrink-0 text-slate-500">{label}</span>
      <code className="whitespace-pre-wrap break-all font-mono text-slate-800">{value}</code>
    </div>
  );
}

function CaseRow({ c }: { c: CaseResult }) {
  return (
    <li className="px-4 py-2.5">
      <div className="flex items-center gap-3">
        {c.passed ? (
          <CircleCheck className="h-5 w-5 shrink-0 fill-emerald-500 text-white" />
        ) : (
          <CircleX className="h-5 w-5 shrink-0 fill-red-500 text-white" />
        )}
        <span className="flex-1 text-sm text-slate-800">{c.label}</span>
        {!c.visible && (
          <span className="flex items-center gap-1 text-xs text-slate-400">
            <EyeOff className="h-3.5 w-3.5" />
            hidden
          </span>
        )}
      </div>

      {/* Details exist only for visible cases (hidden ones are cleared by the API). */}
      {c.visible && !c.passed && (
        <div className="ml-8 mt-2 space-y-1 rounded-md bg-slate-50 p-3 text-xs">
          <Detail label="Input" value={c.inputs} />
          <Detail label="Expected" value={c.expected} />
          <Detail label="Got" value={c.got} />
        </div>
      )}
    </li>
  );
}

// Only a Submit result has "solved"; a Run result does not, so a Run shows no banner.
function SubmitBanner({ result }: { result: Result }) {
  if (!("solved" in result)) return null;
  if (result.solved) {
    return (
      <div className="m-4 mb-0 rounded-md bg-emerald-50 p-3 text-sm text-emerald-800">
        Solved on attempt {result.attempt_no}. Nice work!
      </div>
    );
  }
  return (
    <div className="m-4 mb-0 rounded-md bg-amber-50 p-3 text-sm text-amber-800">
      Not solved yet (attempt {result.attempt_no}).{" "}
      {result.give_up_available && "You can now give up and reveal the solution."}
    </div>
  );
}

export default function TestResults({ result, pending, error }: Props) {
  let body;

  if (pending) {
    body = (
      <p className="flex items-center gap-2 p-4 text-sm text-slate-500">
        <LoaderCircle className="h-4 w-4 animate-spin" />
        Running tests…
      </p>
    );
  } else if (error) {
    body = <p className="p-4 text-sm text-red-600">{error.message}</p>;
  } else if (!result) {
    body = (
      <p className="p-4 text-sm text-slate-500">Run your code to see the test results.</p>
    );
  } else {
    body = (
      <>
        <SubmitBanner result={result} />
        {result.status === "error" && (
          <pre className="m-4 overflow-x-auto whitespace-pre-wrap rounded-md bg-red-50 p-3 font-mono text-xs text-red-700">
            {result.message}
          </pre>
        )}
        {result.status === "passed" && !("solved" in result) && (
          <p className="px-4 pt-3 text-sm text-emerald-700">
            These tests pass. Submit to check the hidden ones too.
          </p>
        )}
        <ul className="divide-y divide-slate-100">
          {result.cases.map((c, i) => (
            <CaseRow key={i} c={c} />
          ))}
        </ul>
      </>
    );
  }

  return (
    <div
      aria-live="polite"
      className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm"
    >
      <div className="flex items-center justify-between border-b border-slate-200 px-4 py-2 text-sm">
        <span className="border-b-2 border-blue-600 pb-2.5 font-semibold text-blue-700">
          Test Results
        </span>
        {result && (
          <span className={`mb-2 rounded-full px-2.5 py-0.5 text-xs font-semibold ${
              result.passed_count === result.total
                ? "bg-emerald-50 text-emerald-700"
                : "bg-slate-100 text-slate-600"
            }`}>
              {result.passed_count} / {result.total} tests
          </span>
        )}
      </div>
      {body}
    </div>
  );
}
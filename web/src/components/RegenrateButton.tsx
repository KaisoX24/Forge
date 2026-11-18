import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Loader2, RefreshCw } from "lucide-react";
import { useActiveJobs, useJob } from "../api/queries";
import { useRegenerateStep } from "../api/mutations";

export default function RegenerateButton({
  courseKey,
  stepId,
  onDone,
}: {
  courseKey: string;
  stepId: string;
  onDone?: () => void;
}) {
  const qc = useQueryClient();
  const regenerate = useRegenerateStep(courseKey, stepId);
  const [jobId, setJobId] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);

  // After a refresh, pick up a regeneration that is still running.
  const active = useActiveJobs(courseKey);
  const resumed = active.data?.find((j) => j.kind === "step" && j.step_id === stepId);
  const job = useJob(jobId ?? resumed?.id ?? null);
  const status = job.data?.status;

  useEffect(() => {
    if (status !== "done" && status !== "failed") return;
    // Wait for the fresh data to load, then tell the page.
    Promise.all([
      qc.invalidateQueries({ queryKey: ["step", courseKey, stepId] }),
      qc.invalidateQueries({ queryKey: ["course", courseKey] }),
      qc.invalidateQueries({ queryKey: ["solution", courseKey, stepId] }),
      qc.invalidateQueries({ queryKey: ["jobs", courseKey] }),
    ]).then(() => onDone?.());
  }, [status]);

  if (status === "queued" || status === "running") {
    return (
      <div className="flex items-center gap-2 text-sm text-slate-600">
        <Loader2 className="h-4 w-4 animate-spin text-blue-600" />
        Regenerating… {job.data!.current_stage ?? "queued"}
      </div>
    );
  }

  if (confirming) {
    return (
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <span className="text-slate-700">
          This replaces the lesson and exercise and resets your progress on this step.
        </span>
        <button
          type="button"
          disabled={regenerate.isPending}
          onClick={() =>
            regenerate.mutate(undefined, {
              onSuccess: (j) => {
                setJobId(j.id);
                setConfirming(false);
              },
            })
          }
          className="rounded-lg bg-red-600 px-3 py-1.5 font-semibold text-white hover:bg-red-700 disabled:opacity-50"
        >
          Regenerate
        </button>
        <button
          type="button"
          onClick={() => setConfirming(false)}
          className="font-medium text-slate-500 hover:text-slate-800"
        >
          Cancel
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm text-slate-500">
      Not happy with this lesson?
      <button
        type="button"
        onClick={() => setConfirming(true)}
        className="flex items-center gap-1.5 font-medium text-blue-600 hover:text-blue-800"
      >
        <RefreshCw className="h-3.5 w-3.5" />
        Regenerate
      </button>
      {status === "failed" && (
        <span className="text-red-600">{job.data?.error ?? "Regeneration failed."}</span>
      )}
      {regenerate.error && <span className="text-red-600">{regenerate.error.message}</span>}
    </div>
  );
}
import { RefreshCw, ServerOff, TriangleAlert } from "lucide-react";
import { ApiError } from "../api/client";

export default function ErrorScreen({
  error,
  onRetry,
}: {
  error: Error;
  onRetry?: () => void;
}) {
  // Network failure, or the dev proxy's empty 5xx when the backend is down.
  const offline = !(error instanceof ApiError) || (error.status >= 500 && !error.message);
  const Icon = offline ? ServerOff : TriangleAlert;

  return (
    <div className="flex h-full min-h-[50vh] items-center justify-center p-8">
      <div className="max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-red-50">
          <Icon className="h-6 w-6 text-red-500" />
        </div>
        <h2 className="text-lg font-bold text-slate-900">
          {offline ? "Can't reach the Forge backend" : "Something went wrong"}
        </h2>
        <p className="mt-2 text-sm text-slate-600">
          {offline
            ? "Site currently under maintainance, try again later."
            : error.message}
        </p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mx-auto mt-5 flex items-center gap-2 rounded-xl bg-blue-600 px-5 py-2.5 font-semibold text-white shadow-sm hover:bg-blue-700"
          >
            <RefreshCw className="h-4 w-4" />
            Try again
          </button>
        )}
      </div>
    </div>
  );
}
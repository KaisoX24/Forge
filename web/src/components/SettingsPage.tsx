import { useState } from "react";
import { Cloud, Cpu, Info } from "lucide-react";
import { useSettings } from "../api/queries";
import ErrorScreen from "./ErrorScreen";

export default function SettingsPage() {
  const { data, isPending, error, refetch } = useSettings();
  // Which provider card is selected while browsing. This is not the active model yet.
  const [picked, setPicked] = useState<string | null>(null);
  const [model, setModel] = useState<string | null>(null);

  if (isPending) return <p className="p-8 text-slate-500">Loading settings…</p>;
  if (error) return <ErrorScreen error={error} onRetry={() => refetch()} />;

  const active = data.active;
  const activeLabel = data.providers.find((p) => p.id === active?.provider)?.label;
  // Nothing is preselected: with no active model and no click, no card is highlighted.
  const selected = picked ?? active?.provider ?? null;
  const selectedProvider = data.providers.find((p) => p.id === selected);
  const activeModelHere = selected && active?.provider === selected ? active.model : null;
  const modelValue = model ?? activeModelHere ?? "";

  return (
    <div className="h-full overflow-y-auto rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
      <h1 className="text-3xl font-bold text-slate-900">Settings</h1>
      <p className="mt-1 text-slate-600">
        {active ? (
          <>
            Active model:{" "}
            <span className="font-semibold text-slate-900">
              {activeLabel} · {active.model}
            </span>
          </>
        ) : (
          "No model selected"
        )}
      </p>

      {!active && (
        <div className="mt-5 flex items-start gap-3 rounded-xl border border-blue-100 bg-blue-50/60 p-4 text-sm text-slate-700">
          <Info className="mt-0.5 h-5 w-5 shrink-0 text-blue-600" />
          Pick a provider and a model to start generating lessons. Lessons you already
          have stay readable without one.
        </div>
      )}

      <h2 className="mt-8 text-lg font-bold text-slate-900">1. Provider</h2>
      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {data.providers.map((p) => {
          const isSelected = selected === p.id;
          const Icon = p.needs_key ? Cloud : Cpu;
          return (
            <button
              key={p.id}
              type="button"
              aria-pressed={isSelected}
              onClick={() => {
                setPicked(p.id);
                setModel(null);
                }}
              className={`rounded-xl border p-4 text-left transition ${
                isSelected
                  ? "border-blue-500 bg-blue-50 ring-2 ring-blue-100"
                  : "border-slate-200 bg-white hover:border-blue-300"
              }`}
            >
              <div className="flex items-center justify-between">
                <Icon className="h-6 w-6 text-blue-600" />
                {active?.provider === p.id && (
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                    Active
                  </span>
                )}
              </div>
              <div className="mt-3 font-semibold text-slate-900">{p.label}</div>
              <div
                className={`mt-0.5 text-sm ${
                  p.needs_key && p.has_key ? "text-emerald-700" : "text-slate-500"
                }`}
              >
                {!p.needs_key ? "Runs on your machine" : p.has_key ? "Key saved" : "No key yet"}
              </div>
            </button>
          );
        })}
      </div>
      {selectedProvider && (
        <ModelSection
            providerId={selectedProvider.id}
            models={selectedProvider.models}
            activeModel={activeModelHere}
            value={modelValue}
            onChange={setModel}
        />
        )}

    </div>
  );
}

function ModelSection({
  providerId,
  models,
  activeModel,
  value,
  onChange,
}: {
  providerId: string;
  models: string[];
  activeModel: string | null;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <>
      <h2 className="mt-8 text-lg font-bold text-slate-900">2. Model</h2>

      {models.length > 0 ? (
        <div className="mt-3 space-y-2" role="radiogroup">
          {models.map((m) => {
            const chosen = value === m;
            return (
              <button
                key={m}
                type="button"
                role="radio"
                aria-checked={chosen}
                onClick={() => onChange(m)}
                className={`flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition ${
                  chosen
                    ? "border-blue-500 bg-blue-50"
                    : "border-slate-200 hover:border-blue-300"
                }`}
              >
                <span
                  className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
                    chosen ? "border-blue-600" : "border-slate-300"
                  }`}
                >
                  {chosen && <span className="h-2 w-2 rounded-full bg-blue-600" />}
                </span>
                <span className="flex-1 font-medium text-slate-900">{m}</span>
                {m === activeModel && (
                  <span className="rounded-full bg-emerald-50 px-2 py-0.5 text-xs font-semibold text-emerald-700">
                    Active
                  </span>
                )}
              </button>
            );
          })}
        </div>
      ) : (
        <p className="mt-3 text-sm text-slate-500">
          No models saved for this provider yet. Type one below.
        </p>
      )}

      <label className="mt-4 block text-sm font-medium text-slate-700">
        {models.length > 0 ? "Or use a different model" : "Model name"}
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={
            providerId === "ollama"
              ? "A model name from `ollama list`"
              : "The exact model name from the provider's docs"
          }
          className="mt-1.5 block w-full max-w-md rounded-xl border border-slate-200 px-3 py-2 text-sm font-normal outline-none placeholder:text-slate-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
        />
      </label>
    </>
  );
}
import { useState } from "react";
import { Cloud, Cpu, Info, KeyRound, TriangleAlert } from "lucide-react";
import { useRemoveKey, useSaveKey, useChooseModel } from "../api/mutations";
import type { components } from "../api/schema";
import { useSettings } from "../api/queries";
import ErrorScreen from "./ErrorScreen";
import { looksTooSmall } from "../lib/modelSize";


type Provider = components["schemas"]["ProviderView"];

export default function SettingsPage() {
  const choose=useChooseModel();
  const { data, isPending, error, refetch } = useSettings();
  // Which provider card is selected while browsing. This is not the active model yet.
  const [picked, setPicked] = useState<string | null>(null);
  // The model chosen or typed for each provider, kept while switching cards.
  const [chosen, setChosen] = useState<Record<string, string>>({});

  if (isPending) return <p className="p-8 text-slate-500">Loading settings…</p>;
  if (error) return <ErrorScreen error={error} onRetry={() => refetch()} />;

  const active = data.active;
  const activeLabel = data.providers.find((p) => p.id === active?.provider)?.label;
  // Nothing is preselected: with no active model and no click, no card is highlighted.
  const selected = picked ?? active?.provider ?? null;
  const selectedProvider = data.providers.find((p) => p.id === selected);
  const activeModelHere = selected && active?.provider === selected ? active.model : null;
  // An empty string is a real value (the field was cleared), so only null/undefined fall through.
  const modelValue = (selected ? chosen[selected] : undefined) ?? activeModelHere ?? "";
  const trimmed = modelValue.trim();
  const alreadyActive = active?.provider === selected && active?.model === trimmed;
  const missingKey = !!selectedProvider?.needs_key && !selectedProvider.has_key;
  const canUse = !!selectedProvider && !!trimmed && !missingKey && !alreadyActive && !choose.isPending;
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
              onClick={() => setPicked(p.id)}
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
          onChange={(m) => setChosen((c) => ({ ...c, [selectedProvider.id]: m }))}
        />
      )}
      {selectedProvider?.needs_key && (
          <KeySection key={selectedProvider.id} provider={selectedProvider} />
        )}

      {selectedProvider && (
        <div className="mt-8 border-t border-slate-200 pt-6">
          {looksTooSmall(trimmed) && (
            <div className="mb-4 flex max-w-xl items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
              <TriangleAlert className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
              Models under 9B often struggle with lesson and exercise generation. It will
              work, but expect weaker results.
            </div>
          )}

          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              disabled={!canUse}
              onClick={() => choose.mutate({ provider: selectedProvider.id, model: trimmed })}
              className="rounded-xl bg-blue-600 px-6 py-2.5 font-semibold text-white shadow-sm hover:bg-blue-700 disabled:opacity-40"
            >
              {choose.isPending ? "Saving…" : alreadyActive ? "In use" : "Use this model"}
            </button>
            {missingKey && <span className="text-sm text-slate-500">Save an API key first.</span>}
          </div>

          {choose.isError && <p className="mt-2 text-sm text-red-600">{choose.error.message}</p>}
          <p className="mt-3 text-xs text-slate-500">
            A generation that's already running keeps its model. The next one uses this.
          </p>
        </div>
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
            const isChosen = value === m;
            return (
              <button
                key={m}
                type="button"
                role="radio"
                aria-checked={isChosen}
                onClick={() => onChange(m)}
                className={`flex w-full items-center gap-3 rounded-xl border px-4 py-3 text-left transition ${
                  isChosen
                    ? "border-blue-500 bg-blue-50"
                    : "border-slate-200 hover:border-blue-300"
                }`}
              >
                <span
                  className={`flex h-4 w-4 shrink-0 items-center justify-center rounded-full border ${
                    isChosen ? "border-blue-600" : "border-slate-300"
                  }`}
                >
                  {isChosen && <span className="h-2 w-2 rounded-full bg-blue-600" />}
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
        {models.length > 0 ? "Or type a different model" : "Model name"}
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
      {value.trim() && !models.includes(value.trim()) && (
        <p className="mt-2 text-sm text-slate-500">
          New model. It's added to your list when you press “Use this model”.
        </p>
      )}
    </>
  );
}

function KeySection({ provider }: { provider: Provider }) {
  const save = useSaveKey();
  const remove = useRemoveKey();
  const [draft, setDraft] = useState("");
  const [replacing, setReplacing] = useState(false);

  const busy = save.isPending || remove.isPending;
  const error = save.isError ? save.error : remove.isError ? remove.error : null;

  function submit() {
    const key = draft.trim();
    if (!key) return;
    remove.reset();
    save.mutate(
      { provider: provider.id, key },
      {
        onSuccess: () => {
          setDraft("");
          setReplacing(false);
        },
      },
    );
  }

  return (
    <>
      <h2 className="mt-8 text-lg font-bold text-slate-900">3. API key</h2>

      {provider.has_key && !replacing ? (
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <span className="flex items-center gap-2 text-sm text-emerald-700">
            <KeyRound className="h-4 w-4" />
            Key saved. It's stored in your system's credential manager.
          </span>
          <button
            type="button"
            onClick={() => setReplacing(true)}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            Replace
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              save.reset();
              remove.mutate(provider.id);
            }}
            className="rounded-lg px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
          >
            Remove
          </button>
        </div>
      ) : (
        <div className="mt-3 flex max-w-md gap-2">
          <input
            type="password"
            autoComplete="off"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") submit();
            }}
            placeholder={`Paste your ${provider.label} API key`}
            className="block w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none placeholder:text-slate-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
          />
          <button
            type="button"
            onClick={submit}
            disabled={!draft.trim() || busy}
            className="rounded-xl bg-blue-600 px-4 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-40"
          >
            Save
          </button>
          {replacing && (
            <button
              type="button"
              onClick={() => {
                setReplacing(false);
                setDraft("");
              }}
              className="px-2 text-sm font-medium text-slate-500 hover:text-slate-800"
            >
              Cancel
            </button>
          )}
        </div>
      )}

      {error && <p className="mt-2 text-sm text-red-600">{error.message}</p>}
      <p className="mt-2 text-xs text-slate-500">
        The key stays on this computer. It isn't shown again after saving.
      </p>
    </>
  );
}
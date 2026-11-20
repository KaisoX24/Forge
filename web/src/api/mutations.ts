import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "./client";
import type { useStep } from "./queries";
import type { components } from "./schema";
type Step = NonNullable<ReturnType<typeof useStep>["data"]>;

type Files=Record<string,string>;

function useRefresh(courseKey: string, stepId: string) {
  const qc = useQueryClient();
  return () =>
    Promise.all([
      qc.invalidateQueries({ queryKey: ["step", courseKey, stepId] }),
      qc.invalidateQueries({ queryKey: ["course", courseKey] }),
      qc.invalidateQueries({ queryKey: ["solution", courseKey, stepId] }),
    ]);
}

const path = (courseKey: string, stepId: string) => ({
  params: { path: { course_key: courseKey, step_id: stepId } },
});

export function useRun(courseKey: string, stepId: string) {
  return useMutation({
    mutationFn: async (files: Files) =>
      unwrap(
        await api.POST("/api/courses/{course_key}/steps/{step_id}/run", {
          ...path(courseKey, stepId),
          body: { files },
        }),
      ),
  });
}

export function useSubmit(courseKey: string, stepId: string) {
  const refresh = useRefresh(courseKey, stepId);
  return useMutation({
    mutationFn: async (files: Files) =>
      unwrap(
        await api.POST("/api/courses/{course_key}/steps/{step_id}/submit", {
          ...path(courseKey, stepId),
          body: { files },
        }),
      ),
    onSuccess: refresh,
  });
}

export function useSaveDraft(courseKey: string, stepId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (files: Files) =>
      unwrap(
        await api.PUT("/api/courses/{course_key}/steps/{step_id}/draft", {
          ...path(courseKey, stepId),
          body: { files },
        }),
      ),
    onSuccess: (_data, files) => {
      qc.setQueryData<Step>(["step", courseKey, stepId], (old) =>
        old?.exercise ? { ...old, exercise: { ...old.exercise, files } } : old,
      );
    },
  });
}

export function useNextHint(courseKey: string, stepId: string) {
  const refresh = useRefresh(courseKey, stepId);
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/courses/{course_key}/steps/{step_id}/hints/next", path(courseKey, stepId)),
      ),
    onSuccess: refresh,
  });
}

export function useGiveUp(courseKey: string, stepId: string) {
  const refresh = useRefresh(courseKey, stepId);
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/courses/{course_key}/steps/{step_id}/give-up", path(courseKey, stepId)),
      ),
    onSuccess: refresh,
  });
}

export function useComplete(courseKey: string, stepId: string) {
  const refresh = useRefresh(courseKey, stepId);
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/courses/{course_key}/steps/{step_id}/complete", path(courseKey, stepId)),
      ),
    onSuccess: refresh,
  });
}

export function useGenerateModule(courseKey: string) {
  return useMutation({
    mutationFn: async (moduleIndex: number) =>
      unwrap(
        await api.POST("/api/courses/{course_key}/modules/{module_index}/generate", {
          params: { path: { course_key: courseKey, module_index: moduleIndex } },
        }),
      ),
  });
}

export function useRegenerateStep(courseKey: string, stepId: string) {
  return useMutation({
    mutationFn: async () =>
      unwrap(
        await api.POST("/api/courses/{course_key}/steps/{step_id}/regenerate", {
          ...path(courseKey, stepId),
        }),
      ),
  });
}

type SettingsView = components["schemas"]["SettingsView"];

// Every settings endpoint returns the full, fresh view, so we put it
// straight into the cache and the page updates without another request.
function useSettingsMutation<TVars>(run: (vars: TVars) => Promise<SettingsView>) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: run,
    onSuccess: (view) => qc.setQueryData(["settings"], view),
  });
}

export function useChooseModel() {
  return useSettingsMutation(async (body: { provider: string; model: string }) =>
    unwrap(await api.PUT("/api/settings/model", { body })),
  );
}

export function useSaveKey() {
  return useSettingsMutation(async (v: { provider: string; key: string }) =>
    unwrap(
      await api.PUT("/api/settings/keys/{provider}", {
        params: { path: { provider: v.provider } },
        body: { key: v.key },
      }),
    ),
  );
}

export function useRemoveKey() {
  return useSettingsMutation(async (provider: string) =>
    unwrap(
      await api.DELETE("/api/settings/keys/{provider}", {
        params: { path: { provider } },
      }),
    ),
  );
}
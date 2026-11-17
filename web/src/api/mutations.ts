import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "./client";

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
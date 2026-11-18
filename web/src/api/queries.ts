import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "./client";

export function useCourses() {
  return useQuery({
    queryKey: ["courses"],
    queryFn: async () => unwrap(await api.GET("/api/courses")),
  });
}

export function useCourse(courseKey: string) {
  return useQuery({
    queryKey: ["course", courseKey],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/courses/{course_key}", {
          params: { path: { course_key:courseKey} },
        }),
      ),
  });
}

export function useStep(courseKey:string,stepId:string){
    return useQuery({
        queryKey:['step',courseKey,stepId],
        queryFn:async()=>
            unwrap(
                await api.GET("/api/courses/{course_key}/steps/{step_id}",{
                    params:{path: {course_key: courseKey, step_id: stepId }},
                }),
            ),
    });
}

export function useSolution(courseKey: string, stepId: string, unlocked: boolean) {
  return useQuery({
    queryKey: ["solution", courseKey, stepId],
    enabled: unlocked,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/courses/{course_key}/steps/{step_id}/solution", {
          params: { path: { course_key: courseKey, step_id: stepId } },
        }),
      ),
  });
}

export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ["job", jobId],
    enabled: jobId != null,
    queryFn: async () =>
      unwrap(
        await api.GET("/api/jobs/{job_id}", {
          params: { path: { job_id: jobId! } },
        }),
      ),
    // Poll every second until the job finishes.
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "done" || status === "failed" ? false : 1000;
    },
  });
}

export function useActiveJobs(courseKey: string) {
  return useQuery({
    queryKey: ["jobs", courseKey],
    queryFn: async () =>
      unwrap(
        await api.GET("/api/courses/{course_key}/jobs", {
          params: { path: { course_key: courseKey }, query: { active: true } },
        }),
      ),
  });
}
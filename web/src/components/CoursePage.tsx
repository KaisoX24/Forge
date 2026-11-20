import { Link } from "react-router";
import { useState } from "react";
import { ArrowRight, Layers } from "lucide-react";
import { useCourses } from "../api/queries";
import { matchesQuery } from "../lib/search";
import SearchBox from "./SearchBox";
import ErrorScreen from "./ErrorScreen";

function actionLabel(percent: number) {
  if (percent <= 0) return "Start course";
  if (percent >= 100) return "Review";
  return "Continue";
}

export default function CoursesPage() {
    const [query, setQuery] = useState("");
    const { data: courses, isPending, error, refetch } = useCourses();

    if (isPending) return <p className="p-8 text-slate-500">Loading courses…</p>;
    if (error) return <ErrorScreen error={error} onRetry={() => refetch()} />;
    const visible = courses.filter((c) => matchesQuery(c, query));
    return (
        <div className="h-full overflow-y-auto rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
        <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
                <h1 className="text-3xl font-bold text-slate-900">My Courses</h1>
                <p className="mt-1 text-slate-600">Pick up where you left off.</p>
            </div>
            <SearchBox value={query} onChange={setQuery} />
            </div>
        {courses.length === 0 ? (
            <p className="mt-8 text-slate-500">No courses yet.</p>) : visible.length===0 ? (
                <p className="mt-8 text-slate-500">No courses match “{query.trim()}”.</p>):(
                <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {visible.map((course) => (
                <Link
                key={course.key}
                to={`/course/${course.key}`}
                className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:border-blue-300 hover:shadow-md"
                >
                <div className="flex items-center gap-3">
                    <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-blue-50">
                    <Layers className="h-6 w-6 text-blue-600" />
                    </div>
                    <div className="min-w-0">
                    <div className="truncate text-lg font-bold text-slate-900">{course.title}</div>
                    <div className="truncate text-sm text-slate-500">{course.framework}</div>
                    </div>
                </div>

                <div className="mt-5 flex items-center gap-3">
                    <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-200">
                    <div
                        className="h-full rounded-full bg-blue-600"
                        style={{ width: `${course.progress_percent}%` }}
                    />
                    </div>
                    <span className="text-sm font-semibold text-slate-600">
                    {course.progress_percent}%
                    </span>
                </div>

                <div className="mt-4 flex items-center gap-1.5 text-sm font-semibold text-blue-600 group-hover:text-blue-800">
                    {actionLabel(course.progress_percent)}
                    <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
                </div>
                </Link>
            ))}
            </div>
        )}
        </div>
    );
}
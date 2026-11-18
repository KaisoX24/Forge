import { BrowserRouter, Navigate, Outlet, Route, Routes, useParams } from "react-router";
import { useCourse } from "./api/queries";
import Sidebar from "./components/Sidebar";
import StepPage from "./components/StepPage";
import ModuleCelebration from "./components/ModuleCelebration";
import ErrorScreen from "./components/ErrorScreen";

function CourseLayout() {
  const { courseKey = "" } = useParams();
  const { data: course, isPending, error, refetch } = useCourse(courseKey);

  if (isPending) return <p className="p-8 text-slate-500">Loading course…</p>;
  if (error) return <ErrorScreen error={error} onRetry={() => refetch()} />;

  return (
    <div className="flex h-screen bg-[#F3F9FE] text-slate-900">
      <Sidebar course={course} />
      <ModuleCelebration key={course.key} course={course} />
      <main className="min-w-0 flex-1 overflow-hidden p-5">
        <Outlet />
      </main>
    </div>
  );
}

function CourseHome() {
  const { courseKey = "" } = useParams();
  const { data: course } = useCourse(courseKey);
  if (!course) return null;

  // Steps in unlocked modules, in course order.
  const steps = course.modules.filter((m) => m.unlocked).flatMap((m) => m.steps);

  const target =
    steps.find((s) => s.progress === "open") ??
    steps[steps.length - 1] ??
    course.modules[0]?.steps[0];

  if (!target) return <p className="p-8 text-slate-500">This course has no steps yet.</p>;
  return <Navigate to={`/course/${courseKey}/step/${target.id}`} replace />;
}


export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* v1 has one course; a course picker comes later. */}
        <Route path="/" element={<Navigate to="/course/fastapi" replace />} />
        <Route path="/course/:courseKey" element={<CourseLayout />}>
          <Route index element={<CourseHome/>} />
          <Route path="step/:stepId" element={<StepPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
import { BrowserRouter, Navigate, Outlet, Route, Routes, useParams } from "react-router";
import { useCourse } from "./api/queries";
import ErrorScreen from "./components/ErrorScreen";
import ModuleCelebration from "./components/ModuleCelebration";
import Sidebar from "./components/Sidebar";
import StepPage from "./components/StepPage";
import CoursesPage from "./components/CoursePage";
import ProgressPage from "./components/ProgressPage";
import SettingsPage from "./components/SettingsPage";

// Always visible: logo, nav, and (inside a course) the module list.
function AppShell() {
  return (
    <div className="flex h-screen bg-[#F3F9FE] text-slate-900">
      <Sidebar />
      <main className="min-w-0 flex-1 overflow-hidden p-5">
        <Outlet />
      </main>
    </div>
  );
}

// Only loads the course and hosts what belongs to it.
function CourseLayout() {
  const { courseKey = "" } = useParams();
  const { data: course, isPending, error, refetch } = useCourse(courseKey);

  if (isPending) return <p className="p-8 text-slate-500">Loading course…</p>;
  if (error) return <ErrorScreen error={error} onRetry={() => refetch()} />;

  return (
    <>
      <ModuleCelebration key={course.key} course={course} />
      <Outlet />
    </>
  );
}

function CourseHome() {
  const { courseKey = "" } = useParams();
  const { data: course } = useCourse(courseKey);
  if (!course) return null;

  const steps = course.modules.filter((m) => m.unlocked).flatMap((m) => m.steps);
  const target =
    steps.find((s) => s.progress === "open") ??
    steps[steps.length - 1] ??
    course.modules[0]?.steps[0];

  if (!target) return <p className="p-8 text-slate-500">This course has no steps yet.</p>;
  return <Navigate to={`/course/${courseKey}/step/${target.id}`} replace />;
}

// Stand-in until each page is built.
function Placeholder({ title }: { title: string }) {
  return (
    <div className="h-full overflow-y-auto rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
      <h1 className="text-2xl font-bold text-slate-900">{title}</h1>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/" element={<Navigate to="/course/fastapi" replace />} />
          <Route path="/courses" element={ <CoursesPage/> } />
          <Route path="/progress" element={ <ProgressPage/> } />
          <Route path="/settings" element={ <SettingsPage/> } />
          <Route path="/course/:courseKey" element={<CourseLayout />}>
            <Route index element={<CourseHome />} />
            <Route path="step/:stepId" element={<StepPage />} />
          </Route>
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
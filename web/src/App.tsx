import { BrowserRouter, Navigate, Outlet, Route, Routes, useParams } from "react-router";
import { useCourse } from "./api/queries";
import Sidebar from "./components/Sidebar";
import StepPage from "./components/StepPage";
import ModuleCelebration from "./components/ModuleCelebration";

function CourseLayout() {
  const { courseKey = "" } = useParams();
  const { data: course, isPending, error } = useCourse(courseKey);

  if (isPending) return <p className="p-8 text-slate-500">Loading course…</p>;
  if (error) return <p className="p-8 text-red-600">{error.message}</p>;

  return (
    <div className="flex h-screen bg-white text-slate-900">
      <Sidebar course={course} />
      <ModuleCelebration key={course.key} course={course} />
      <main className="min-w-0 flex-1 overflow-hidden">
        <Outlet />
      </main>
    </div>
  );
}


export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* v1 has one course; a course picker comes later. */}
        <Route path="/" element={<Navigate to="/course/fastapi" replace />} />
        <Route path="/course/:courseKey" element={<CourseLayout />}>
          <Route index element={<p className="p-8 text-slate-500">Pick a step.</p>} />
          <Route path="step/:stepId" element={<StepPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
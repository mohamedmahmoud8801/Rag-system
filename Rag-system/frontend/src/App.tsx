import type { ReactElement } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { AppShell } from "@/components/layout/AppShell";
import { Spinner } from "@/components/ui";
import { useAuth } from "@/hooks/auth";
import AdminUsers from "@/pages/app/AdminUsers";
import Chat from "@/pages/app/Chat";
import Dashboard from "@/pages/app/Dashboard";
import Data from "@/pages/app/Data";
import Databases from "@/pages/app/Databases";
import Evaluation from "@/pages/app/Evaluation";
import Knowledge from "@/pages/app/Knowledge";
import Projects from "@/pages/app/Projects";
import Settings from "@/pages/app/Settings";
import Video from "@/pages/app/Video";
import Forgot from "@/pages/auth/Forgot";
import Login from "@/pages/auth/Login";
import Register from "@/pages/auth/Register";
import Reset from "@/pages/auth/Reset";
import Verify from "@/pages/auth/Verify";

function FullScreenSpinner() {
  return (<div className="grid h-full place-items-center"><Spinner className="size-8" /></div>);
}

function GuestOnly({ children }: { children: ReactElement }) {
  const { status } = useAuth();
  if (status === "loading") return <FullScreenSpinner />;
  return status === "authenticated" ? <Navigate to="/" replace /> : children;
}

function RequireAuth({ children }: { children: ReactElement }) {
  const { status } = useAuth();
  const location = useLocation();
  if (status === "loading") return <FullScreenSpinner />;
  return status === "authenticated" ? children : <Navigate to="/login" replace state={{ from: location.pathname }} />;
}

function RequireAdmin({ children }: { children: ReactElement }) {
  const { user } = useAuth();
  return user?.role === "admin" ? children : <Navigate to="/" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<GuestOnly><Login /></GuestOnly>} />
        <Route path="/register" element={<GuestOnly><Register /></GuestOnly>} />
        <Route path="/verify" element={<GuestOnly><Verify /></GuestOnly>} />
        <Route path="/forgot" element={<GuestOnly><Forgot /></GuestOnly>} />
        <Route path="/reset" element={<GuestOnly><Reset /></GuestOnly>} />

        <Route element={<RequireAuth><AppShell /></RequireAuth>}>
          <Route index element={<Dashboard />} />
          <Route path="chat" element={<Chat />} />
          <Route path="projects" element={<Projects />} />
          
          {/* 👇 هنا التعديل: الـ Redirect والـ Route بتاع المهام */}
          <Route path="knowledge" element={<Navigate to="/knowledge/summary" replace />} />
          <Route path="knowledge/:task" element={<Knowledge />} />
          
          <Route path="video" element={<Video />} />
          <Route path="data" element={<Data />} />
          <Route path="databases" element={<Databases />} />
          <Route path="evaluation" element={<Evaluation />} />
          <Route path="settings" element={<Settings />} />
          <Route path="admin/users" element={<RequireAdmin><AdminUsers /></RequireAdmin>} />
        </Route>

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  );
}
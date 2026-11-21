import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "sonner";
import "@/App.css";
import { AuthProvider, useAuth } from "@/context/AuthContext";
import { NotificationProvider } from "@/context/NotificationContext";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import Protected from "@/components/Protected";
import Landing from "@/pages/Landing";
import Login from "@/pages/Login";
import Register from "@/pages/Register";
import Dashboard from "@/pages/Dashboard";
import Enroll from "@/pages/Enroll";
import Gallery from "@/pages/Gallery";
import Notifications from "@/pages/Notifications";
import Events from "@/pages/Events";
import EventDetail from "@/pages/EventDetail";
import Admin from "@/pages/Admin";
import PanitiaDashboard from "@/pages/PanitiaDashboard";
import VerificationQueue from "@/pages/VerificationQueue";
import Team from "@/pages/Team";

function HomeRouter() {
  const { loading } = useAuth();
  if (loading) return null;
  return <Landing />;
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <NotificationProvider>
        <div className="min-h-screen flex flex-col bg-[#F5F5F2] text-[#171717] overflow-x-clip">
          <Navbar />
          <main className="flex-1 w-full min-w-0">
            <Routes>
              <Route path="/" element={<HomeRouter />} />
              <Route path="/team" element={<Team />} />
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />

              <Route path="/dashboard" element={<Protected roles={["mahasiswa"]}><Dashboard /></Protected>} />
              <Route path="/enroll" element={<Protected roles={["mahasiswa"]}><Enroll /></Protected>} />
              <Route path="/gallery" element={<Protected roles={["mahasiswa"]}><Gallery /></Protected>} />
              <Route path="/notifications" element={<Protected roles={["mahasiswa"]}><Notifications /></Protected>} />

              <Route path="/panitia" element={<Protected roles={["panitia", "admin"]}><PanitiaDashboard /></Protected>} />
              <Route path="/verification" element={<Protected roles={["mahasiswa"]}><VerificationQueue /></Protected>} />
              <Route path="/events" element={<Protected roles={["mahasiswa", "panitia", "admin"]}><Events /></Protected>} />
              <Route path="/events/:id" element={<Protected roles={["mahasiswa", "panitia", "admin"]}><EventDetail /></Protected>} />

              <Route path="/admin" element={<Protected roles={["admin"]}><Admin /></Protected>} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
          <Footer />
          <Toaster position="bottom-right" richColors closeButton />
        </div>
        </NotificationProvider>
      </BrowserRouter>
    </AuthProvider>
  );
}

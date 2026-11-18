import { Navigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";

export default function Protected({ roles, children }) {
  const { user, loading } = useAuth();
  if (loading) {
    return (
      <div className="min-h-[60vh] grid place-items-center">
        <div className="font-mono text-xs uppercase tracking-[0.3em] text-neutral-500 animate-pulse">
          Loading session…
        </div>
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) {
    return <Navigate to="/dashboard" replace />;
  }
  return children;
}

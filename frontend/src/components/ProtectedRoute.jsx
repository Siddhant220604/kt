import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function ProtectedRoute({ children, adminOnly = false }) {
  const { user } = useAuth();
  const loc = useLocation();
  if (user === null) {
    return (
      <div className="flex min-h-[60vh] items-center justify-center text-sm text-muted-foreground">Loading…</div>
    );
  }
  if (user === false) {
    return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  }
  if (adminOnly && user.role !== "admin") {
    return <Navigate to="/" replace />;
  }
  return children;
}

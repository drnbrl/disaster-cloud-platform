import { useEffect, useState, type ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { isAuthenticated } from "../auth";

export function ProtectedRoute({ children }: { children: ReactNode }) {
  const [state, setState] = useState<"loading" | "yes" | "no">("loading");
  useEffect(() => { void isAuthenticated().then(ok => setState(ok ? "yes" : "no")); }, []);
  if (state === "loading") return <main className="centered">Oturum kontrol ediliyor…</main>;
  if (state === "no") return <Navigate to="/admin/login" replace />;
  return <>{children}</>;
}

import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AdminLoginPage } from "./pages/AdminLoginPage";
import { AllocationPage } from "./pages/AllocationPage";
import { CitizenPage } from "./pages/CitizenPage";
import { DashboardPage } from "./pages/DashboardPage";
import { StatusPage } from "./pages/StatusPage";

export default function App() {
  return <BrowserRouter><Routes>
    <Route path="/" element={<CitizenPage />} />
    <Route path="/status/:requestId" element={<StatusPage />} />
    <Route path="/admin/login" element={<AdminLoginPage />} />
    <Route path="/admin" element={<ProtectedRoute><DashboardPage /></ProtectedRoute>} />
    <Route path="/admin/allocation" element={<ProtectedRoute><AllocationPage /></ProtectedRoute>} />
  </Routes></BrowserRouter>;
}

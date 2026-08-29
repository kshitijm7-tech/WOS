import { Routes, Route } from "react-router-dom";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import AdminLogin from "./pages/AdminLogin";
import Register from "./pages/Register";
import ComingSoon from "./pages/ComingSoon";
import ProtectedRoute from "./components/ProtectedRoute";
import CustomerDashboard from "./pages/CustomerDashboard";
import CustomerProducts from "./pages/CustomerProducts";
import CustomerClaims from "./pages/CustomerClaims";
import CustomerClaimDetail from "./pages/CustomerClaimDetail";
import NewClaim from "./pages/NewClaim";
import AdminDashboard from "./pages/AdminDashboard";
import AdminClaims from "./pages/AdminClaims";
import AdminClaimDetail from "./pages/AdminClaimDetail";
import AdminAIIntelligence from "./pages/AdminAIIntelligence";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route path="/login" element={<Login />} />
      <Route path="/admin/login" element={<AdminLogin />} />
      <Route path="/register" element={<Register />} />

      {/* Customer — real in Part 1.3 */}
      <Route
        path="/customer/dashboard"
        element={
          <ProtectedRoute role="customer">
            <CustomerDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/customer/products"
        element={
          <ProtectedRoute role="customer">
            <CustomerProducts />
          </ProtectedRoute>
        }
      />
      <Route
        path="/customer/claims"
        element={
          <ProtectedRoute role="customer">
            <CustomerClaims />
          </ProtectedRoute>
        }
      />
      <Route
        path="/customer/claims/new"
        element={
          <ProtectedRoute role="customer">
            <NewClaim />
          </ProtectedRoute>
        }
      />
      <Route
        path="/customer/claims/:id"
        element={
          <ProtectedRoute role="customer">
            <CustomerClaimDetail />
          </ProtectedRoute>
        }
      />
      <Route
        path="/customer/notifications"
        element={
          <ProtectedRoute role="customer">
            <ComingSoon title="Notifications" phase="Part 2" />
          </ProtectedRoute>
        }
      />

      {/* Admin — real in Part 1.3 */}
      <Route
        path="/admin/dashboard"
        element={
          <ProtectedRoute role="admin">
            <AdminDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/claims"
        element={
          <ProtectedRoute role="admin">
            <AdminClaims />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/claims/:id"
        element={
          <ProtectedRoute role="admin">
            <AdminClaimDetail />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/ai-intelligence"
        element={
          <ProtectedRoute role="admin">
            <AdminAIIntelligence />
          </ProtectedRoute>
        }
      />

      <Route
        path="/admin/reviews"
        element={
          <ProtectedRoute role="admin">
            <ComingSoon title="Human Review Queue" phase="Phase 8" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/products"
        element={
          <ProtectedRoute role="admin">
            <ComingSoon title="Products" phase="Phase 5" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/inventory"
        element={
          <ProtectedRoute role="admin">
            <ComingSoon title="Inventory" phase="Phase 9" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/policies"
        element={
          <ProtectedRoute role="admin">
            <ComingSoon title="Warranty Policies" phase="Phase 5" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/fault-intelligence"
        element={
          <ProtectedRoute role="admin">
            <ComingSoon title="Fault Intelligence" phase="Phase 10" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/analytics"
        element={
          <ProtectedRoute role="admin">
            <ComingSoon title="Analytics" phase="Phase 10" />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/settings"
        element={
          <ProtectedRoute role="admin">
            <ComingSoon title="Settings" phase="Phase 12" />
          </ProtectedRoute>
        }
      />

      <Route path="*" element={<ComingSoon title="Page not found" phase="404" />} />
    </Routes>
  );
}

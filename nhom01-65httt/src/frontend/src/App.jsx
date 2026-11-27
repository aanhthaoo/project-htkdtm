import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext.jsx";
import ProtectedRoute from "./auth/ProtectedRoute.jsx";
import Layout from "./components/Layout.jsx";
import NotFound from "./pages/NotFound.jsx";
import { ROUTES } from "./routes.jsx";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route element={<Layout />}>
            {ROUTES.map((r) => (
              <Route
                key={r.path}
                path={r.path}
                element={
                  r.minRole === "guest" ? r.element : <ProtectedRoute minRole={r.minRole}>{r.element}</ProtectedRoute>
                }
              />
            ))}
            <Route path="*" element={<NotFound />} />
          </Route>
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

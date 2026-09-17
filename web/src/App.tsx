import { useEffect, useState, type ReactElement } from "react";
import { Navigate, Route, Routes } from "react-router-dom";
import { api } from "./api";
import MailApp from "./pages/Mail";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Settings from "./pages/Settings";
import type { User } from "./types";

function Gate({ children }: { children: (user: User) => ReactElement }) {
  const [user, setUser] = useState<User | null | undefined>(undefined);
  useEffect(() => {
    api
      .me()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);
  if (user === undefined) return <div className="auth">Загрузка…</div>;
  if (!user) return <Navigate to="/login" replace />;
  return children(user);
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/settings" element={<Gate>{() => <Settings />}</Gate>} />
      <Route path="/" element={<Gate>{(user) => <MailApp user={user} />}</Gate>} />
    </Routes>
  );
}

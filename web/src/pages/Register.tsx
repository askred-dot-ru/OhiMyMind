import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { BrandLockup } from "../Logo";

export default function Register() {
  const nav = useNavigate();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.register(login, password);
      nav("/login");
    } catch (err) {
      setError(err instanceof Error ? err.message : "ошибка регистрации");
    }
  }

  return (
    <div className="auth">
      <form className="card" onSubmit={onSubmit}>
        <BrandLockup />
        <h1>Регистрация</h1>
        <p className="muted">После регистрации войдите отдельно — сессия не создаётся автоматически.</p>
        <input placeholder="Логин" value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" />
        <input
          placeholder="Пароль (от 8 символов)"
          type="password"
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="new-password"
        />
        {error ? <div className="error">{error}</div> : null}
        <button className="primary" type="submit">
          Создать
        </button>
        <div className="muted">
          Уже есть аккаунт? <Link to="/login">Вход</Link>
        </div>
      </form>
    </div>
  );
}

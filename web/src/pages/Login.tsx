import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";
import { BrandLockup } from "../Logo";
import { ThemeToggle } from "../ThemeToggle";

export default function Login() {
  const nav = useNavigate();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.login(login, password);
      nav("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "ошибка входа");
    }
  }

  return (
    <div className="auth">
      <form className="card" onSubmit={onSubmit}>
        <div className="auth-brand">
          <BrandLockup large />
          <ThemeToggle />
        </div>
        <p className="muted">Хаотичные потоки — в извлекаемую базу знаний. Почта сейчас поток №1.</p>
        <input placeholder="Логин" value={login} onChange={(e) => setLogin(e.target.value)} autoComplete="username" />
        <input
          placeholder="Пароль"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
        {error ? <div className="error">{error}</div> : null}
        <button className="primary" type="submit">
          Войти
        </button>
        <div className="muted">
          Нет аккаунта? <Link to="/register">Регистрация</Link>
        </div>
      </form>
    </div>
  );
}

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { login } from "../auth";

export function AdminLoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const mutation = useMutation({ mutationFn: () => login(username, password), onSuccess: () => navigate("/admin") });
  return (
    <main className="page narrow">
      <Link to="/">← Vatandaş ekranı</Link>
      <header className="hero compact"><h1>Yetkili girişi</h1><p>Yalnızca yetkilendirilmiş demo yöneticileri içindir.</p></header>
      <form className="panel form-grid" onSubmit={e => { e.preventDefault(); mutation.mutate(); }}>
        <label>E-posta<input type="email" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required /></label>
        <label>Şifre<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
        {mutation.error && <p className="error-box">{mutation.error.message}</p>}
        <button className="button" disabled={mutation.isPending}>{mutation.isPending ? "Giriş yapılıyor…" : "Giriş yap"}</button>
      </form>
    </main>
  );
}

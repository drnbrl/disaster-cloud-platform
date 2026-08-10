import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { confirmNewPassword, isAuthenticated, isLocalAuthMode, login } from "../auth";

const NEW_PASSWORD_MIN_LENGTH = 8;

export function AdminLoginPage() {
  const navigate = useNavigate();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [newPasswordRequired, setNewPasswordRequired] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    if (isLocalAuthMode) return;
    let ignore = false;
    void isAuthenticated().then(authenticated => {
      if (!ignore && authenticated) navigate("/admin", { replace: true });
    });
    return () => { ignore = true; };
  }, [navigate]);

  const loginMutation = useMutation({
    mutationFn: async (credentials: { username: string; password: string }) => {
      if (!isLocalAuthMode && await isAuthenticated()) return { status: "signedIn" as const };
      return login(credentials.username, credentials.password);
    },
    onSuccess: result => {
      setFormError(null);
      if (result.status === "signedIn") {
        navigate("/admin");
        return;
      }
      setNewPasswordRequired(true);
      setNewPassword("");
      setConfirmPassword("");
    }
  });

  const newPasswordMutation = useMutation({
    mutationFn: (challengeResponse: string) => confirmNewPassword(challengeResponse),
    onSuccess: result => {
      setFormError(null);
      if (result.status === "signedIn") {
        navigate("/admin");
        return;
      }
      setFormError(`Giriş tamamlanamadı. Sonraki oturum açma adımı: ${result.signInStep}`);
    }
  });

  function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    loginMutation.mutate({ username, password });
  }

  function submitNewPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const validationError = validateNewPassword(newPassword, confirmPassword);
    if (validationError) {
      setFormError(validationError);
      return;
    }
    setFormError(null);
    newPasswordMutation.mutate(newPassword);
  }

  const errorMessage = formError ?? (newPasswordRequired ? newPasswordMutation.error?.message : loginMutation.error?.message);

  return (
    <main className="page narrow">
      <Link to="/">← Vatandaş ekranı</Link>
      <header className="hero compact"><h1>Yetkili girişi</h1><p>Yalnızca yetkilendirilmiş demo yöneticileri içindir.</p></header>
      {newPasswordRequired ? (
        <form className="panel form-grid" onSubmit={submitNewPassword} noValidate>
          <label>
            New password
            <input
              type="password"
              autoComplete="new-password"
              minLength={NEW_PASSWORD_MIN_LENGTH}
              value={newPassword}
              onChange={e => setNewPassword(e.target.value)}
              required
            />
          </label>
          <label>
            Confirm new password
            <input
              type="password"
              autoComplete="new-password"
              minLength={NEW_PASSWORD_MIN_LENGTH}
              value={confirmPassword}
              onChange={e => setConfirmPassword(e.target.value)}
              required
            />
          </label>
          {errorMessage && <p className="error-box">{errorMessage}</p>}
          <button className="button" disabled={newPasswordMutation.isPending}>
            {newPasswordMutation.isPending ? "Şifre güncelleniyor…" : "Şifreyi güncelle"}
          </button>
        </form>
      ) : (
        <form className="panel form-grid" onSubmit={submitLogin}>
          <label>E-posta<input type="email" autoComplete="username" value={username} onChange={e => setUsername(e.target.value)} required /></label>
          <label>Şifre<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required /></label>
          {errorMessage && <p className="error-box">{errorMessage}</p>}
          <button className="button" disabled={loginMutation.isPending}>{loginMutation.isPending ? "Giriş yapılıyor…" : "Giriş yap"}</button>
        </form>
      )}
    </main>
  );
}

function validateNewPassword(newPassword: string, confirmPassword: string): string | null {
  if (!newPassword.trim()) return "Yeni şifre boş olamaz.";
  if (newPassword.length < NEW_PASSWORD_MIN_LENGTH) return `Yeni şifre en az ${NEW_PASSWORD_MIN_LENGTH} karakter olmalıdır.`;
  if (newPassword !== confirmPassword) return "Yeni şifreler eşleşmiyor.";
  return null;
}

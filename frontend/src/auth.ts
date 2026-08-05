export const isLocalAuthMode = import.meta.env.VITE_AUTH_MODE === "local";

const BASE_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8001").replace(/\/$/, "");
const localSessionStorageKey = "disaster-platform-local-admin-token";
let amplifyConfigured = false;

interface LocalLoginResponse {
  accessToken: string;
}

async function configureAmplify(): Promise<void> {
  if (amplifyConfigured) return;
  const { Amplify } = await import("aws-amplify");
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId: import.meta.env.VITE_COGNITO_USER_POOL_ID,
        userPoolClientId: import.meta.env.VITE_COGNITO_USER_POOL_CLIENT_ID,
        loginWith: { email: true }
      }
    }
  });
  amplifyConfigured = true;
}

export async function login(username: string, password: string): Promise<void> {
  if (isLocalAuthMode) {
    const result = await localAuthRequest<LocalLoginResponse>("/v1/local-auth/login", {
      method: "POST",
      body: JSON.stringify({ email: username, password })
    });
    sessionStorage.setItem(localSessionStorageKey, result.accessToken);
    return;
  }
  await configureAmplify();
  const { signIn } = await import("aws-amplify/auth");
  const result = await signIn({ username, password });
  if (!result.isSignedIn) throw new Error(`Giriş tamamlanamadı: ${result.nextStep.signInStep}`);
}

export async function logout(): Promise<void> {
  if (isLocalAuthMode) {
    sessionStorage.removeItem(localSessionStorageKey);
    return;
  }
  await configureAmplify();
  const { signOut } = await import("aws-amplify/auth");
  await signOut();
}

export async function isAuthenticated(): Promise<boolean> {
  if (isLocalAuthMode) {
    const token = sessionStorage.getItem(localSessionStorageKey);
    if (!token) return false;
    try {
      await localAuthRequest("/v1/local-auth/me", {
        headers: { Authorization: `Bearer ${token}` }
      });
      return true;
    } catch {
      sessionStorage.removeItem(localSessionStorageKey);
      return false;
    }
  }
  try {
    await configureAmplify();
    const { getCurrentUser } = await import("aws-amplify/auth");
    await getCurrentUser();
    return true;
  } catch {
    return false;
  }
}

export async function accessToken(): Promise<string> {
  if (isLocalAuthMode) {
    const token = sessionStorage.getItem(localSessionStorageKey);
    if (!token) throw new Error("Oturum bulunamadı.");
    return token;
  }
  await configureAmplify();
  const { fetchAuthSession } = await import("aws-amplify/auth");
  const token = (await fetchAuthSession()).tokens?.idToken?.toString();
  if (!token) throw new Error("Oturum bulunamadı.");
  return token;
}

async function localAuthRequest<T = unknown>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const response = await fetch(`${BASE_URL}${path}`, { ...init, headers });
  const body = await response.json().catch(() => ({})) as { detail?: unknown; message?: unknown; error?: unknown };
  if (!response.ok) throw new Error(extractErrorMessage(body));
  return body as T;
}

function extractErrorMessage(body: { detail?: unknown; message?: unknown; error?: unknown }): string {
  for (const value of [body.detail, body.message, body.error]) {
    if (typeof value === "string" && value.trim()) return value;
  }
  return "İşlem tamamlanamadı.";
}

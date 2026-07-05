export const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || "http://127.0.0.1:8000";

async function readJson(res) {
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || data.message || "Request failed");
  return data;
}

export async function apiSignup(fullName, email, password) {
  const res = await fetch(`${API_BASE_URL}/api/auth/signup`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ full_name: fullName, email, password, preferred_reward_type: "cashback" })
  });
  return readJson(res);
}

export async function apiLogin(email, password) {
  const res = await fetch(`${API_BASE_URL}/api/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password })
  });
  return readJson(res);
}

export async function apiMe(token) {
  const res = await fetch(`${API_BASE_URL}/api/me`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return readJson(res);
}

export async function apiMyCards(token) {
  const res = await fetch(`${API_BASE_URL}/api/my-cards`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return readJson(res);
}

import axios from "axios";

const isBrowser = typeof window !== "undefined";
const isLocalDev3000 =
  isBrowser &&
  window.location.port === "3000" &&
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1");

const ENV_BACKEND_URL = (
  process.env.REACT_APP_BACKEND_URL || "https://novel-agree-specialty-regulatory.trycloudflare.com"
).trim().replace(/\/+$/, "");

const BACKEND_URL = isLocalDev3000
  ? "http://localhost:8000"
  : ENV_BACKEND_URL || "https://novel-agree-specialty-regulatory.trycloudflare.com";

export const API_BASE = `${BACKEND_URL}/api`;
export const UPLOADS_BASE = `${BACKEND_URL}`;

export function fileSrc(url, width) {
  if (!url) return "";
  const t = localStorage.getItem("fodoc_token");
  const params = new URLSearchParams();
  if (t) params.set("auth", t);
  if (width) params.set("w", String(width));
  const qs = params.toString();
  const sep = url.includes("?") ? "&" : "?";
  return `${BACKEND_URL}${url}${qs ? `${sep}${qs}` : ""}`;
}

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
});

// Mirror token in header too so cross-domain cookies that get stripped still work.
api.interceptors.request.use((config) => {
  const t = localStorage.getItem("fodoc_token");
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

export function formatApiError(detail) {
  if (detail == null) return "Terjadi kesalahan, coba lagi.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail))
    return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).join(" ");
  if (detail && typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

export default api;

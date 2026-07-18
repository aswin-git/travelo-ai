// Centralized configuration — uses env vars at build time, falls back to local dev defaults
export const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

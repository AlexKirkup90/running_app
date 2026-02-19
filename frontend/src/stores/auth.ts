import { create } from "zustand";
import { login as apiLogin, ApiError } from "@/api/client";

interface AuthState {
  token: string | null;
  role: string | null;
  userId: number | null;
  athleteId: number | null;
  username: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  hydrate: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  role: null,
  userId: null,
  athleteId: null,
  username: null,
  isAuthenticated: false,
  isLoading: false,
  error: null,

  login: async (username: string, password: string) => {
    set({ isLoading: true, error: null });
    try {
      const res = await apiLogin(username, password);
      localStorage.setItem("token", res.access_token);
      localStorage.setItem("role", res.role);
      localStorage.setItem("userId", String(res.user_id));
      localStorage.setItem("athleteId", String(res.athlete_id ?? ""));
      localStorage.setItem("username", username);
      set({
        token: res.access_token,
        role: res.role,
        userId: res.user_id,
        athleteId: res.athlete_id,
        username,
        isAuthenticated: true,
        isLoading: false,
      });
    } catch (err) {
      const message =
        err instanceof ApiError ? err.detail : "Login failed";
      set({ isLoading: false, error: message });
      throw err;
    }
  },

  logout: () => {
    localStorage.removeItem("token");
    localStorage.removeItem("role");
    localStorage.removeItem("userId");
    localStorage.removeItem("athleteId");
    localStorage.removeItem("username");
    set({
      token: null,
      role: null,
      userId: null,
      athleteId: null,
      username: null,
      isAuthenticated: false,
      error: null,
    });
  },

  hydrate: () => {
    const token = localStorage.getItem("token");
    if (token) {
      set({
        token,
        role: localStorage.getItem("role"),
        userId: Number(localStorage.getItem("userId")),
        athleteId: localStorage.getItem("athleteId")
          ? Number(localStorage.getItem("athleteId"))
          : null,
        username: localStorage.getItem("username"),
        isAuthenticated: true,
      });
    }
  },
}));

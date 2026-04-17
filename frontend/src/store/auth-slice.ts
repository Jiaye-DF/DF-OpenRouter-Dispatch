import { createSlice, type PayloadAction } from "@reduxjs/toolkit";
import type { Actor } from "@/types/api";

interface AuthState {
  actor: Actor | null;
  status: "idle" | "loading" | "authenticated" | "unauthenticated";
}

const initialState: AuthState = {
  actor: null,
  status: "idle",
};

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    setActor(state, action: PayloadAction<Actor | null>) {
      state.actor = action.payload;
      state.status = action.payload ? "authenticated" : "unauthenticated";
    },
    setAuthLoading(state) {
      state.status = "loading";
    },
    clearAuth(state) {
      state.actor = null;
      state.status = "unauthenticated";
    },
  },
});

export const { setActor, setAuthLoading, clearAuth } = authSlice.actions;
export default authSlice.reducer;

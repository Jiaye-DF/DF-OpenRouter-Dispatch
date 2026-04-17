import { createSlice, type PayloadAction } from "@reduxjs/toolkit";

// 主題型別：light / dark 為官方深淺；其餘三種為自訂色系
export type ThemeName = "light" | "dark" | "cool" | "warm" | "purple";

interface ThemeState {
  theme: ThemeName;
  sidebarState: "expanded" | "collapsed" | "hidden";
}

const initialState: ThemeState = {
  theme: "light",
  sidebarState: "expanded",
};

const themeSlice = createSlice({
  name: "theme",
  initialState,
  reducers: {
    setTheme(state, action: PayloadAction<ThemeName>) {
      state.theme = action.payload;
    },
    setSidebarState(
      state,
      action: PayloadAction<"expanded" | "collapsed" | "hidden">
    ) {
      state.sidebarState = action.payload;
    },
    cycleSidebarState(state) {
      state.sidebarState =
        state.sidebarState === "expanded"
          ? "collapsed"
          : state.sidebarState === "collapsed"
            ? "hidden"
            : "expanded";
    },
  },
});

export const { setTheme, setSidebarState, cycleSidebarState } =
  themeSlice.actions;
export default themeSlice.reducer;

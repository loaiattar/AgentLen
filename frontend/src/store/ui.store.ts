import { create } from 'zustand'
import { devtools, persist } from 'zustand/middleware'

interface UiState {
  isSidebarOpen: boolean
  toggleSidebar: () => void
  setSidebarOpen: (open: boolean) => void
}

export const useUiStore = create<UiState>()(
  devtools(
    persist(
      (set) => ({
        isSidebarOpen: true,
        toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
        setSidebarOpen: (open) => set({ isSidebarOpen: open }),
      }),
      { name: 'ui-store', version: 1 },
    ),
    { name: 'UiStore', enabled: import.meta.env.DEV },
  ),
)

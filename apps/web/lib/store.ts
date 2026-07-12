import { create } from "zustand";

export interface Project {
  id: string;
  title: string;
  premise: string;
  target_runtime_seconds: number;
  genre?: string;
  style?: string;
  created_at: string;
  updated_at: string;
  status: "draft" | "processing" | "completed" | "failed";
}

export interface Branch {
  id: string;
  project_id: string;
  parent_id?: string;
  decision_text: string;
  branch_option: string;
  depth_level: number;
  created_at: string;
}

interface AppStore {
  currentProject: Project | null;
  projects: Project[];
  branches: Branch[];
  loading: boolean;
  error: string | null;

  setCurrentProject: (project: Project | null) => void;
  setProjects: (projects: Project[]) => void;
  setBranches: (branches: Branch[]) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  addProject: (project: Project) => void;
}

export const useAppStore = create<AppStore>((set) => ({
  currentProject: null,
  projects: [],
  branches: [],
  loading: false,
  error: null,

  setCurrentProject: (project) => set({ currentProject: project }),
  setProjects: (projects) => set({ projects }),
  setBranches: (branches) => set({ branches }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  addProject: (project) =>
    set((state) => ({ projects: [...state.projects, project] })),
}));

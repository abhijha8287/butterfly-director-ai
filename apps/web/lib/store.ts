import { create } from "zustand";

export interface Project {
  id: string;
  title: string;
  premise: string;
  genre?: string | null;
  tone?: string | null;
  status: "draft" | "generating" | "ready" | "archived";
  settings: Record<string, unknown>;
  owner_id?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Branch {
  id: string;
  timeline_id: string;
  parent_branch_id?: string | null;
  name: string;
  summary?: string | null;
  decision_summary?: Record<string, unknown> | null;
  depth: number;
  status: "pending" | "producing" | "completed" | "failed" | "pruned";
  is_canonical: boolean;
  butterfly_score?: number | null;
  probability?: string | null;
  confidence_score?: string | null;
  stability_explanation?: string | null;
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

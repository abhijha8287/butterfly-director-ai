import axios, { AxiosInstance } from "axios";

// Use relative path so Next.js can rewrite it
const apiBaseUrl = "/api/v1";

const apiClient: AxiosInstance = axios.create({
  baseURL: apiBaseUrl,
  headers: {
    "Content-Type": "application/json",
  },
});

export const api = {
  // Health
  health: () => apiClient.get("/health"),

  // Projects
  listProjects: (skip = 0, limit = 10) =>
    apiClient.get("/projects", { params: { skip, limit } }).then(res => ({
      data: Array.isArray(res.data) ? res.data : (Array.isArray(res.data?.items) ? res.data.items : res.data?.data || [])
    })),
  getProject: (projectId: string) => apiClient.get(`/projects/${projectId}`),
  createProject: (data: {
    title: string;
    premise: string;
    target_runtime_seconds: number;
    genre?: string;
    style?: string;
  }) => apiClient.post("/projects", data),

  // Story Architect Agent
  triggerStoryArchitect: (projectId: string) =>
    apiClient.post(`/projects/${projectId}/agents/story-architect`),

  // Character Architect Agent
  triggerCharacterArchitect: (projectId: string) =>
    apiClient.post(`/projects/${projectId}/agents/character-architect`),

  // Decision Detector Agent
  triggerDecisionDetector: (projectId: string) =>
    apiClient.post(`/projects/${projectId}/agents/decision-detector`),

  // Timeline Generator Agent
  triggerTimelineGenerator: (projectId: string) =>
    apiClient.post(`/projects/${projectId}/agents/timeline-generator`),

  // Get agent status
  getAgentStatus: (projectId: string, agentName: string) =>
    apiClient.get(`/projects/${projectId}/agents/${agentName}/status`),

  // Get jobs for a project
  getProjectJobs: (projectId: string) =>
    apiClient.get(`/projects/${projectId}/jobs`),

  // Timelines
  getTimelines: (projectId: string) =>
    apiClient.get("/timelines", { params: { project_id: projectId } }),
  getTimeline: (timelineId: string) =>
    apiClient.get(`/timelines/${timelineId}`),

  // Timeline branches
  getBranches: (timelineId: string) =>
    apiClient.get("/branches", { params: { timeline_id: timelineId } }),
  getBranch: (branchId: string) =>
    apiClient.get(`/branches/${branchId}`),

  // Storyboard
  getStoryboard: (branchId: string) =>
    apiClient.get(`/storyboard`, { params: { branch_id: branchId } }),

  // Generated media
  getGeneratedMedia: (projectId: string) =>
    apiClient.get(`/projects/${projectId}/media`),
};

export default apiClient;

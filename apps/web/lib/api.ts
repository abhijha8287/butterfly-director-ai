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
  // ProjectCreate on the backend only accepts title/premise/genre/tone/settings
  // (see apps/api/app/schemas/project.py) - target_runtime_seconds and style
  // aren't top-level fields, so they're mapped into settings/tone here instead
  // of being silently dropped by Pydantic.
  createProject: (data: {
    title: string;
    premise: string;
    target_runtime_seconds: number;
    genre?: string;
    style?: string;
  }) =>
    apiClient.post("/projects", {
      title: data.title,
      premise: data.premise,
      genre: data.genre || undefined,
      tone: data.style || undefined,
      settings: { target_runtime_seconds: data.target_runtime_seconds },
    }),

  triggerStoryArchitect: (projectId: string) =>
    apiClient.post(`/projects/${projectId}/agents/story-architect`),
  triggerCharacterArchitect: (projectId: string) =>
    apiClient.post(`/projects/${projectId}/agents/character-architect`),
  triggerDecisionDetector: (projectId: string) =>
    apiClient.post(`/projects/${projectId}/agents/decision-detector`),
  triggerTimelineGenerator: (projectId: string) =>
    apiClient.post(`/projects/${projectId}/agents/timeline-generator`),
  triggerCharacterMemory: (projectId: string) =>
    apiClient.post(`/projects/${projectId}/agents/character-memory`),
  triggerStoryboard: (projectId: string) =>
    apiClient.post(`/projects/${projectId}/agents/storyboard`),
  triggerPromptDirector: (projectId: string) =>
    apiClient.post(`/projects/${projectId}/agents/prompt-director`),
  triggerVideoGeneration: (projectId: string) =>
    apiClient.post(`/projects/${projectId}/agents/video-generation`),
  triggerVoice: (projectId: string) =>
    apiClient.post(`/projects/${projectId}/agents/voice`),
  triggerMusic: (projectId: string) =>
    apiClient.post(`/projects/${projectId}/agents/music`),
  triggerEditor: (projectId: string) =>
    apiClient.post(`/projects/${projectId}/agents/editor`),

  // Get agent status
  getAgentStatus: (projectId: string, agentName: string) =>
    apiClient.get(`/projects/${projectId}/agents/${agentName}/status`),

  // Timelines
  getTimelines: (projectId: string) =>
    apiClient.get("/timelines", { params: { project_id: projectId } }),
  getTimeline: (timelineId: string) =>
    apiClient.get(`/timelines/${timelineId}`),
  getTimelineTree: (timelineId: string) =>
    apiClient.get(`/timelines/${timelineId}/tree`),

  // Timeline branches
  getBranches: (timelineId: string) =>
    apiClient.get("/branches", { params: { timeline_id: timelineId, limit: 100 } }),
  getBranch: (branchId: string) =>
    apiClient.get(`/branches/${branchId}`),

  // Story bible (persisted rows, distinct from the generate-response payload)
  getStories: (projectId: string) =>
    apiClient.get("/stories", { params: { project_id: projectId, limit: 100 } }),

  // Character roster (Character Architect output)
  getCharacterProfiles: (storyId: string) =>
    apiClient.get("/character", { params: { story_id: storyId, limit: 100 } }),

  // Decision points (Decision Detector output)
  getDecisions: (storyId: string) =>
    apiClient.get("/decision", { params: { story_id: storyId, limit: 100 } }),

  // Per-branch character continuity/drift (Character Memory output)
  getCharacterMemory: (branchId: string) =>
    apiClient.get("/character-memory", { params: { branch_id: branchId, limit: 100 } }),

  // Storyboard (version history, most recent first)
  getStoryboard: (branchId: string) =>
    apiClient.get(`/storyboard`, { params: { branch_id: branchId, limit: 100 } }),

  // Prompt history: shot prompts (Prompt Director), voice lines, music cues.
  // A single branch can easily exceed the API's default page size of 20
  // (10 shots + voice lines + music cues all share this list) - request the
  // server's max_page_size (100) explicitly so results don't silently
  // truncate and hide agent output from the Results view.
  getPromptHistory: (branchId: string) =>
    apiClient.get("/prompt-history", { params: { branch_id: branchId, limit: 100 } }),

  // Rendered assets: video/voice/music/final-cut, project-wide
  getAssets: (projectId: string) =>
    apiClient.get("/assets", { params: { project_id: projectId, limit: 100 } }),

  // Final movie for a branch (status + final_asset_id once Editor completes)
  getMovieByBranch: (branchId: string) =>
    apiClient.get(`/movies/by-branch/${branchId}`),
};

export default apiClient;

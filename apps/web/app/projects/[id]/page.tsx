"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { AgentStatus } from "@/components/AgentStatus";
import { TimelineVisualizer } from "@/components/TimelineVisualizer";
import { ArrowLeft, Sparkles, Loader } from "lucide-react";

const AGENTS = [
  { id: "story-architect", name: "Story Architect" },
  { id: "character-architect", name: "Character Architect" },
  { id: "decision-detector", name: "Decision Detector" },
  { id: "timeline-generator", name: "Timeline Generator" },
  { id: "character-memory", name: "Character Memory" },
  { id: "storyboard", name: "Storyboard" },
  { id: "prompt-director", name: "Prompt Director" },
  { id: "video-generation", name: "Video Generation" },
  { id: "voice", name: "Voice" },
  { id: "music", name: "Music" },
  { id: "editor", name: "Editor" },
];

export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.id as string;

  const { currentProject, setCurrentProject, setBranches, branches } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [agentStatuses, setAgentStatuses] = useState<
    { [key: string]: "pending" | "running" | "completed" | "failed" }
  >({});
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("overview");

  useEffect(() => {
    const fetchProject = async () => {
      try {
        setLoading(true);
        const response = await api.getProject(projectId);
        setCurrentProject(response.data);

        // Initialize agent statuses
        const statuses: { [key: string]: "pending" | "running" | "completed" | "failed" } = {};
        AGENTS.forEach((agent) => {
          statuses[agent.id] = "pending";
        });
        setAgentStatuses(statuses);

        // Fetch timelines for this project
        const timelinesResponse = await api.getTimelines(projectId);
        const timelines = Array.isArray(timelinesResponse.data) 
          ? timelinesResponse.data 
          : (timelinesResponse.data?.items || []);
        
        // Fetch branches for the first timeline
        if (timelines.length > 0) {
          const branchesResponse = await api.getBranches(timelines[0].id);
          const branches = Array.isArray(branchesResponse.data)
            ? branchesResponse.data
            : (branchesResponse.data?.items || []);
          setBranches(branches);
        }
      } catch (err) {
        setError("Failed to load project details.");
        console.error(err);
      } finally {
        setLoading(false);
      }
    };

    fetchProject();
  }, [projectId, setCurrentProject, setBranches]);

  const handleTriggerAgent = async (agentId: string) => {
    try {
      setAgentStatuses((prev) => ({ ...prev, [agentId]: "running" }));

      const triggerMap: { [key: string]: () => Promise<any> } = {
        "story-architect": () => api.triggerStoryArchitect(projectId),
        "character-architect": () => api.triggerCharacterArchitect(projectId),
        "decision-detector": () => api.triggerDecisionDetector(projectId),
        "timeline-generator": () => api.triggerTimelineGenerator(projectId),
      };

      if (triggerMap[agentId]) {
        await triggerMap[agentId]();
        setAgentStatuses((prev) => ({ ...prev, [agentId]: "completed" }));
      }
    } catch (err) {
      setAgentStatuses((prev) => ({ ...prev, [agentId]: "failed" }));
      console.error(err);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <Loader className="h-8 w-8 animate-spin text-blue-600" />
      </div>
    );
  }

  if (!currentProject) {
    return (
      <div className="space-y-6 p-4 md:p-6">
        <Link
          href="/projects"
          className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Projects
        </Link>
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-red-700">
          Project not found.
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6 p-4 md:p-6">
      {/* Header */}
      <Link
        href="/projects"
        className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Projects
      </Link>

      <div className="rounded-lg bg-white border border-gray-200 p-6">
        <div className="flex items-start justify-between mb-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{currentProject.title}</h1>
            <p className="text-gray-600 mt-2">{currentProject.premise}</p>
          </div>
          <span className="px-4 py-2 rounded-full text-sm font-semibold bg-blue-100 text-blue-800">
            {currentProject.status}
          </span>
        </div>

        <div className="flex flex-wrap gap-4 text-sm text-gray-600">
          {currentProject.genre && <span>📌 {currentProject.genre}</span>}
          <span>⏱️ {currentProject.target_runtime_seconds}s</span>
          <span>📅 {new Date(currentProject.created_at).toLocaleDateString()}</span>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg bg-red-50 border border-red-200 p-4 text-red-700">
          {error}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-4 border-b border-gray-200">
        <button
          onClick={() => setActiveTab("overview")}
          className={`px-4 py-2 font-medium border-b-2 transition-colors ${
            activeTab === "overview"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-600 hover:text-gray-900"
          }`}
        >
          Agents & Generation
        </button>
        <button
          onClick={() => setActiveTab("timeline")}
          className={`px-4 py-2 font-medium border-b-2 transition-colors ${
            activeTab === "timeline"
              ? "border-blue-600 text-blue-600"
              : "border-transparent text-gray-600 hover:text-gray-900"
          }`}
        >
          Story Timeline
        </button>
      </div>

      {/* Agent Panel */}
      {activeTab === "overview" && (
        <div className="space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-sm text-blue-800">
              💡 Trigger agents in order to generate your story. Start with Story Architect, then Character Architect,
              Decision Detector, and Timeline Generator to create the branching narrative.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {AGENTS.map((agent) => (
              <div key={agent.id} className="bg-white border border-gray-200 rounded-lg p-4">
                <div className="flex items-start justify-between mb-3">
                  <h3 className="font-semibold text-gray-900">{agent.name}</h3>
                  <span
                    className={`text-xs px-2 py-1 rounded-full font-medium ${
                      agentStatuses[agent.id] === "completed"
                        ? "bg-green-100 text-green-800"
                        : agentStatuses[agent.id] === "running"
                        ? "bg-blue-100 text-blue-800"
                        : agentStatuses[agent.id] === "failed"
                        ? "bg-red-100 text-red-800"
                        : "bg-gray-100 text-gray-800"
                    }`}
                  >
                    {agentStatuses[agent.id]}
                  </span>
                </div>

                {["story-architect", "character-architect", "decision-detector", "timeline-generator"].includes(
                  agent.id
                ) && (
                  <button
                    onClick={() => handleTriggerAgent(agent.id)}
                    disabled={agentStatuses[agent.id] === "running"}
                    className="w-full mt-3 flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-blue-400 transition-colors"
                  >
                    {agentStatuses[agent.id] === "running" && (
                      <Loader className="h-3 w-3 animate-spin" />
                    )}
                    {agentStatuses[agent.id] === "running" ? "Running..." : "Trigger"}
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Timeline Tab */}
      {activeTab === "timeline" && (
        <div className="space-y-4">
          {branches.length === 0 ? (
            <div className="text-center rounded-lg border border-gray-200 bg-white p-8">
              <p className="text-gray-600">
                No timeline branches yet. Run the Timeline Generator agent to create story branches.
              </p>
            </div>
          ) : (
            <TimelineVisualizer branches={branches} />
          )}
        </div>
      )}
    </div>
  );
}

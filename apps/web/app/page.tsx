"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useAppStore, Project } from "@/lib/store";
import { api } from "@/lib/api";
import { ProjectCard } from "@/components/ProjectCard";
import { Sparkles, Film, Zap } from "lucide-react";

export default function Home() {
  const { projects, setProjects, setLoading, loading } = useAppStore();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchProjects = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await api.listProjects();
        setProjects(response.data || []);
      } catch (err: any) {
        const errorMessage = err?.message || "Failed to load projects";
        setError(errorMessage);
        console.error("Error fetching projects:", err);
        // Don't show projects loading state if API fails
        setProjects([]);
      } finally {
        setLoading(false);
      }
    };

    fetchProjects();
  }, [setProjects, setLoading]);

  return (
    <div className="space-y-8 p-4 md:p-6">
      {/* Hero Section */}
      <div className="rounded-lg bg-gradient-to-r from-blue-600 to-purple-600 p-8 text-white md:p-12">
        <div className="max-w-2xl">
          <div className="flex items-center gap-3 mb-4">
            <Film className="h-8 w-8" />
            <h1 className="text-4xl md:text-5xl font-bold">
              Butterfly Director AI
            </h1>
          </div>
          <p className="text-lg text-blue-100 mb-6">
            Turn a single story premise into a branching multiverse of fully generated short films.
          </p>
          <Link
            href="/create"
            className="inline-flex items-center gap-2 rounded-lg bg-white px-6 py-3 font-semibold text-blue-600 hover:bg-blue-50 transition-colors"
          >
            <Sparkles className="h-5 w-5" />
            Create Your First Story
          </Link>
        </div>
      </div>

      {/* Features */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <Sparkles className="h-8 w-8 text-blue-600 mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">AI-Powered Story</h3>
          <p className="text-sm text-gray-600">
            Our agents architect stories, characters, and decision points automatically.
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <Zap className="h-8 w-8 text-purple-600 mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Branching Timelines</h3>
          <p className="text-sm text-gray-600">
            Explore multiple story paths with automatic timeline generation.
          </p>
        </div>
        <div className="rounded-lg border border-gray-200 bg-white p-6">
          <Film className="h-8 w-8 text-green-600 mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">Full Production</h3>
          <p className="text-sm text-gray-600">
            Video, voiceover, music, and editing—all generated and composed.
          </p>
        </div>
      </div>

      {/* Projects Section */}
      <div>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl font-bold text-gray-900">
            Your Projects
          </h2>
          {Array.isArray(projects) && projects.length > 0 && (
            <Link
              href="/create"
              className="text-blue-600 hover:text-blue-700 font-medium text-sm"
            >
              Create New →
            </Link>
          )}
        </div>

        {error && (
          <div className="rounded-lg bg-blue-50 border border-blue-200 p-4 text-blue-700 mb-6">
            <p className="font-medium">Note:</p>
            <p className="text-sm">{error}</p>
            <p className="text-xs mt-2 text-blue-600">Make sure the backend API is running on http://localhost:8000</p>
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => (
              <div
                key={i}
                className="rounded-lg border border-gray-200 bg-white p-6 animate-pulse"
              >
                <div className="h-6 bg-gray-200 rounded mb-3 w-3/4"></div>
                <div className="h-4 bg-gray-200 rounded mb-4 w-full"></div>
                <div className="h-4 bg-gray-200 rounded w-1/2"></div>
              </div>
            ))}
          </div>
        ) : !Array.isArray(projects) || projects.length === 0 ? (
          <div className="text-center rounded-lg border border-gray-200 bg-white p-12">
            <Film className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-900 mb-2">
              No projects yet
            </h3>
            <p className="text-gray-600 mb-6">
              Create your first story premise to get started.
            </p>
            <Link
              href="/create"
              className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-6 py-2 font-medium text-white hover:bg-blue-700 transition-colors"
            >
              <Sparkles className="h-4 w-4" />
              Create Story
            </Link>
          </div>
        ) : Array.isArray(projects) && projects.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {projects.map((project: Project) => (
              <ProjectCard key={project.id} project={project} />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

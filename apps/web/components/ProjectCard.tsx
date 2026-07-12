"use client";

import Link from "next/link";
import { Project } from "@/lib/store";
import { Clock, Tag, Zap } from "lucide-react";

interface ProjectCardProps {
  project: any;
}

export function ProjectCard({ project }: ProjectCardProps) {
  const statusColors: { [key: string]: string } = {
    draft: "bg-gray-100 text-gray-800",
    processing: "bg-blue-100 text-blue-800",
    completed: "bg-green-100 text-green-800",
    failed: "bg-red-100 text-red-800",
  };

  const status = project.status || "draft";

  return (
    <Link href={`/projects/${project.id}`}>
      <div className="overflow-hidden rounded-lg border border-gray-200 bg-white p-6 hover:shadow-lg transition-shadow cursor-pointer">
        <div className="flex items-start justify-between mb-3">
          <h3 className="text-lg font-semibold text-gray-900 flex-1">{project.title}</h3>
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${
              statusColors[status] || statusColors.draft
            }`}
          >
            {status}
          </span>
        </div>

        <p className="text-sm text-gray-600 mb-4 line-clamp-2">
          {project.premise}
        </p>

        <div className="flex flex-wrap gap-2 text-xs text-gray-500 mb-3">
          {project.genre && (
            <span className="flex items-center gap-1">
              <Tag className="h-3 w-3" />
              {project.genre}
            </span>
          )}
        </div>

        <div className="text-xs text-gray-400">
          Created {new Date(project.created_at).toLocaleDateString()}
        </div>
      </div>
    </Link>
  );
}

"use client";

import { CheckCircle, Clock, AlertCircle, Loader } from "lucide-react";

interface AgentStatusProps {
  name: string;
  status: "pending" | "running" | "completed" | "failed";
  progress?: number;
}

export function AgentStatus({ name, status, progress = 0 }: AgentStatusProps) {
  const statusConfig = {
    pending: { icon: Clock, color: "text-gray-400", bg: "bg-gray-100" },
    running: { icon: Loader, color: "text-blue-600", bg: "bg-blue-100" },
    completed: { icon: CheckCircle, color: "text-green-600", bg: "bg-green-100" },
    failed: { icon: AlertCircle, color: "text-red-600", bg: "bg-red-100" },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-semibold text-gray-900">{name}</h4>
        <div className={`p-2 rounded-full ${config.bg}`}>
          <Icon
            className={`h-4 w-4 ${config.color} ${
              status === "running" ? "animate-spin" : ""
            }`}
          />
        </div>
      </div>

      <p className="text-xs text-gray-600 mb-2 capitalize">{status}</p>

      {status === "running" && progress > 0 && (
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-blue-600 h-2 rounded-full transition-all"
            style={{ width: `${progress}%` }}
          ></div>
        </div>
      )}
    </div>
  );
}

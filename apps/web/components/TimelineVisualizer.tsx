"use client";

import { Branch } from "@/lib/store";
import { GitBranch } from "lucide-react";

interface TimelineVisualizerProps {
  branches: Branch[];
}

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-gray-100 text-gray-700",
  producing: "bg-blue-100 text-blue-700",
  completed: "bg-green-100 text-green-700",
  failed: "bg-red-100 text-red-700",
  pruned: "bg-gray-100 text-gray-400",
};

export function TimelineVisualizer({ branches }: TimelineVisualizerProps) {
  // Group branches by depth (root = 0, each fork increases depth by 1)
  const branchesByLevel: { [key: number]: Branch[] } = {};
  branches.forEach((branch) => {
    if (!branchesByLevel[branch.depth]) {
      branchesByLevel[branch.depth] = [];
    }
    branchesByLevel[branch.depth].push(branch);
  });

  const levels = Object.keys(branchesByLevel)
    .map(Number)
    .sort((a, b) => a - b);

  if (levels.length === 0) {
    return (
      <div className="flex items-center justify-center rounded-lg border border-gray-200 p-8 text-gray-500">
        <p>No branches generated yet. Run the Timeline Generator agent to create branches.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200 p-6 bg-white">
      <div className="flex gap-8">
        {levels.map((level) => (
          <div key={level} className="flex flex-col gap-4 min-w-max">
            <h3 className="font-semibold text-gray-700">Depth {level}</h3>
            {branchesByLevel[level].map((branch) => (
              <div
                key={branch.id}
                className="rounded-lg border border-blue-200 bg-blue-50 p-4 w-80"
              >
                <div className="flex items-start gap-2 mb-2">
                  <GitBranch className="h-4 w-4 text-blue-600 flex-shrink-0 mt-1" />
                  <div className="flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-gray-900">
                        {branch.name}
                        {branch.is_canonical && (
                          <span className="ml-2 text-[10px] uppercase tracking-wide text-blue-600">
                            canonical
                          </span>
                        )}
                      </p>
                      <span
                        className={`shrink-0 text-[10px] px-2 py-0.5 rounded-full font-medium ${
                          STATUS_STYLES[branch.status] ?? "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {branch.status}
                      </span>
                    </div>
                    {branch.summary && (
                      <p className="text-xs text-gray-600 mt-1">{branch.summary}</p>
                    )}
                    {branch.butterfly_score !== null && branch.butterfly_score !== undefined && (
                      <p className="text-[11px] text-gray-500 mt-2">
                        🦋 Butterfly score: {branch.butterfly_score}
                        {branch.probability && ` · P=${branch.probability}`}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

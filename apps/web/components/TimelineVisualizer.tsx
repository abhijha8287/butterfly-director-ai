"use client";

import { Branch } from "@/lib/store";
import { GitBranch } from "lucide-react";

interface TimelineVisualizerProps {
  branches: Branch[];
}

export function TimelineVisualizer({ branches }: TimelineVisualizerProps) {
  // Group branches by depth level
  const branchesByLevel: { [key: number]: Branch[] } = {};
  branches.forEach((branch) => {
    if (!branchesByLevel[branch.depth_level]) {
      branchesByLevel[branch.depth_level] = [];
    }
    branchesByLevel[branch.depth_level].push(branch);
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
            <h3 className="font-semibold text-gray-700">Decision {level}</h3>
            {branchesByLevel[level].map((branch) => (
              <div
                key={branch.id}
                className="rounded-lg border border-blue-200 bg-blue-50 p-4 w-80"
              >
                <div className="flex items-start gap-2 mb-2">
                  <GitBranch className="h-4 w-4 text-blue-600 flex-shrink-0 mt-1" />
                  <div className="flex-1">
                    <p className="text-sm font-semibold text-gray-900">
                      {branch.branch_option}
                    </p>
                    <p className="text-xs text-gray-600 mt-1">
                      {branch.decision_text}
                    </p>
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

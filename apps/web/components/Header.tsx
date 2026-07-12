"use client";

import Link from "next/link";
import { Film, Plus } from "lucide-react";

export function Header() {
  return (
    <header className="border-b border-gray-200 bg-white">
      <div className="flex items-center justify-between p-4 md:p-6">
        <Link href="/" className="flex items-center gap-2">
          <Film className="h-8 w-8 text-blue-600" />
          <h1 className="text-2xl font-bold text-gray-900">Butterfly Director AI</h1>
        </Link>
        <nav className="flex items-center gap-4">
          <Link
            href="/projects"
            className="text-sm font-medium text-gray-700 hover:text-gray-900"
          >
            Projects
          </Link>
          <Link
            href="/create"
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
          >
            <Plus className="h-4 w-4" />
            New Story
          </Link>
        </nav>
      </div>
    </header>
  );
}

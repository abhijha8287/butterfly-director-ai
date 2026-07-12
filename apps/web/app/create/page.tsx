"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAppStore } from "@/lib/store";
import { ArrowLeft, Loader } from "lucide-react";
import Link from "next/link";

export default function CreatePage() {
  const router = useRouter();
  const { addProject, setError } = useAppStore();
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    title: "",
    premise: "",
    target_runtime_seconds: 300,
    genre: "",
    style: "",
  });

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: name === "target_runtime_seconds" ? parseInt(value) : value,
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await api.createProject(formData);
      const newProject = response.data;
      addProject(newProject);
      router.push(`/projects/${newProject.id}`);
    } catch (error) {
      setError("Failed to create project. Please try again.");
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const genreOptions = ["Science Fiction", "Fantasy", "Drama", "Comedy", "Thriller", "Horror"];
  const styleOptions = ["Cinematic", "Animated", "Documentary", "Experimental", "Nostalgic"];

  return (
    <div className="space-y-6 p-4 md:p-6 max-w-2xl mx-auto">
      <Link
        href="/"
        className="inline-flex items-center gap-2 text-blue-600 hover:text-blue-700 font-medium"
      >
        <ArrowLeft className="h-4 w-4" />
        Back to Projects
      </Link>

      <div>
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Create a New Story</h1>
        <p className="text-gray-600">
          Define your story premise and let our AI agents generate a branching multiverse.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6 bg-white rounded-lg border border-gray-200 p-6">
        {/* Title */}
        <div>
          <label htmlFor="title" className="block text-sm font-semibold text-gray-900 mb-2">
            Story Title
          </label>
          <input
            type="text"
            id="title"
            name="title"
            value={formData.title}
            onChange={handleChange}
            required
            placeholder="e.g., The Last Light"
            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>

        {/* Premise */}
        <div>
          <label htmlFor="premise" className="block text-sm font-semibold text-gray-900 mb-2">
            Story Premise
          </label>
          <textarea
            id="premise"
            name="premise"
            value={formData.premise}
            onChange={handleChange}
            required
            rows={5}
            placeholder="Describe your story idea. Include the main character, conflict, and setting..."
            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900 placeholder:text-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 font-sans"
          />
        </div>

        {/* Runtime */}
        <div>
          <label htmlFor="target_runtime_seconds" className="block text-sm font-semibold text-gray-900 mb-2">
            Target Runtime (seconds)
          </label>
          <div className="flex items-center gap-4">
            <input
              type="range"
              id="target_runtime_seconds"
              name="target_runtime_seconds"
              min="30"
              max="900"
              step="30"
              value={formData.target_runtime_seconds}
              onChange={handleChange}
              className="flex-1"
            />
            <span className="min-w-fit font-semibold text-gray-900">
              {Math.round(formData.target_runtime_seconds / 60)} min
            </span>
          </div>
          <p className="text-xs text-gray-500 mt-1">
            {formData.target_runtime_seconds} seconds
          </p>
        </div>

        {/* Genre */}
        <div>
          <label htmlFor="genre" className="block text-sm font-semibold text-gray-900 mb-2">
            Genre (Optional)
          </label>
          <select
            id="genre"
            name="genre"
            value={formData.genre}
            onChange={handleChange}
            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select a genre...</option>
            {genreOptions.map((genre) => (
              <option key={genre} value={genre}>
                {genre}
              </option>
            ))}
          </select>
        </div>

        {/* Style */}
        <div>
          <label htmlFor="style" className="block text-sm font-semibold text-gray-900 mb-2">
            Visual Style (Optional)
          </label>
          <select
            id="style"
            name="style"
            value={formData.style}
            onChange={handleChange}
            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-gray-900 focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">Select a style...</option>
            {styleOptions.map((style) => (
              <option key={style} value={style}>
                {style}
              </option>
            ))}
          </select>
        </div>

        {/* Submit Button */}
        <button
          type="submit"
          disabled={loading}
          className="w-full flex items-center justify-center gap-2 rounded-lg bg-blue-600 px-6 py-3 font-semibold text-white hover:bg-blue-700 disabled:bg-blue-400 transition-colors"
        >
          {loading && <Loader className="h-4 w-4 animate-spin" />}
          {loading ? "Creating Story..." : "Create Story"}
        </button>
      </form>
    </div>
  );
}

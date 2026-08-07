"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Branch } from "@/lib/store";
import { Loader, Film, Music2, Mic, Clapperboard, Users, GitFork, BookOpen } from "lucide-react";

interface StoryBible {
  title?: string;
  logline?: string;
  synopsis?: string;
  genre?: string;
  tone?: string;
  themes?: string[];
  setting?: string;
  protagonist_summary?: string;
  antagonist_summary?: string | null;
  visual_style?: string;
}

interface Story {
  id: string;
  world_bible: StoryBible;
  status: string;
}

interface CharacterProfile {
  id: string;
  name: string;
  role: string;
  age_range?: string;
  physical_description?: string;
  personality_traits?: string[];
  backstory?: string;
  motivation?: string;
}

interface BranchCandidate {
  label: string;
  description: string;
  tone_shift: string;
}

interface DecisionPoint {
  id: string;
  beat_index: number;
  description: string;
  branch_candidates: BranchCandidate[];
}

interface Shot {
  scene: string;
  shot_number: number;
  description: string;
  camera: string;
  duration_seconds: number;
  characters_present: string[];
}

interface StoryboardVersion {
  id: string;
  version_number: number;
  shots: Shot[];
}

interface PromptHistoryEntry {
  id: string;
  stage: "story" | "storyboard" | "shot_prompt" | "video" | "voice" | "music";
  rendered_prompt: string;
  input_payload: Record<string, any>;
  response_payload: Record<string, any> | null;
  provider: string;
}

interface Asset {
  id: string;
  kind: "image" | "video" | "audio" | "json";
  owner_type: string;
  owner_id: string;
  oss_key: string;
  duration_seconds: string | null;
}

interface Movie {
  id: string;
  status: string;
  duration_seconds: number | null;
  final_asset_id: string | null;
  extra_metadata: Record<string, any>;
}

interface CharacterState {
  id: string;
  character_name: string;
  state_diff: Record<string, any>;
  drift_severity: string;
  drift_warning: string | null;
}

function extractItems<T>(data: any): T[] {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.items)) return data.items;
  return [];
}

function SectionCard({
  icon,
  title,
  subtitle,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="flex items-center gap-2 mb-3">
        {icon}
        <h3 className="font-semibold text-gray-900">{title}</h3>
        {subtitle && <span className="text-xs text-gray-500">{subtitle}</span>}
      </div>
      {children}
    </div>
  );
}

function Empty({ label }: { label: string }) {
  return <p className="text-sm text-gray-500 italic">{label}</p>;
}

export function ProjectResults({ projectId }: { projectId: string }) {
  const [loading, setLoading] = useState(true);
  const [story, setStory] = useState<Story | null>(null);
  const [characters, setCharacters] = useState<CharacterProfile[]>([]);
  const [decisions, setDecisions] = useState<DecisionPoint[]>([]);
  const [selectedBranch, setSelectedBranch] = useState<Branch | null>(null);
  const [branches, setBranchList] = useState<Branch[]>([]);
  const [characterStates, setCharacterStates] = useState<CharacterState[]>([]);
  const [storyboard, setStoryboard] = useState<StoryboardVersion | null>(null);
  const [promptHistory, setPromptHistory] = useState<PromptHistoryEntry[]>([]);
  const [assets, setAssets] = useState<Asset[]>([]);
  const [movie, setMovie] = useState<Movie | null>(null);

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setLoading(true);
      try {
        const storiesRes = await api.getStories(projectId);
        const stories = extractItems<Story>(storiesRes.data);
        const firstStory = stories[0] ?? null;
        if (cancelled) return;
        setStory(firstStory);

        if (firstStory) {
          const [charRes, decRes] = await Promise.all([
            api.getCharacterProfiles(firstStory.id),
            api.getDecisions(firstStory.id),
          ]);
          if (cancelled) return;
          setCharacters(extractItems<CharacterProfile>(charRes.data));
          setDecisions(extractItems<DecisionPoint>(decRes.data));
        }

        const assetsRes = await api.getAssets(projectId);
        if (!cancelled) setAssets(extractItems<Asset>(assetsRes.data));

        const timelinesRes = await api.getTimelines(projectId);
        const timelines = extractItems<{ id: string }>(timelinesRes.data);
        if (timelines.length === 0) return;

        const branchesRes = await api.getBranches(timelines[0].id);
        const branchList = extractItems<Branch>(branchesRes.data);
        if (cancelled) return;
        setBranchList(branchList);

        // Prefer the deepest non-root branch (most likely to have a full
        // storyboard/render pipeline run against it) over the root.
        const branch =
          [...branchList].sort((a, b) => b.depth - a.depth)[0] ?? null;
        setSelectedBranch(branch);
        if (!branch) return;

        const [memRes, sbRes, phRes] = await Promise.all([
          api.getCharacterMemory(branch.id),
          api.getStoryboard(branch.id),
          api.getPromptHistory(branch.id),
        ]);
        if (cancelled) return;
        setCharacterStates(extractItems<CharacterState>(memRes.data));
        const storyboards = extractItems<StoryboardVersion>(sbRes.data);
        setStoryboard(storyboards[0] ?? null);
        setPromptHistory(extractItems<PromptHistoryEntry>(phRes.data));

        try {
          const movieRes = await api.getMovieByBranch(branch.id);
          if (!cancelled) setMovie(movieRes.data);
        } catch {
          if (!cancelled) setMovie(null);
        }
      } catch (err) {
        console.error("Failed to load results", err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    load();
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center p-12">
        <Loader className="h-6 w-6 animate-spin text-blue-600" />
      </div>
    );
  }

  const bible = story?.world_bible;
  const shotPrompts = promptHistory.filter((p) => p.stage === "shot_prompt");
  const voiceLines = promptHistory.filter((p) => p.stage === "voice");
  const musicCues = promptHistory.filter((p) => p.stage === "music");
  const videoAssets = assets.filter((a) => a.kind === "video" && a.owner_type === "shot");
  const voiceAssets = assets.filter((a) => a.kind === "audio" && a.owner_type === "voice");
  const finalAsset = movie?.final_asset_id
    ? assets.find((a) => a.id === movie.final_asset_id)
    : null;

  return (
    <div className="space-y-4">
      {/* Story Bible */}
      <SectionCard icon={<BookOpen className="h-4 w-4 text-blue-600" />} title="Story Bible">
        {!bible ? (
          <Empty label="Not generated yet. Trigger Story Architect above." />
        ) : (
          <div className="space-y-2">
            <p className="text-lg font-semibold text-gray-900">{bible.title}</p>
            <p className="text-sm text-gray-700 italic">{bible.logline}</p>
            <p className="text-sm text-gray-600">{bible.synopsis}</p>
            <div className="flex flex-wrap gap-2 pt-1 text-xs text-gray-600">
              {bible.genre && <span className="px-2 py-1 rounded-full bg-gray-100">{bible.genre}</span>}
              {bible.tone && <span className="px-2 py-1 rounded-full bg-gray-100">{bible.tone}</span>}
              {bible.setting && <span className="px-2 py-1 rounded-full bg-gray-100">{bible.setting}</span>}
            </div>
            {bible.themes && bible.themes.length > 0 && (
              <p className="text-xs text-gray-500">Themes: {bible.themes.join(", ")}</p>
            )}
          </div>
        )}
      </SectionCard>

      {/* Characters */}
      <SectionCard
        icon={<Users className="h-4 w-4 text-blue-600" />}
        title="Characters"
        subtitle={characters.length ? `${characters.length} generated` : undefined}
      >
        {characters.length === 0 ? (
          <Empty label="Not generated yet. Trigger Character Architect above." />
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {characters.map((c) => (
              <div key={c.id} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                <p className="text-sm font-semibold text-gray-900">
                  {c.name} <span className="text-xs font-normal text-gray-500">({c.role})</span>
                </p>
                {c.physical_description && (
                  <p className="text-xs text-gray-600 mt-1 line-clamp-3">{c.physical_description}</p>
                )}
                {c.personality_traits && c.personality_traits.length > 0 && (
                  <p className="text-xs text-gray-500 mt-1">{c.personality_traits.join(", ")}</p>
                )}
              </div>
            ))}
          </div>
        )}
      </SectionCard>

      {/* Decision Points */}
      <SectionCard
        icon={<GitFork className="h-4 w-4 text-blue-600" />}
        title="Decision Points"
        subtitle={decisions.length ? `${decisions.length} forks found` : undefined}
      >
        {decisions.length === 0 ? (
          <Empty label="Not generated yet, or this story is linear (no forks)." />
        ) : (
          <div className="space-y-3">
            {decisions
              .sort((a, b) => a.beat_index - b.beat_index)
              .map((d) => (
                <div key={d.id} className="rounded-lg border border-gray-100 bg-gray-50 p-3">
                  <p className="text-sm font-medium text-gray-900">
                    Beat {d.beat_index}: {d.description}
                  </p>
                  <div className="flex flex-wrap gap-2 mt-2">
                    {d.branch_candidates.map((bc, i) => (
                      <span
                        key={i}
                        className="text-xs px-2 py-1 rounded-full bg-blue-100 text-blue-800"
                        title={bc.description}
                      >
                        {bc.label}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
          </div>
        )}
      </SectionCard>

      {/* Selected branch deep-dive */}
      {selectedBranch && (
        <>
          <div className="text-sm text-gray-500 px-1">
            Showing generated output for branch{" "}
            <span className="font-semibold text-gray-800">{selectedBranch.name}</span>
            {branches.length > 1 && ` (of ${branches.length} branches)`}
          </div>

          {/* Character Memory / drift */}
          <SectionCard
            icon={<Users className="h-4 w-4 text-purple-600" />}
            title="Character Memory (this branch)"
            subtitle={characterStates.length ? `${characterStates.length} characters resolved` : undefined}
          >
            {characterStates.length === 0 ? (
              <Empty label="Not generated yet for this branch." />
            ) : (
              <div className="space-y-2">
                {characterStates.map((cs) => (
                  <div key={cs.id} className="rounded-lg border border-gray-100 bg-gray-50 p-3 text-sm">
                    <div className="flex items-center justify-between">
                      <span className="font-medium text-gray-900">{cs.character_name}</span>
                      {cs.drift_severity !== "none" && (
                        <span className="text-xs px-2 py-0.5 rounded-full bg-amber-100 text-amber-800">
                          drift: {cs.drift_severity}
                        </span>
                      )}
                    </div>
                    {cs.drift_warning && (
                      <p className="text-xs text-amber-700 mt-1">{cs.drift_warning}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          {/* Storyboard */}
          <SectionCard
            icon={<Clapperboard className="h-4 w-4 text-blue-600" />}
            title="Storyboard"
            subtitle={storyboard ? `v${storyboard.version_number} · ${storyboard.shots.length} shots` : undefined}
          >
            {!storyboard ? (
              <Empty label="Not generated yet. Trigger Storyboard above." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead className="text-gray-500 border-b border-gray-200">
                    <tr>
                      <th className="py-1 pr-3">#</th>
                      <th className="py-1 pr-3">Scene</th>
                      <th className="py-1 pr-3">Description</th>
                      <th className="py-1 pr-3">Camera</th>
                      <th className="py-1 pr-3">Dur.</th>
                    </tr>
                  </thead>
                  <tbody>
                    {storyboard.shots
                      .sort((a, b) => a.shot_number - b.shot_number)
                      .map((s) => (
                        <tr key={s.shot_number} className="border-b border-gray-100 align-top">
                          <td className="py-1.5 pr-3 text-gray-500">{s.shot_number}</td>
                          <td className="py-1.5 pr-3 text-gray-600 whitespace-nowrap">{s.scene}</td>
                          <td className="py-1.5 pr-3 text-gray-800">{s.description}</td>
                          <td className="py-1.5 pr-3 text-gray-500">{s.camera}</td>
                          <td className="py-1.5 pr-3 text-gray-500">{s.duration_seconds}s</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}
          </SectionCard>

          {/* Shot prompts + rendered video */}
          <SectionCard
            icon={<Film className="h-4 w-4 text-blue-600" />}
            title="Prompt Director & Video Generation"
            subtitle={
              shotPrompts.length
                ? `${shotPrompts.length} prompts · ${videoAssets.length} rendered`
                : undefined
            }
          >
            {shotPrompts.length === 0 ? (
              <Empty label="Not generated yet. Trigger Prompt Director, then Video Generation, above." />
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {shotPrompts
                  .sort(
                    (a, b) =>
                      (a.input_payload?.shot?.shot_number ?? 0) -
                      (b.input_payload?.shot?.shot_number ?? 0)
                  )
                  .map((p) => {
                    const shotNum = p.input_payload?.shot?.shot_number;
                    const rendered = Boolean(p.response_payload?.video_url);
                    return (
                      <div key={p.id} className="rounded-lg border border-gray-100 bg-gray-50 p-3 text-xs">
                        <div className="flex items-center justify-between mb-1">
                          <p className="font-medium text-gray-700">Shot {shotNum}</p>
                          {p.response_payload && (
                            <span
                              className={`text-[10px] px-2 py-0.5 rounded-full ${
                                rendered ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700"
                              }`}
                            >
                              {rendered ? "rendered" : "failed"}
                            </span>
                          )}
                        </div>
                        <p className="text-gray-600">{p.rendered_prompt}</p>
                      </div>
                    );
                  })}
                {videoAssets.length > 0 && (
                  <p className="text-xs text-gray-500 pt-1">
                    {videoAssets.length} shot(s) rendered via <span className="font-mono">{videoAssets[0]?.oss_key.startsWith("mock://") ? "mock provider (placeholder)" : "real provider"}</span>
                  </p>
                )}
              </div>
            )}
          </SectionCard>

          {/* Voice */}
          <SectionCard
            icon={<Mic className="h-4 w-4 text-blue-600" />}
            title="Voice"
            subtitle={voiceLines.length ? `${voiceLines.length} lines · ${voiceAssets.length} synthesized` : undefined}
          >
            {voiceLines.length === 0 ? (
              <Empty label="Not generated yet, or no spoken dialogue in this branch." />
            ) : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {voiceLines.map((v) => (
                  <div key={v.id} className="rounded-lg border border-gray-100 bg-gray-50 p-3 text-xs">
                    <p className="font-medium text-gray-700">
                      {v.input_payload?.character_name} — shot {v.input_payload?.shot_number}
                    </p>
                    <p className="text-gray-600 mt-1">&ldquo;{v.rendered_prompt}&rdquo;</p>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          {/* Music */}
          <SectionCard
            icon={<Music2 className="h-4 w-4 text-blue-600" />}
            title="Music"
            subtitle={musicCues.length ? `${musicCues.length} cues` : undefined}
          >
            {musicCues.length === 0 ? (
              <Empty label="Not generated yet." />
            ) : (
              <div className="space-y-2">
                {musicCues.map((m) => (
                  <div key={m.id} className="rounded-lg border border-gray-100 bg-gray-50 p-3 text-xs">
                    <p className="font-medium text-gray-700">
                      Shots {m.input_payload?.start_shot_number}–{m.input_payload?.end_shot_number} ·{" "}
                      {m.input_payload?.mood} · {m.input_payload?.tempo_bpm} BPM
                    </p>
                    <p className="text-gray-600 mt-1">{m.rendered_prompt}</p>
                  </div>
                ))}
              </div>
            )}
          </SectionCard>

          {/* Final movie */}
          <SectionCard icon={<Clapperboard className="h-4 w-4 text-green-600" />} title="Final Cut">
            {!movie ? (
              <Empty label="Not assembled yet. Trigger Editor above (requires Video Generation to have run first)." />
            ) : (
              <div className="text-sm space-y-1">
                <p>
                  Status:{" "}
                  <span
                    className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                      movie.status === "completed"
                        ? "bg-green-100 text-green-800"
                        : "bg-gray-100 text-gray-700"
                    }`}
                  >
                    {movie.status}
                  </span>
                </p>
                {movie.duration_seconds !== null && (
                  <p className="text-gray-600">Duration: {movie.duration_seconds}s</p>
                )}
                {finalAsset && (
                  <p className="text-gray-500 text-xs font-mono break-all">{finalAsset.oss_key}</p>
                )}
              </div>
            )}
          </SectionCard>
        </>
      )}
    </div>
  );
}

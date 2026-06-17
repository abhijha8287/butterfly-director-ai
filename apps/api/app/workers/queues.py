STORY_QUEUE = "story"
TIMELINE_QUEUE = "timeline"
STORYBOARD_QUEUE = "storyboard"
VIDEO_QUEUE = "video"
VOICE_QUEUE = "voice"
MUSIC_QUEUE = "music"
EDITING_QUEUE = "editing"
MAINTENANCE_QUEUE = "maintenance"

# Approved design doc (docs/design/abhij-design-20260617-133804.md, Approach C):
# a single worker process binds to all of these queues for the hackathon build.
# Names are kept queue-per-concern so splitting into dedicated worker pools later
# (per ARCHITECTURE.md) is a deploy/compose change, not a code change.
ALL_QUEUES = [
    STORY_QUEUE,
    TIMELINE_QUEUE,
    STORYBOARD_QUEUE,
    VIDEO_QUEUE,
    VOICE_QUEUE,
    MUSIC_QUEUE,
    EDITING_QUEUE,
    MAINTENANCE_QUEUE,
]

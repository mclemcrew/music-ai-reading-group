#!/usr/bin/env bash
set -euo pipefail

# Usage: npm run new-post "My Article Title"
#   or:  bash scripts/new-post.sh "My Article Title"

if [ $# -eq 0 ]; then
  echo "Usage: npm run new-post \"My Article Title\""
  echo ""
  echo "Creates a new .svx post with frontmatter template and asset directories."
  exit 1
fi

TITLE="$1"
# Convert to kebab-case slug
SLUG=$(echo "$TITLE" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//;s/-$//')
DATE=$(date +%Y-%m-%d)
FILE="src/posts/${SLUG}.svx"

if [ -f "$FILE" ]; then
  echo "Error: $FILE already exists!"
  exit 1
fi

# Create post file
cat > "$FILE" << TEMPLATE
---
title: "${TITLE}"
subtitle: ""
date: "${DATE}"
authors: ["Music AI Reading Group"]
tags: []
description: ""
published: false
---

<script>
  // Import components you need:
  // import AudioGrid from '\$lib/components/audio/AudioGrid.svelte';
  // import AudioPlayer from '\$lib/components/audio/AudioPlayer.svelte';
  // import ManimVideo from '\$lib/components/media/ManimVideo.svelte';
  // import ResponsiveImage from '\$lib/components/media/ResponsiveImage.svelte';
  // import ResourceLink from '\$lib/components/ui/ResourceLink.svelte';
  //
  // Visualization components:
  // import PhaseAccumulation from '\$lib/components/viz/PhaseAccumulation.svelte';
  // import HarmonicSeries from '\$lib/components/viz/HarmonicSeries.svelte';
  // import FilteredNoise from '\$lib/components/viz/FilteredNoise.svelte';
  // import TrainingConvergence from '\$lib/components/viz/TrainingConvergence.svelte';
  // import SignalChain from '\$lib/components/viz/SignalChain.svelte';
</script>

## Introduction

Start writing here...

TEMPLATE

# Create asset directories
mkdir -p "static/audio/${SLUG}"
mkdir -p "static/videos/${SLUG}"

echo ""
echo "Created new post:"
echo "  File:   ${FILE}"
echo "  Audio:  static/audio/${SLUG}/"
echo "  Video:  static/videos/${SLUG}/"
echo ""
echo "Next steps:"
echo "  1. Edit ${FILE} — add your content and uncomment imports"
echo "  2. Set published: true when ready"
echo "  3. npm run dev    — preview locally"
echo "  4. npm run build  — build for deployment"
echo ""

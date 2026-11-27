# CareerPilot dashboard visual system

Reference: https://linear.app/homepage
Inspected on November 14, 2026 using Firecrawl branding extraction and a local 1440 x 900 browser capture. Reference capture: work/linear-reference/linear-home-desktop.png (development artifact, excluded from the skill package).

## Extracted values

Firecrawl reports background #08090A, text #D0D6E0, primary-button background #E5E5E6 with #08090A text, secondary surface #141516, heading/body family Inter, 64px homepage heading, 48px section heading, 15px body, 4px spacing unit. Branding extraction is indicative, not a complete stylesheet audit.

## Visually observed

Near-black canvas, large left-aligned sans headings, restrained gray supporting copy, rounded off-white primary action, thin dividers and a broad outlined product surface. Screenshots of Linear products and its logo are reference material only; none are copied into CareerPilot.

## Dashboard adaptation

Keep CareerPilot's logo, functional sidebar, Today, Jobs, Search, and job inspector. Use 52px Today/search headings on desktop and 36px on phones, 16px body, 44px interactive targets. These are implementation choices rather than extracted site values. Use a subtle raised surface for the decision list. Preserve semantic status colors for application states. Keep transitions short and disable them under reduced motion.

The font stack names Inter but uses local system fallbacks if unavailable; no font is downloaded or remotely requested. This is a visual adaptation, not a pixel-exact replica. Reference mobile layouts and animations were not audited. Marketing copy, brand assets and promotional illustrations are not imported.

All colors and font families are declared in the dashboard stylesheet's root token block. Keep candidate data in its private workspace.

## Current direction: glass and color

The user subsequently requested icons, color, liquid glass and cards. This supersedes the monochrome treatment above. Use a deep navy canvas, mint primary actions, softly tinted blue/mint/peach/rose summary cards, translucent dark panels with edge highlights, and consistent decorative SVG line icons. The color roles reinforce labels; they never replace status text. Keep the existing workflows and local system font fallback.

Blur is progressive enhancement: unsupported browsers use solid panels. Reduced-transparency and reduced-motion media preferences remove the corresponding effects. This is a CSS glass treatment, not physical refraction or an animation dependency.

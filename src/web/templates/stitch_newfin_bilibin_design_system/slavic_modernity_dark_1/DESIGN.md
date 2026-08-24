---
name: Slavic Modernity Dark
colors:
  surface: '#131313'
  surface-dim: '#131313'
  surface-bright: '#393939'
  surface-container-lowest: '#0e0e0e'
  surface-container-low: '#1c1b1b'
  surface-container: '#201f1f'
  surface-container-high: '#2a2a2a'
  surface-container-highest: '#353534'
  on-surface: '#e5e2e1'
  on-surface-variant: '#c3caad'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#313030'
  outline: '#8d9479'
  outline-variant: '#434933'
  surface-tint: '#a1d800'
  primary: '#ffffff'
  on-primary: '#253500'
  primary-container: '#b8f600'
  on-primary-container: '#506e00'
  inverse-primary: '#4b6700'
  secondary: '#bcf532'
  on-secondary: '#253500'
  secondary-container: '#a1d800'
  on-secondary-container: '#415a00'
  tertiary: '#ffffff'
  on-tertiary: '#412d00'
  tertiary-container: '#ffdea5'
  on-tertiary-container: '#7e5f1f'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#b8f600'
  primary-fixed-dim: '#a1d800'
  on-primary-fixed: '#141f00'
  on-primary-fixed-variant: '#384e00'
  secondary-fixed: '#bcf532'
  secondary-fixed-dim: '#a1d800'
  on-secondary-fixed: '#141f00'
  on-secondary-fixed-variant: '#384e00'
  tertiary-fixed: '#ffdea5'
  tertiary-fixed-dim: '#e9c176'
  on-tertiary-fixed: '#261900'
  on-tertiary-fixed-variant: '#5d4201'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353534'
  tsar-red: '#ff4d3d'
  ink-black: '#000000'
  parchment-dim: '#e1e5cf'
  forest-base: '#191d10'
typography:
  headline-xl:
    fontFamily: JetBrains Mono
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: JetBrains Mono
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: JetBrains Mono
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-lg-mobile:
    fontFamily: JetBrains Mono
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
  body-lg:
    fontFamily: JetBrains Mono
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: JetBrains Mono
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-sm:
    fontFamily: JetBrains Mono
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.1em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 64px
  max-width: 1280px
---

## Brand & Style

This design system evolves the "Slavic Modernity" narrative into a high-contrast, technical aesthetic. It blends the intricate storytelling of Russian folklore illustrations with a futuristic, developer-centric clarity. The personality is disciplined, intellectual, and authoritative.

The design style is **High-Contrast / Technical Minimalism**. By shifting to a dark-mode default, the UI mimics a modern terminal or a luxury "night mode" editorial. We utilize the structural precision of monospaced typography and bold, glowing primary accents to create a "Cyber-Folk" atmosphere. Visuals are defined by razor-sharp clarity, generous dark space, and sophisticated geometric accents that replace traditional organic flourishes.

## Colors

The palette is optimized for a dark-first experience, ensuring high legibility and a premium feel.

- **Primary (Electric Lime):** The core action color. It is highly saturated to "glow" against the dark background. Use for primary CTAs and critical data highlights.
- **Secondary (Muted Lime):** Used for hover states and secondary interactive elements to maintain a monochromatic green hierarchy.
- **Tertiary (Folklore Gold):** Reserved for premium status indicators, decorative borders, and "expert" tiers.
- **Neutral (Deep Ink):** The primary background color is `#121212`, providing a pure, high-contrast base for light-colored text.
- **Surface Strategy:** Layers are built using `forest-base` (#191d10) for containers to provide a subtle, organic warmth to the dark interface.

## Typography

The typography system is unified under a high-performance monospaced aesthetic using **JetBrains Mono**. This removes the traditional serif "folk" influence and replaces it with a "technical folklore" vibe.

- **Headlines:** Use heavy weights with slightly tighter letter-spacing for a modern, impactful look.
- **Body Text:** Leverages the inherent legibility of monospaced fonts for technical data, schedules, and fitness metrics.
- **Labels:** Use all-caps with increased letter-spacing (`0.1em`) to create clear visual anchors and mimic traditional ledger headers in a digital context.
- **Contrast:** All text should default to high-brightness neutrals (near-white) against dark containers.

## Layout & Spacing

The layout is a **Fixed Grid** system that emphasizes structural integrity and "framed" content.

- **Desktop:** A 12-column grid within a 1280px container. Large 64px margins create a "stage" for the content, focusing the user's attention.
- **Mobile:** Transitions to a fluid single-column layout with 16px margins for maximum content density.
- **Rhythm:** An 8px linear scale governs all padding and margins. Vertical rhythm is strictly maintained to reinforce the "grid-paper" precision of the design.

## Elevation & Depth

This system avoids soft, blurry shadows in favor of **Tonal Layers** and **Luminous Outlines**.

- **Surfaces:** Depth is created by lightening the background hex. Base is `#121212`, cards/modals use `#191d10` or `#25291c`.
- **Borders:** Instead of shadows, use 1px solid borders. For inactive containers, use `primary_color_hex` at 15% opacity. For active or focused containers, use `primary_color_hex` at 50-80% opacity to create a "glow" effect.
- **Glassmorphism:** Use sparingly for navigation bars—a 20px backdrop blur with a 10% white tint to maintain visibility of background elements while scrolling.

## Shapes

The shape language is **Rounded (0.5rem)**. This "ROUND_EIGHT" (8px) approach softens the technical edges of the monospaced typography, making the fitness app feel approachable and modern rather than purely industrial.

- **Buttons & Cards:** Use the standard `0.5rem` radius.
- **Large Sections:** Can utilize `rounded-xl` (1.5rem) for a "pill-card" look on major content blocks.
- **Interactive States:** Maintain consistent corner radius across all states to ensure stability.

## Components

### Buttons
- **Primary:** Solid `primary_color_hex` with `ink-black` text. Rounded-lg (0.5rem). Bold text.
- **Secondary:** Ghost style. `primary_color_hex` 1.5px border, light text, 0.5rem radius.

### Input Fields
- **Technical Style:** Full-border box using `forest-base` fill. Focus state triggers a 1px `primary_color_hex` border and a subtle inner glow. Label is always `label-sm` placed above the field.

### Cards
- **Fitness Cards:** Background of `forest-base`. Images should have a slight desaturation to blend into the dark theme, with a 1px border at 10% opacity.

### Chips & Tags
- Pill-shaped (rounded-full). Dark background with `secondary_color_hex` text. Use for exercise categories or status indicators.

### Progress Bars
- High contrast: Track is a dark neutral; the fill is a solid `primary_color_hex` gradient or solid block to emphasize technical performance metrics.

### Lists
- Separated by thin, low-opacity lines. Interactive list items should have a "highlight" state that changes the background to a slightly lighter forest-green tone.
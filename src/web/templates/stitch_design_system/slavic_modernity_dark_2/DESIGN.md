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
  on-surface-variant: '#c4c7c8'
  inverse-surface: '#e5e2e1'
  inverse-on-surface: '#313030'
  outline: '#8e9192'
  outline-variant: '#444748'
  surface-tint: '#c6c6c7'
  primary: '#ffffff'
  on-primary: '#2f3131'
  primary-container: '#e2e2e2'
  on-primary-container: '#636565'
  inverse-primary: '#5d5f5f'
  secondary: '#bcf532'
  on-secondary: '#253500'
  secondary-container: '#a1d801'
  on-secondary-container: '#425a00'
  tertiary: '#ffffff'
  on-tertiary: '#402d04'
  tertiary-container: '#ffdea5'
  on-tertiary-container: '#796133'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#e2e2e2'
  primary-fixed-dim: '#c6c6c7'
  on-primary-fixed: '#1a1c1c'
  on-primary-fixed-variant: '#454747'
  secondary-fixed: '#bcf532'
  secondary-fixed-dim: '#a1d801'
  on-secondary-fixed: '#141f00'
  on-secondary-fixed-variant: '#384e00'
  tertiary-fixed: '#ffdea5'
  tertiary-fixed-dim: '#e2c28b'
  on-tertiary-fixed: '#271900'
  on-tertiary-fixed-variant: '#594318'
  background: '#131313'
  on-background: '#e5e2e1'
  surface-variant: '#353534'
  tsar-red: '#ff4d3d'
  ink-black: '#000000'
  parchment-dim: '#e1e5cf'
  forest-base: '#191d10'
  electric-lime: '#a1d800'
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
  headline-lg-mobile:
    fontFamily: JetBrains Mono
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
  headline-md:
    fontFamily: JetBrains Mono
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
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
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 64px
  max-width: 1280px
---

## Brand & Style

The design system embodies a "Cyber-Folk" aesthetic, evolving Slavic cultural narratives into a high-contrast, technical environment. The personality is disciplined, intellectual, and authoritative, mimicking the precision of a modern terminal or a luxury "night mode" editorial.

The design style is **Technical Minimalism**. It relies on razor-sharp clarity, generous dark space, and sophisticated geometric accents. By blending the structural rigor of developer tools with bold, glowing accents, the UI evokes a sense of "technical folklore"—a disciplined digital space that feels both ancient in its narrative roots and futuristic in its execution.

## Colors

The palette is optimized for a dark-first experience, focusing on high-contrast legibility and a premium, glowing feel.

- **Primary (White):** Used for core headlines and high-impact UI elements to provide stark, absolute contrast against the dark background.
- **Secondary (Muted Lime):** Acts as the primary interactive accent. Its high saturation allows it to "glow" against the deep base.
- **Tertiary (Folklore Gold):** Reserved for premium status indicators, "expert" tiers, and decorative accents.
- **Neutral (Deep Ink):** The fundamental background layer, providing a pure, non-distracting base.
- **Surface Strategy:** Layers are constructed using `forest-base` (#191d10) for containers, providing a subtle organic warmth that prevents the dark interface from feeling cold or sterile.

## Typography

This system uses a unified monospaced aesthetic to achieve a "technical folklore" vibe, replacing organic flourishes with structural precision.

- **Headlines:** Heavy weights with tight tracking for a modern, impactful look.
- **Body Text:** Leverages the inherent legibility of monospaced characters for data-heavy content and metrics.
- **Labels:** Set in all-caps with increased letter-spacing to mimic traditional ledger headers.
- **Hierarchy:** Contrast is achieved through weight and brightness; all text defaults to near-white or light-gray variants to ensure visibility against the dark surface containers.

## Layout & Spacing

The layout follows a **Fixed Grid** philosophy, emphasizing structural integrity and "framed" content areas.

- **Grid System:** A 12-column grid is used on desktop with a maximum width of 1280px. Large 64px margins create a "stage" effect, centering focus.
- **Mobile Adaptivity:** Transitions to a fluid single-column layout with 16px side margins to maximize content density on small screens.
- **Rhythm:** An 8px linear scale (2x the 4px base unit) governs all padding and margins. Vertical rhythm is strictly enforced to reinforce the "grid-paper" precision of the interface.

## Elevation & Depth

This system avoids soft shadows, opting instead for **Tonal Layers** and **Luminous Outlines** to convey depth.

- **Surfaces:** Depth is expressed by slightly lightening the background color. Modals and cards use `forest-base` or slightly elevated tiers to stand out from the `ink-black` background.
- **Borders:** Depth is defined by 1px solid borders. Inactive containers use a low-opacity border (15%), while focused or active elements use a higher opacity (50-80%) to create a "wireframe glow" effect.
- **Glassmorphism:** Reserved exclusively for navigation bars to maintain context of background content during scrolling, using a 20px blur with a subtle light tint.

## Shapes

The shape language is strictly controlled with a **3px fixed radius** across all components. This specific "Micro-Softened" approach maintains the architectural, rigid feel of the monospaced typography while providing just enough refinement to prevent the UI from feeling aggressive or "un-styled."

- **Uniformity:** Every button, card, input field, and container must adhere to the 3px radius.
- **Interactive Elements:** This radius remains constant across all states (hover, active, disabled) to ensure visual stability in the grid.

## Components

### Buttons
- **Primary:** Solid `secondary_color_hex` (Lime) with `ink-black` text. Fixed 3px radius.
- **Secondary:** Ghost style with a 1.5px border of `primary_color_hex`, light text, and a 3px radius.

### Input Fields
- **Technical Style:** Solid `forest-base` fill with a subtle 1px border. Focus state triggers a glow effect using a brighter border opacity. Labels use `label-sm` and are positioned above the field.

### Cards
- **Structure:** Background of `forest-base`. 1px border at 10% opacity. 3px corner radius.
- **Content:** Images should be slightly desaturated to maintain the dark-mode atmosphere.

### Chips & Tags
- Rectangular with the 3px fixed radius. Dark background with `secondary_color_hex` text. Used for status indicators and exercise categories.

### Lists
- Items are separated by thin, low-opacity 1px lines. Highlighting an item changes its background to a slightly lighter forest-green tone, maintaining the rectangular 3px corner shape.
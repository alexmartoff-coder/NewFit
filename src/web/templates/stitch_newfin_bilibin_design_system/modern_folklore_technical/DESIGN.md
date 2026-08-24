---
name: Modern Folklore Technical
colors:
  surface: '#f8fce5'
  surface-dim: '#d8dcc6'
  surface-bright: '#f8fce5'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f6df'
  surface-container: '#ecf0d9'
  surface-container-high: '#e6ead4'
  surface-container-highest: '#e1e5ce'
  on-surface: '#191d0f'
  on-surface-variant: '#444839'
  inverse-surface: '#2e3223'
  inverse-on-surface: '#eff3dc'
  outline: '#757968'
  outline-variant: '#c5c8b5'
  surface-tint: '#4b6700'
  primary: '#384d00'
  on-primary: '#ffffff'
  primary-container: '#4b6700'
  on-primary-container: '#c2e577'
  inverse-primary: '#b0d368'
  secondary: '#4d6453'
  on-secondary: '#ffffff'
  secondary-container: '#cfe9d3'
  on-secondary-container: '#536a59'
  tertiary: '#394858'
  on-tertiary: '#ffffff'
  tertiary-container: '#516070'
  on-tertiary-container: '#cbdaed'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ccef80'
  primary-fixed-dim: '#b0d368'
  on-primary-fixed: '#141f00'
  on-primary-fixed-variant: '#384e00'
  secondary-fixed: '#cfe9d3'
  secondary-fixed-dim: '#b3cdb8'
  on-secondary-fixed: '#0a2013'
  on-secondary-fixed-variant: '#364c3c'
  tertiary-fixed: '#d4e4f7'
  tertiary-fixed-dim: '#b8c8db'
  on-tertiary-fixed: '#0d1d2a'
  on-tertiary-fixed-variant: '#394857'
  background: '#f8fce5'
  on-background: '#191d0f'
  surface-variant: '#e1e5ce'
  parchment-base: '#F9F7F2'
  paper-shadow: '#EBE7DE'
  tsar-red: '#A62C21'
  folklore-gold: '#C5A059'
  ink-black: '#121212'
  lime-accent: '#beff00'
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
    fontFamily: Manrope
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: Manrope
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-sm:
    fontFamily: Manrope
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.05em
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
  section-gap: 48px
  max-width: 1280px
---

## Brand & Style

The design system marries the disciplined world of modern fitness with the intricate, narrative-driven aesthetic of Ivan Bilibin’s Russian folklore illustrations, now updated with a **technical, precise edge**. The target audience includes health-conscious urbanites and professional sports specialists who value performance, cultural depth, and data-driven clarity.

The UI should feel like a premium, illustrated technical manual—airy and intellectual—yet highly functional. We utilize a **Minimalist** framework layered with **Art Nouveau** flourishes and **Monospaced** precision. This juxtaposition creates a unique "NewFit" identity: traditional strength meets modern wellness and technical accuracy.

## Colors

The palette is anchored by a "Parchment" neutral base, moving away from sterile whites to a warmer, more organic canvas reminiscent of aged paper.

- **Primary (Lime Green):** Used for high-priority actions and active selections to provide a high-visibility contrast against the traditional background.
- **Secondary (Forest Green):** A deep, earthy tone used for structural elements and grounding the UI.
- **Named Colors:** "Tsar Red" acts as the notification accent, while "Folklore Gold" is reserved for ornamental borders and premium states. "Ink Black" is used for typography to maintain the feel of printed illustrations and technical manuscripts.

## Typography

The typographic system relies on a dual-personality approach that balances folkloric structure with modern legibility:

1.  **JetBrains Mono:** Used for all headlines. Replacing the traditional serif with this monospace font injects a sense of technical precision and modern craftsmanship into the "bookish" layout. It should be treated with generous leading.
2.  **Manrope:** Used for all functional body text, labels, and inputs. It ensures that performance data, schedules, and prices are legible at a glance.

Small labels and category tags use uppercase Manrope with increased letter spacing to mimic the rhythmic layout of traditional headers and technical diagrams.

## Layout & Spacing

The layout follows a **Fixed Grid** model on desktop to mimic the structured pages of an illustrated volume, while transitioning to a fluid layout on mobile.

- **Desktop:** 12-column grid with a max-width of 1280px. Large margins act as the "frame" for the content.
- **Mobile:** Single column with 16px margins.
- **Rhythm:** An 8px-based spacing scale is used for internal component padding. Section-level spacing is intentionally wide to prevent the monospaced typography and ornamental elements from feeling cluttered.

## Elevation & Depth

Depth is conveyed through **Tonal Layering** and **Fine Outlines** rather than soft shadows, reinforcing the "woodblock print" aesthetic.

- **Tiers:** Surfaces (cards, drawers) use a slightly lighter off-white or the `paper-shadow` color against the `parchment-base` background.
- **Borders:** Use 1px solid borders in `secondary_color` at 10-20% opacity.
- **Ornamental Elevation:** Key containers feature a "double-line" border—a thin outer line and an even thinner inner line—mimicking traditional framing techniques.

## Shapes

The shape language is **Soft (0.25rem)**, specifically targeting a 3px radius for standard elements. This maintains a "cut paper" aesthetic.

Interactive elements use these tight corners, while specific decorative containers may use "ornate corners"—subtle 45-degree notches—to reinforce the folklore theme without sacrificing the precision of the JetBrains Mono typeface.

## Components

### Buttons
- **Primary:** Solid `primary_color_hex` with `ink-black` text. High contrast, sharp edges.
- **Secondary:** Transparent background with a `folklore-gold` 1.5px border and decorative "corner brackets" (2px L-shapes at the corners).

### Chips & Badges
- Subtle parchment background and a `secondary_color` border. For status badges, use a small dot icon in the appropriate state color to maintain the technical manual aesthetic.

### Input Fields
- Underlined style to mimic ledger lines, or a full box with very light `paper-shadow` fill. Labels use `label-sm` Manrope above the field.

### Cards
- **Specialist Card:** Features a large photo with a 1px border. The footer uses a "woodblock" style (solid `secondary_color` with white text) for price and rating sections.

### Decorative Dividers
- Custom SVG dividers featuring a centered geometric knot or stylized leaf pattern that tapers into a fine line, separating major content blocks.
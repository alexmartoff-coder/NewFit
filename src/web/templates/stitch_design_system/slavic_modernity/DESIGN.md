---
name: Slavic Modernity
colors:
  surface: '#f8fce5'
  surface-dim: '#d8dcc7'
  surface-bright: '#f8fce5'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f6e0'
  surface-container: '#ecf0da'
  surface-container-high: '#e6ead4'
  surface-container-highest: '#e1e5cf'
  on-surface: '#191d10'
  on-surface-variant: '#434933'
  inverse-surface: '#2e3223'
  inverse-on-surface: '#eff3dd'
  outline: '#737a61'
  outline-variant: '#c3caad'
  surface-tint: '#4b6700'
  primary: '#4b6700'
  on-primary: '#ffffff'
  primary-container: '#beff00'
  on-primary-container: '#547300'
  inverse-primary: '#a1d800'
  secondary: '#4d6453'
  on-secondary: '#ffffff'
  secondary-container: '#cde6d1'
  on-secondary-container: '#516857'
  tertiary: '#516070'
  on-tertiary: '#ffffff'
  tertiary-container: '#ddecff'
  on-tertiary-container: '#5c6b7b'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#b8f600'
  primary-fixed-dim: '#a1d800'
  on-primary-fixed: '#141f00'
  on-primary-fixed-variant: '#384e00'
  secondary-fixed: '#d0e9d4'
  secondary-fixed-dim: '#b4cdb8'
  on-secondary-fixed: '#0b2013'
  on-secondary-fixed-variant: '#364c3c'
  tertiary-fixed: '#d5e4f7'
  tertiary-fixed-dim: '#b9c8da'
  on-tertiary-fixed: '#0e1d2a'
  on-tertiary-fixed-variant: '#3a4857'
  background: '#f8fce5'
  on-background: '#191d10'
  surface-variant: '#e1e5cf'
  parchment-base: '#F9F7F2'
  paper-shadow: '#EBE7DE'
  tsar-red: '#A62C21'
  folklore-gold: '#C5A059'
  ink-black: '#121212'
typography:
  headline-xl:
    fontFamily: Libre Caslon Text
    fontSize: 48px
    fontWeight: '700'
    lineHeight: 56px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Libre Caslon Text
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-md:
    fontFamily: Libre Caslon Text
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
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
  headline-lg-mobile:
    fontFamily: Libre Caslon Text
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
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

The design system marries the disciplined world of modern fitness with the intricate, narrative-driven aesthetic of Ivan Bilibin’s Russian folklore illustrations. The target audience includes health-conscious urbanites and professional sports specialists who value both performance and cultural depth.

The UI should feel like a premium, illustrated book—airy and intellectual—yet highly functional. We utilize a **Modern Minimalist** framework as the foundation, layering it with **Art Nouveau** and **Folkloric** flourishes. Expect clean functional blocks, generous whitespace (parchment-toned), and sophisticated, fine-line ornamental borders that frame high-action fitness content. This juxtaposition creates a unique "NewFit" identity: traditional strength meets modern wellness.

## Colors

The palette is anchored by a "Parchment" neutral base, moving away from sterile whites to a warmer, more organic canvas.

- **Primary (Lime Green):** Taken directly from the logo, used sparingly for high-priority actions (CTA buttons, active selection) to provide a modern, high-visibility contrast against the traditional background.
- **Secondary (Forest Green):** A deep, earthy tone used for structural elements and grounding the UI.
- **Named Colors:** "Tsar Red" acts as the error and notification accent, while "Folklore Gold" is reserved for ornamental borders and high-tier (subscription) states. "Ink Black" is used for typography to maintain the feel of a printed illustration.

## Typography

The typographic system relies on a dual-personality approach:

1.  **Libre Caslon Text:** Used for all headlines. This serif brings the "bookish," authoritative, and folkloric feel. It should be treated with generous leading to maintain an airy, editorial quality.
2.  **Manrope:** Used for all functional body text, labels, and inputs. It provides the necessary modern clarity for a fitness booking app, ensuring that schedules and prices are legible at a glance.

Small labels and category tags use uppercase Manrope with increased letter spacing to mimic the rhythmic layout of traditional book headers.

## Layout & Spacing

The layout follows a **Fixed Grid** model on desktop to mimic the structured pages of an illustrated volume, while transitioning to a fluid, high-comfort layout on mobile.

- **Desktop:** 12-column grid with a max-width of 1280px. Large margins (64px) act as the "frame" for the content.
- **Mobile:** Single column with 16px margins.
- **Rhythm:** An 8px-based spacing scale is used for internal component padding, but section-level spacing is intentionally wide (48px+) to prevent the ornamental elements from feeling cluttered. Content "reflows" into structured cards that maintain their proportions.

## Elevation & Depth

This system avoids heavy shadows and physical extrusion. Depth is conveyed through **Tonal Layering** and **Fine Outlines**:

- **Tiers:** The background is `parchment-base`. Surfaces (cards, drawers) use a slightly lighter off-white or the `paper-shadow` color to create a stacked effect.
- **Borders:** Instead of shadows, use 1px solid borders in `secondary_color` (Forest Green) at 10-20% opacity.
- **Ornamental Elevation:** Key containers (like the specialist profile card) feature a "double-line" border—a thin outer line and an even thinner inner line—mimicking the framing techniques used in Bilibin's plates.

## Shapes

The shape language is primarily **Soft (0.25rem)**. While modern apps often trend toward high roundedness, this design system uses tighter corners to maintain the "cut paper" or "woodblock" aesthetic characteristic of traditional illustrations.

Interactive elements like buttons and input fields use the `Soft` setting, while specific decorative containers may use "ornate corners"—subtle 45-degree notches or small geometric protrusions at the vertices—to reinforce the folklore theme without sacrificing professional utility.

## Components

### Buttons
- **Primary:** Solid `primary_color_hex` (Lime) with `ink-black` text. No shadow.
- **Secondary:** Transparent background with a `folklore-gold` 1.5px border and decorative "corner brackets" (2px L-shapes at the corners).

### Chips & Badges
- Used for specializations (e.g., "Tennis", "Padel"). These should have a subtle parchment background and a `secondary_color` border. For status badges (e.g., "Approved"), use a small dot icon in the appropriate state color.

### Lists & Scheduling
- **Slot Grid:** Time slots are clean rectangles. Selected slots use a `primary_color` fill.
- **Weekly View:** Days are separated by thin vertical lines with a "floral" or "geometric" node at the top of the divider.

### Input Fields
- Underlined style (rather than boxed) to mimic handwriting lines in a ledger, or a full box with very light `paper-shadow` fill. Labels sit above the field in `label-sm` typography.

### Cards
- **Specialist Card:** Features a large photo with a 1px border. The footer of the card uses a "woodblock" style background (solid `secondary_color` with white text) for the price/rating section to create high contrast.

### Decorative Dividers
- Use a custom SVG divider: a centered geometric knot or a stylized leaf pattern that tapers off into a fine line. This is used to separate major sections on the `SpecialistDetailsPage`.
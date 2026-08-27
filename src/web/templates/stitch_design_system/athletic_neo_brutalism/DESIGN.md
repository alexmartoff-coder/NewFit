---
name: Athletic Neo-Brutalism
colors:
  surface: '#FFFFFF'
  surface-dim: '#F4F4F5'
  surface-bright: '#f9f9f9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f3'
  surface-container: '#eeeeee'
  surface-container-high: '#e8e8e8'
  surface-container-highest: '#e2e2e2'
  on-surface: '#1a1c1c'
  on-surface-variant: '#444933'
  inverse-surface: '#2f3131'
  inverse-on-surface: '#f0f1f1'
  outline: '#747a60'
  outline-variant: '#c4c9ac'
  surface-tint: '#516600'
  primary: '#516600'
  on-primary: '#ffffff'
  primary-container: '#ceff00'
  on-primary-container: '#5c7300'
  inverse-primary: '#acd600'
  secondary: '#5f5e5e'
  on-secondary: '#ffffff'
  secondary-container: '#e5e2e1'
  on-secondary-container: '#656464'
  tertiary: '#b0008e'
  on-tertiary: '#ffffff'
  tertiary-container: '#ffe7f2'
  on-tertiary-container: '#c700a1'
  error: '#EF4444'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#c5f400'
  primary-fixed-dim: '#acd600'
  on-primary-fixed: '#161e00'
  on-primary-fixed-variant: '#3c4d00'
  secondary-fixed: '#e5e2e1'
  secondary-fixed-dim: '#c8c6c5'
  on-secondary-fixed: '#1c1b1b'
  on-secondary-fixed-variant: '#474646'
  tertiary-fixed: '#ffd8ec'
  tertiary-fixed-dim: '#ffaddf'
  on-tertiary-fixed: '#3b002e'
  on-tertiary-fixed-variant: '#87006c'
  background: '#f9f9f9'
  on-background: '#1a1c1c'
  surface-variant: '#e2e2e2'
  ink-black: '#121212'
  lime-vibrant: '#CEFF00'
  magenta-accent: '#FF00CF'
  success: '#10B981'
  warning: '#F59E0B'
  info: '#3B82F6'
typography:
  display-2xl:
    fontFamily: Montserrat
    fontSize: 48px
    fontWeight: '800'
    lineHeight: 56px
    letterSpacing: -0.03em
  headline-lg:
    fontFamily: Montserrat
    fontSize: 28px
    fontWeight: '700'
    lineHeight: 36px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Montserrat
    fontSize: 24px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Montserrat
    fontSize: 22px
    fontWeight: '700'
    lineHeight: 28px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-base:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-semibold:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
  label-caps:
    fontFamily: Montserrat
    fontSize: 12px
    fontWeight: '700'
    lineHeight: 16px
    letterSpacing: 0.06em
  stat-number:
    fontFamily: Montserrat
    fontSize: 32px
    fontWeight: '800'
    lineHeight: 36px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
  sidebar-width: 260px
  gutter: 24px
  margin-mobile: 16px
  margin-desktop: 32px
---

## Brand & Style

This design system blends the raw, functional utility of **Neo-Brutalism** with a high-energy, athletic pulse. Inspired by the minimalist efficiency of Gumroad, it utilizes heavy borders, high-contrast surfaces, and vibrant accents to create a decisive and professional marketplace environment.

The target audience includes fitness professionals and health-conscious clients who value speed, clarity, and performance. The UI should evoke a sense of **momentum, reliability, and digital-first sophistication**.

**Key Visual Principles:**
- **Bold Linework:** Consistent use of 1.5px to 2px solid black borders to define containers.
- **High-Contrast:** Stark transitions between ink-black, pure white, and vibrant lime.
- **Functional Depth:** Avoid soft shadows in favor of hard, offset shadows for a tactile, "clickable" feel.
- **Utility-First:** Layouts prioritize data density and clear action paths (e.g., booking grids).

## Colors

The palette is driven by **Vibrant Lime (#CEFF00)**, a color that signals energy and action. It is strictly paired with **Ink Black (#121212)** for legibility and brand authority.

- **Primary:** Used for main CTAs, active states, and selected interactive elements.
- **Secondary:** Used for headers, borders, and high-emphasis text.
- **Tertiary:** Magenta is used sparingly for "VIP" status, rocket-sports categories, or special highlights.
- **Neutral:** A clean, slightly warm-white background ensures the high-contrast elements don't cause eye strain.

**State Colors:**
- **Success:** Specialist approved, payment confirmed.
- **Warning:** Profile pending, subscription expiring.
- **Error:** Slot cancelled, payment failed, account deletion.

## Typography

The typography system uses **Montserrat** for headlines and brand-heavy labels to mirror the bold, geometric nature of the logo. **Inter** is used for body copy and UI labels to ensure maximum readability in data-heavy views.

**Usage Notes:**
- **All-Caps Labels:** Use for category tags (e.g., `TENNIS`, `BEAUTY`) and table headers.
- **Stat Numbers:** Reserved for ratings, prices, and session counts.
- **Tight Leading:** Headlines use tight line-heights to maintain a punchy, aggressive aesthetic.

## Layout & Spacing

This design system uses a **fixed-fluid hybrid grid** model.

- **Sidebar (Desktop):** A fixed 260px sidebar navigation persists on the left, consistent with the Gumroad reference.
- **Main Canvas:** A fluid 12-column grid that clamps at a max-width of 1440px.
- **Gutters & Margins:** 24px gutters provide generous breathing room between cards. Mobile margins are reduced to 16px to maximize screen real estate.

**Responsive Reflow:**
- **Desktop:** 3-column cards.
- **Tablet:** 2-column cards.
- **Mobile:** Single column list, with the sidebar collapsing into a bottom tab navigation for thumb-friendly access.

## Elevation & Depth

Depth is achieved through **hard shadows and solid borders** rather than gradients or soft blurs. This "Neo-Brutalist" approach ensures the UI feels tactile and responsive.

- **Level 0 (Flat):** Inputs, disabled slots, and background layout containers.
- **Level 1 (Surface):** Cards and buttons with a 1.5px border.
- **Level 2 (Interactive):** On hover, primary elements (cards, buttons) translate -2px upwards and gain a **hard 4px black shadow** (`#121212`) offset to the bottom right.
- **Level 3 (Modal/Overlay):** Large drawers and modals use a thicker 2px border and a heavy 8px hard shadow to signify high priority.

## Shapes

The shape language balances the "brutal" linework with **rounded corners** to keep the interface friendly and modern.

- **Standard Cards:** Use `rounded-lg` (16px) for a soft container feel.
- **Buttons & Chips:** Use `rounded-lg` (8px) or `rounded-full` for pill-style indicators (like specialist categories).
- **Interactive Slots:** Use `rounded-lg` (8px) for time capsules in the booking grid.

## Components

### Buttons
- **Primary:** #CEFF00 background, #121212 text, 2px solid black border. Hard shadow on hover.
- **Secondary:** White background, 1.5px solid black border.
- **Ghost:** No border, grey text, background fill on hover.

### Cards (Catalog)
- **Specialist Card:** 1.5px black border, `rounded-xl`. Features a 1:1 photo aspect ratio. Price tags use `stat-number` typography.
- **Status Badges:** Small pill-shaped badges with background tints (e.g., #D1FAE5 for Approved) and matching dark borders.

### Booking System
- **Slot Grid:** Time capsules arranged in a 4-column grid. Selected slots toggle to #CEFF00 with a black checkmark icon.
- **Calendar Picker:** Horizontal scroll of dates. Active date uses #121212 background with a lime indicator dot below.

### Forms & Inputs
- **Inputs:** 1.5px border, #FFFFFF background. On focus, the border remains black but gains a 3px "glow" ring of #CEFF00.
- **Checkbox:** Square 2px border. Checked state is a solid #CEFF00 fill with a black checkmark.

### Navigation
- **Sidebar:** Clean white surface, 1.5px right border. Active items use a #CEFF00 background "pill" within the sidebar width.
- **Status Badges:** `pending` (Amber), `approved` (Emerald), `active` (Emerald).
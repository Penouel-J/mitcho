---
name: Mitchô Digital Intelligence
colors:
  surface: '#f5fbf3'
  surface-dim: '#d6dcd4'
  surface-bright: '#f5fbf3'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f0f5ee'
  surface-container: '#eaefe8'
  surface-container-high: '#e4eae2'
  surface-container-highest: '#dee4dd'
  on-surface: '#171d19'
  on-surface-variant: '#3e4a41'
  inverse-surface: '#2c322d'
  inverse-on-surface: '#edf2eb'
  outline: '#6e7a70'
  outline-variant: '#bdcabe'
  surface-tint: '#006d40'
  primary: '#006b3f'
  on-primary: '#ffffff'
  primary-container: '#008751'
  on-primary-container: '#fdfff9'
  inverse-primary: '#70db9d'
  secondary: '#745b22'
  on-secondary: '#ffffff'
  secondary-container: '#fedb95'
  on-secondary-container: '#785f25'
  tertiary: '#9d3d43'
  on-tertiary: '#ffffff'
  tertiary-container: '#bd555a'
  on-tertiary-container: '#fffeff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#8df8b7'
  primary-fixed-dim: '#70db9d'
  on-primary-fixed: '#002110'
  on-primary-fixed-variant: '#00522f'
  secondary-fixed: '#ffdf9e'
  secondary-fixed-dim: '#e4c27e'
  on-secondary-fixed: '#261a00'
  on-secondary-fixed-variant: '#5a430b'
  tertiary-fixed: '#ffdad9'
  tertiary-fixed-dim: '#ffb3b3'
  on-tertiary-fixed: '#40000a'
  on-tertiary-fixed-variant: '#80272e'
  background: '#f5fbf3'
  on-background: '#171d19'
  surface-variant: '#dee4dd'
typography:
  display-lg:
    fontFamily: Playfair Display
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Playfair Display
    fontSize: 32px
    fontWeight: '700'
    lineHeight: '1.2'
  headline-lg-mobile:
    fontFamily: Playfair Display
    fontSize: 28px
    fontWeight: '700'
    lineHeight: '1.2'
  headline-md:
    fontFamily: Playfair Display
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  label-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '500'
    lineHeight: '1.2'
    letterSpacing: 0.05em
  caption:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: '1.4'
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  container-max: 1200px
  gutter: 24px
  margin-mobile: 16px
  section-gap: 80px
  stack-sm: 8px
  stack-md: 16px
  stack-lg: 32px
---

## Brand & Style
The design system embodies a synthesis of institutional authority and modern digital efficiency. It is designed for high-level decision-makers in Benin, requiring a UI that feels reliable, intellectually stimulating, and effortlessly navigable.

The aesthetic follows a **Premium Minimalist** movement, drawing inspiration from high-end editorial publications and leading technology platforms. It prioritizes clarity over decoration, using generous whitespace to reduce cognitive load and high-quality typography to establish a clear information hierarchy. The interface should feel "quiet" yet "powerful," evoking the emotional response of a trusted advisor: calm, informed, and precise.

## Colors
The palette is rooted in an "Academic White" foundation, utilizing varied shades of white and extremely light grays to define sections without the need for heavy borders. 

- **Primary (Beninese Green):** Used sparingly for high-priority actions, the AI chat interface, and subtle branding accents. It represents growth and national identity.
- **Secondary (Bronze):** A sophisticated accent used for metadata, premium features, or callouts. It adds a layer of "prestige" to the institutional feel.
- **Text (Charcoal):** We avoid pure black (#000) to maintain an editorial softness, using a deep charcoal for readability and a medium gray for secondary information.

## Typography
The typographic strategy relies on a classic "Serif for Headlines, Sans for Utility" pairing. 

**Playfair Display** provides the editorial authority. It should be used for article titles, section headers, and significant quotes. Large display sizes should use a slight negative letter-spacing to feel more "locked-in" and premium.

**Inter** provides the functional backbone. Its high legibility at small sizes makes it ideal for dense intelligence data, reports, and interface labels. Use "Label-SM" with uppercase styling for category tags and metadata to create a distinct visual break from body prose.

## Layout & Spacing
This design system employs a **Fixed Grid** philosophy for content readability, centered within the viewport. 

- **Desktop:** A 12-column grid with a 1200px max-width. Use large `section-gap` (80px+) to separate major intelligence briefs, allowing each topic to breathe.
- **Mobile:** Transition to a single-column stack with 16px side margins. 
- **Rhythm:** Spacing follows an 8px base unit. Consistent vertical rhythm is critical for the "Stripe-like" precision; ensure that all padding and margins are multiples of 8.

## Elevation & Depth
Depth is conveyed through **Tonal Layering** and **Low-Contrast Outlines** rather than heavy shadows.

- **Level 0 (Surface):** Pure White (#FFFFFF) for the main background.
- **Level 1 (Cards/Containers):** Light Gray (#F9FAFB) background or a 1px border (#E5E7EB) with no shadow.
- **Floating Elements:** The AI Chat Bubble and main dropdowns use a very soft, diffused ambient shadow (0px 10px 30px rgba(0,0,0,0.04)) to suggest they sit just above the page content.
- **Transitions:** Use CSS `ease-in-out` for fade-ins. Elements should appear to emerge smoothly rather than "pop" into existence.

## Shapes
We utilize a **Soft** shape language. While the brand is institutional, perfectly sharp corners can feel too aggressive or dated. 

- **Standard Elements:** 0.25rem (4px) radius for inputs, small cards, and buttons.
- **Large Elements:** 0.5rem (8px) radius for major container blocks.
- **Specialty:** The AI Floating Bubble uses a pill-shape (full rounding) to differentiate it as a modern, interactive assistant versus static content.

## Components
- **Navbar:** Fixed to the top, blur-behind effect (backdrop-filter) with a 1px bottom border. Links use `label-sm` typography.
- **Publication Cards:** Minimalist layouts. Headlines in `headline-md`, category tags in `label-sm` using the Bronze accent color. No heavy borders; use subtle background shifts on hover.
- **Buttons:** 
  - *Primary:* Solid Beninese Green, white text, 4px radius. 
  - *Secondary:* Ghost style, 1px charcoal border, charcoal text.
- **Input Fields:** Bottom-border only or very light 4-sided stroke. Focus state should highlight the border in Beninese Green with no "glow" effect.
- **AI Chat Bubble:** Circular or pill-shaped, fixed to the bottom right. Use the Primary Green with a crisp white icon. 
- **Lists:** Data lists should use "zebra-striping" with the `#F9FAFB` secondary background to maintain alignment in dense intelligence reports.
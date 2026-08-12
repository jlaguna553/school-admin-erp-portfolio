/**
 * Derive a whole palette from one brand colour.
 *
 * A school configures a single hex; everything else — the dark-mode variant,
 * the accent tint, and the ink that sits on top of the brand — is computed.
 * That is the point: six hand-picked colours can produce an interface nobody
 * can read, and an operator has no way to know until someone complains.
 *
 * Kept dependency-free and pure so it can run on the server, where the theme is
 * inlined into the page before it is sent.
 */

const DEFAULT_BRAND = '#1d4ed8';

interface Rgb {
  r: number;
  g: number;
  b: number;
}

/** Accepts `#rrggbb` only — the API validates the same shape. */
export function parseHex(hex: string): Rgb | null {
  const match = /^#([0-9a-f]{6})$/i.exec(hex.trim());
  if (!match) return null;
  const value = Number.parseInt(match[1]!, 16);
  return { r: (value >> 16) & 0xff, g: (value >> 8) & 0xff, b: value & 0xff };
}

function toHex({ r, g, b }: Rgb): string {
  const channel = (value: number) =>
    Math.max(0, Math.min(255, Math.round(value)))
      .toString(16)
      .padStart(2, '0');
  return `#${channel(r)}${channel(g)}${channel(b)}`;
}

function mix(from: Rgb, to: Rgb, amount: number): Rgb {
  return {
    r: from.r + (to.r - from.r) * amount,
    g: from.g + (to.g - from.g) * amount,
    b: from.b + (to.b - from.b) * amount,
  };
}

/**
 * Relative luminance, per WCAG 2.1.
 *
 * Not a simple average of the channels: the eye is far more sensitive to green
 * than to blue, so averaging would call a saturated blue "light" and put black
 * text on it.
 */
export function relativeLuminance({ r, g, b }: Rgb): number {
  const channel = (value: number) => {
    const c = value / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrastRatio(a: Rgb, b: Rgb): number {
  const [light, dark] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x);
  return (light! + 0.05) / (dark! + 0.05);
}

const WHITE: Rgb = { r: 255, g: 255, b: 255 };
/** Not pure black: matches the near-black the rest of the palette already uses. */
const INK: Rgb = { r: 17, g: 24, b: 39 };

/**
 * The text colour to place on the brand — whichever of the two reads better.
 *
 * A yellow or lime brand needs dark ink; most blues and greens need white.
 * Picking by contrast ratio rather than by a luminance threshold means the
 * answer is the one that actually scores higher, including at the boundary.
 */
export function inkOn(brand: Rgb): string {
  return contrastRatio(brand, WHITE) >= contrastRatio(brand, INK) ? toHex(WHITE) : toHex(INK);
}

export interface BrandTokens {
  primary: string;
  primaryForeground: string;
  accent: string;
  accentForeground: string;
  primaryDark: string;
  primaryForegroundDark: string;
  accentDark: string;
  accentForegroundDark: string;
}

export function deriveBrandTokens(hex: string): BrandTokens {
  const brand = parseHex(hex) ?? parseHex(DEFAULT_BRAND)!;

  // Dark surfaces need a lighter brand or it disappears into the background —
  // the same relationship the hand-written default palette already has between
  // its light (#1d4ed8) and dark (#3b82f6) primaries.
  const brandDark = mix(brand, WHITE, 0.35);

  return {
    primary: toHex(brand),
    primaryForeground: inkOn(brand),
    // A wash of the brand, for hover states and subtle fills.
    accent: toHex(mix(brand, WHITE, 0.92)),
    accentForeground: toHex(brand),
    primaryDark: toHex(brandDark),
    primaryForegroundDark: inkOn(brandDark),
    accentDark: toHex(mix(brand, { r: 11, g: 18, b: 32 }, 0.82)),
    accentForegroundDark: toHex(mix(brand, WHITE, 0.55)),
  };
}

/**
 * The tokens as a stylesheet, ready to inline in `<head>`.
 *
 * Only the brand-derived tokens are overridden. Surfaces, borders and the status
 * colours stay as authored, so a school's colour cannot turn a "paid" badge into
 * something that no longer reads as success.
 */
export function brandStylesheet(hex: string): string {
  const t = deriveBrandTokens(hex);
  return [
    ':root{',
    `--primary:${t.primary};`,
    `--primary-foreground:${t.primaryForeground};`,
    `--accent:${t.accent};`,
    `--accent-foreground:${t.accentForeground};`,
    `--ring:${t.primary};`,
    '}',
    '.dark{',
    `--primary:${t.primaryDark};`,
    `--primary-foreground:${t.primaryForegroundDark};`,
    `--accent:${t.accentDark};`,
    `--accent-foreground:${t.accentForegroundDark};`,
    `--ring:${t.primaryDark};`,
    '}',
  ].join('');
}

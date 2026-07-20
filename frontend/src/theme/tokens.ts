// Design tokens — Dark-First Utility per /app/design_guidelines.json
export const colors = {
  surface: '#050505',
  onSurface: '#FAFAFA',
  surfaceSecondary: '#121212',
  onSurfaceSecondary: '#A3A3A3',
  surfaceTertiary: '#1C1C1C',
  onSurfaceTertiary: '#8A8A8A',
  surfaceInverse: '#FAFAFA',
  onSurfaceInverse: '#050505',
  brand: '#E3A72F',
  brandPrimary: '#E3A72F',
  onBrandPrimary: '#050505',
  brandSecondary: '#F4C970',
  brandTertiary: '#3A2B0E',
  onBrandTertiary: '#E3A72F',
  success: '#45C97A',
  warning: '#FFB224',
  error: '#E5484D',
  border: '#1A1A1A',
  borderStrong: '#2A2A2A',
  divider: '#141414',
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, xxl: 32, xxxl: 48 };
export const radius = { sm: 6, md: 12, lg: 20, pill: 999 };

export const type = {
  display: { fontWeight: '700' as const, letterSpacing: -1 },
  body: { fontWeight: '400' as const },
  mono: { fontWeight: '500' as const },
};

export const platformMeta: Record<string, { label: string; color: string; emoji: string }> = {
  youtube:   { label: 'YouTube',    color: '#FF3D3D', emoji: '▶' },
  instagram: { label: 'Instagram',  color: '#E1306C', emoji: '◉' },
  tiktok:    { label: 'TikTok',     color: '#25F4EE', emoji: '♪' },
  course:    { label: 'Course',     color: '#E3A72F', emoji: '◆' },
  newsletter:{ label: 'Newsletter', color: '#7FB3FF', emoji: '✉' },
  podcast:   { label: 'Podcast',    color: '#B68FFF', emoji: '◐' },
  saas:      { label: 'SaaS',       color: '#45C97A', emoji: '▣' },
  affiliate: { label: 'Affiliate',  color: '#F97316', emoji: '↗' },
  digital:   { label: 'Digital',    color: '#22D3EE', emoji: '⬢' },
};

export const fmtCurrency = (n: number) => {
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 10_000)    return `$${(n / 1_000).toFixed(1)}k`;
  return `$${n.toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
};
export const fmtCompact = (n: number) => {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}k`;
  return `${n}`;
};
export const fmtPercent = (n: number) => `${n.toFixed(1)}%`;

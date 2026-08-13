# Design System Quick Start Guide

## Color Palette

Use CSS variables for all colors. Never hardcode colors.

```tsx
// ❌ DON'T
<div style={{ color: '#1b4332' }}>Text</div>

// ✅ DO
<div className="text-[var(--color-brand-green)]">Text</div>
// OR
<div className="text-brand-green">Text</div> {/* via tailwind */}
```

### Brand Colors
- **Emerald Green**: `var(--color-brand-green)` or `text-brand-green`
- **Gold**: `var(--color-brand-gold)` or `text-brand-gold`
- **Dark Navy**: `var(--color-bg-dark)` or `bg-bg-dark`

### Text Colors
- **Primary**: `text-text-primary`
- **Secondary**: `text-text-secondary`
- **Muted**: `text-text-muted`

---

## Glassmorphism

Apply glass effects with built-in utility classes:

```tsx
// Glass card with blur and transparency
<div className="glass-card p-6">Content</div>

// Opaque glass panel (more solid)
<div className="glass-panel p-6">Content</div>

// Custom glass effect
<div className="bg-white/75 backdrop-blur-[16px] border border-white/30">Content</div>
```

---

## Luxury UI Components

### 1. LuxuryStatCard
Dashboard stat card with icon badge and value.

```tsx
import { LuxuryStatCard } from '@/components/ui/LuxuryStatCard'

<LuxuryStatCard
  label="Pending Leads"
  value="13"
  subtext="Awaiting CRM sync"
  icon="⏳"
  badgeColor="cyan"  // emerald, gold, blue, purple, cyan
  variant="premium"  // default, glass, premium
  onClick={() => navigate('/leads')}
/>
```

### 2. LuxuryCard
Reusable card container with multiple variants.

```tsx
import { LuxuryCard } from '@/components/ui/LuxuryCard'

// Glass effect
<LuxuryCard variant="glass">
  <h2>Welcome</h2>
  <p>Your dashboard overview</p>
</LuxuryCard>

// Premium gradient
<LuxuryCard variant="premium" className="p-8">
  <h2>Important Info</h2>
</LuxuryCard>

// Maximum elevation (most luxury)
<LuxuryCard variant="elevated">
  Featured content
</LuxuryCard>
```

### 3. LuxuryBadge
Status indicator with color-coded variants.

```tsx
import { LuxuryBadge } from '@/components/ui/LuxuryBadge'

<LuxuryBadge 
  label="Active" 
  variant="approved"  // pending, approved, completed, error, info, warning
  style="gradient"    // default, glass, gradient
  icon="🟢"
  animated={true}
/>
```

### 4. LuxuryTable
Premium data table component.

```tsx
import { LuxuryTable } from '@/components/ui/LuxuryTable'

<LuxuryTable
  columns={[
    { key: 'name', label: 'Name', width: '30%' },
    { 
      key: 'status', 
      label: 'Status',
      render: (value) => (
        <LuxuryBadge label={value} variant="approved" />
      )
    },
    { key: 'date', label: 'Date', align: 'right' },
  ]}
  data={leads}
  variant="premium"  // default, glass, premium
  striped={true}
/>
```

---

## Text Utilities

Use semantic text classes for proper hierarchy:

```tsx
<h1 className="text-luxury-heading text-2xl">Main Heading</h1>
<h2 className="text-luxury-subheading text-lg">Sub Heading</h2>
<p className="text-luxury-body">Body text with proper line height</p>

// Or use Tailwind utilities
<p className="text-text-primary font-semibold">Primary text</p>
<p className="text-text-secondary">Secondary text</p>
<p className="text-text-muted text-sm">Muted text</p>
```

---

## Buttons

Use the updated Button component with luxury variants:

```tsx
import { Button } from '@/components/ui/button'

// Emerald green gradient
<Button className="btn-luxury-primary">
  Click Me
</Button>

// Gold accent
<Button className="btn-luxury-gold">
  Premium Action
</Button>

// Glass variant
<Button variant="glass">
  Subtle Action
</Button>
```

---

## Hover & Animation Effects

### Luxury Lift
Applies smooth hover animation with elevation:

```tsx
<div className="luxury-hover-lift p-6 bg-white rounded-xl">
  Hover to lift
</div>
```

### Glow Pulse
Animated glow effect:

```tsx
<div className="glow-pulse p-6 bg-brand-green rounded-xl">
  Glowing content
</div>
```

### Custom Animations
```tsx
<div className="animate-slide-in">Slides in</div>
<div className="animate-fade-in">Fades in</div>
<div className="animate-shimmer">Shimmering effect</div>
```

---

## Common Patterns

### Stat Grid (Dashboard)
```tsx
<div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
  <LuxuryStatCard label="Total" value="4,821" icon="📊" />
  <LuxuryStatCard label="Pending" value="13" icon="⏳" />
  {/* ... */}
</div>
```

### Welcome Section
```tsx
<LuxuryCard variant="glass" className="p-6">
  <h2 className="text-luxury-heading mb-2">Welcome Back</h2>
  <p className="text-luxury-body mb-4">Dashboard overview</p>
  <div className="flex gap-2">
    <LuxuryBadge label="Online" variant="approved" />
    <LuxuryBadge label="Synced" variant="info" />
  </div>
</LuxuryCard>
```

### Data Table
```tsx
<LuxuryTable
  columns={[...]}
  data={data}
  variant="premium"
  striped={true}
/>
```

---

## CSS Variable Reference

### Colors
```css
--color-brand-green: #1b4332
--color-brand-gold: #d4af37
--color-bg-primary: #f8f6f1
--color-text-primary: #0f172a
--color-border-luxury: #cbd5e1
```

### Effects
```css
--glass-bg: rgba(255, 255, 255, 0.75)
--glass-blur: blur(16px)
--glass-shadow: 0 20px 40px -15px rgba(0, 0, 0, 0.07)
```

### Gradients
```css
--gradient-luxury: linear-gradient(135deg, #1b4332 0%, #2d6a4f 50%, #52b788 100%)
--gradient-gold: linear-gradient(135deg, #d4af37 0%, #f4d03f 100%)
```

### Shadows
```css
--shadow-luxury: 0 25px 50px -20px rgba(0, 0, 0, 0.1)
--shadow-glow: 0 0 20px rgba(27, 67, 50, 0.3)
```

### Timing
```css
--duration-fast: 150ms
--duration-normal: 300ms
--easing-luxury: cubic-bezier(0.4, 0, 0.2, 1)
```

---

## Responsive Design

The design system is mobile-first:

```tsx
// Cards automatically stack on mobile
<div className="grid grid-cols-2 xl:grid-cols-4">
  {/* 2 columns on mobile/tablet, 4 on desktop */}
</div>

// Sidebar is hidden on mobile
<aside className="hidden md:flex">
  {/* Desktop sidebar */}
</aside>
```

---

## RTL Support

All components automatically support Arabic (RTL):

```tsx
// Logical properties (works for both LTR/RTL)
<div className="ps-4 pe-2 ms-auto">Content</div>
// ps = padding-start (right in RTL, left in LTR)
// pe = padding-end
// ms = margin-start
// me = margin-end
```

---

## Performance Tips

1. **Use CSS variables** - They're fast and cacheable
2. **Avoid inline styles** - Use Tailwind classes
3. **Lazy load tables** - Use React.memo on LuxuryTable
4. **Optimize animations** - Use `duration-fast` for frequent interactions
5. **Keep components small** - Easier to test and reuse

---

## Troubleshooting

### Colors not showing?
- Check if CSS variables are defined in `shared-design-system.css`
- Ensure `index.css` imports it
- Check browser console for CSS errors

### Glass effect not working?
- Verify browser supports `backdrop-filter` (all modern browsers)
- Check if parent has `overflow: hidden` (can clip backdrop blur)
- Use `glass-card` or `glass-panel` utilities

### Build errors?
- Clear cache: `rm -rf node_modules dist && npm install`
- Rebuild: `npm run build`
- Check TypeScript: `npm run type-check`

---

## Best Practices

✅ **DO**:
- Use luxury components for dashboards
- Keep colors in CSS variables
- Use Tailwind utilities
- Test on mobile
- Check RTL layout

❌ **DON'T**:
- Hardcode colors
- Use `!important`
- Mix inline styles with classes
- Create new color variables
- Skip mobile testing

---

## Getting Help

See full documentation:
- `TASK_1_DESIGN_SYSTEM_IMPLEMENTATION.md` - Full implementation details
- `shared-design-system.css` - All available utilities and variables
- `src/components/ui/*.tsx` - Component source code

---

**Last Updated**: 2026-08-12  
**Status**: ✅ Production Ready

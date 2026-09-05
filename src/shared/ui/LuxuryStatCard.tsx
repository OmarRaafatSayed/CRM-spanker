/**
 * LuxuryStatCard.tsx
 * ==================
 * Premium stat card component for CRM Dashboard with:
 * - Glassmorphism effects
 * - Luxury gradients & shadows
 * - Icon badges with brand colors
 * - Hover animations with luxury lift
 */

import React from 'react'

interface LuxuryStatCardProps {
  label: string
  value: string | number
  subtext?: string
  icon: React.ReactNode
  badgeColor?: 'emerald' | 'gold' | 'blue' | 'purple' | 'cyan'
  variant?: 'default' | 'glass' | 'premium'
  onClick?: () => void
}

const badgeColorMap = {
  emerald: 'from-[var(--color-brand-green)]/20 to-[var(--color-brand-green-light)]/20 text-[var(--color-brand-green)]',
  gold: 'from-[var(--color-brand-gold)]/20 to-[var(--color-brand-gold-light)]/20 text-[var(--color-brand-gold)]',
  blue: 'from-blue-500/20 to-cyan-500/20 text-blue-600',
  purple: 'from-purple-500/20 to-pink-500/20 text-purple-600',
  cyan: 'from-cyan-500/20 to-teal-500/20 text-cyan-600',
}

const variantStyles = {
  default: 'bg-white border border-[var(--color-border-light)] shadow-sm hover:shadow-md',
  glass: 'glass-card hover:glass-panel',
  premium: 'bg-gradient-to-br from-white to-[var(--color-bg-primary)] border border-[var(--color-border-luxury)] shadow-luxury hover:shadow-luxury-hover',
}

export const LuxuryStatCard: React.FC<LuxuryStatCardProps> = ({
  label,
  value,
  subtext,
  icon,
  badgeColor = 'emerald',
  variant = 'default',
  onClick,
}) => {
  return (
    <div
      onClick={onClick}
      className={`
        stat-card ${variant === 'premium' ? 'premium' : ''}
        rounded-2xl p-6 flex items-start gap-4
        transition-all duration-300
        ${onClick ? 'cursor-pointer' : ''}
        ${variantStyles[variant]}
      `}
    >
      {/* Icon Badge */}
      <div className={`
        flex h-14 w-14 shrink-0 items-center justify-center rounded-xl
        bg-gradient-to-br ${badgeColorMap[badgeColor]}
        shadow-md transition-all duration-300
      `}>
        <div className="text-2xl">{icon}</div>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <p className="text-3xl font-bold text-[var(--color-text-primary)] mb-1">
          {value}
        </p>
        <p className="text-sm font-medium text-[var(--color-text-secondary)]">
          {label}
        </p>
        {subtext && (
          <p className="text-xs text-[var(--color-text-muted)] mt-1">
            {subtext}
          </p>
        )}
      </div>
    </div>
  )
}

export default LuxuryStatCard

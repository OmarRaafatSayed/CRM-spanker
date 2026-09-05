/**
 * LuxuryBadge.tsx
 * ===============
 * Premium badge component for status indicators with:
 * - Glassmorphism variant
 * - Luxury gradients
 * - Color-coded states
 * - Animated pulse effects
 */

import React from 'react'

type BadgeVariant = 'pending' | 'approved' | 'completed' | 'error' | 'info' | 'warning'
type BadgeStyle = 'default' | 'glass' | 'gradient'

interface LuxuryBadgeProps {
  label: string
  variant?: BadgeVariant
  style?: BadgeStyle
  animated?: boolean
  icon?: React.ReactNode
}

const badgeConfig: Record<BadgeVariant, Record<BadgeStyle, string>> = {
  pending: {
    default: 'bg-yellow-100 text-yellow-700 border border-yellow-200',
    glass: 'glass-card text-yellow-600 border-yellow-200/50',
    gradient: 'bg-gradient-to-r from-yellow-400/20 to-amber-400/20 text-yellow-700 border border-yellow-300/50',
  },
  approved: {
    default: 'bg-emerald-100 text-emerald-700 border border-emerald-200',
    glass: 'glass-card text-emerald-600 border-emerald-200/50',
    gradient: 'bg-gradient-to-r from-[var(--color-brand-green)]/20 to-emerald-400/20 text-[var(--color-brand-green)] border border-[var(--color-brand-green)]/30',
  },
  completed: {
    default: 'bg-green-100 text-green-700 border border-green-200',
    glass: 'glass-card text-green-600 border-green-200/50',
    gradient: 'bg-gradient-to-r from-green-400/20 to-teal-400/20 text-green-700 border border-green-300/50',
  },
  error: {
    default: 'bg-red-100 text-red-700 border border-red-200',
    glass: 'glass-card text-red-600 border-red-200/50',
    gradient: 'bg-gradient-to-r from-red-400/20 to-pink-400/20 text-red-700 border border-red-300/50',
  },
  info: {
    default: 'bg-blue-100 text-blue-700 border border-blue-200',
    glass: 'glass-card text-blue-600 border-blue-200/50',
    gradient: 'bg-gradient-to-r from-blue-400/20 to-cyan-400/20 text-blue-700 border border-blue-300/50',
  },
  warning: {
    default: 'bg-orange-100 text-orange-700 border border-orange-200',
    glass: 'glass-card text-orange-600 border-orange-200/50',
    gradient: 'bg-gradient-to-r from-orange-400/20 to-red-400/20 text-orange-700 border border-orange-300/50',
  },
}

export const LuxuryBadge: React.FC<LuxuryBadgeProps> = ({
  label,
  variant = 'info',
  style = 'default',
  animated = false,
  icon,
}) => {
  return (
    <div
      className={`
        inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold
        transition-all duration-200
        ${badgeConfig[variant][style]}
        ${animated ? 'glow-pulse' : ''}
      `}
    >
      {icon && <span className="flex-shrink-0">{icon}</span>}
      <span>{label}</span>
    </div>
  )
}

export default LuxuryBadge

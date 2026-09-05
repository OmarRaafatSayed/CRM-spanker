/**
 * LuxuryCard.tsx
 * ==============
 * Reusable luxury card component with multiple variants:
 * - Default: Classic white card with subtle shadow
 * - Glass: Glassmorphism with backdrop blur
 * - Premium: Gradient background with luxury shadow
 * - Elevated: Maximum lift with enhanced hover effect
 */

import React from 'react'

type LuxuryCardVariant = 'default' | 'glass' | 'premium' | 'elevated'

interface LuxuryCardProps {
  children: React.ReactNode
  variant?: LuxuryCardVariant
  className?: string
  onClick?: () => void
  hover?: boolean
}

const variantStyles = {
  default: 'bg-white border border-[var(--color-border-light)] shadow-sm hover:shadow-md',
  glass: 'glass-card hover:glass-panel',
  premium: 'bg-gradient-to-br from-white to-[var(--color-bg-primary)] border border-[var(--color-border-luxury)] shadow-luxury hover:shadow-luxury-hover transform hover:-translate-y-2 hover:scale-[1.01]',
  elevated: 'bg-gradient-to-br from-white via-[var(--color-bg-primary)] to-[var(--color-bg-alt)] border border-[var(--color-border-luxury)] shadow-luxury-hover transform hover:-translate-y-3 hover:scale-[1.02]',
}

export const LuxuryCard: React.FC<LuxuryCardProps> = ({
  children,
  variant = 'default',
  className = '',
  onClick,
  hover = true,
}) => {
  return (
    <div
      onClick={onClick}
      className={`
        rounded-2xl p-6 transition-all duration-300
        ${variantStyles[variant]}
        ${hover ? 'luxury-hover-lift' : ''}
        ${onClick ? 'cursor-pointer' : ''}
        ${className}
      `}
    >
      {children}
    </div>
  )
}

export default LuxuryCard

import { useTranslation } from 'react-i18next'
import { applyHtmlDir } from '@/shared/i18n'

export function LangToggle({ compact = false }: { compact?: boolean }) {
  const { i18n, t } = useTranslation()
  const isAr = i18n.language === 'ar'

  const toggle = () => {
    const next = isAr ? 'en' : 'ar'
    i18n.changeLanguage(next)
    applyHtmlDir(next)
  }

  return (
    <button
      onClick={toggle}
      aria-label="Toggle language"
      className={`
        flex items-center gap-1.5 rounded-lg border border-gray-200
        bg-white hover:bg-gray-50 active:scale-95
        transition-all text-sm font-semibold text-gray-700 shadow-sm
        ${compact ? 'px-2 py-1.5 text-xs' : 'px-3 py-2'}
      `}
    >
      {/* Globe icon */}
      <svg
        xmlns="http://www.w3.org/2000/svg"
        viewBox="0 0 24 24" fill="none"
        stroke="currentColor" strokeWidth={2}
        strokeLinecap="round" strokeLinejoin="round"
        className={compact ? 'h-3.5 w-3.5' : 'h-4 w-4'}
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="2" y1="12" x2="22" y2="12" />
        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
      </svg>

      {/* Current lang indicator */}
      <span className="font-bold tracking-wide">
        {t('lang.current')}
      </span>

      {/* Arrow to next lang */}
      <span className="text-gray-400 text-xs">→</span>
      <span className="text-blue-600">{t('lang.toggle')}</span>
    </button>
  )
}

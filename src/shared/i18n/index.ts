import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import en from './locales/en'
import ar from './locales/ar'

i18n
  .use(LanguageDetector)          // auto-detect browser / localStorage lang
  .use(initReactI18next)
  .init({
    resources: {
      en: { translation: en },
      ar: { translation: ar },
    },
    fallbackLng: 'en',
    supportedLngs: ['en', 'ar'],

    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'crm_lang',
    },

    interpolation: { escapeValue: false },
  })

/** Sync <html dir> and <html lang> with current language */
export function applyHtmlDir(lng: string) {
  const isRtl = lng === 'ar'
  document.documentElement.setAttribute('dir', isRtl ? 'rtl' : 'ltr')
  document.documentElement.setAttribute('lang', lng)
}

// Apply on load
applyHtmlDir(i18n.language)

// Keep in sync when language changes
i18n.on('languageChanged', applyHtmlDir)

export default i18n

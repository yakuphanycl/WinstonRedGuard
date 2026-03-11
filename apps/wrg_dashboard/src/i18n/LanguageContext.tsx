import { createContext, useEffect, useMemo, useState } from "react";
import type { PropsWithChildren } from "react";
import type { Language, MessageKey } from "./messages";
import { messages } from "./messages";

const STORAGE_KEY = "wrg_dashboard_language";

type LanguageContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  t: (key: MessageKey | string) => string;
};

function readLanguage(): Language {
  if (typeof window === "undefined") {
    return "en";
  }
  const raw = window.localStorage.getItem(STORAGE_KEY);
  return raw === "tr" || raw === "en" ? raw : "en";
}

const defaultValue: LanguageContextValue = {
  language: "en",
  setLanguage: () => {},
  t: (key) => messages.en[key as MessageKey] ?? key
};

export const LanguageContext = createContext<LanguageContextValue>(defaultValue);

export function LanguageProvider({ children }: PropsWithChildren): JSX.Element {
  const [language, setLanguage] = useState<Language>(readLanguage);

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORAGE_KEY, language);
    }
  }, [language]);

  const value = useMemo<LanguageContextValue>(() => {
    return {
      language,
      setLanguage,
      t: (key: MessageKey | string) => messages[language][key as MessageKey] ?? messages.en[key as MessageKey] ?? key
    };
  }, [language]);

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>;
}

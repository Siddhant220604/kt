import React, { createContext, useContext, useEffect, useState } from 'react';

const Ctx = createContext(null);
export const ThemeProvider = ({ children }) => {
  const [theme, setTheme] = useState(() => localStorage.getItem('kt_theme') || 'light');
  useEffect(() => {
    document.documentElement.classList.toggle('dark', theme === 'dark');
    localStorage.setItem('kt_theme', theme);
  }, [theme]);
  return <Ctx.Provider value={{ theme, setTheme, toggle: () => setTheme(t => t === 'dark' ? 'light' : 'dark') }}>{children}</Ctx.Provider>;
};
export const useTheme = () => useContext(Ctx);

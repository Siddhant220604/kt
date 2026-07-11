import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from './api';

const DEFAULT_SETTINGS = {
  email: 'kirantraders1996@gmail.com',
};

const Ctx = createContext({});
export const SettingsProvider = ({ children }) => {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const load = async () => {
    try {
      const { data } = await api.get('/settings');
      setSettings({ ...DEFAULT_SETTINGS, ...(data || {}) });
    } catch {
      setSettings(DEFAULT_SETTINGS);
    }
  };
  useEffect(() => { load(); }, []);
  return <Ctx.Provider value={{ settings, reload: load }}>{children}</Ctx.Provider>;
};
export const useSettings = () => useContext(Ctx);

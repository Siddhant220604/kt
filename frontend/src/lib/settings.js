import React, { createContext, useContext, useEffect, useState } from 'react';
import { api } from './api';

const Ctx = createContext({});
export const SettingsProvider = ({ children }) => {
  const [settings, setSettings] = useState({});
  const load = async () => {
    try { const { data } = await api.get('/settings'); setSettings(data || {}); } catch {}
  };
  useEffect(() => { load(); }, []);
  return <Ctx.Provider value={{ settings, reload: load }}>{children}</Ctx.Provider>;
};
export const useSettings = () => useContext(Ctx);

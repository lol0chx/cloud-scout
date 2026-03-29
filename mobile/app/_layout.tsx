import { Stack } from 'expo-router';
import React, { createContext, useContext, useState } from 'react';
import { C } from '../lib/theme';
import type { Sport } from '../lib/types';

interface SportCtx {
  sport: Sport;
  setSport: (s: Sport) => void;
}

export const SportContext = createContext<SportCtx>({ sport: 'NBA', setSport: () => {} });
export const useSport = () => useContext(SportContext);

export default function RootLayout() {
  const [sport, setSport] = useState<Sport>('NBA');
  return (
    <SportContext.Provider value={{ sport, setSport }}>
      <Stack screenOptions={{ headerShown: false, contentStyle: { backgroundColor: C.bg } }} />
    </SportContext.Provider>
  );
}

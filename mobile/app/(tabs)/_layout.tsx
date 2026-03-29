import { Tabs } from 'expo-router';
import React from 'react';
import { Text } from 'react-native';
import { C } from '../../lib/theme';

function Icon({ emoji, focused }: { emoji: string; focused: boolean }) {
  return <Text style={{ fontSize: 20, opacity: focused ? 1 : 0.5 }}>{emoji}</Text>;
}

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: {
          backgroundColor: C.card,
          borderTopColor: C.border,
        },
        tabBarActiveTintColor: C.primary,
        tabBarInactiveTintColor: C.sub,
        tabBarLabelStyle: { fontSize: 10, fontWeight: '600' },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: 'Games', tabBarIcon: ({ focused }) => <Icon emoji="🏟" focused={focused} /> }}
      />
      <Tabs.Screen
        name="form"
        options={{ title: 'Form', tabBarIcon: ({ focused }) => <Icon emoji="📈" focused={focused} /> }}
      />
      <Tabs.Screen
        name="players"
        options={{ title: 'Players', tabBarIcon: ({ focused }) => <Icon emoji="👤" focused={focused} /> }}
      />
      <Tabs.Screen
        name="standings"
        options={{ title: 'Standings', tabBarIcon: ({ focused }) => <Icon emoji="🏆" focused={focused} /> }}
      />
      <Tabs.Screen
        name="predict"
        options={{ title: 'Predict', tabBarIcon: ({ focused }) => <Icon emoji="⚡" focused={focused} /> }}
      />
      <Tabs.Screen
        name="ai"
        options={{ title: 'AI Scout', tabBarIcon: ({ focused }) => <Icon emoji="🤖" focused={focused} /> }}
      />
    </Tabs>
  );
}

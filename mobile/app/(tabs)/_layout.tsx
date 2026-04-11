import { Tabs, Redirect } from 'expo-router';
import { useAuthStore } from '@/stores/authStore';

export default function TabsLayout() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  if (!isAuthenticated) {
    return <Redirect href="/(auth)/welcome" />;
  }

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarStyle: { backgroundColor: '#0A0A0A', borderTopColor: '#1A1A1A' },
        tabBarActiveTintColor: '#F5A623',
        tabBarInactiveTintColor: '#555',
      }}
    >
      <Tabs.Screen
        name="index"
        options={{ title: 'Today', tabBarIcon: ({ color }) => null /* add icon */ }}
      />
      <Tabs.Screen
        name="sweepstakes"
        options={{ title: 'Win', tabBarIcon: ({ color }) => null }}
      />
      <Tabs.Screen
        name="profile"
        options={{ title: 'Profile', tabBarIcon: ({ color }) => null }}
      />
    </Tabs>
  );
}

import { Stack, Redirect } from 'expo-router';
import { useAuthStore } from '@/stores/authStore';

export default function AuthLayout() {
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const user = useAuthStore((s) => s.user);

  // If already authenticated and onboarding complete, redirect to the main app
  if (isAuthenticated && user?.has_completed_onboarding) {
    return <Redirect href="/(tabs)" />;
  }

  return (
    <Stack screenOptions={{ headerShown: false }}>
      <Stack.Screen name="welcome" />
      <Stack.Screen name="onboarding" />
    </Stack>
  );
}

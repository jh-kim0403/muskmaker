/**
 * Welcome / sign-in screen.
 * Apple Sign-In is required on iOS when any social login is offered (App Review 4.8).
 */
import { useState } from 'react';
import { View, Text, StyleSheet, Pressable, ActivityIndicator, Alert } from 'react-native';
import { router } from 'expo-router';
import auth from '@react-native-firebase/auth';
import { AppleAuthenticationButton, AppleAuthenticationButtonType, AppleAuthenticationButtonStyle, signInAsync, AppleAuthenticationScope } from 'expo-apple-authentication';
import { Platform } from 'react-native';

export default function WelcomeScreen() {
  const [loading, setLoading] = useState(false);

  const signInWithApple = async () => {
    setLoading(true);
    try {
      const credential = await signInAsync({
        requestedScopes: [AppleAuthenticationScope.FULL_NAME, AppleAuthenticationScope.EMAIL],
      });
      const { identityToken } = credential;
      if (!identityToken) throw new Error('No identity token');
      const appleCredential = auth.AppleAuthProvider.credential(identityToken);
      await auth().signInWithCredential(appleCredential);
      // Root layout auth listener handles the rest
    } catch (err: any) {
      if (err.code !== 'ERR_REQUEST_CANCELED') {
        Alert.alert('Sign in failed', err.message ?? 'Please try again');
      }
    } finally {
      setLoading(false);
    }
  };

  const signInWithGoogle = async () => {
    // Implement with @react-native-google-signin/google-signin if needed
    Alert.alert('Coming soon', 'Google sign-in will be available soon');
  };

  return (
    <View style={styles.container}>
      <View style={styles.hero}>
        <Text style={styles.title}>MuskMaker</Text>
        <Text style={styles.subtitle}>
          Build real habits.{'\n'}Earn real rewards.
        </Text>
        <Text style={styles.tagline}>
          Complete goals → earn coins → enter sweepstakes.{'\n'}
          No purchase necessary. Odds based on effort.
        </Text>
      </View>

      <View style={styles.authButtons}>
        {loading ? (
          <ActivityIndicator color="#F5A623" size="large" />
        ) : (
          <>
            {Platform.OS === 'ios' && (
              <AppleAuthenticationButton
                buttonType={AppleAuthenticationButtonType.SIGN_IN}
                buttonStyle={AppleAuthenticationButtonStyle.WHITE}
                cornerRadius={12}
                style={styles.appleButton}
                onPress={signInWithApple}
              />
            )}
            <Pressable style={styles.googleButton} onPress={signInWithGoogle}>
              <Text style={styles.googleButtonText}>Continue with Google</Text>
            </Pressable>
          </>
        )}
      </View>

      <Text style={styles.legal}>
        By continuing you agree to our Terms of Service and Privacy Policy.
        No purchase is necessary to participate in sweepstakes.
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#0A0A0A', justifyContent: 'space-between', padding: 32 },
  hero: { flex: 1, justifyContent: 'center', gap: 16 },
  title: { fontSize: 48, fontWeight: '800', color: '#F5A623' },
  subtitle: { fontSize: 28, fontWeight: '700', color: '#FFFFFF', lineHeight: 36 },
  tagline: { fontSize: 15, color: '#888', lineHeight: 22, marginTop: 8 },
  authButtons: { gap: 12, marginBottom: 24 },
  appleButton: { height: 56, width: '100%' },
  googleButton: {
    height: 56, backgroundColor: '#1A1A1A', borderRadius: 12,
    justifyContent: 'center', alignItems: 'center', borderWidth: 1, borderColor: '#333',
  },
  googleButtonText: { color: '#FFF', fontSize: 16, fontWeight: '600' },
  legal: { fontSize: 12, color: '#555', textAlign: 'center', lineHeight: 18 },
});

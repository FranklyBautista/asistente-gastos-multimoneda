import { Link, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, Platform, Text, View } from "react-native";

import { Button, Field, Screen, styles } from "@/components/ui";
import { authErrorMessage } from "@/lib/auth-errors";
import { supabase } from "@/lib/supabase";

export default function LoginScreen() {
  // auth/callback manda aquí con ?error=confirmacion si el enlace del correo no sirvió.
  const { error: callbackError } = useLocalSearchParams<{ error?: string }>();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function signIn() {
    if (!email.trim() || !password) return setError("Escribe tu correo y tu contraseña.");
    setBusy(true);
    setError(null);
    const { error: authError } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password,
    });
    setBusy(false);
    // Con sesión, el layout de (cuenta) redirige al panel solo.
    if (authError) setError(authErrorMessage(authError.code, "signIn"));
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <Screen title="Inicia sesión" subtitle="Asistente de gastos" profile={false}>
        <View style={{ gap: 14 }}>
          {callbackError === "confirmacion" ? (
            <Text style={styles.error} accessibilityRole="alert">
              No se pudo confirmar el correo: el enlace venció o se abrió en otro dispositivo.
              Inicia sesión; si te lo pide, vuelve a registrarte para recibir un correo nuevo.
            </Text>
          ) : null}
          <Field
            label="Correo"
            value={email}
            onChangeText={setEmail}
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
            textContentType="emailAddress"
          />
          <Field
            label="Contraseña"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoComplete="current-password"
            textContentType="password"
            onSubmitEditing={signIn}
          />
          {error ? (
            <Text style={styles.error} accessibilityLiveRegion="polite">
              {error}
            </Text>
          ) : null}
          <Button label={busy ? "Entrando…" : "Entrar"} onPress={signIn} disabled={busy} />
          <Link href="/registro" style={[styles.muted, { textAlign: "center", padding: 12 }]}>
            ¿No tienes cuenta? <Text style={{ color: "#8dfb86" }}>Regístrate</Text>
          </Link>
        </View>
      </Screen>
    </KeyboardAvoidingView>
  );
}

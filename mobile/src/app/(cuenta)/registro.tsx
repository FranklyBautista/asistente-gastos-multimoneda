import { Link } from "expo-router";
import { useState } from "react";
import { KeyboardAvoidingView, Platform, Text, View } from "react-native";

import { Button, Field, Screen, styles } from "@/components/ui";
import { authErrorMessage } from "@/lib/auth-errors";
import { supabase } from "@/lib/supabase";

export default function SignUpScreen() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function signUp() {
    if (!email.trim()) return setError("Escribe tu correo.");
    if (password.length < 8) return setError("La contraseña debe tener al menos 8 caracteres.");
    setBusy(true);
    setError(null);
    // Sin emailRedirectTo: el enlace de confirmación abre la web (site_url) y luego se entra
    // aquí con el correo y la contraseña.
    const { data, error: authError } = await supabase.auth.signUp({
      email: email.trim(),
      password,
    });
    setBusy(false);
    if (authError) return setError(authErrorMessage(authError.code, "signUp"));
    if (!data.session) {
      setNotice("Te enviamos un correo para confirmar la cuenta. Ábrelo y luego inicia sesión.");
    }
  }

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <Screen title="Crea tu cuenta" subtitle="Asistente de gastos">
        <View style={{ gap: 14 }}>
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
            label="Contraseña (mínimo 8 caracteres)"
            value={password}
            onChangeText={setPassword}
            secureTextEntry
            autoComplete="new-password"
            textContentType="newPassword"
            onSubmitEditing={signUp}
          />
          {error ? (
            <Text style={styles.error} accessibilityLiveRegion="polite">
              {error}
            </Text>
          ) : null}
          {notice ? (
            <Text style={styles.notice} accessibilityLiveRegion="polite">
              {notice}
            </Text>
          ) : null}
          <Button label={busy ? "Creando…" : "Crear cuenta"} onPress={signUp} disabled={busy} />
          <Link href="/login" style={[styles.muted, { textAlign: "center", padding: 12 }]}>
            ¿Ya tienes cuenta? <Text style={{ color: "#8dfb86" }}>Inicia sesión</Text>
          </Link>
        </View>
      </Screen>
    </KeyboardAvoidingView>
  );
}

import Ionicons from "@expo/vector-icons/Ionicons";
import { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";

import { Button, styles } from "@/components/ui";
import { useAppLock } from "@/lib/app-lock-provider";
import { supabase } from "@/lib/supabase";
import { colors } from "@/theme";

/**
 * Tapa toda la app mientras falta desbloquear. Pide la huella, el rostro o el PIN apenas
 * aparece; si no se puede, queda cerrar sesión (volver a entrar pide la contraseña).
 */
export function LockScreen() {
  const { locked, ready, unlock } = useAppLock();
  const [failed, setFailed] = useState(false);

  function tryUnlock() {
    void unlock().then((ok) => setFailed(!ok));
  }

  // Se pide apenas aparece la pantalla, sin esperar a que toquen «Desbloquear».
  useEffect(() => {
    if (locked && ready) void unlock().then((ok) => setFailed(!ok));
  }, [locked, ready, unlock]);

  if (!locked) return null;
  // Mientras se revisa la preferencia, solo se tapa el contenido.
  if (!ready) return <View style={lock.cover} />;
  return (
    <View style={lock.cover} accessibilityViewIsModal>
      <Ionicons name="lock-closed" size={44} color={colors.lime} />
      <Text style={styles.title} accessibilityRole="header">
        Tus finanzas están bloqueadas
      </Text>
      <Text style={[styles.muted, { textAlign: "center" }]}>
        Usa tu huella, tu rostro o el PIN del teléfono para verlas.
      </Text>
      <View style={{ alignSelf: "stretch", gap: 10, marginTop: 12 }}>
        <Button label="Desbloquear" onPress={tryUnlock} />
        {failed ? (
          <Button
            label="Cerrar sesión"
            variant="ghost"
            onPress={() => void supabase.auth.signOut()}
          />
        ) : null}
      </View>
    </View>
  );
}

const lock = StyleSheet.create({
  cover: {
    ...StyleSheet.absoluteFill,
    backgroundColor: colors.background,
    alignItems: "center",
    justifyContent: "center",
    padding: 28,
    gap: 12,
  },
});

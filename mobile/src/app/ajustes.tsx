import { useState } from "react";
import { ScrollView, Switch, Text, View } from "react-native";

import { Button, Card, styles } from "@/components/ui";
import { useAppLock } from "@/lib/app-lock-provider";
import { supabase } from "@/lib/supabase";
import { colors } from "@/theme";

/** Ajustes de la app: el bloqueo con biometría y cerrar sesión. */
export default function SettingsScreen() {
  const { available, enabled, setEnabled } = useAppLock();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function toggle(next: boolean) {
    setBusy(true);
    setError(await setEnabled(next));
    setBusy(false);
  }

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.background }}
      contentContainerStyle={styles.content}
    >
      <Card style={{ gap: 10 }}>
        <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
          <View style={{ flex: 1, gap: 4 }}>
            <Text style={styles.subtitle} nativeID="lock-label">
              Bloquear la app
            </Text>
            <Text style={styles.muted}>
              Pide tu huella, tu rostro o el PIN del teléfono al abrirla y al volver después de 30
              segundos.
            </Text>
          </View>
          <Switch
            accessibilityLabelledBy="lock-label"
            accessibilityLabel="Bloquear la app"
            value={Boolean(available && enabled)}
            onValueChange={(next) => void toggle(next)}
            disabled={busy || available === null}
            trackColor={{ false: colors.chip, true: colors.lime }}
            thumbColor={colors.foreground}
          />
        </View>
        {available === false ? (
          <Text style={styles.notice}>
            Tu teléfono no tiene bloqueo de pantalla. Actívalo en los ajustes del teléfono para
            poder usarlo aquí.
          </Text>
        ) : null}
        {error ? (
          <Text style={styles.error} accessibilityLiveRegion="polite">
            {error}
          </Text>
        ) : null}
      </Card>
      <Button label="Cerrar sesión" variant="ghost" onPress={() => void supabase.auth.signOut()} />
    </ScrollView>
  );
}

import { useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { useState } from "react";
import { Text, View } from "react-native";

import { Button, Field, styles } from "@/components/ui";
import { CODE_PATTERN, linkErrorMessage, normalizeCode } from "@/lib/link-errors";
import { redeemLinkCode } from "@/lib/queries";
import { colors } from "@/theme";

/** Canje del código de /vincular con redeem_link_code, con los mismos mensajes que la web. */
export default function LinkScreen() {
  const queryClient = useQueryClient();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function redeem() {
    const normalized = normalizeCode(code);
    if (!CODE_PATTERN.test(normalized)) {
      return setError("El código tiene 8 letras y números (sin I, O, 0 ni 1).");
    }
    setBusy(true);
    setError(null);
    try {
      await redeemLinkCode(normalized);
      await queryClient.invalidateQueries();
      router.back();
    } catch (e) {
      setError(linkErrorMessage(e instanceof Error ? e.message : undefined));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ flex: 1, backgroundColor: colors.background, padding: 20, gap: 14 }}>
      <Text style={styles.body}>
        Escribe /vincular al bot en Telegram y pega aquí el código. Dura 10 minutos.
      </Text>
      <Field
        label="Código"
        value={code}
        onChangeText={setCode}
        autoCapitalize="characters"
        autoCorrect={false}
        maxLength={12}
        placeholder="ABCD2345"
        onSubmitEditing={redeem}
      />
      {error ? (
        <Text style={styles.error} accessibilityLiveRegion="polite">
          {error}
        </Text>
      ) : null}
      <Button label={busy ? "Vinculando…" : "Vincular"} onPress={redeem} disabled={busy} />
    </View>
  );
}

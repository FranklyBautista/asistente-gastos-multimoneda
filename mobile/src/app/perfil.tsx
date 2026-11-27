import Ionicons from "@expo/vector-icons/Ionicons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, Switch, Text, View } from "react-native";

import { Button, Card, ErrorState, LinkBanner, Loading, styles } from "@/components/ui";
import { useAppLock } from "@/lib/app-lock-provider";
import { useAuth } from "@/lib/auth";
import { formatDay } from "@/lib/format";
import { useLinkedUser } from "@/lib/hooks";
import {
  CURRENCY_OPTIONS,
  preferenceErrorMessage,
  RATE_SOURCE_OPTIONS,
  TIMEZONE_OPTIONS,
  timezoneLabel,
} from "@/lib/preferences";
import { type LinkedUser, updatePreferences } from "@/lib/queries";
import { supabase } from "@/lib/supabase";
import { colors, radius } from "@/theme";

/**
 * Todo lo de la cuenta en un lugar: quién eres, el vínculo con Telegram, las preferencias que
 * usa el bot, el bloqueo de la app y cerrar sesión. Las preferencias se guardan con la función
 * update_preferences: la app no escribe la tabla `users` directamente (ADR 0012).
 */
export default function ProfileScreen() {
  const { session } = useAuth();
  const user = useLinkedUser();
  const email = session?.user.email ?? null;

  return (
    <ScrollView
      style={{ flex: 1, backgroundColor: colors.background }}
      contentContainerStyle={styles.content}
    >
      <Identity name={user.data?.displayName ?? null} email={email} user={user.data ?? null} />

      {user.isPending ? (
        <Loading />
      ) : user.isError ? (
        <ErrorState onRetry={() => void user.refetch()} />
      ) : !user.data ? (
        <LinkBanner />
      ) : (
        <>
          <Card style={{ gap: 6 }}>
            <Text style={styles.subtitle} accessibilityRole="header">
              Telegram
            </Text>
            <Text style={[styles.body, { color: colors.lime, fontWeight: "700" }]}>
              Cuenta vinculada
            </Text>
            <Text style={styles.muted}>
              Lo que anotas en el bot aparece aquí. Para vincular otra cuenta, escribe /vincular al
              bot.
            </Text>
          </Card>
          <Preferences user={user.data} />
        </>
      )}

      <AppLockCard />
      <Button label="Cerrar sesión" variant="ghost" onPress={() => void supabase.auth.signOut()} />
    </ScrollView>
  );
}

function initials(name: string | null, email: string | null): string {
  const words = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (words.length >= 2) return (words[0][0] + words[1][0]).toUpperCase();
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (email ?? "?").slice(0, 1).toUpperCase();
}

/** Día local `YYYY-MM-DD` de un instante, en la zona del usuario. */
function localDay(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone }).format(new Date(iso));
}

function Identity({
  name,
  email,
  user,
}: {
  name: string | null;
  email: string | null;
  user: LinkedUser | null;
}) {
  return (
    <Card style={{ alignItems: "center", gap: 6, paddingVertical: 24 }}>
      <View style={local.avatar} accessibilityElementsHidden importantForAccessibility="no">
        <Text style={local.avatarText}>{initials(name, email)}</Text>
      </View>
      <Text style={[styles.title, { textAlign: "center" }]} accessibilityRole="header">
        {name ?? "Tu cuenta"}
      </Text>
      {email ? <Text style={styles.muted}>{email}</Text> : null}
      {user ? (
        <Text style={styles.faint}>
          Usas el asistente desde el {formatDay(localDay(user.createdAt, user.timezone), "medium")}
        </Text>
      ) : null}
    </Card>
  );
}

/**
 * Las preferencias que usa el bot, editables: se guardan al tocar una opción. Al guardar se
 * recargan todos los datos, porque la tasa de los Bs y la zona horaria cambian saldos y fechas.
 */
function Preferences({ user }: { user: LinkedUser }) {
  const queryClient = useQueryClient();
  const save = useMutation({
    mutationFn: updatePreferences,
    onSuccess: () => queryClient.invalidateQueries(),
  });
  // Mientras guarda, la opción tocada ya se ve elegida.
  const shown = { ...user, ...(save.isPending ? save.variables : {}) };
  // Una sola lista abierta a la vez.
  const [open, setOpen] = useState<string | null>(null);
  const toggle = (key: string) => setOpen((current) => (current === key ? null : key));

  return (
    <Card style={{ gap: 4 }}>
      <Text style={styles.subtitle} accessibilityRole="header">
        Preferencias
      </Text>
      <Dropdown
        label="Moneda por defecto"
        hint="La que usa el bot cuando no dices la moneda."
        options={CURRENCY_OPTIONS}
        value={shown.defaultCurrency}
        open={open === "currency"}
        onToggle={() => toggle("currency")}
        disabled={save.isPending}
        onChange={(defaultCurrency) => save.mutate({ defaultCurrency })}
      />
      <Dropdown
        label="Tasa de los Bs"
        hint="Con la que se pasan tus bolívares a dólares."
        options={RATE_SOURCE_OPTIONS}
        value={shown.vesRateSource}
        open={open === "rate"}
        onToggle={() => toggle("rate")}
        disabled={save.isPending}
        onChange={(vesRateSource) => save.mutate({ vesRateSource })}
      />
      <Dropdown
        label="Zona horaria"
        hint="Define dónde empiezan y terminan tus días y tus semanas."
        options={TIMEZONE_OPTIONS}
        value={shown.timezone}
        currentLabel={timezoneLabel(shown.timezone)}
        open={open === "timezone"}
        onToggle={() => toggle("timezone")}
        disabled={save.isPending}
        onChange={(timezone) => save.mutate({ timezone })}
      />
      <View style={[local.row, local.divider]}>
        <View style={{ flex: 1, gap: 4 }}>
          <Text style={styles.label} nativeID="context-label">
            Contexto al anotar
          </Text>
          <Text style={styles.faint}>
            El bot te dice cómo vas con tus topes cada vez que anotas un gasto.
          </Text>
        </View>
        <Switch
          accessibilityLabelledBy="context-label"
          accessibilityLabel="Contexto al anotar"
          value={shown.contextReplies}
          onValueChange={(contextReplies) => save.mutate({ contextReplies })}
          disabled={save.isPending}
          trackColor={{ false: colors.chip, true: colors.lime }}
          thumbColor={colors.foreground}
        />
      </View>
      {save.isError ? (
        <Text style={styles.error} accessibilityLiveRegion="polite">
          {preferenceErrorMessage(save.error.message)}
        </Text>
      ) : null}
    </Card>
  );
}

/**
 * Una preferencia como fila desplegable: muestra el valor elegido y, al tocarla, la lista de
 * opciones debajo. Elegir una la guarda y cierra la lista.
 */
function Dropdown<T extends string>({
  label,
  hint,
  options,
  value,
  currentLabel,
  open,
  onToggle,
  disabled,
  onChange,
}: {
  label: string;
  hint: string;
  options: { value: T; label: string }[];
  value: string;
  /** Lo que se muestra si el valor no está entre las opciones. */
  currentLabel?: string;
  open: boolean;
  onToggle: () => void;
  disabled: boolean;
  onChange: (value: T) => void;
}) {
  const selected = options.find((o) => o.value === value)?.label ?? currentLabel ?? value;
  return (
    <View style={local.divider}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${label}: ${selected}`}
        accessibilityHint={open ? "Cierra la lista" : "Abre la lista de opciones"}
        accessibilityState={{ expanded: open }}
        onPress={onToggle}
        style={({ pressed }) => [local.row, pressed && { opacity: 0.7 }]}
      >
        <Text style={[styles.label, { flex: 1 }]}>{label}</Text>
        <Text style={[styles.body, { fontWeight: "700" }]}>{selected}</Text>
        <Ionicons name={open ? "chevron-up" : "chevron-down"} size={18} color={colors.muted} />
      </Pressable>
      {open ? (
        <View style={{ gap: 6, paddingBottom: 12 }}>
          <View style={local.options}>
            {options.map((o, i) => {
              const isSelected = o.value === value;
              return (
                <Pressable
                  key={o.value}
                  accessibilityRole="button"
                  accessibilityState={{ selected: isSelected, disabled }}
                  disabled={disabled}
                  onPress={() => {
                    if (!isSelected) onChange(o.value);
                    onToggle();
                  }}
                  style={({ pressed }) => [
                    local.option,
                    i > 0 && local.optionDivider,
                    pressed && { backgroundColor: colors.chip },
                  ]}
                >
                  <Text
                    style={[styles.body, isSelected && { color: colors.lime, fontWeight: "700" }]}
                  >
                    {o.label}
                  </Text>
                  {isSelected ? <Ionicons name="checkmark" size={18} color={colors.lime} /> : null}
                </Pressable>
              );
            })}
          </View>
          <Text style={styles.faint}>{hint}</Text>
        </View>
      ) : null}
    </View>
  );
}

/** El bloqueo con biometría. */
function AppLockCard() {
  const { available, enabled, setEnabled } = useAppLock();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function toggle(next: boolean) {
    setBusy(true);
    setError(await setEnabled(next));
    setBusy(false);
  }

  return (
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
          Tu teléfono no tiene bloqueo de pantalla. Actívalo en los ajustes del teléfono para poder
          usarlo aquí.
        </Text>
      ) : null}
      {error ? (
        <Text style={styles.error} accessibilityLiveRegion="polite">
          {error}
        </Text>
      ) : null}
    </Card>
  );
}

const local = StyleSheet.create({
  avatar: {
    width: 72,
    height: 72,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.chip,
    borderWidth: 2,
    borderColor: colors.lime,
    marginBottom: 6,
  },
  avatarText: { color: colors.lime, fontSize: 26, fontWeight: "800" },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 12,
    paddingVertical: 10,
  },
  divider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.line },
  options: {
    borderRadius: radius.row,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.field,
    overflow: "hidden",
  },
  option: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    minHeight: 48,
    paddingHorizontal: 16,
  },
  optionDivider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.line },
});

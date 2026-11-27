import Ionicons from "@expo/vector-icons/Ionicons";
import { Link } from "expo-router";
import type { ReactNode } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  type TextInputProps,
  View,
  type ViewStyle,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { colors, radius } from "@/theme";

/** Pantalla con scroll, márgenes y «tirar para actualizar». */
export function Screen({
  title,
  subtitle,
  children,
  refreshing = false,
  onRefresh,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  return (
    <SafeAreaView style={styles.safe} edges={["top"]}>
      <ScrollView
        contentContainerStyle={styles.content}
        refreshControl={
          onRefresh ? (
            <RefreshControl
              refreshing={refreshing}
              onRefresh={onRefresh}
              tintColor={colors.lime}
              colors={[colors.onLime]}
              progressBackgroundColor={colors.lime}
            />
          ) : undefined
        }
      >
        <Header title={title} subtitle={subtitle} profile />
        {children}
      </ScrollView>
    </SafeAreaView>
  );
}

/** Título de la pantalla; con `profile`, el acceso al Perfil a la derecha. */
export function Header({
  title,
  subtitle,
  profile = false,
}: {
  title: string;
  subtitle?: string;
  profile?: boolean;
}) {
  return (
    <View style={{ flexDirection: "row", alignItems: "flex-end", gap: 12 }}>
      <View style={{ flex: 1, gap: 4 }}>
        {subtitle ? <Text style={styles.muted}>{subtitle}</Text> : null}
        <Text style={styles.title} accessibilityRole="header">
          {title}
        </Text>
      </View>
      {profile ? (
        <Link href="/perfil" asChild>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Perfil"
            hitSlop={8}
            style={styles.iconButton}
          >
            <Ionicons name="person-outline" size={22} color={colors.muted} />
          </Pressable>
        </Link>
      ) : null}
    </View>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function Loading() {
  return (
    <View style={styles.center} accessibilityLabel="Cargando…" accessibilityRole="progressbar">
      <ActivityIndicator color={colors.lime} />
    </View>
  );
}

export function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <Card style={{ gap: 12 }}>
      <Text style={styles.body}>No se pudieron cargar los datos. Revisa tu conexión.</Text>
      <Button label="Reintentar" onPress={onRetry} variant="ghost" />
    </Card>
  );
}

export function Empty({ children }: { children: string }) {
  return (
    <Text style={[styles.muted, { paddingVertical: 24, textAlign: "center" }]}>{children}</Text>
  );
}

/** Aviso para la cuenta web sin vincular: sin vínculo la RLS no devuelve datos (ADR 0012). */
export function LinkBanner() {
  return (
    <Card style={{ gap: 12 }}>
      <Text style={styles.subtitle}>Vincula tu cuenta de Telegram</Text>
      <Text style={styles.body}>
        Escribe /vincular al bot y pega aquí el código de 8 caracteres para ver tus datos.
      </Text>
      <Link href="/vincular" asChild>
        <Button label="Tengo un código" />
      </Link>
    </Card>
  );
}

export function Button({
  label,
  onPress,
  disabled,
  variant = "lime",
}: {
  label: string;
  onPress?: () => void;
  disabled?: boolean;
  variant?: "lime" | "ghost";
}) {
  const lime = variant === "lime";
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ disabled }}
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        lime ? { backgroundColor: colors.lime } : styles.ghost,
        (pressed || disabled) && { opacity: 0.6 },
      ]}
    >
      <Text style={[styles.buttonText, { color: lime ? colors.onLime : colors.lime }]}>
        {label}
      </Text>
    </Pressable>
  );
}

export function Field({ label, ...props }: TextInputProps & { label: string }) {
  return (
    <View style={{ gap: 6 }}>
      <Text style={styles.label}>{label}</Text>
      <TextInput
        accessibilityLabel={label}
        placeholderTextColor={colors.faint}
        style={styles.input}
        {...props}
      />
    </View>
  );
}

export function Chip({
  label,
  selected,
  onPress,
}: {
  label: string;
  selected: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected }}
      onPress={onPress}
      style={[styles.chip, selected && { backgroundColor: colors.lime, borderColor: colors.lime }]}
    >
      <Text style={[styles.chipText, selected && { color: colors.onLime }]}>{label}</Text>
    </Pressable>
  );
}

export const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  content: { padding: 20, paddingBottom: 40, gap: 16 },
  center: { paddingVertical: 32, alignItems: "center" },
  title: { color: colors.foreground, fontSize: 26, fontWeight: "800", letterSpacing: -0.5 },
  subtitle: { color: colors.foreground, fontSize: 17, fontWeight: "700" },
  body: { color: colors.foreground, fontSize: 15, lineHeight: 21 },
  muted: { color: colors.muted, fontSize: 13 },
  faint: { color: colors.faint, fontSize: 12 },
  label: { color: colors.muted, fontSize: 13, fontWeight: "600" },
  card: {
    backgroundColor: colors.surface,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.card,
    padding: 18,
  },
  row: {
    backgroundColor: colors.surface,
    borderColor: colors.line,
    borderWidth: 1,
    borderRadius: radius.row,
    paddingHorizontal: 16,
    paddingVertical: 14,
    gap: 4,
  },
  button: {
    minHeight: 52,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 20,
  },
  ghost: { borderWidth: 1, borderColor: colors.line },
  buttonText: { fontSize: 15, fontWeight: "700" },
  input: {
    minHeight: 52,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.field,
    color: colors.foreground,
    paddingHorizontal: 18,
    fontSize: 15,
  },
  chip: {
    minHeight: 40,
    justifyContent: "center",
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.chip,
    paddingHorizontal: 14,
  },
  chipText: { color: colors.foreground, fontSize: 13, fontWeight: "600" },
  iconButton: {
    width: 44,
    height: 44,
    borderRadius: radius.pill,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.chip,
  },
  error: { color: colors.danger, fontSize: 14 },
  notice: { color: colors.limeSoft, fontSize: 14 },
});

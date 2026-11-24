import Ionicons from "@expo/vector-icons/Ionicons";
import { Redirect, Tabs } from "expo-router";
import type { ComponentProps } from "react";
import type { ColorValue } from "react-native";

import { Loading } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { colors } from "@/theme";

type IconName = ComponentProps<typeof Ionicons>["name"];

function icon(name: IconName) {
  // Los tintes de la barra son strings (colors.lime y colors.muted).
  function TabIcon({ color, size }: { color: ColorValue; size: number }) {
    return (
      <Ionicons name={name} color={typeof color === "string" ? color : undefined} size={size} />
    );
  }
  return TabIcon;
}

/** Las cinco secciones del panel; sin sesión, al login. */
export default function PanelLayout() {
  const { session, loading } = useAuth();
  if (loading) return <Loading />;
  if (!session) return <Redirect href="/login" />;
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.lime,
        tabBarInactiveTintColor: colors.muted,
        tabBarStyle: { backgroundColor: "#08100a", borderTopColor: colors.line },
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Inicio", tabBarIcon: icon("wallet-outline") }} />
      <Tabs.Screen
        name="movimientos"
        options={{ title: "Movimientos", tabBarIcon: icon("list-outline") }}
      />
      <Tabs.Screen
        name="graficas"
        options={{ title: "Gráficas", tabBarIcon: icon("bar-chart-outline") }}
      />
      <Tabs.Screen
        name="cambios"
        options={{ title: "Cambios", tabBarIcon: icon("swap-horizontal-outline") }}
      />
      <Tabs.Screen
        name="deudas"
        options={{ title: "Deudas", tabBarIcon: icon("people-outline") }}
      />
    </Tabs>
  );
}

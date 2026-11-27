import { router, useFocusEffect } from "expo-router";
import { useCallback } from "react";
import { Pressable, Text, useWindowDimensions, View } from "react-native";
import Animated, {
  cancelAnimation,
  Easing,
  type SharedValue,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withRepeat,
  withTiming,
} from "react-native-reanimated";

import { CURRENCY_ACCENT, CurrencyIcon } from "@/components/currency";
import { CURRENCIES, CURRENCY_LABELS, type Currency, formatUsd } from "@/lib/format";
import type { Balance } from "@/lib/queries";
import { colors } from "@/theme";

/** Saldo de todas las cuentas de una moneda (igual que la web). */
export type CurrencyGroup = {
  currency: Currency;
  balance: number;
  /** null si ninguna cuenta de la moneda tiene tasa todavía. */
  balanceUsd: number | null;
};

export function groupByCurrency(balances: Balance[]): CurrencyGroup[] {
  return CURRENCIES.flatMap((currency) => {
    const accounts = balances.filter((b) => b.currency === currency);
    if (accounts.length === 0) return [];
    const priced = accounts.filter((b) => b.balanceUsd !== null);
    const balanceUsd = priced.length ? priced.reduce((s, b) => s + (b.balanceUsd ?? 0), 0) : null;
    return [
      {
        currency,
        balance: accounts.reduce((s, b) => s + b.balance, 0),
        balanceUsd,
      },
    ];
  });
}

/** Ángulos (grados, 0 = derecha, sentido horario) de cada burbuja alrededor del centro. */
function angles(n: number): number[] {
  // Con 4 monedas: Bs arriba a la izquierda, COP arriba a la derecha, USD y USDT abajo.
  if (n === 4) return [-135, -45, 135, 45];
  return Array.from({ length: n }, (_, i) => -90 + (i * 360) / n);
}

function circle(d: number) {
  return { width: d, height: d, borderRadius: d / 2 };
}

/** Grosor del aro de color de cada burbuja, por fuera del ícono. */
const BUBBLE_BORDER = 2;

/** Segundos que tarda una burbuja en dar la vuelta completa al centro. */
const ORBIT_SECONDS = 30;

/**
 * Gira las burbujas mientras la pantalla está visible: se detiene al salir y retoma desde el
 * mismo ángulo al volver. Con "reducir movimiento" activado se quedan quietas.
 */
function useOrbitRotation(): SharedValue<number> {
  const rotation = useSharedValue(0);
  const reduceMotion = useReducedMotion();

  useFocusEffect(
    useCallback(() => {
      if (reduceMotion) return;
      // .get()/.set() en vez de .value: es lo que pide Reanimated con el React Compiler.
      const from = rotation.get() % 360;
      rotation.set(from);
      rotation.set(
        withRepeat(
          withTiming(from + 360, { duration: ORBIT_SECONDS * 1000, easing: Easing.linear }),
          -1,
        ),
      );
      return () => cancelAnimation(rotation);
    }, [reduceMotion, rotation]),
  );

  return rotation;
}

type OrbitingBubbleProps = {
  group: CurrencyGroup;
  /** Ángulo inicial en grados. */
  angle: number;
  rotation: SharedValue<number>;
  size: number;
  bubble: number;
  orbit: number;
};

function OrbitingBubble({ group: g, angle, rotation, size, bubble, orbit }: OrbitingBubbleProps) {
  const label = g.currency === "VES" ? "VES / Bs" : CURRENCY_LABELS[g.currency];
  const color = CURRENCY_ACCENT[g.currency];

  // Solo se traslada (no rota), así el texto de la burbuja siempre queda derecho.
  const orbitStyle = useAnimatedStyle(() => {
    const rad = ((angle + rotation.get()) * Math.PI) / 180;
    return {
      transform: [{ translateX: orbit * Math.cos(rad) }, { translateY: orbit * Math.sin(rad) }],
    };
  });

  return (
    <Animated.View
      style={[
        circle(bubble),
        { position: "absolute", left: (size - bubble) / 2, top: (size - bubble) / 2 },
        orbitStyle,
      ]}
    >
      <Pressable
        onPress={() =>
          router.push({ pathname: "/moneda/[codigo]", params: { codigo: g.currency } })
        }
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityHint="Abre su saldo y sus movimientos"
        style={({ pressed }) => [
          circle(bubble),
          {
            alignItems: "center",
            justifyContent: "center",
            backgroundColor: "#13251a",
            borderWidth: BUBBLE_BORDER,
            borderColor: pressed ? color : `${color}88`,
            shadowColor: color,
            shadowOpacity: 0.35,
            shadowRadius: 10,
            shadowOffset: { width: 0, height: 0 },
            elevation: 8,
            transform: [{ scale: pressed ? 0.95 : 1 }],
          },
        ]}
      >
        {/* La burbuja entera es el ícono; el nombre de la moneda queda en accessibilityLabel. */}
        <CurrencyIcon currency={g.currency} size={bubble - BUBBLE_BORDER * 2} />
      </Pressable>
    </Animated.View>
  );
}

/**
 * El consolidado en una burbuja central con cada moneda alrededor. Tocar una moneda abre su
 * detalle (saldo y movimientos).
 */
export function BalanceOrbit({ groups, totalUsd }: { groups: CurrencyGroup[]; totalUsd: number }) {
  const { width } = useWindowDimensions();
  const size = Math.min(width - 40, 380);
  // Radio del centro 0,27 + hueco 0,04 + radio de burbuja 0,09 = órbita 0,40; el borde de afuera
  // (0,49) cabe en la caja. Las burbujas no tocan el centro.
  const core = size * 0.54;
  const bubble = size * 0.18;
  const orbit = size * 0.4; // radio
  const positions = angles(groups.length);
  const rotation = useOrbitRotation();

  return (
    <View style={{ width: size, height: size, alignSelf: "center" }}>
      {/* Órbita punteada. */}
      <View
        style={[
          circle(orbit * 2),
          {
            position: "absolute",
            left: size / 2 - orbit,
            top: size / 2 - orbit,
            borderWidth: 1,
            borderStyle: "dashed",
            borderColor: "rgba(255, 255, 255, 0.15)",
          },
        ]}
      />

      {/* Centro: el consolidado. */}
      <View
        style={[
          circle(core),
          {
            position: "absolute",
            left: (size - core) / 2,
            top: (size - core) / 2,
            alignItems: "center",
            justifyContent: "center",
            paddingHorizontal: core * 0.08,
            backgroundColor: "#0c1a0f",
            borderWidth: 2,
            borderColor: colors.lime,
            shadowColor: colors.lime,
            shadowOpacity: 0.6,
            shadowRadius: 24,
            shadowOffset: { width: 0, height: 0 },
            elevation: 12,
          },
        ]}
      >
        <Text style={{ color: colors.muted, fontSize: 13, fontWeight: "600" }}>Saldo total</Text>
        <Text
          style={{ color: colors.foreground, fontSize: size * 0.085, fontWeight: "800" }}
          numberOfLines={1}
          adjustsFontSizeToFit
          testID="total-usd"
        >
          {formatUsd(totalUsd)}
        </Text>
        <Text style={{ color: colors.faint, fontSize: 12, marginTop: 2 }}>consolidado en USD</Text>
      </View>

      {/* Una burbuja por moneda, girando alrededor del centro. */}
      {groups.map((g, i) => (
        <OrbitingBubble
          key={g.currency}
          group={g}
          angle={positions[i]}
          rotation={rotation}
          size={size}
          bubble={bubble}
          orbit={orbit}
        />
      ))}
    </View>
  );
}

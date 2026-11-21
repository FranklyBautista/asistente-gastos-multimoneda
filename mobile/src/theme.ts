/**
 * Los mismos colores que la web (web/src/app/globals.css): negro con verde lima de acento.
 * Contrastes: muted y faint pasan 4.5:1 sobre las superficies; sobre el lima va onLime.
 */
export const colors = {
  background: "#050a06",
  surface: "#0f1d12",
  field: "#070e08",
  chip: "#16301b",
  line: "rgba(150, 255, 160, 0.12)",
  foreground: "#eef6ef",
  muted: "#a3b8a6",
  faint: "#8fa693",
  lime: "#8dfb86",
  limeSoft: "#b8ffb0",
  onLime: "#072b0e",
  danger: "#ff8a82",
  warn: "#f5c451",
} as const;

/** Forma: tarjetas 24, filas y campos 18, botones y chips en píldora. */
export const radius = { card: 24, row: 18, pill: 999 } as const;

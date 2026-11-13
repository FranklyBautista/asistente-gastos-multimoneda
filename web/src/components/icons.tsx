/** Íconos de trazo (24×24, color del texto). Decorativos: el texto de al lado dice qué son. */
type IconProps = { className?: string; strokeWidth?: number };

function Svg({
  className = "size-5",
  strokeWidth = 1.9,
  children,
}: IconProps & { children: React.ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className={className}
    >
      {children}
    </svg>
  );
}

export const HomeIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z" />
  </Svg>
);
export const ListIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01" />
  </Svg>
);
export const PieIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M21 12A9 9 0 1 1 12 3v9z" />
    <path d="M15 3.5A9 9 0 0 1 20.5 9H15z" />
  </Svg>
);
export const SwapIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M7 4 3 8l4 4M3 8h14M17 20l4-4-4-4M21 16H7" />
  </Svg>
);
export const SendIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M22 2 11 13M22 2l-7 20-4-9-9-4z" />
  </Svg>
);
export const PlusIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 5v14M5 12h14" />
  </Svg>
);
export const WalletIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 7a2 2 0 0 1 2-2h13v4" />
    <rect x="3" y="7" width="18" height="13" rx="2" />
    <path d="M16 13.5h2" />
  </Svg>
);
export const LogoutIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 17l-5-5 5-5M5 12h11" />
  </Svg>
);
export const ArrowRightIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Svg>
);
export const ChevronLeftIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="m15 18-6-6 6-6" />
  </Svg>
);
export const ChevronRightIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="m9 18 6-6-6-6" />
  </Svg>
);
export const ArrowInIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M17 7 7 17M17 17H7V7" />
  </Svg>
);
export const ArrowOutIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M7 17 17 7M7 7h10v10" />
  </Svg>
);
export const MailIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3" y="5" width="18" height="14" rx="2" />
    <path d="m3 7 9 6 9-6" />
  </Svg>
);
export const LockIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="4" y="11" width="16" height="10" rx="2" />
    <path d="M8 11V7a4 4 0 0 1 8 0v4" />
  </Svg>
);
export const KeyIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="8" cy="15" r="4" />
    <path d="m10.8 12.2 9.2-9.2M17 6l3 3" />
  </Svg>
);
export const FilterIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 6h10M18 6h2M4 12h4M12 12h8M4 18h12" />
    <circle cx="16" cy="6" r="2" />
    <circle cx="10" cy="12" r="2" />
    <circle cx="18" cy="18" r="2" />
  </Svg>
);
export const AlertIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 3 2 20h20zM12 10v4M12 17h.01" />
  </Svg>
);
export const CartIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="9" cy="20" r="1.5" />
    <circle cx="18" cy="20" r="1.5" />
    <path d="M2 3h3l2.7 12.4a1 1 0 0 0 1 .8h9.6a1 1 0 0 0 1-.8L21 7H6" />
  </Svg>
);
const FoodIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 3v8a3 3 0 0 0 3 3v7M10 3v8a3 3 0 0 1-3 3M7 3v7M17 21V3c-2.2 0-4 2.5-4 6v5h4" />
  </Svg>
);
const CarIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 16v-4l2-5h14l2 5v4H3z" />
    <circle cx="7" cy="16" r="2" />
    <circle cx="17" cy="16" r="2" />
  </Svg>
);
const BoltIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M13 2 4 14h7l-1 8 9-12h-7z" />
  </Svg>
);
const HealthIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3" y="7" width="18" height="13" rx="3" />
    <path d="M12 10v7M8.5 13.5h7M9 7V4h6v3" />
  </Svg>
);
const BriefcaseIcon = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3" y="7" width="18" height="13" rx="2" />
    <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 13h18" />
  </Svg>
);
const HouseIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M4 11 12 4l8 7M6 9.5V20h12V9.5M10 20v-5h4v5" />
  </Svg>
);
const PlayIcon = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="m10 8.5 5 3.5-5 3.5z" />
  </Svg>
);
const TagIcon = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9z" />
    <circle cx="7.5" cy="7.5" r="1.5" />
  </Svg>
);

/** Ícono según el nombre de la categoría; las desconocidas llevan una etiqueta. */
export function CategoryIcon({ name, ...p }: IconProps & { name: string | null }) {
  const n = (name ?? "").toLowerCase();
  if (/comida|mercado|restaurant|super/.test(n)) return <FoodIcon {...p} />;
  if (/transporte|gasolina|taxi|pasaje|carro/.test(n)) return <CarIcon {...p} />;
  if (/servicio|luz|agua|internet|tel[eé]fono/.test(n)) return <BoltIcon {...p} />;
  if (/salud|farmacia|m[eé]dic/.test(n)) return <HealthIcon {...p} />;
  if (/hogar|casa|alquiler|renta/.test(n)) return <HouseIcon {...p} />;
  if (/ocio|entreten|diversi/.test(n)) return <PlayIcon {...p} />;
  if (/compra|ropa/.test(n)) return <CartIcon {...p} />;
  if (/sueldo|salario|trabajo|cliente|ingreso|freelance/.test(n)) return <BriefcaseIcon {...p} />;
  return <TagIcon {...p} />;
}

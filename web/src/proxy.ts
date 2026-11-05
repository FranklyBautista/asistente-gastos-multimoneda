import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";

import { supabaseEnv } from "@/lib/supabase/env";

// Rutas que se ven sin sesión; con sesión, redirigen al inicio.
const PUBLIC_PATHS = ["/login", "/registro"];
// Rutas que no exigen ni redirigen (callback de confirmación de correo).
const OPEN_PATHS = ["/auth/"];

/**
 * Refresca la sesión de Supabase en cada navegación (los tokens duran 1 hora) y redirige
 * según haya sesión o no. La autorización real la hace la RLS; esto solo evita mostrar
 * páginas vacías.
 */
export async function proxy(request: NextRequest) {
  let response = NextResponse.next({ request });
  const { url, publishableKey } = supabaseEnv();

  const supabase = createServerClient(url, publishableKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet, headers) {
        for (const { name, value } of cookiesToSet) request.cookies.set(name, value);
        response = NextResponse.next({ request });
        for (const { name, value, options } of cookiesToSet) {
          response.cookies.set(name, value, options);
        }
        // Cabeceras anti-caché que manda Supabase al renovar la sesión.
        for (const [key, value] of Object.entries(headers ?? {})) {
          response.headers.set(key, value);
        }
      },
    },
  });

  // getClaims valida la firma del token; no confiar en getSession() en el servidor.
  const { data } = await supabase.auth.getClaims();
  const signedIn = Boolean(data?.claims);
  const path = request.nextUrl.pathname;

  if (OPEN_PATHS.some((p) => path.startsWith(p))) return response;

  const isPublic = PUBLIC_PATHS.includes(path);
  if (!signedIn && !isPublic) return redirectTo(request, "/login", response);
  if (signedIn && isPublic) return redirectTo(request, "/", response);
  return response;
}

/** Redirige conservando las cookies de sesión que se acaban de renovar. */
function redirectTo(request: NextRequest, path: string, from: NextResponse) {
  const redirect = NextResponse.redirect(new URL(path, request.url));
  for (const cookie of from.cookies.getAll()) redirect.cookies.set(cookie);
  return redirect;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)"],
};

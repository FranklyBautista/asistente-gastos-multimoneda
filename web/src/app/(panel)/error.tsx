"use client";

import Link from "next/link";
import { useEffect } from "react";

/**
 * Si una página del panel falla (la base no responde o rechaza un dato), se muestra este aviso
 * dentro del panel, con la barra y el menú, en vez de la página de error por defecto.
 */
export default function PanelError({ error, retry }: { error: unknown; retry: () => void }) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <section role="alert" className="glass flex flex-col gap-4 rounded-3xl p-5 text-sm">
      <p className="text-base font-bold">No se pudieron cargar los datos.</p>
      <p className="text-muted">
        Revisa tu conexión e inténtalo de nuevo. Si usaste un enlace con filtros, puede que alguno
        no sea válido.
      </p>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => retry()}
          className="btn-lime grid h-12 place-items-center rounded-full px-6 font-bold"
        >
          Reintentar
        </button>
        <Link
          href="/"
          className="glass grid h-12 place-items-center rounded-full px-6 font-semibold text-muted hover:text-foreground"
        >
          Ir al inicio
        </Link>
      </div>
    </section>
  );
}

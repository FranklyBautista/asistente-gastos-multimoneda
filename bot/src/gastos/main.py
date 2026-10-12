"""Arranque del bot: polling en dev, webhook en prod (se implementa en la Fase 2)."""

from gastos.config import get_settings


def run() -> None:
    settings = get_settings()
    print(f"gastos: configuración cargada (env={settings.env}). El bot llega en la Fase 2.")


if __name__ == "__main__":
    run()

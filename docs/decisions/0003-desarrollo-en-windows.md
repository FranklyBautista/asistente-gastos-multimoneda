# 0003. Desarrollo nativo en Windows con `tasks.ps1`

- **Estado:** aceptada
- **Fecha:** 2026-10-12

## Contexto

La guía asumía WSL2 y un `Makefile`. WSL dejó de ser una opción para el entorno de desarrollo, y Windows no trae `make`. Además, el proyecto estaba dentro de una carpeta sincronizada por OneDrive, que bloquea archivos durante la sincronización, sube miles de archivos de `.venv` y subiría `bot/.env` a la nube.

## Decisión

- El proyecto vive en `C:\dev\gastos-multimoneda`, fuera de OneDrive. El respaldo es GitHub.
- Las tareas comunes se ejecutan con `tasks.ps1` (PowerShell 5.1 o superior) en lugar del `Makefile`.
- Herramientas instaladas en Windows: uv y GitHub CLI con winget; Supabase CLI desde el binario oficial de GitHub Releases; pre-commit con `uv tool install`.
- Supabase local usa los puertos 553xx para no chocar con otros proyectos locales.
- `.gitattributes` fuerza finales de línea LF para que el repositorio sea igual en Windows y en el CI (Linux).

## Consecuencias

- No hace falta instalar `make` ni ninguna capa de compatibilidad.
- El CI sigue corriendo en Linux; `tasks.ps1` es solo para desarrollo local. Si una tarea cambia, hay que mantener alineados `tasks.ps1` y los workflows.
- Quien desarrolle en macOS o Linux puede correr los mismos comandos de `uv` y `supabase` a mano (están listados en el script).

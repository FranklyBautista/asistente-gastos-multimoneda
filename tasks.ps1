<#
.SYNOPSIS
    Tareas comunes del proyecto (reemplaza al Makefile en Windows).
.EXAMPLE
    .\tasks.ps1 setup
    .\tasks.ps1 check
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('help', 'setup', 'hooks', 'run', 'check', 'test', 'test-int', 'db-up', 'db-down', 'db-reset', 'db-test')]
    [string]$Task = 'help'
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Bot = Join-Path $Root 'bot'

# Ejecuta un comando en una carpeta y corta la tarea si devuelve un codigo distinto de 0.
function Invoke-Step {
    param([string]$Dir, [string]$Exe, [string[]]$Arguments = @())
    Write-Host "> $Exe $($Arguments -join ' ')" -ForegroundColor Cyan
    Push-Location $Dir
    try {
        # PowerShell 5.1 trata la salida de stderr como error; solo cuenta el codigo de salida.
        $ErrorActionPreference = 'Continue'
        & $Exe @Arguments
        if ($LASTEXITCODE -ne 0) { throw "Error en: $Exe $($Arguments -join ' ')" }
    }
    finally {
        Pop-Location
    }
}

function Invoke-BotChecks {
    Invoke-Step $Bot 'uv' @('run', 'ruff', 'check', '.')
    Invoke-Step $Bot 'uv' @('run', 'ruff', 'format', '--check', '.')
    # pyright y lint-imports se llaman por Python: Windows Application Control bloquea sus .exe.
    Invoke-Step $Bot 'uv' @('run', 'python', '-m', 'pyright')
    Invoke-Step $Bot 'uv' @('run', 'python', '-c', 'import sys; from importlinter.cli import lint_imports; sys.exit(lint_imports())')
    Invoke-Step $Bot 'uv' @('run', 'pytest', 'tests/unit', '-q')
}

switch ($Task) {
    'setup'    { Invoke-Step $Bot 'uv' @('sync') }
    'hooks'    {
        if (-not (Get-Command pre-commit -ErrorAction SilentlyContinue)) {
            Invoke-Step $Root 'uv' @('tool', 'install', 'pre-commit')
        }
        Invoke-Step $Root 'pre-commit' @('install')
    }
    'run'      { Invoke-Step $Bot 'uv' @('run', 'python', '-m', 'gastos.main') }
    'test'     { Invoke-Step $Bot 'uv' @('run', 'pytest', 'tests/unit', '-q') }
    'test-int' { Invoke-Step $Bot 'uv' @('run', 'pytest', 'tests/integration', '-q') }
    'db-up'    { Invoke-Step $Root 'supabase' @('start') }
    'db-down'  { Invoke-Step $Root 'supabase' @('stop') }
    'db-reset' { Invoke-Step $Root 'supabase' @('db', 'reset') }
    'db-test'  { Invoke-Step $Root 'supabase' @('test', 'db') }
    'check'    {
        Invoke-BotChecks
        Invoke-Step $Bot 'uv' @('run', 'pytest', 'tests/integration', '-q')
        Invoke-Step $Root 'supabase' @('test', 'db')
    }
    'help'     {
        Write-Host 'Uso: .\tasks.ps1 <tarea>'
        Write-Host '  setup     instala las dependencias del bot (uv sync)'
        Write-Host '  run       arranca el bot en modo polling (requiere bot\.env y db-up)'
        Write-Host '  hooks     instala pre-commit (ruff + gitleaks)'
        Write-Host '  check     lint, formato, tipos, capas, pruebas (unit + integracion) y pgTAP'
        Write-Host '  test      solo las pruebas unitarias del bot'
        Write-Host '  test-int  pruebas de integracion contra Supabase local'
        Write-Host '  db-up     levanta Supabase local (requiere Docker Desktop)'
        Write-Host '  db-down   detiene Supabase local'
        Write-Host '  db-reset  reaplica migraciones y seed'
        Write-Host '  db-test   corre las pruebas pgTAP'
    }
}

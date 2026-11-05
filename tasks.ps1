<#
.SYNOPSIS
    Tareas comunes del proyecto (reemplaza al Makefile en Windows).
.EXAMPLE
    .\tasks.ps1 setup
    .\tasks.ps1 check
#>
param(
    [Parameter(Position = 0)]
    [ValidateSet('help', 'setup', 'hooks', 'run', 'check', 'test', 'test-int', 'eval', 'image', 'db-up', 'db-down', 'db-reset', 'db-test', 'web-setup', 'web', 'web-check', 'e2e')]
    [string]$Task = 'help'
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
$Bot = Join-Path $Root 'bot'
$Web = Join-Path $Root 'web'

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
    'eval'     { Invoke-Step $Bot 'uv' @('run', 'python', 'eval/run_eval.py') }
    'image'    { Invoke-Step $Bot 'docker' @('build', '-t', 'gastos-bot:local', '.') }
    'db-up'    { Invoke-Step $Root 'supabase' @('start') }
    'db-down'  { Invoke-Step $Root 'supabase' @('stop') }
    'db-reset' { Invoke-Step $Root 'supabase' @('db', 'reset') }
    'db-test'  { Invoke-Step $Root 'supabase' @('test', 'db') }
    'web-setup' { Invoke-Step $Web 'npm' @('install') }
    'web'      { Invoke-Step $Web 'npm' @('run', 'dev') }
    'web-check' {
        Invoke-Step $Web 'npm' @('run', 'lint')
        Invoke-Step $Web 'npm' @('run', 'format:check')
        Invoke-Step $Web 'npx' @('next', 'typegen')
        Invoke-Step $Web 'npm' @('run', 'typecheck')
        Invoke-Step $Web 'npm' @('run', 'build')
    }
    'e2e'      {
        # La prueba crea el usuario del bot con la llave de servicio de Supabase local.
        # PowerShell 5.1 trata el stderr de la CLI como error; solo interesa el JSON de stdout.
        $ErrorActionPreference = 'Continue'
        $status = (& supabase status -o json 2>$null | Out-String) | ConvertFrom-Json
        $ErrorActionPreference = 'Stop'
        if (-not $status.SECRET_KEY) { throw 'Supabase local no responde: corre .\tasks.ps1 db-up' }
        $env:SUPABASE_SECRET_KEY = $status.SECRET_KEY
        Invoke-Step $Web 'npm' @('run', 'build')
        Invoke-Step $Web 'npm' @('run', 'e2e')
    }
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
        Write-Host '  eval      mide la extraccion con Gemini real (bot\eval, consume cuota)'
        Write-Host '  image     construye la imagen Docker de produccion (bot\Dockerfile)'
        Write-Host '  db-up     levanta Supabase local (requiere Docker Desktop)'
        Write-Host '  db-down   detiene Supabase local'
        Write-Host '  db-reset  reaplica migraciones y seed'
        Write-Host '  db-test   corre las pruebas pgTAP'
        Write-Host '  web-setup instala las dependencias de la web (npm install)'
        Write-Host '  web       arranca la web en modo desarrollo (requiere web\.env.local y db-up)'
        Write-Host '  web-check lint, formato, tipos y build de la web'
        Write-Host '  e2e       pruebas de Playwright de la web contra Supabase local'
    }
}

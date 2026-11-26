# Запуск агента в Windows PowerShell 5.1+:
#   .\run.ps1 docs\requirements.pdf reports\report.md
# При первом запуске создаёт виртуальное окружение .venv и ставит зависимости.
param(
    [Parameter(Mandatory = $true)][string]$InputPath,
    [Parameter(Mandatory = $true)][string]$OutputPath,
    [Parameter(ValueFromRemainingArguments = $true)]$Rest
)
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot
$py = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) {
    Write-Host "Создаю окружение .venv ..."
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw "Не найден Python 3.9+. Установите его с python.org и повторите." }
    & $py -m pip install --disable-pip-version-check -q -r requirements.txt
}
if (-not (Test-Path ".env")) {
    Write-Host "Нет файла .env: скопируйте .env.example в .env и впишите ключ (см. README)." -ForegroundColor Yellow
    exit 2
}
& $py -m lsj $InputPath $OutputPath @Rest
exit $LASTEXITCODE

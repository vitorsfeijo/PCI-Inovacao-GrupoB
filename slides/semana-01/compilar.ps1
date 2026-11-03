param([string]$Engine = 'pdflatex')
$ErrorActionPreference = 'Stop'

function Invoke-LaTeX([string]$Source, [int]$Passes = 1) {
    New-Item -ItemType Directory -Path 'build' -Force | Out-Null
    $stem = [IO.Path]::GetFileNameWithoutExtension($Source)
    for ($pass = 1; $pass -le $Passes; $pass++) {
        $output = & $Engine '-interaction=nonstopmode' '-halt-on-error' '-file-line-error' '-output-directory=build' $Source 2>&1
        $code = $LASTEXITCODE
        $output | Out-File -LiteralPath "build/$stem-console.txt" -Encoding utf8
        if ($code -ne 0) {
            $output | Select-Object -Last 45 | Write-Host
            throw "Falha ao compilar $Source. Consulte build/$stem.log."
        }
    }
    Copy-Item -LiteralPath "build/$stem.pdf" -Destination "$stem.pdf" -Force
    Write-Host "Compilado: $stem.pdf"
}

Push-Location $PSScriptRoot
try {
    Push-Location 'figs'
    try {
        Invoke-LaTeX '01-rotas-e-regras.tex'
        Invoke-LaTeX '02-planejamento-com-regras.tex'
        Invoke-LaTeX '03-reposicao-no-plano.tex'
    } finally { Pop-Location }
    Invoke-LaTeX 'pitch.tex' 2
} finally { Pop-Location }

# 宿主机构建前端后启动 compose（避免 web 镜像依赖 node 基础镜像）。
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

npm --prefix frontend ci
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

npm --prefix frontend run build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

docker compose up --build -d

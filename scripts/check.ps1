$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "Checking Python syntax..." -ForegroundColor Cyan
python -m py_compile `
  "backend\main.py" `
  "backend\database.py" `
  "backend\models.py" `
  "backend\security.py" `
  "backend\RAG\config_data.py" `
  "backend\RAG\rag.py" `
  "backend\RAG\knowledge_base.py" `
  "backend\RAG\vector_stores.py" `
  "backend\RAG\ragas_evaluator.py" `
  "backend\agent\agent_controller.py" `
  "backend\agent\answer_agent.py" `
  "backend\agent\task_planner.py" `
  "backend\agent\evaluator_agent.py" `
  "backend\agent\retrieval_agent.py"

Write-Host "Building frontend..." -ForegroundColor Cyan
npm --prefix frontend run build

Write-Host "Checks completed." -ForegroundColor Green

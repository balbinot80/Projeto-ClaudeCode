# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Status

This project is newly initialized and does not yet contain source code.

## GitHub Repository

- **URL:** https://github.com/balbinot80/Projeto-ClaudeCode
- **Visibilidade:** Privado
- **Branch principal:** `main`

## Sincronização Automática com GitHub

Este projeto está configurado para sincronizar automaticamente com o GitHub a cada resposta do Claude Code via um hook `Stop` em `.claude/settings.json`.

**Como funciona:**
- Ao final de cada resposta do Claude, o hook verifica se há alterações não commitadas
- Se houver, executa `git add -A`, cria um commit com timestamp e faz `git push`
- A mensagem de commit segue o padrão: `Auto-update: YYYY-MM-DD HH:MM:SS`

**Para desativar temporariamente:**
- Acesse `/hooks` no Claude Code e desabilite o hook Stop
- Ou remova o bloco `"Stop"` de `.claude/settings.json`

**Para commitar manualmente:**
```
git add -A
git commit -m "sua mensagem aqui"
git push
```

## Commands

<!-- Add build, test, and lint commands here as the project grows. Example:
- Build: `npm run build`
- Test: `npm test`
- Lint: `npm run lint`
-->

## Regras de Negócio

As regras de negócio completas do sistema estão documentadas em [`REGRAS_NEGOCIO.md`](REGRAS_NEGOCIO.md).

Esse arquivo descreve: glossário, regra de competência, todas as telas e abas, cálculos de nível/premiações/estoque/compras, lógica de entradas e saídas, e como o cache funciona. Leia antes de alterar qualquer lógica de negócio.

## Architecture

**Stack:** Python + Streamlit (frontend/backend), Supabase (persistência), API Jueri (ERP externo).

**Estrutura principal:**
- `app.py` — roteamento, autenticação, sidebar
- `src/pages/` — uma tela por arquivo
- `src/logic/` — regras de negócio puras (sem UI)
- `src/api/jueri_client.py` — acesso à API com cache em duas camadas
- `src/api/cache_supabase.py` — operações de cache no Supabase

# Anki Deck Generator

## What This Is

`Anki Deck Generator` e um CLI em Python para gerar decks de vocabulario do Anki a partir de palavras frequentes, provedores configuraveis e exportacao final em `.apkg`. O proximo passo do produto e transformar o pipeline textual em um fluxo orientado por IA, com frases mais naturais e campos semanticamente corretos, sem perder a base brownfield que ja funciona.

## Core Value

Gerar cards de vocabulario uteis e semanticamente corretos a partir de palavras frequentes, com qualidade suficiente para exportar o deck final sem grande retrabalho manual.

## Requirements

### Validated

- ✓ Usuario pode gerar um deck Anki `.apkg` a partir do CLI com palavras frequentes e templates configurados — existing
- ✓ Usuario pode obter definicao, traducao, frase de exemplo e audio por meio de provedores configuraveis com fallback — existing
- ✓ Usuario pode reutilizar cache, resume/progresso e logs estruturados durante a geracao — existing
- ✓ Usuario pode exportar metadados, fila de revisao e relatorio de qualidade junto do deck final — existing

### Active

- [ ] O motor deve gerar frases principalmente com IA, usando `vocabGenarator.py` como referencia para prompt e logica de chamada
- [ ] O motor deve usar IA para revisar ou corrigir traducao e definicao antes de aceitar um card
- [ ] O pipeline deve eliminar cards duplicados e elevar a taxa final de aprovacao para acima de 60%
- [ ] O fluxo novo deve continuar baseado em `wordfreq` e niveis de frequencia, mas funcionar como motor generico para os idiomas configurados
- [ ] O fluxo novo deve preservar export `.apkg`, audio/TTS, cache/resume e integracoes necessarias do deck atual

### Out of Scope

- Trocar `wordfreq` por curadoria manual ou outra fonte principal de palavras — a selecao por frequencia continua sendo a base do produto
- Remover exportacao `.apkg`, audio/TTS ou o mecanismo de cache/resume — essas capacidades precisam continuar disponiveis
- Reescrever o produto como aplicacao web ou servico hospedado — o foco atual continua sendo o pipeline CLI existente

## Context

- A base atual tem taxa de adesao/aprovacao final em torno de 20%
- O uso de fontes web como Tatoeba para frases nao esta produzindo qualidade suficiente
- O servico de traducao atual gera traducoes de frases com erro
- Definicoes geradas por IA frequentemente nao representam o significado real da palavra
- Cards aprovados hoje ainda podem sair duplicados ou com campos errados
- `vocabGenarator.py` ja provou uma qualidade melhor de geracao de frases em outro projeto e sera usado como referencia para a nova logica de IA
- O codebase atual ja possui capacidades que precisam ser preservadas: audio/TTS, cache, resume, logs, relatorios de qualidade e exportacao `.apkg`

## Constraints

- **Tech stack**: Python 3.11 e a arquitetura atual de `ankideck_generator` — o produto ja roda sobre esse stack e nao sera refeito agora
- **Compatibility**: `wordfreq`, niveis de frequencia, audio/TTS, cache/resume e export `.apkg` devem continuar funcionando durante a mudanca
- **Quality**: sucesso significa frases naturais, traducao boa, definicao certa, ausencia de duplicatas e taxa final de aprovacao acima de 60%
- **Product shape**: a melhoria deve resultar em um motor generico para os idiomas configurados, nao em um fluxo travado para um unico idioma

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| IA sera a fonte principal para geracao de frases | As fontes web atuais nao entregam qualidade suficiente e `vocabGenarator.py` mostrou resultados melhores | — Pending |
| IA tambem revisara traducao e definicao | Trocar apenas a frase nao resolve os erros semanticos que hoje derrubam a aprovacao final | — Pending |
| `wordfreq`, niveis, audio/TTS, cache/resume e export `.apkg` permanecem como base | O produto ja possui uma pipeline operacional util e a melhoria precisa aumentar qualidade sem quebrar o fluxo existente | — Pending |
| A evolucao deve ser pensada como motor generico para idiomas configurados | O objetivo nao e otimizar so um caminho local, mas melhorar a logica central da geracao | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check -> still the right priority?
3. Audit Out of Scope -> reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-15 after initialization*

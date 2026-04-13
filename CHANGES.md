# CHANGES — O que remover e alterar no código

Este arquivo descreve precisamente o que deve ser **removido**, **alterado** ou **substituído** no código
para corrigir os problemas identificados na geração de decks.

---

## REMOVER

### `time_budget` — Limite de tempo por nível
**Problema:** O gerador para antes de concluir todos os cards (ex: 673/1000, 603/1000).
**Ação:** Remover completamente a verificação de tempo que dispara `"stopping by time budget"`.
**Onde procurar:** Loop principal de geração de cards — condição do tipo `if elapsed > time_budget`.

---

### `sentence_template_fallback` — Templates de frases
**Problema:** 97.7% das frases geradas são templates inválidos (`"Это слово X"`).
**Ação:** Remover toda a lógica de construção de frases via template pré-definido.
**Onde procurar:** Função de fallback chamada quando Tatoeba não retorna resultado.
**Nunca gerar frases como:**
```
"Это слово еще."
"Это слово будет."
"Это слово которые."
"Это слово который."
"Это слово эти."
"Это слово между."
"Это слово этой."
"Это слово города."
"Это слово каждый."
"Это слово нибудь."
```

---

### Seleção de palavras por ordem arbitrária / aleatória
**Problema:** A seleção atual não segue frequência real do idioma.
**Ação:** Remover a lógica atual de seleção de palavras e substituir pela lista de frequência.

---

## ALTERAR

### Fonte de seleção de palavras → lista de frequência por idioma
**Problema:** Palavras não seguem ordem de relevância/frequência.
**Novo comportamento:** Usar lista de palavras ordenada por frequência de uso real no idioma.
**Implementação sugerida:**
```python
# Opção 1 — biblioteca wordfreq
from wordfreq import top_n_list
words = top_n_list('ru', 1000)  # Top 1000 palavras em russo

# Opção 2 — arquivo .txt de frequência por idioma
# Ex: https://en.wiktionary.org/wiki/Wiktionary:Frequency_lists/Russian
```

---

### Geração de `Definitions` → definição real e primária
**Problema:** Definições incorretas ou inúteis (ex: `"alternative spelling of ещё"` para `еще`).
**Novo comportamento:**
- Retornar o **significado principal** da palavra (ex: `"more / still / yet"` para `еще`)
- Nunca retornar "alternative spelling of X" como definição principal
- Se a palavra tiver múltiplos sentidos, listar os 2-3 principais
**Onde procurar:** Função responsável por buscar/gerar o campo `definitions` ou `meaning`.

---

### Fallback de geração de frases → IA (sem template)
**Problema:** Quando Tatoeba falha, o sistema recorre a templates ruins.
**Novo comportamento:** Quando Tatoeba não retornar resultado, chamar IA com prompt adequado.
**Prompt sugerido para a IA:**
```
Gere uma frase natural em [IDIOMA] que use a palavra "[PALAVRA]" em contexto real.
A frase deve soar como algo que um falante nativo diria no dia a dia.
Não use construções artificiais ou didáticas.
```

---

### Validação de qualidade de frase antes de aceitar
**Problema:** Frases sem sentido passam pelo filtro atual.
**Novo comportamento:** Antes de aceitar uma frase, validar:
- [ ] A palavra-alvo aparece na frase em contexto real (não isolada)
- [ ] A frase tem no mínimo N palavras (sugestão: 5)
- [ ] A frase não é quase idêntica a outra já aceita no deck (similaridade < 85%)

---

### `tatoeba_hit_rate: 0.0%` para russo — investigar e corrigir
**Problema:** Nenhuma frase foi encontrada no Tatoeba para russo (2019 palavras tentadas).
**Ação:** Investigar:
1. O endpoint/API do Tatoeba está configurado corretamente para russo (`lang=rus`)?
2. A query está no formato correto?
3. Há algum rate-limit ou bloqueio de rede?

---

## MANTER / NÃO ALTERAR

- Estrutura de níveis (Level 1, Level 2, Level 3) — manter, apenas remover o time budget
- Formato de exportação do deck (Anki / CSV / etc.) — não alterar
- Lógica de geração por IA quando usada corretamente — manter e promover como fallback principal

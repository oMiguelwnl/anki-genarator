# TODO — Melhorias na Geração de Decks

## 🔴 Alta Prioridade

### 1. Remover o limite de tempo (time budget)
- [ ] Localizar o parâmetro `time_budget` (aprox. `20.0 min`) no código de geração de decks
- [ ] Remover ou desativar a lógica de `stopping by time budget`
- [ ] Garantir que o loop rode até processar todos os cards (ex: 1000/1000)

---

### 2. Remover o fallback para templates de frases
- [ ] Localizar a lógica de `sentence_template_fallback` no código
- [ ] Remover ou desativar completamente o uso de templates pré-definidos (atualmente responsável por 97.7% das frases)
- [ ] Garantir que o sistema nunca recorra a templates como `"Это слово X"` para montar frases
- [ ] Após remoção, revalidar que `template` não aparece mais em `source_mix`

---

### 3. Corrigir frases geradas por seed (frases inválidas/sem sentido)
- [ ] Identificar onde o seed é usado para montar frases
- [ ] Remover a lógica de seed que gera construções como:
  - `"Это слово еще."` / `"Это слово будет."` / `"Это слово которые."` etc.
- [ ] Substituir por busca real de frases com a palavra-alvo em contexto natural
- [ ] Adicionar validação mínima: rejeitar frases onde a palavra aparece isolada sem contexto

---

### 4. Corrigir a geração de Definitions
- [ ] Identificar a fonte atual das definições (ex: dicionário, API, scraping)
- [ ] Corrigir erros como: `еще` → definição incorreta `"adverb: alternative spelling of ещё"` em vez de `"more / still / yet"`
- [ ] Garantir que a definição retorne o **significado real e primário** da palavra
- [ ] Remover entradas do tipo "alternative spelling of X" como definição principal
- [ ] Adicionar fallback para IA **somente** quando nenhuma definição confiável for encontrada

---

### 5. Seleção de palavras por frequência no idioma
- [ ] Integrar uma fonte de lista de palavras por frequência para cada idioma suportado
  - Opções recomendadas:
    - [Wiktionary Frequency Lists](https://en.wiktionary.org/wiki/Wiktionary:Frequency_lists)
    - `wordfreq` (biblioteca Python) — `pip install wordfreq`
    - Corpus OPUS / OpenSubtitles por idioma
- [ ] Substituir a seleção atual de palavras pela ordem de frequência (mais comum primeiro)
- [ ] Garantir que o deck gerado siga essa ordem (Level 1 = palavras mais frequentes, etc.)

---

### 6. Eliminar frases duplicadas ou quase-duplicadas
- [ ] Adicionar verificação de similaridade entre frases já geradas no mesmo deck
- [ ] Rejeitar frases com similaridade acima de um threshold (ex: 85%) em relação a frases já aceitas
- [ ] Exemplo a evitar: `"Это слово которые"` e `"Это слово который"` no mesmo deck

---

## 🟡 Média Prioridade

### 7. Integrar lógica de geração de frases do projeto externo
- [ ] Revisar o código Python do outro projeto que gera frases e definitions superiores
- [ ] Identificar as funções/módulos reutilizáveis
- [ ] Planejar a integração ou substituição da lógica atual pela do projeto externo
- [ ] Testar geração comparativa antes e depois da integração

---

### 8. Melhorar o fallback de geração de frases por IA
- [ ] Quando Tatoeba não retornar resultado, usar IA (não template) como fallback
- [ ] Garantir que o prompt enviado à IA solicite uma frase **natural e contextualizada** com a palavra-alvo
- [ ] Adicionar critério de rejeição de frases geradas por IA que sejam artificiais ou sem sentido

---

## 🟢 Baixa Prioridade / Validação

### 9. Logging e métricas pós-geração
- [ ] Atualizar o `Run summary` para incluir:
  - Taxa de frases rejeitadas por baixa qualidade
  - Fonte real de cada frase (Tatoeba / IA / outro corpus)
  - Cobertura das palavras mais frequentes geradas com sucesso
- [ ] Remover ou renomear `sentence_template_fallback_hit` do summary (após remoção da feature)

---

## 📝 Notas

- O sistema atualmente tem `tatoeba_hit_rate: 0.0%` para russo — investigar se é problema de conectividade, idioma não suportado, ou configuração da query
- A geração por IA (`ai=2.3%`) é a mais confiável até agora; deve ser promovida como fallback principal (não template)
- Referência de qualidade: projeto Python externo com geração superior (a ser integrado)

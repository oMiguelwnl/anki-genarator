# 🤖 **Prompt para IA Gerar Código Python - Anki Deck Generator**

## **Contexto do Projeto**

Crie um programa Python que gera decks para o Anki automaticamente, usando palavras mais frequentes de uma língua escolhida, com estrutura em três níveis e validações de qualidade.

## **📋 Requisitos Técnicos Detalhados**

### **1. Entrada do Usuário**

- Interface CLI que permita escolher entre 6 idiomas: inglês, espanhol, francês, italiano, alemão, russo
- Opção para modo teste (gera 20 palavras por nível) ou modo completo (3000 palavras)
- Opção para modo interativo (editar/revisar cards)

### **2. Estrutura dos Dados**

```python
class CardData:
    def __init__(self):
        self.focus: str = ""          # Palavra principal
        self.index: int = 0           # Ranking (apenas nível 1)
        self.ipa: str = ""            # Transcrição fonética
        self.definition: str = ""     # Definição na língua estudada
        self.sentence: str = ""       # Frase exemplo
        self.translation: str = ""    # Tradução (não para nível 3)
        self.audio: str = ""          # Caminho/HTML do áudio
        self.level: int = 1           # 1, 2 ou 3
        self.language: str = ""       # Código do idioma
```

### **3. Processamento em Níveis**

#### **Nível 1:**

- Usar biblioteca `wordfreq` para obter 1000 palavras mais frequentes do idioma escolhido
- Ordenar por frequência e atribuir índice

#### **Nível 2:**

- Gerar 1000 palavras aleatórias que sejam "i+1" em relação ao nível 1
- Implementar lógica para identificar palavras relacionadas/similares

#### **Nível 3:**

- 1000 palavras aleatórias com definições apenas na língua estudada
- Sem campo de tradução

### **4. Providers (com fallback)**

Implementar sistema de rotação com prioridade:

1. **Definições:** WordNet → Wiktionary API → Google Dictionary
2. **Traduções:** Google Translate → DeepL → LibreTranslate
3. **Áudio:** Google TTS → ResponsiveVoice → local TTS
4. **Frases:** Tatoeba → WordInContext → gerador próprio

### **5. Validações Obrigatórias**

```python
VALIDATIONS = {
    "no_duplicate_focus": True,
    "no_duplicate_sentences": True,
    "focus_in_sentence": True,
    "valid_characters": True,
    "ipa_format": True,
    "audio_generated": True,
    "definition_not_literal_translation": True,
    "sentence_length": (5, 20),
    "sentence_difficulty_matches_level": True,
    "ai_quality_check": False  # Opcional
}
```

### **6. Cache e Persistência**

- Salvar definições/traduções em JSON local para evitar reprocessamento
- Auto-save a cada 10 palavras processadas
- Capacidade de retomar processamento interrompido
- Logs detalhados em JSON com: palavra, provider usado, validações passadas, timestamp

### **7. Modo Interativo**

- Permitir editar cada campo antes de confirmar
- Opção para pular palavra atual
- Ver estatísticas em tempo real

### **8. Geração do Deck Anki**

- Usar biblioteca `genanki` para criar deck .apkg
- Implementar templates HTML/CSS conforme especificado
- Incluir áudio como arquivos embutidos

### **9. Estatísticas e Saída**

- Gerar arquivo JSON com metadados
- Mostrar progresso em tempo real na CLI
- Exportar deck .apkg final

## **🛠️ Dependências Necessárias**

```python
REQUIRED_PACKAGES = [
    "genanki>=0.13.0",      # Geração decks Anki
    "wordfreq>=3.0.0",      # Frequência de palavras
    "requests>=2.28.0",     # APIs HTTP
    "googletrans==4.0.0rc1", # Tradução
    "gtts>=2.3.0",          # Text-to-speech Google
    "pycountry>=22.3.0",    # Códigos idiomas
    "nltk>=3.8.0",          # Processamento linguístico
    "colorama>=0.4.6",      # Cores no terminal
    "tqdm>=4.65.0",         # Barra de progresso
    "pydantic>=2.0.0",      # Validação de dados
    "langdetect>=1.0.9"     # Detecção de idioma
]
```

## **📁 Estrutura de Arquivos**

```
ankideck_generator/
├── main.py                    # Ponto de entrada
├── config.yaml               # Configurações
├── core/
│   ├── __init__.py
│   ├── deck_builder.py       # Lógica principal
│   ├── providers.py          # APIs de dados
│   ├── validators.py         # Validações
│   ├── cache_manager.py      # Cache local
│   └── models.py             # Classes de dados
├── utils/
│   ├── __init__.py
│   ├── language_tools.py     # Helper de idiomas
│   ├── file_utils.py         # Manipulação de arquivos
│   └── logger.py             # Sistema de logs
├── templates/
│   ├── card_front.html       # Template front
│   ├── card_back.html        # Template back
│   └── styles.css            # Estilos CSS
├── data/
│   ├── cache/                # Cache JSON
│   ├── audio/                # Arquivos de áudio
│   └── logs/                 # Logs de execução
└── tests/                    # Testes unitários
```

## **🚀 Funcionalidades-Chave a Implementar**

1. **CLI interativa com opções:**

```bash
$ python main.py --language es --mode full --interactive
$ python main.py --language en --mode test --output deck.apkg
```

2. **Sistema de cache inteligente:**

```python
# Se tradução já existe no cache, não consultar API
if word in translation_cache:
    return translation_cache[word]
```

3. **Processamento com fallback:**

```python
def get_translation(word, target_lang):
    for provider in [GoogleTranslator, DeepLTranslator, LibreTranslator]:
        try:
            return provider.translate(word, target_lang)
        except Exception as e:
            continue
    raise TranslationError("All providers failed")
```

4. **Validação automática:**

```python
def validate_card(card):
    errors = []
    if not 5 <= len(card.sentence.split()) <= 20:
        errors.append("Sentence length invalid")
    if card.focus not in card.sentence:
        errors.append("Focus word not in sentence")
    # ... mais validações
    return errors
```

5. **Geração progressiva com savepoint:**

```python
def process_words(words):
    for i, word in enumerate(words):
        if i % 10 == 0:
            save_progress(current_state)
        # Processar palavra...
```

## **🎯 Exemplo de Fluxo**

```
1. Usuário seleciona idioma: "es"
2. Programa baixa 1000 palavras mais frequentes em espanhol
3. Para cada palavra:
   a. Busca definição em espanhol
   b. Gera frase de exemplo
   c. Traduz frase para português
   d. Gera áudio da frase
   e. Valida todos os campos
   f. Cacheia resultados
   g. Salva progresso a cada 10 palavras
4. Gera nível 2 (palavras i+1)
5. Gera nível 3 (sem traduções)
6. Compila deck Anki com templates
7. Exporta arquivo .apkg
```

## **✅ Critérios de Aceitação**

- [ ] Gera deck com 3000 palavras (1000 por nível)
- [ ] Funciona para todos os 6 idiomas suportados
- [ ] Validações implementadas e funcionando
- [ ] Cache evita chamadas API desnecessárias
- [ ] Modo interativo permite revisão/edição
- [ ] Modo teste funciona (60 cartões)
- [ ] Retoma de processamento interrompido
- [ ] Arquivo .apkg gerado é importável no Anki
- [ ] Templates renderizam corretamente
- [ ] Estatísticas salvas em JSON

## **📝 Instruções para IA**

Implemente o código Python seguindo:

1. **Modularidade**: Separe responsabilidades em módulos
2. **Tratamento de erros**: Log detalhado, fallback automático
3. **Performance**: Cache eficiente, processamento assíncrono quando possível
4. **Extensibilidade**: Fácil adicionar novos idiomas/providers
5. **Qualidade**: Código limpo, tipado, documentado
6. **UI/UX**: CLI amigável com cores e progresso visual

**Comece por:**

1. Configurar estrutura de pastas
2. Implementar modelos de dados (Pydantic)
3. Criar sistema de cache
4. Implementar providers básicos
5. Adicionar validações
6. Criar CLI
7. Integrar com genanki
8. Testar com modo teste primeiro

**Dica**: Implemente versão mínima viável primeiro (apenas inglês, apenas Google Translate), depois expanda funcionalidades.

---

**Prompt para IA**: "Implemente o código Python completo para o Anki Deck Generator conforme especificado acima. Inclua todos os módulos, tratamento de erros, cache, validações, e geração do arquivo .apkg. Use práticas modernas de Python e as bibliotecas sugeridas."

# Anki Deck Generator

## Python recomendado

Use Python **3.11**. O `googletrans` nao e estavel no Python 3.13 e pode falhar ao importar dependencias.

## Execucao recomendada

Para gerar o deck final completo, execute sem retomada:

```bash
python -m ankideck_generator --language es --mode full --no-resume --output output/deck.apkg
```

`--resume` existe para retomada de processamento, mas nao e recomendado para export final.

## Preflight de IA

Com `strict_quality: true`, a execucao valida no startup se ha provedor de IA configurado (chave + endpoint + modelos). Configure no `.env`:

```bash
ANKI_AI_KEY=...
# opcional
GROQ_API_KEY_1=...
GROQ_API_KEY_2=...
```

Os campos do card devem ser:

| Campo       | Descrição                                                 | Presente em         |
| ----------- | --------------------------------------------------------- | ------------------- |
| Focus       | Palavra a ser aprendida                                   | Todos               |
| Index       | Índice da palavra no ranking de frequência                | Nível 1             |
| IPA         | Transcrição fonética da palavra (Focus)                   | Todos               |
| Definition  | Definição da palavra na língua estudada                   | Todos               |
| Sentence    | Frase exemplo na língua estudada contendo a palavra Focus | Todos               |
| Translation | Tradução da frase (Sentence)                              | Apenas Níveis 1 e 2 |
| Image       | Campo para imagem (não preenchido automaticamente)        | Todos               |
| Audio       | Áudio da frase (Sentence)                                 | Todos               |

Estilização dos campos:

### Front Template

```html
<div class="card front">
  <div class="focus">{{Focus}}</div>
  {{#IPA}}
  <div class="ipa">{{IPA}}</div>
  {{/IPA}} {{#Audio}}
  <div class="audio-controls">{{Audio}}</div>
  {{/Audio}} {{#Sentence}}
  <div class="sentence">{{Sentence}}</div>
  {{/Sentence}}
  <script>
    const audio = document.querySelector("audio");
    if (audio) audio.play().catch((e) => console.log("Auto-play blocked"));
  </script>
</div>
```

### Back Template

```html
<div class="card back">
  {{FrontSide}}
  <hr class="answer-divider" />
  {{#Translation}}
  <div class="translation">{{Translation}}</div>
  {{/Translation}}
  <div class="definition">{{Definition}}</div>
  {{#Image}}
  <div class="image-container">{{Image}}</div>
  {{/Image}}
</div>
```

### Styling (CSS)

.card {
text-align: center;
color: #e0e0e0;
background-color: #121212;
padding: 5px;
border-radius: 15px;
width: 100%;
font-family: serif;
margin: 0 auto;
box-sizing: border-box;
}

.focus {
font-size: 36px;
font-weight: bold;
color: #64b5f6;
margin: 18px 0;
text-shadow: 0 0 8px rgba(100, 181, 246, 0.3);
letter-spacing: 1px;
}

.ipa {
font-size: 14px;
color: #666;
margin-bottom: 10px;
letter-spacing: 2px;
}

.sentence {
font-size: 18px;
color: #b0bec5;
font-style: normal;
margin: 10px 0;
padding: 0 10px;
line-height: 1.6;
}

.translation {
font-size: 18px;
color: #b0bec5;
margin: 18px 0;
padding: 0 10px;
line-height: 1.6;
}

.definition {
font-size: 16px;
color: #90caf9;
margin: 45px 12px;
padding: 12px;
padding-left: 18px;
line-height: 1.5;
border-left: 3px solid #90caf9;
text-align: left;
}

.audio-controls {
margin: 15px 0;
display: flex;
justify-content: center;
align-items: center;
gap: 12px;
}

.replay-button {
background: rgba(100, 181, 246, 0.2);
border: none;
color: #64b5f6;
font-size: 24px;
width: 42px;
height: 42px;
border-radius: 50%;
cursor: pointer;
}

.image-container img {
max-width: 100%;
max-height: 280px;
border-radius: 12px;
border: 1px solid #333;
box-shadow: 0 3px 10px rgba(0, 0, 0, 0.2);
margin: 15px 0;
}

.divider {
border: none;
height: 1px;
background: linear-gradient(to right, transparent, #333, transparent);
}

.answer-divider {
border: none;
height: 2px;
background: linear-gradient(to right, transparent, #555, transparent);
margin: 5px 10%;
}

- As frases do Sentence estão sem sentido 
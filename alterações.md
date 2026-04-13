Remover essa "stopping by time budget" quero que ele rode até o fim.

Generating deck for Russian...
Level 1: stopping by time budget (20.0 min)
Level 1: 67%|███████████████████████████████████████████████ | 673/1000 [19:59<09:43, 1.78s/card]
Level 2: stopping by time budget (20.0 min)
Level 2: 60%|██████████████████████████████████████████▏ | 603/1000 [20:00<13:10, 1.99s/card]
Level 3: stopping by time budget (20.0 min)
Level 3: 63%|████████████████████████████████████████████▍ | 634/1000 [20:00<11:32, 1.89s/card]

Run summary da geracao de deck full em russo:
A mudança mais drástica e importante está na seção Sentence source stats:

tatoeba_hit_rate: 0.0%: A busca no Tatoeba falhou completamente. Nenhuma frase foi encontrada para as 2019 palavras tentadas.
source_mix: ... template=97.7%: Esta é a grande novidade. Quase todas as frases (97.7%) foram criadas usando um "template" (um modelo pré-definido).
sentence_template_fallback_hit: 1901: Este número confirma que 1901 frases foram geradas com sucesso usando esse método de fallback (plano B).
sentence:ai: ... ai=2.3%: A geração de frases por IA foi usada muito pouco, apenas como um último recurso.

- frases (97.7%) foram criadas usando um "template" (um modelo pré-definido), remova isso nao quero que ele recorra á um template .

- Quero que a seleção das palavras, seja as palavras mais comuns no idioma por ordem, voce vai ter que encontrar e algo que te mostre quais sao essas palavras, assim gerar os cards,
- Essa coisa de seed separa frases horriveis como por exemplo:"Это слово еще.","Это слово будет" , nenhum humano usa uma frase como essa.
- O significado "Definitions" está completamente errado em alguns decks, por exemplo: palavra->еще que significa more, está com o seguinte Definitions -> "adverb: alternative spelling of ещё.
- Isso é apenas algums exemplos, por isso quero mudar essa forma de seleção/criação de frases, para que não tenha esses problemas.
- Tem frases que sao praticamente iguais Ex: "Это слово которые", "Это слово который."
- "Это слово эти, Это слово между, Это слово этой, Это слово города,Это слово каждый,Это слово нибудь." Frases pessimas horríveis como essas foram geradas. É para gerar ou encontrar frases que tenha a palavra que voce esta buscando, mas nao frases ridiculas como essas
- Quero que a logica de geração das definition seja a defição da palavra sem nenhum error

- Faça uma lista de todo, com postos a serem removidos e/ou alterados no codigo para que as frases sejam geradas corretamente.

- Eu tenho um codigo pyton de um outro projeto que gera frases, defenition muito superiores ao que esse projeto esta gerando

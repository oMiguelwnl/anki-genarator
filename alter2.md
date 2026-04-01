-

- O tatoeba_hit_rate: 0.4%, isso é muito pouco.

- Quero reestruturar essa parte de geração e busca de frases. Quero que me explique o funcionamente de procura de frases no tatoeba, se ele tem sistema de nível. Eu quero saber como encontrar uma frase que seja mais natural entre todas as outras frases que contenha a palavra. Se o range de tamanho das frases está impedindo, ou outra validação que impede essa busca.

- no Nível 3, o uso do Tatoeba foi muito maior (level3_source_mix: tatoeba=82.9%), eu acho que é o tamanho da frase que enterfere no uso, me diga se é isso mesmo.

- O Stage timings consumindo um total de 2.503.519 milissegundos (cerca de 41 minutos,), isso é muito lento.

- Quero que me explique o que é o stage timings, e quais são os processos que estão consumindo mais tempo. Quero entender se tem como otimizar isso, ou se é algo que não tem como ser otimizado.

- O Serviço de TTS que esta configurado nao foi adicionado ao card, mesmo sem estar no nivel de teste.

- Quero criar um arquivo que padronize a geração de Definitions, me propoe como fazer isso. Pois elas estao sem algum padrao, por exemplo, "нет
  /ɲɛt/
  DEFINITIONS:
  particle: there is not, there are no .mw-parser-output .object-usage-tag{font-style:italic}.mw-parser-output .deprecated{color:var} [ with genitive",

  Tem algumas com espaçamento errado, может
  /может/
  DEFINITIONS:
  adverb: maybe , perhaps , possibly.

Me explique o como funciona o definition_missing pois no card Em 5232 tentativas, o script não conseguiu encontrar uma definição para a palavra.

- Como nao é possivel gerar uma frase com a palavra, sendo que o projeto pode gerar uma com ai ?

- Ocorreram 5260 falhas ao tentar gerar uma frase de exemplo para a palavra. Isso significa que, mesmo que a palavra e a definição fossem válidas, a falta de uma frase de exemplo fez com que o cartão fosse descartado

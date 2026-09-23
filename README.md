# SortInator

Aplicação local para Windows 11 que vigia Downloads, pede a classificação dos
ficheiros académicos e mantém uma biblioteca pesquisável por disciplina,
tópico e tipo de conteúdo, com cópias de segurança do catálogo.

**Índice:** [Vídeo](#vídeo) · [Funcionalidades](#funcionalidades) ·
[Proteção dos ficheiros](#proteção-dos-ficheiros) · [Instalação no
Windows](#instalação-no-windows) · [Área de
notificação](#área-de-notificação) · [Cópias de
segurança](#cópias-de-segurança) · [Dados e privacidade](#dados-e-privacidade) ·
[Atualização e reversão](#atualização-e-reversão) ·
[Desinstalação](#desinstalação) · [Limitações atuais](#limitações-atuais) ·
[Contribuir](#contribuir) · [Política de assinatura de código](#política-de-assinatura-de-código) · [Licenças](#licenças)

## Vídeo

[![Vídeo de apresentação do SortInator](https://github.com/user-attachments/assets/93e18966-5711-49b7-adc9-3c25867b47b5)](https://github.com/user-attachments/assets/e362318e-088a-42be-adcc-72284971a93a)





*Vídeo de apresentação — 22 segundos. Clica para ver com música.*

## Funcionalidades

**Vigilância e recolha**

- Vigia apenas os novos ficheiros elegíveis na pasta Downloads configurada; as
  extensões aceites são configuráveis nas Definições.
- Move cada ficheiro para uma caixa de entrada segura antes de pedir uma decisão.
- Permite importar ficheiros existentes manualmente em lotes limitados.
- Recupera operações interrompidas sem adivinhar quando o estado é ambíguo.

**Decisão de organização**

- O popup mostra a sugestão de disciplina e tipo e espera pela tua decisão;
  também pode fechar sozinho após N segundos, se ativares essa opção nas
  Definições.
- Permite escolher disciplina, tipo de conteúdo, nome final e uma tarefa
  opcional com prazo.
- Deteta quando o mesmo ficheiro já existe no catálogo e mostra onde está:
  podes abrir o existente ou substituir a versão anterior, que fica na pasta
  com o sufixo «versão anterior» e é reposta se desfizeres a organização.
- "Mais tarde" mantém o ficheiro na Caixa de Entrada; "✕" e "Não é da
  universidade" devolvem-no à pasta de origem.
- Organiza sem substituir silenciosamente ficheiros existentes.
- Move um documento já organizado para outro tipo da mesma disciplina ou para
  outra disciplina, mantendo o catálogo e a pesquisa atualizados.

**Pesquisa e indexação**

- Mantém pesquisa textual local no nome e no conteúdo dos formatos suportados
  (PDF, DOCX, PPTX, XLSX, IPYNB, Markdown, TXT e CSV), com índice SQLite FTS.
- Lê PDFs digitalizados (só imagem) com o OCR do Windows, quando a opção está
  ativa.
- Permite adotar no catálogo um ficheiro já existente numa disciplina sem o
  mover, e marcar ocorrências de reconciliação como revistas.
- Mantém histórico e permite desfazer a organização mais recente.

**Organização de estudo**

- Gere disciplinas com código, cor, palavras-chave e arquivo, e as respetivas
  pastas por tipo de conteúdo.
- Mantém tarefas com prazo, calendário e aviso antecipado configurável.

**Integração com o Windows**

- Menu de contexto do Explorador: "Organizar com SortInator" para os
  ficheiros com as extensões configuradas; "Devolver" repõe-nos na pasta de
  origem.
- Notificações nativas clicáveis ("Mostrar na pasta") que continuam
  funcionais depois de fechar a app.
- Vive na área de notificação e pode iniciar com a sessão do Windows.
- Cinco temas e interface em português, inglês, espanhol ou francês.

**Navegação por teclado**

- `Ctrl+K` abre a paleta de comandos: escreve para filtrar e executa ações como
  navegar entre páginas, importar de Downloads, pausar ou retomar a vigilância,
  desfazer a última organização, procurar atualizações, abrir a pasta
  Universidade ou criar uma cópia de segurança.
- `Ctrl+F` foca a pesquisa de apontamentos; `Ctrl+1` a `Ctrl+6` abrem as
  páginas diretamente.
- No popup de organização, as teclas `1` a `9` escolhem a disciplina.

**Cópias de segurança**

- Cria cópias do catálogo e das definições, exporta-as num `.zip` portátil,
  importa-as de volta e restaura-as com validação completa.
- As cópias manuais nunca são apagadas automaticamente.

## Proteção dos ficheiros

O SortInator não substitui nem elimina documentos silenciosamente. Aguarda que
um download deixe de ser temporário e permaneça estável, usa nomes alternativos
como `nome (2).pdf` em caso de colisão e regista cada movimento para permitir
recuperação depois de uma interrupção. Estados ambíguos ficam visíveis para
revisão manual em vez de serem corrigidos por tentativa.

Substituir a versão anterior nunca apaga o ficheiro existente: o antigo é
renomeado com o sufixo «versão anterior» e o par de movimentos é revertido
quando desfazes a organização.

Ficheiros que já estavam em Downloads antes do arranque não são importados
automaticamente. A importação manual exige confirmação e processa no máximo 25
ficheiros de cada vez.

As cópias de segurança e as reposições abrangem apenas o catálogo e as
definições. Nem as atualizações nem as restaurações tocam na pasta Universidade
nem em Downloads.

Ao sair, as operações de ficheiros já aceites terminam antes de fechar a app.
Enquanto estiverem em curso, guardar definições ou instalar uma atualização
fica bloqueado com uma explicação. Cópias interrompidas durante a recolha
ficam para revisão manual na Caixa de Entrada.

## Instalação no Windows

O instalador por utilizador é a forma recomendada. Instala em
`%LOCALAPPDATA%\Programs\SortInator` sem pedir administrador, cria a entrada
no menu Iniciar (e, se quiseres, um atalho no ambiente de trabalho) e aparece
em **Aplicações instaladas** para desinstalar.

1. Abre a versão pretendida na página
   [Releases](https://github.com/Parrolas/SortInator/releases).
2. Transfere `SortInator-<versão>-Setup.exe` e o ficheiro `.sha256` com o
   mesmo nome.
3. Verifica o SHA-256 no PowerShell:

   ```powershell
   Get-FileHash .\SortInator-<versão>-Setup.exe -Algorithm SHA256
   Get-Content .\SortInator-<versão>-Setup.exe.sha256
   ```

4. Confirma que os dois valores são iguais e executa o `Setup.exe`. Fecha o
   SortInator pelo menu do ícone antes de instalar ou desinstalar.

### Versão portátil (ZIP)

Também podes usar `SortInator-<versão>-windows-x64.zip`. Verifica o `.sha256`
da mesma forma, extrai todo o ZIP para uma pasta permanente e executa
`SortInator.exe`. Não movas apenas o executável: a pasta `_internal` que o
acompanha também é necessária.

O executável ainda não tem assinatura de código. O Microsoft Defender
SmartScreen pode mostrar "O Windows protegeu o PC" na primeira execução. Se o
ficheiro veio da página oficial e o SHA-256 coincide, escolhe **Mais
informações** e depois **Executar mesmo assim**. Não ignores o aviso se a
origem ou o hash não forem os esperados.

Na primeira execução, escolhe a pasta Universidade. Por predefinição, a
aplicação usa `Documentos\Universidade`, cria `_Caixa de Entrada` dentro dessa
pasta e vigia a pasta Downloads conhecida pelo Windows. Tudo pode ser alterado
em **Definições**, incluindo as extensões aceites, o modelo do nome e as
notificações.

## Área de notificação

Fechar a janela principal não termina a aplicação: esconde-a na área de
notificação para continuar a vigiar Downloads. O menu do ícone permite abrir a
Caixa de Entrada, pausar a vigilância, desfazer a última organização, procurar
e instalar atualizações, abrir as Definições e sair.

As notificações de arquivo são nativas do Windows: clicar numa abre a pasta com
o ficheiro selecionado, mesmo depois de fechar a app. Num lote com vários
destinos, a notificação lista os ficheiros numa janela com a ação "Mostrar na
pasta".

## Cópias de segurança

Em **Definições → Cópias de segurança** podes criar uma cópia manual do
catálogo e das definições, exportá-la para um `.zip` portátil (por exemplo,
para uma pen ou para outra pasta) e restaurá-la mais tarde.

- **Criar cópia agora** cria uma cópia interna em
  `%LOCALAPPDATA%\SortInator\backups`.
- **Criar e exportar .zip…** cria a cópia e escreve também um ficheiro
  `SortInator-backup-<data>.zip` na pasta que escolheres.
- **Restaurar…** lista as cópias disponíveis (manuais, anteriores a uma
  atualização e anteriores a uma reposição) e permite importar um `.zip`. A
  reposição valida o manifesto e todos os hashes, cria primeiro uma cópia de
  segurança automática dos dados atuais e só depois substitui o catálogo e as
  definições; a app reabre sozinha para concluir. Os teus documentos não são
  tocados.
- As cópias manuais nunca são apagadas automaticamente. As cópias automáticas
  (antes de atualizar ou de repor) mantêm as duas mais recentes de cada tipo,
  no máximo durante 30 dias.

Uma cópia abrange o catálogo, o histórico, o índice de pesquisa e as
definições — não inclui os documentos da pasta Universidade, que continuam a
ser os ficheiros originais.

## Dados e privacidade

O SortInator trabalha localmente. Não envia ficheiros, nomes, conteúdo ou
estatísticas para serviços externos; a verificação de atualizações contacta
apenas o GitHub para ler o número da versão mais recente.

Os dados internos ficam em `%LOCALAPPDATA%\SortInator`:

- `settings.json`: definições da aplicação.
- `sortinator.db`: catálogo, histórico e índice de pesquisa SQLite.
- `backups\`: cópias de segurança do catálogo e das definições.
- `updates\`: estado transitório das atualizações.
- `sortinator.log`: diagnóstico local com rotação.

Os documentos continuam na pasta Universidade escolhida pelo utilizador. A
aplicação nunca usa a base de dados como cópia dos documentos.

## Atualização e reversão

A app verifica automaticamente se existe uma versão nova no arranque (podes
desativar isto nas Definições). Quando existe, aparece "Instalar atualização"
no menu do ícone; um clique transfere, verifica o SHA-256 publicado e a
versão do pacote, prepara a atualização numa área isolada e só depois reinicia
para aplicar. Um assistente dedicado espera que a app antiga termine, troca as
pastas com verificação de cada passo e só confirma quando a nova versão arranca
com sucesso. Os teus dados ficam sempre em `%LOCALAPPDATA%\SortInator` e nunca
são tocados pela atualização.

A app segue as versões estáveis publicadas. Uma versão prévia (prerelease)
instala-se manualmente com o respetivo Setup ou ZIP.

Antes de qualquer migração da base de dados, a app cria uma cópia de segurança
automática (base de dados e definições) e só a fecha depois de um arranque
completo. Se a nova versão falhar antes de ficar saudável — incluindo depois da
troca de pastas — a versão e os dados anteriores são repostos automaticamente e
o resultado é mostrado uma vez no arranque seguinte. Depois de saudável, nunca
há reposição automática de dados: a versão anterior é mantida para recuperação
manual.

A versão anterior é mantida numa pasta de segurança até o novo arranque correr
com sucesso, servindo de reversão imediata se algo correr mal.

Antes de atualizar manualmente:

1. Usa **Sair** no ícone da área de notificação.
2. Cria uma cópia de segurança em **Definições → Cópias de segurança** (ou
   copia a pasta `%LOCALAPPDATA%\SortInator`).
3. Conserva o Setup/ZIP da versão atual até confirmares a nova versão.
4. Instala o novo Setup ou extrai a nova versão para uma pasta nova e
   executa-a.

As migrações da base de dados são automáticas. Para reverter, termina a
aplicação, volta ao Setup/ZIP anterior e restaura também a cópia dos dados
feita por essa versão. Não mistures uma base de dados já migrada com um
executável mais antigo. Os documentos da pasta Universidade não precisam de ser
restaurados.

## Desinstalação

**Instalador (recomendado):**

1. Em **Definições**, desativa **Iniciar o SortInator quando entro no
   Windows** e guarda (a desinstalação também limpa esse registo).
2. Usa **Sair** no ícone da área de notificação.
3. Em **Aplicações instaladas** do Windows, desinstala **SortInator**.

A desinstalação remove o programa, os atalhos e os registos no Windows, mas
mantém `%LOCALAPPDATA%\SortInator` para que possas reinstalar sem perder o
catálogo.

**Versão portátil:**

1. Usa **Sair** no ícone da área de notificação.
2. Elimina a pasta onde extraíste a aplicação.
3. Se também quiseres apagar o catálogo, histórico, definições, cópias e logs,
   elimina `%LOCALAPPDATA%\SortInator`.

Em qualquer dos casos, a desinstalação não elimina a pasta Universidade nem os
documentos nela guardados.

## Limitações atuais

- Os PDFs digitalizados (só imagem) são lidos pelo OCR do Windows quando a
  opção está ativa nas Definições. As línguas preferidas seguem o idioma da
  app (português, inglês, espanhol ou francês), com recurso ao inglês; sem o
  pacote de idioma instalado, esses ficheiros entram na pesquisa apenas pelo
  nome.
- `.doc`, `.ppt`, `.xls` e ficheiros OneNote podem ser organizados, mas o
  conteúdo não é indexado.
- Documentos com mais de 50 MB são organizados sem indexação para limitar
  memória em segundo plano.
- O texto indexado por documento é limitado para proteger a base de dados;
  documentos muito longos ficam pesquisáveis pelo início.
- As sugestões aprendidas dependem de padrões de nome repetidos e continuam a
  exigir confirmação.
- O menu de contexto do Explorador só aparece para as extensões configuradas
  nas Definições.
- O popup de organização trata um ficheiro de cada vez; os restantes ficam em
  fila até serem revistos.
- As cópias de segurança abrangem o catálogo e as definições, não os
  documentos.
- Mudanças entre discos diferentes preservam conteúdo, datas e atributos
  básicos, mas não fluxos de dados alternativos (ADS), ACLs, encriptação nem
  dispersão; estes casos ficam registados no diagnóstico.

## Contribuir

As instruções de desenvolvimento, build e publicação estão em
[CONTRIBUTING.md](CONTRIBUTING.md). O
[roteiro de uma semana de uso](docs/daily-use-checklist.md) ajuda a registar
problemas concretos antes de escolher a próxima melhoria.

## Política de assinatura de código

**Code signing policy.** Free code signing provided by SignPath.io, certificate by
SignPath Foundation.

As versões publicadas do SortInator são assinadas digitalmente através do programa
de código aberto da SignPath Foundation, que verifica que cada binário foi
construído a partir deste repositório. A chave privada do certificado é gerada e
guardada no módulo de segurança (HSM) da SignPath; nunca sai de lá.

Funções da equipa (todas desempenhadas por José Parrolas,
[@Parrolas](https://github.com/Parrolas)):

- Committers e revisores: o mantenedor do repositório.
- Aprovadores: o mantenedor do repositório.

Política de privacidade: [PRIVACY.md](PRIVACY.md) — a aplicação funciona
localmente e não transfere informação para outros sistemas em rede, exceto a
verificação de atualizações no GitHub quando está ativa. Código de conduta:
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Licenças

O código do SortInator é distribuído sob a licença MIT em `LICENSE`. O pacote
Windows inclui componentes de terceiros com licenças próprias, documentados em
`LICENSES/THIRD-PARTY-NOTICES.md` e nos respetivos textos de licença.

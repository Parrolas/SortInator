# ruff: noqa: E501
"""English, Spanish and French translations for Organizador.

Keys are the Portuguese source strings. English is complete; Spanish and
French mirror it. A missing key falls back to the Portuguese source at
runtime, and the parity tests keep the three languages aligned.
"""

from __future__ import annotations

EN_STRINGS: dict[str, str] = {
    "Notificação indisponível": "Notification unavailable",
    "A notificação expirou ou algum ficheiro já não está disponível. Consulta os ficheiros na app.": "The notification expired or a file is no longer available. Browse your files in the app.",
    "A terminar o Organizador": "Closing Organizador",
    "A concluir {count} operações de ficheiros antes de sair…": "Finishing {count} file operations before closing…",
    "A concluir a cópia de segurança antes de sair…": ("Finishing the backup before closing…"),
    "Espera que as operações de ficheiros terminem antes de guardar.": "Wait for file operations to finish before saving.",
    "Atualização em espera": "Update waiting",
    "Espera que as operações de ficheiros terminem antes de atualizar.": "Wait for file operations to finish before updating.",
    "Não foi possível preparar a recolha do ficheiro.": "Could not prepare the file transfer into the inbox.",
    "Download com recolha interrompida; o original foi mantido para revisão.": "Download transfer interrupted; the original was kept for review.",
    "Cópia por verificar; pode estar incompleta. Compara com o original em Downloads.": "Unverified copy; it may be incomplete. Compare it with the original in Downloads.",
    "Ver existente": "View existing",
    "Substituir a versão anterior": "Replace the previous version",
    "A versão atual fica na pasta com o sufixo «versão anterior».": "The current version stays in the folder with the \u201cprevious version\u201d suffix.",
    "Já tens este ficheiro em {location}: {name}": "You already have this file in {location}: {name}",
    "versão anterior": "previous version",
    "Renomeação de versão interrompida; o original foi mantido para revisão.": "Version rename interrupted; the original was kept for review.",
    "Cópia da versão anterior por verificar; compara os ficheiros.": "Unverified previous-version copy; compare the files.",
    " Os outros {count} ficam em Downloads para um próximo lote.": (
        " The other {count} stay in Downloads for a later batch."
    ),
    " bytes": " bytes",
    " dias": " days",
    "({count}) por organizar": "({count}) to organize",
    "1 dia antes": "1 day before",
    "1 resultado · os parênteses retos mostram a correspondência": (
        "1 result · square brackets mark the match"
    ),
    "1 semana antes": "1 week before",
    "2 dias antes": "2 days before",
    "3 dias antes": "3 days before",
    "A aplicação não conseguiu abrir o catálogo local. Consulta organizador.log antes de tentar novamente.\n\n{error}": (
        "The application could not open the local catalog. "
        "Check organizador.log before trying again.\n\n{error}"
    ),
    "A app ainda não tem histórico. Organiza o primeiro ficheiro para começar.": (
        "The app has no history yet. Organize your first file to get started."
    ),
    "A caixa está vazia": "The inbox is empty",
    "A importar…": "Importing…",
    "A importação foi interrompida. Os ficheiros ainda não importados ficaram em Downloads.": (
        "The import was interrupted. Files not yet imported stayed in Downloads."
    ),
    "A iniciar…": "Starting…",
    "A janela fechou, mas Downloads continua a ser vigiado no tabuleiro do sistema.": (
        "The window closed, but Downloads is still being watched from the system tray."
    ),
    "A mostrar tarefas de {date}": "Showing tasks for {date}",
    "A ocorrência foi marcada como revista. O ficheiro não foi alterado.": (
        "The finding was marked as reviewed. The file was not changed."
    ),
    "A pasta de dados da aplicação não está disponível. Nenhum ficheiro foi alterado.\n\n{error}": (
        "The application data folder is unavailable. No file was changed.\n\n{error}"
    ),
    "A pesquisa é local. Escreve duas ou mais letras para começar.": (
        "Search is local. Type two or more letters to begin."
    ),
    "A pesquisa é local. PDFs digitalizados só como imagem podem não ter texto pesquisável.": (
        "Search is local. Scanned image-only PDFs may not have searchable text."
    ),
    "A preparar a vigilância de Downloads…": "Preparing the Downloads watch…",
    "A verificar {count} ficheiros…": "Checking {count} files…",
    "A verificar {count} ficheiro…": "Checking {count} file…",
    "A vigiar Downloads": "Watching Downloads",
    "A vigilância de Downloads está desligada nas Definições.": (
        "The Downloads watch is turned off in Settings."
    ),
    "Abre a Caixa de Entrada para rever.": "Open the Inbox to review.",
    "Abrir": "Open",
    "Abrir Downloads": "Open Downloads",
    "Abrir Organizador": "Open Organizador",
    "Abrir Universidade": "Open University folder",
    "Abrir pasta": "Open folder",
    "Abrir pasta Universidade": "Open University folder",
    "Adiciona a próxima entrega acima ou cria-a ao organizar um documento.": (
        "Add your next assignment above, or create one while organizing a document."
    ),
    "Adicionar": "Add",
    "Adicionar disciplina": "Add subject",
    "Adicionar à pesquisa sem mover o ficheiro": "Add to search without moving the file",
    "Adotar": "Adopt",
    "Ainda não existe uma organização reversível.": ("There is no reversible organization yet."),
    "Ainda não há ficheiros organizados nesta disciplina.": (
        "No files organized in this subject yet."
    ),
    "Ainda não há prazos. Cria uma tarefa ou associa-a quando organizares um ficheiro.": (
        "No deadlines yet. Create a task or attach one while organizing a file."
    ),
    "Ainda sem ficheiros organizados": "No organized files yet",
    "Alterar a pasta Universidade afeta os próximos ficheiros; os já organizados não são movidos automaticamente.": (
        "Changing the University folder affects future files; organized ones are not moved automatically."
    ),
    "Arquivada": "Archived",
    "Arquivar": "Archive",
    "Arquivar disciplina?": "Archive subject?",
    "As palavras-chave ajudam a reconhecer ficheiros pelo nome.": (
        "Keywords help recognize files by their name."
    ),
    "Atrasada · {date}": "Overdue · {date}",
    "Avisar prazos antes": "Remind before deadlines",
    "Aviso": "Reminder",
    "Caixa de Entrada": "Inbox",
    "Caixa de Entrada  {count}": "Inbox  {count}",
    "Caixa de Entrada ({count})": "Inbox ({count})",
    "Caixa de Entrada vazia": "Inbox empty",
    "Caminho não encontrado": "Path not found",
    "Cancelar": "Cancel",
    "Com quantos dias de antecedência avisar prazos": (
        "How many days in advance to warn about deadlines"
    ),
    "Começa por uma disciplina": "Start with a subject",
    "Começar a vigiar Downloads depois da configuração": ("Start watching Downloads after setup"),
    "Conclui a configuração da aplicação antes de importar ficheiros.": (
        "Finish setting up the application before importing files."
    ),
    "Controla exatamente quais ficheiros entram e onde ficam guardados.": (
        "Control exactly which files come in and where they are stored."
    ),
    "Cor": "Color",
    "Cor da disciplina": "Subject color",
    "Cria outra disciplina antes de arquivar esta.": (
        "Create another subject before archiving this one."
    ),
    "Cria uma disciplina para a app saber onde guardar o próximo download.": (
        "Create a subject so the app knows where to keep your next download."
    ),
    "Criar a minha organização": "Create my organization",
    "Criar tarefa para cada ficheiro": "Create a task for each file",
    "Código": "Code",
    "Definições": "Settings",
    "Definições danificadas": "Damaged settings",
    "Definições guardadas.": "Settings saved.",
    "Desfazer última organização": "Undo last organization",
    "Destino de uma organização interrompida; compara antes de continuar.": (
        "Destination of an interrupted organization; compare before continuing."
    ),
    "Destino em Downloads de uma devolução interrompida; compara os ficheiros.": (
        "Downloads destination of an interrupted return; compare the files."
    ),
    "Devolver este ficheiro a Downloads": "Return this file to Downloads",
    "Disciplina": "Subject",
    "Disciplinas": "Subjects",
    "Documento registado que já não está no destino esperado.": (
        "A cataloged document is no longer at its expected destination."
    ),
    "Downloads arrumados\nantes de se perderem.": "Downloads organized\nbefore they get lost.",
    "Downloads vigiado. Só os formatos de estudo configurados entram.": (
        "Downloads is watched. Only the configured study formats come in."
    ),
    "Editar": "Edit",
    "Editar disciplina": "Edit subject",
    "Editar tarefa": "Edit task",
    "Elimina o filtro para ver todas as tarefas ou adiciona uma tarefa para este dia.": (
        "Clear the filter to see all tasks, or add a task for this day."
    ),
    "Eliminar": "Delete",
    "Encontrado numa disciplina sem registo. Não foi movido nem alterado.": (
        "Found in a subject without a record. It was not moved or changed."
    ),
    "Escolhe o teu ponto de partida": "Choose your starting point",
    "Escolhe uma disciplina antes de organizar.": "Choose a subject before organizing.",
    "Escolhe uma opção": "Choose an option",
    "Escolhe uma pasta para a Universidade.": "Choose a folder for the University.",
    "Escolher pasta": "Choose folder",
    "Escolher pasta Universidade": "Choose University folder",
    "Escolher…": "Browse…",
    "Escreve o nome da disciplina para continuar.": "Type the subject name to continue.",
    "Escreve o nome da primeira disciplina.": "Type the first subject's name.",
    "Escreve o título da tarefa para continuar.": "Type the task title to continue.",
    "Escreve uma tarefa antes de adicionar.": "Type a task before adding.",
    "Espera que a importação de Downloads termine antes de guardar.": (
        "Wait for the Downloads import to finish before saving."
    ),
    "Espera que o lote atual termine antes de iniciar outro.": (
        "Wait for the current batch to finish before starting another."
    ),
    "Esta base de dados foi criada por uma versão mais recente do Organizador. Abre a versão mais recente da app. Nenhum ficheiro foi alterado.": (
        "This database was created by a newer version of Organizador. "
        "Open the newest version of the app. No file was changed."
    ),
    "Ex.: Cálculo I": "e.g. Calculus I",
    "Ex.: MAT101": "e.g. MAT101",
    "Ex.: MAT101 (opcional)": "e.g. MAT101 (optional)",
    "Ex.: cálculo, derivadas, integrais": "e.g. calculus, derivatives, integrals",
    "Ex.: regra da cadeia, normalização, Revolução Francesa…": (
        "e.g. chain rule, normalization, French Revolution…"
    ),
    "Experimenta menos palavras ou confirma se o ficheiro aparece nos organizados recentes.": (
        "Try fewer words, or check whether the file appears under recently organized."
    ),
    "Extensões aceites": "Accepted extensions",
    "Fechar": "Close",
    "Ficheiro devolvido": "File returned",
    "Ficheiro organizado": "File organized",
    "Ficheiro restaurado por uma operação de desfazer interrompida.": (
        "File restored by an interrupted undo operation."
    ),
    "Ficheiros adotados": "Adopted files",
    "Ficheiros de {name}": "Files of {name}",
    "Foram encontrados {total} ficheiros elegíveis. Serão verificados no máximo {selected} e movidos para a Caixa de Entrada.{remaining}\n\nCada ficheiro continuará a precisar da tua confirmação.": (
        "{total} eligible files were found. At most {selected} will be checked and moved "
        "to the Inbox.{remaining}\n\nEach file will still need your confirmation."
    ),
    "Geral": "General",
    "Guardar definições": "Save settings",
    "Guardar disciplina": "Save subject",
    "Guardar tarefa": "Save task",
    "Idioma": "Language",
    "Importar de Downloads…": "Import from Downloads…",
    "Importar ficheiros existentes?": "Import existing files?",
    "Importação de Downloads concluída": "Downloads import finished",
    "Importação em curso": "Import in progress",
    "Importação indisponível": "Import unavailable",
    "Iniciar o Organizador quando entro no Windows": "Start Organizador when I sign in to Windows",
    "Início": "Home",
    "Já existe uma disciplina ativa com o mesmo nome ou pasta: {names}. Edita-a primeiro para libertar o nome.": (
        "An active subject already uses the same name or folder: {names}. "
        "Edit it first to free the name."
    ),
    "Já existe uma disciplina com esse nome.\n\n{error}": (
        "A subject with that name already exists.\n\n{error}"
    ),
    "Já existe uma disciplina ou pasta com esse nome.\n\n{error}": (
        "A subject or folder with that name already exists.\n\n{error}"
    ),
    "Mais tarde": "Later",
    "Mais tarde em {count}s": "Later in {count}s",
    "Mantém cada entrega junto da disciplina a que pertence.": (
        "Keep each assignment with the subject it belongs to."
    ),
    "Mantém uma disciplina ativa": "Keep one active subject",
    "Marcar revisto": "Mark reviewed",
    "Modelo do nome": "Name template",
    "Mostrar arquivadas": "Show archived",
    "Mostrar na pasta": "Show in folder",
    "Mostrar os ficheiros organizados nesta disciplina": (
        "Show the files organized in this subject"
    ),
    "Nada para desfazer": "Nothing to undo",
    "Nada para importar": "Nothing to import",
    "Nada é arquivado sem uma decisão. Organiza agora ou deixa para mais tarde.": (
        "Nothing is filed without a decision. Organize now or leave it for later."
    ),
    "Nenhum ficheiro foi substituído ou apagado.": "No file was overwritten or deleted.",
    "Nenhum ficheiro foi substituído ou apagado. ": "No file was overwritten or deleted. ",
    "No dia": "On the day",
    "Nome": "Name",
    "Nome final do ficheiro": "Final file name",
    "Nomes finais": "Final names",
    "Nova disciplina": "New subject",
    "Nova tarefa, por exemplo: entregar ficha 4": ("New task, for example: hand in worksheet 4"),
    "Novo material de estudo": "New study material",
    "Novo material na Caixa de Entrada": "New material in the Inbox",
    "Não encontrei essa expressão": "I could not find that expression",
    "Não existem ficheiros elegíveis no nível principal de Downloads.": (
        "There are no eligible files at the top level of Downloads."
    ),
    "Não foi possível abrir": "Could not open",
    "Não foi possível abrir a pasta configurada: {error}": (
        "Could not open the configured folder: {error}"
    ),
    "Não foi possível abrir as pastas": "Could not open the folders",
    "Não foi possível abrir os dados": "Could not open the data",
    "Não foi possível adotar": "Could not adopt",
    "Não foi possível criar": "Could not create",
    "Não foi possível desfazer": "Could not undo",
    "Não foi possível devolver": "Could not return",
    "Não foi possível encontrar:\n{path}": "Could not find:\n{path}",
    "Não foi possível guardar": "Could not save",
    "Não foi possível iniciar o registo": "Could not start logging",
    "Não foi possível ler as definições guardadas. A app abriu com valores seguros para poderes corrigi-las.\n\n{error}": (
        "Could not read the saved settings. The app started with safe values "
        "so you can fix them.\n\n{error}"
    ),
    "Não foi possível mostrar": "Could not show",
    "Não foi possível procurar": "Could not search",
    "Não foi possível recolher o ficheiro": "Could not collect the file",
    "Não foi possível remover": "Could not remove",
    "Não foi possível restaurar": "Could not restore",
    "Não foi possível restaurar a cópia": "Could not restore the backup",
    "A cópia pedida não pôde ser restaurada e os dados atuais foram mantidos. Consulta organizador.log antes de tentar novamente.\n\n{error}": (
        "The requested backup could not be restored and the current data was kept. "
        "Check organizador.log before trying again.\n\n{error}"
    ),
    "Cópia restaurada": "Backup restored",
    "Os dados foram repostos a partir da cópia de {when}.": (
        "Your data was restored from the backup of {when}."
    ),
    "Não foi possível rever o histórico local: {error}": (
        "Could not review the local history: {error}"
    ),
    "Não é da universidade": "Not university material",
    "Não é da universidade: devolve o ficheiro": ("Not university material: returns the file"),
    "O caminho registado já não é um ficheiro normal. Não foi seguido nem alterado.": (
        "The recorded path is no longer a regular file. It was not followed or changed."
    ),
    "Duas disciplinas partilham a mesma pasta no Windows. Os documentos podem misturar-se; arquiva uma delas se for um engano.": (
        "Two subjects share the same folder on Windows. Documents may get mixed up; "
        "archive one of them if it was a mistake."
    ),
    "O ficheiro ou o registo mudou desde a verificação. Nada foi removido.": (
        "The file or the record changed since the scan. Nothing was removed."
    ),
    "O idioma novo é aplicado ao reiniciar a app.": (
        "The new language is applied when the app restarts."
    ),
    "O primeiro documento organizado aparece aqui. A app não toca nos ficheiros antigos sem pedires.": (
        "Your first organized document appears here. The app does not touch old files unless you ask."
    ),
    "O registo mudou desde que a página foi aberta. Nada foi removido.": (
        "The record changed since the page was opened. Nothing was removed."
    ),
    "O teu semestre, arrumado.": "Your semester, organized.",
    "Oculta a disciplina sem apagar os respetivos ficheiros": (
        "Hides the subject without deleting its files"
    ),
    "Operação de desfazer interrompida; confirma as pastas antes de continuar.": (
        "Interrupted undo operation; confirm the folders before continuing."
    ),
    "Organizador": "Organizador",
    "Organizador continua ativo": "Organizador is still active",
    "Organizador v{version} · código MIT · componentes de terceiros com licenças próprias": (
        "Organizador v{version} · MIT license · third-party components under their own licenses"
    ),
    "Organizador · a preparar": "Organizador · preparing",
    "Organizador · {state}": "Organizador · {state}",
    "Organizar": "Organize",
    "Organizar ficheiro": "Organize file",
    "Organizar seleção": "Organize selection",
    "Organizar seleção ({count})": "Organize selection ({count})",
    "Organizar {count} ficheiro": "Organize {count} file",
    "Organizar {count} ficheiros": "Organize {count} files",
    "Organizar com Organizador": "Organize with Organizador",
    "Atualização em curso": "Update in progress",
    "A organizar {count} ficheiro…": "Organizing {count} file…",
    "A organizar {count} ficheiros…": "Organizing {count} files…",
    "Já existe uma organização em curso; espera que termine.": (
        "A filing operation is already running; wait for it to finish."
    ),
    "Não foi possível concluir a organização.": "Could not complete the filing.",
    "Não foi possível organizar o ficheiro.": "Could not organize the file",
    "Organização desfeita": "Organization undone",
    "Organização que não pode ser desfeita enquanto o ficheiro estiver em falta.": (
        "An organization that cannot be undone while the file is missing."
    ),
    "Origem de uma devolução interrompida; não foi alterada no arranque.": (
        "Origin of an interrupted return; it was not changed at startup."
    ),
    "Origem de uma operação de desfazer interrompida; não foi alterada no arranque.": (
        "Origin of an interrupted undo operation; it was not changed at startup."
    ),
    "Origem de uma organização interrompida; não foi alterada no arranque.": (
        "Origin of an interrupted organization; it was not changed at startup."
    ),
    "Os códigos e palavras-chave tornam as sugestões de arquivo mais precisas.": (
        "Codes and keywords make filing suggestions more accurate."
    ),
    "Os downloads novos aparecem aqui antes de irem para uma disciplina.": (
        "New downloads appear here before they go to a subject."
    ),
    "Os ficheiros elegíveis passam primeiro por uma Caixa de Entrada segura. Tu confirmas a disciplina e nada é substituído.": (
        "Eligible files first pass through a safe Inbox. You confirm the subject and "
        "nothing is overwritten."
    ),
    "Os ficheiros mudaram ou já estavam a ser processados e ficaram em Downloads.": (
        "The files changed or were already being processed and stayed in Downloads."
    ),
    "Padrão das Definições": "Settings default",
    "Palavras-chave": "Keywords",
    "Pasta Downloads": "Downloads folder",
    "Pasta Universidade": "University folder",
    "Pasta: {name}": "Folder: {name}",
    "Pastas e vigilância": "Folders and watching",
    "Pausar vigilância": "Pause watching",
    "Pesquisa": "Search",
    "Pesquisa nos documentos": "Search in documents",
    "Pesquisar nos apontamentos": "Search your notes",
    "Podes alterar estas opções depois. Começa por criar uma disciplina.": (
        "You can change these options later. Start by creating a subject."
    ),
    "Podes corrigir o nome; a extensão original é preservada": (
        "You can edit the name; the original extension is preserved"
    ),
    "Prazo": "Deadline",
    "Prazo amanhã": "Due tomorrow",
    "Prazo das tarefas": "Task deadline",
    "Prazo em {count} dias · {date}": "Due in {count} days · {date}",
    "Prazo hoje": "Due today",
    "Preparar o Organizador": "Set up Organizador",
    "Primeira disciplina": "First subject",
    "Procura palavras dentro de PDFs, documentos Office, ficheiros de texto e notebooks já organizados.": (
        "Search words inside organized PDFs, Office documents, text files and notebooks."
    ),
    "Próximos prazos": "Upcoming deadlines",
    "Quando terminares um download elegível, ele aparece aqui e num pequeno popup.": (
        "When a qualifying download finishes, it appears here and in a small popup."
    ),
    "Reativar disciplina?": "Restore subject?",
    "Recuperação manual necessária  ·  {size}  ·  {when}": (
        "Manual recovery needed  ·  {size}  ·  {when}"
    ),
    "Registo mantido": "Record kept",
    "Remover apenas o registo local; nenhum ficheiro é apagado": (
        "Removes only the local record; no file is deleted"
    ),
    "Remover do catálogo": "Remove from catalog",
    "Remover do catálogo?": "Remove from catalog?",
    "Remover registo": "Remove record",
    "Remover registo em falta?": "Remove missing record?",
    "Restaurar": "Restore",
    "Cópias de segurança": "Backups",
    "Ainda não há cópias de segurança.": "There are no backups yet.",
    "Criar cópia agora": "Create backup now",
    "Criar e exportar .zip…": "Create and export .zip…",
    "Restaurar…": "Restore…",
    "As cópias guardam o catálogo e as definições. Os teus documentos não são alterados.": (
        "Backups store the catalog and the settings. Your documents are not changed."
    ),
    "Última cópia: {when} · {size}": "Last backup: {when} · {size}",
    "Última cópia: {when} · {count} cópias · {size}": (
        "Last backup: {when} · {count} backups · {size}"
    ),
    "A processar a cópia de segurança…": "Processing the backup…",
    "Espera que as operações de ficheiros terminem antes de criar a cópia.": (
        "Wait for the file operations to finish before creating the backup."
    ),
    "Não foi possível concluir a cópia: {error}": "Could not finish the backup: {error}",
    "Cópia importada. Escolhe-a na lista para restaurar.": (
        "Backup imported. Choose it in the list to restore."
    ),
    "Cópia exportada: {name}": "Backup exported: {name}",
    "Cópia criada e exportada: {name}": "Backup created and exported: {name}",
    "Cópia de segurança criada.": "Backup created.",
    "Importar cópia de segurança": "Import backup",
    "Exportar cópia de segurança": "Export backup",
    "Cópias de segurança (*.zip)": "Backups (*.zip)",
    "Remover cópia": "Remove backup",
    "Remover a cópia de {when}? Esta ação não pode ser desfeita.": (
        "Remove the backup from {when}? This cannot be undone."
    ),
    "Restaurar cópia de segurança": "Restore backup",
    "Os dados atuais serão substituídos pela cópia de {when} e a app vai reiniciar. Os teus documentos não são alterados. Continuar?": (
        "The current data will be replaced by the backup from {when} and the app will "
        "restart. Your documents are not changed. Continue?"
    ),
    "Espera que as operações de ficheiros terminem antes de restaurar.": (
        "Wait for the file operations to finish before restoring."
    ),
    "Fecha e reabre o Organizador para concluir a reposição.": (
        "Close and reopen Organizador to finish the restore."
    ),
    "Restaurar substitui o catálogo e as definições atuais.": (
        "Restoring replaces the current catalog and settings."
    ),
    "Manual": "Manual",
    "Antes de atualizar": "Before updating",
    "Antes de restaurar": "Before restoring",
    "Do sistema": "System",
    "{size} · esquema {version}": "{size} · schema {version}",
    "Importar .zip…": "Import .zip…",
    "Exportar": "Export",
    "Remover": "Remove",
    "Retomar vigilância": "Resume watching",
    "Rever {name}": "Review {name}",
    "Revisão manual do histórico": "Manual history review",
    "Revê as Definições antes de ativar a vigilância.\n\n{error}": (
        "Review Settings before enabling the watch.\n\n{error}"
    ),
    "Revê: {errors}.": "Review: {errors}.",
    "Sair": "Quit",
    "Sair da configuração?": "Quit setup?",
    "Selecionar {name}": "Select {name}",
    "Sem palavras-chave": "No keywords",
    "Sem prazo": "No deadline",
    "Sem resultados. O documento pode ainda estar a ser indexado ou ser um PDF digitalizado.": (
        "No results. The document may still be indexing or be a scanned PDF."
    ),
    "Sem sugestão": "No suggestion",
    "Sem tarefas neste dia": "No tasks on this day",
    "Sem tarefas pendentes": "No pending tasks",
    "Sem uma disciplina, a app não começa a mover downloads. Podes voltar a configurar depois.": (
        "Without a subject the app will not start moving downloads. You can set it up later."
    ),
    "Será removido apenas o registo local e o índice de pesquisa. Nenhum ficheiro será apagado. Se o ficheiro reaparecer durante a operação, ficará visível para poder ser adotado novamente.": (
        "Only the local record and the search index will be removed. No file will be "
        "deleted. If the file reappears during the operation, it becomes visible so it "
        "can be adopted again."
    ),
    "Sugestão {percent}%": "Suggestion {percent}%",
    "Só a organização mais recente pode ser desfeita.": (
        "Only the most recent organization can be undone."
    ),
    "Tamanho mínimo": "Minimum size",
    "Tarefa": "Task",
    "Tarefa geral": "General task",
    "Tarefas": "Tasks",
    "Tarefas e prazos": "Tasks and deadlines",
    "Tema": "Theme",
    "Tempo do popup": "Popup timeout",
    "Fechar o popup automaticamente": "Close the popup automatically",
    "Sem esta opção, o popup fica aberto até escolheres uma ação.": (
        "Without this option, the popup stays open until you choose an action."
    ),
    "Tipo": "Type",
    "Tipo de documento": "Document type",
    "Todos vão para a mesma disciplina e tipo. Cada ficheiro mantém o seu próprio histórico; só a última organização pode ser desfeita.": (
        "All go to the same subject and type. Each file keeps its own history; only the "
        "last organization can be undone."
    ),
    "Tokens: {tokens}. A extensão original é sempre preservada.": (
        "Tokens: {tokens}. The original extension is always preserved."
    ),
    "Tranquilidade": "Peace of mind",
    "Tudo fica neste computador. Nenhum documento é enviado para a internet.": (
        "Everything stays on this computer. No document is sent to the internet."
    ),
    "Tudo no lugar": "Everything in place",
    "Título da tarefa": "Task title",
    "Ver ficheiros": "View files",
    "Ver todas": "View all",
    "Verificação de segurança concluída": "Safety check finished",
    "Verificação de segurança incompleta": "Safety check incomplete",
    "Verificação incompleta": "Check incomplete",
    "Versão da base de dados mais recente": "Newer database version",
    "Vigiar novos ficheiros em Downloads": "Watch for new files in Downloads",
    "Vigilância de Downloads desligada": "Downloads watch turned off",
    "Vigilância desligada": "Watching off",
    "Vigilância em pausa": "Watching paused",
    "Vigilância em pausa. Os novos downloads ficam onde estão.": (
        "Watching paused. New downloads stay where they are."
    ),
    "Volta a mostrar a disciplina nas escolhas de arquivo": (
        "Shows the subject again in filing choices"
    ),
    "a verificação atingiu o limite de segurança": "the scan reached its safety limit",
    "alguns caminhos não puderam ser verificados": "some paths could not be checked",
    "diapositivo {page}": "slide {page}",
    "documento": "document",
    "e mais {count}": "and {count} more",
    "estudo local": "local study",
    "está atrasada": "is overdue",
    "folha {page}": "sheet {page}",
    "página {page}": "page {page}",
    "vence amanhã": "is due tomorrow",
    "vence em {count} dias": "is due in {count} days",
    "vence hoje": "is due today",
    "verificação incompleta": "check incomplete",
    "{count} arquivada": "{count} archived",
    "{count} arquivadas": "{count} archived",
    "{count} colisão de nomes resolvida sem substituir nada": (
        "{count} name collision resolved without overwriting"
    ),
    "{count} colisões de nomes resolvidas sem substituir nada": (
        "{count} name collisions resolved without overwriting"
    ),
    "{count} com erro": "{count} with errors",
    "{count} devolução a Downloads": "{count} return to Downloads",
    "{count} devoluções a Downloads": "{count} returns to Downloads",
    "{count} disciplina ativa": "{count} active subject",
    "{count} disciplinas ativas": "{count} active subjects",
    "{count} ficheiro adotado sem mover": "{count} file adopted without moving",
    "{count} ficheiro organizado": "{count} file organized",
    "{count} ficheiro por decidir": "{count} file awaiting decision",
    "{count} ficheiro por decidir · {recovery} precisam de recuperação": (
        "{count} file awaiting decision · {recovery} need recovery"
    ),
    "{count} ficheiro precisa de recuperação manual": ("{count} file needs manual recovery"),
    "{count} ficheiro precisa de revisão manual": "{count} finding needs manual review",
    "{count} ficheiro · {size}": "{count} file · {size}",
    "{count} ficheiros adotados sem mover": "{count} files adopted without moving",
    "{count} ficheiros organizados": "{count} files organized",
    "{count} ficheiros por decidir": "{count} files awaiting decision",
    "{count} ficheiros por decidir · {recovery} precisam de recuperação": (
        "{count} files awaiting decision · {recovery} need recovery"
    ),
    "{count} ficheiros precisam de recuperação manual": ("{count} files need manual recovery"),
    "{count} ficheiros precisam de revisão manual": "{count} findings need manual review",
    "{count} ficheiros · {size}": "{count} files · {size}",
    "{count} ignorado": "{count} skipped",
    "{count} ignorados": "{count} skipped",
    "{count} importado": "{count} imported",
    "{count} importados": "{count} imported",
    "{count} não entraram neste lote e ficaram em Downloads.": (
        "{count} did not join this batch and stayed in Downloads."
    ),
    "{count} ocorrência do histórico precisa de revisão": ("{count} history finding needs review"),
    "{count} ocorrências do histórico precisam de revisão": (
        "{count} history findings need review"
    ),
    "{count} operação interrompida recuperada": ("{count} interrupted operation recovered"),
    "{count} operações interrompidas recuperadas": ("{count} interrupted operations recovered"),
    "{count} organizado, {failed} com erro. Revê: {errors}.": (
        "{count} organized, {failed} with errors. Review: {errors}."
    ),
    "{count} organizado.": "{count} organized.",
    "{count} organizados, {failed} com erro. Revê: {errors}.": (
        "{count} organized, {failed} with errors. Review: {errors}."
    ),
    "{count} organizados.": "{count} organized.",
    "{count} organização desfeita": "{count} organization undone",
    "{count} organizações desfeitas": "{count} organizations undone",
    "{count} registo da Caixa de Entrada foi revisto": ("{count} Inbox record was reviewed"),
    "{count} registos da Caixa de Entrada foram revistos": ("{count} Inbox records were reviewed"),
    "{count} resultados · os parênteses retos mostram a correspondência": (
        "{count} results · square brackets mark the match"
    ),
    "{kind} · {size} · organizado {date}": "{kind} · {size} · organized {date}",
    "{name} (arquivada)": "{name} (archived)",
    "{name} deixa de aparecer nas escolhas. Os ficheiros e tarefas não são apagados.": (
        "{name} stops appearing in filing choices. Its files and tasks are not deleted."
    ),
    "{name} deixará de aparecer na pesquisa e nos recentes. O ficheiro permanecerá exatamente onde está.": (
        "{name} will stop appearing in search and recents. The file stays exactly where it is."
    ),
    "{name} está pronto para organizar.": "{name} is ready to organize.",
    "{name} foi adotado sem mover o ficheiro.": ("{name} was adopted without moving the file."),
    "{name} foi guardado em {destination}.": "{name} was saved to {destination}.",
    "{name} saiu do catálogo; o ficheiro ficou no lugar.": (
        "{name} left the catalog; the file stayed in place."
    ),
    "{name} volta a aparecer nas escolhas de arquivo. Os ficheiros e tarefas não foram alterados.": (
        "{name} appears again in filing choices. Files and tasks were not changed."
    ),
    "{name} voltou para {folder}.": "{name} went back to {folder}.",
    "{name} voltou à Caixa de Entrada.": "{name} returned to the Inbox.",
    "{size}  ·  recebido da pasta {folder}": "{size}  ·  received from the {folder} folder",
    "{size}  ·  {when}  ·  Sugestão: {suggestion} / {kind}": (
        "{size}  ·  {when}  ·  Suggestion: {suggestion} / {kind}"
    ),
    "{subject}  ·  {due}": "{subject}  ·  {due}",
    "{subject}  ·  {kind}  ·  {location}": "{subject}  ·  {kind}  ·  {location}",
    "{subject}  ·  {kind}  ·  {size}": "{subject}  ·  {kind}  ·  {size}",
    "{subject} · {kind} · adotado sem mover": "{subject} · {kind} · adopted without moving",
    "{title} {when}.": "{title} {when}.",
    "Procurar atualizações…": "Check for updates…",
    "Instalar atualização {version}": "Install update {version}",
    "Atualização disponível": "Update available",
    "Organizador {version} está disponível. Escolhe “Instalar atualização” no menu do tabuleiro.": (
        "Organizador {version} is available. Choose “Install update” in the tray menu."
    ),
    "A transferência da atualização falhou: {error}": "The update download failed: {error}",
    "Não foi possível verificar a atualização: {error}": ("Could not verify the update: {error}"),
    "A verificação da atualização falhou; o ficheiro foi descartado.": (
        "The update verification failed; the file was discarded."
    ),
    "A atualização descarregada está corrompida.": "The downloaded update is corrupted.",
    "A atualização não contém a aplicação completa.": (
        "The update does not contain the complete application."
    ),
    "A instalar atualização…": "Installing update…",
    "A transferir e a verificar Organizador {version}.": (
        "Downloading and verifying Organizador {version}."
    ),
    "A reiniciar para aplicar a atualização…": "Restarting to apply the update…",
    "Atualização falhou": "Update failed",
    "Não foi possível instalar a atualização.": "Could not install the update.",
    "A atualização só se aplica à versão instalada.": (
        "Updates only apply to the installed version."
    ),
    "Sem atualizações nesta instalação": "No updates for this installation",
    "Ficheiros organizados": "Files organized",
    "{count} ficheiros estão prontos para organizar.": ("{count} files are ready to organize."),
    "Silenciar notificações de arquivo": "Silence filing notifications",
    "Sem avisos de ficheiros organizados; erros e prazos continuam visíveis.": (
        "No organized-file notices; errors and deadlines stay visible."
    ),
    "A app está a correr em modo de desenvolvimento; as atualizações aplicam-se apenas à versão instalada.": (
        "The app is running in development mode; updates only apply to the installed version."
    ),
    "Procurar atualizações automaticamente": "Check for updates automatically",
    "Atualização pronta": "Update ready",
    "A atualização extraída excede o limite permitido.": (
        "The extracted update exceeds the allowed limit."
    ),
    "Já existe uma instalação de atualização em curso: {owner}.": (
        "An update installation is already in progress: {owner}."
    ),
    "A atualização contém caminhos duplicados.": "The update contains duplicate paths.",
    "A atualização contém caminhos incompatíveis.": "The update contains conflicting paths.",
    "A atualização contém demasiados ficheiros.": "The update contains too many files.",
    "A atualização contém um caminho de ficheiro inseguro.": (
        "The update contains an unsafe file path."
    ),
    "A atualização contém um ficheiro encriptado não suportado.": (
        "The update contains an unsupported encrypted file."
    ),
    "A atualização contém um tipo de ficheiro não permitido.": (
        "The update contains a disallowed file type."
    ),
    "A pasta não contém uma instalação completa do Organizador.": (
        "The folder does not contain a complete Organizador installation."
    ),
    "Não foi possível iniciar o assistente de atualização.": (
        "Could not start the update assistant."
    ),
    "O ficheiro da atualização excede o limite permitido.": (
        "The update file exceeds the allowed limit."
    ),
    "O tamanho de um ficheiro da atualização é inválido.": ("An update file has an invalid size."),
    "Um ficheiro da atualização excede o limite permitido.": (
        "An update file exceeds the allowed limit."
    ),
    "A procurar atualizações…": "Checking for updates…",
    "A instalar atualização {version}…": "Installing update {version}…",
    "Sem atualizações": "No updates",
    "O Organizador está atualizado.": "Organizador is up to date.",
    "Não foi possível procurar atualizações.": "Could not check for updates.",
    "A atualização transferida não corresponde à versão {version}.": (
        "The downloaded update does not match version {version}."
    ),
    "Atualização instalada": "Update installed",
    "Atualização {version} instalada com sucesso.": "Update {version} installed successfully.",
    "Atualização instalada com sucesso.": "Update installed successfully.",
    "Atualização revertida": "Update rolled back",
    "A atualização {version} falhou e a versão anterior foi restaurada.": (
        "Update {version} failed and the previous version was restored."
    ),
    "A atualização falhou e a versão anterior foi restaurada.": (
        "The update failed and the previous version was restored."
    ),
    "A atualização falhou e a reposição automática não foi concluída.": (
        "The update failed and automatic restoration did not complete."
    ),
    "A versão anterior foi mantida em: {path}.": "The previous version was kept at: {path}.",
    "Atualização inválida": "Invalid update",
    "A atualização não corresponde a esta instalação. Nenhum ficheiro foi alterado.": (
        "The update does not match this installation. No files were changed."
    ),
    "A atualização não pôde ser validada. Nenhum ficheiro foi alterado.": (
        "The update could not be validated. No files were changed."
    ),
    "Não foi possível concluir a atualização": "Could not complete the update",
    "Não foi possível recuperar os dados": "Could not recover the data",
    "Não foi possível atualizar os dados": "Could not update the data",
    "Os argumentos da atualização estão incompletos. Nenhum ficheiro foi alterado.": (
        "The update arguments are incomplete. No files were changed."
    ),
    "Existe uma cópia de segurança de migração que não pôde ser restaurada automaticamente. Nenhum ficheiro foi alterado.\n\n{error}": (
        "There is a migration backup that could not be restored automatically. "
        "No files were changed.\n\n{error}"
    ),
    "A aplicação não conseguiu preparar o catálogo local. Foi tentada a reposição da cópia de segurança.\n\n{error}": (
        "The application could not prepare the local catalogue. "
        "Restoring the backup was attempted.\n\n{error}"
    ),
    "Os dados migrados não puderam ser validados. Foi tentada a reposição da cópia de segurança.\n\n{error}": (
        "The migrated data could not be validated. Restoring the backup was attempted.\n\n{error}"
    ),
    "Os dados migrados não puderam ser validados. A versão anterior foi mantida para recuperação manual.": (
        "The migrated data could not be validated. "
        "The previous version was kept for manual recovery."
    ),
    "A nova versão não conseguiu arrancar. A versão anterior foi mantida para recuperação manual.": (
        "The new version failed to start. The previous version was kept for manual recovery."
    ),
    "Não foi possível concluir o arranque": "Could not complete the startup",
    "A aplicação não conseguiu concluir o arranque. Foi tentada a reposição da cópia de segurança.\n\n{error}": (
        "The application could not complete startup. Restoring the backup was attempted.\n\n{error}"
    ),
    "A nova versão não conseguiu arrancar. Foi tentada a reposição da cópia de segurança.": (
        "The new version failed to start. Restoring the backup was attempted."
    ),
    "Não foi possível ler a pasta Downloads configurada.": (
        "Could not read the configured Downloads folder."
    ),
    "Já não foi possível encontrar {name}.": "Could no longer find {name}.",
    "{name} ficou em {origin}, mas uma cópia incompleta pode ter ficado em {leftover}. Compara os ficheiros antes de a remover.": (
        "{name} stayed in {origin}, but an incomplete copy may have been left at "
        "{leftover}. Compare the files before removing it."
    ),
    "{name} mudou ou ainda está a ser usado e ficou em {origin}.": (
        "{name} changed or is still in use and stayed in {origin}."
    ),
    "Não foi possível registar {name}. O ficheiro ficou em {destination}.": (
        "Could not register {name}. The file stayed at {destination}."
    ),
    "Não foi possível registar {name}; foi devolvido a {origin} como {returned}.": (
        "Could not register {name}; it was returned to {origin} as {returned}."
    ),
    "Este ficheiro não pode ser recolhido. Confirma que não está já na Universidade e que a extensão é aceite.": (
        "This file cannot be collected. Check that it is not already in the "
        "university folder and that its extension is accepted."
    ),
    "Este ficheiro já não está na Caixa de Entrada.": "This file is no longer in the Inbox.",
    "Escolhe uma disciplina ativa.": "Choose an active subject.",
    "Escolhe um tipo de documento válido.": "Choose a valid document type.",
    "Não foi possível encontrar {name}.": "Could not find {name}.",
    "Não foi possível preparar o histórico da organização.": (
        "Could not prepare the filing history."
    ),
    "A organização ficou incompleta. O original e a cópia foram mantidos; revê ambos na Caixa de Entrada antes de continuar.": (
        "Filing was left incomplete. The original and the copy were kept; "
        "review both in the Inbox before continuing."
    ),
    "O ficheiro ainda está a ser usado por outra aplicação. Fecha-o e tenta novamente.": (
        "The file is still being used by another application. Close it and try again."
    ),
    "O movimento foi revertido porque não foi possível atualizar o histórico.": (
        "The move was reverted because the history could not be updated."
    ),
    "Não foi possível atualizar o histórico. Revê a Caixa de Entrada antes de repetir.": (
        "Could not update the history. Review the Inbox before retrying."
    ),
    "O ficheiro já não está disponível para devolver.": (
        "The file is no longer available to return."
    ),
    "Não foi possível preparar o histórico da devolução.": (
        "Could not prepare the return history."
    ),
    "A devolução ficou incompleta. O original e a cópia foram mantidos; revê a Caixa de Entrada e Downloads antes de continuar.": (
        "The return was left incomplete. The original and the copy were kept; "
        "review the Inbox and Downloads before continuing."
    ),
    "Não foi possível devolver o ficheiro. Fecha-o noutras aplicações e tenta de novo.": (
        "Could not return the file. Close it in other applications and try again."
    ),
    "Não foi possível registar a devolução do ficheiro.": ("Could not register the file return."),
    "O último ficheiro organizado já não está no destino. O histórico não foi alterado.": (
        "The last organized file is no longer at its destination. History was not changed."
    ),
    "Não foi possível preparar o histórico para desfazer.": (
        "Could not prepare the history for undo."
    ),
    "A operação de desfazer ficou incompleta. O original e a cópia foram mantidos; revê ambos na Caixa de Entrada antes de continuar.": (
        "The undo operation was left incomplete. The original and the copy were kept; "
        "review both in the Inbox before continuing."
    ),
    "Não foi possível desfazer porque o ficheiro está a ser usado.": (
        "Could not undo because the file is in use."
    ),
    "Não foi possível atualizar o histórico ao desfazer.": (
        "Could not update the history while undoing."
    ),
    "Criar tarefa": "Create task",
    "A cópia incompleta ficou em {path}.": "The incomplete copy was left at {path}.",
    "A pasta de destino não é segura: {path}.": "The destination folder is not safe: {path}.",
    "Falha na indexação — o ficheiro continua pesquisável pelo nome.": (
        "Indexing failed — the file is still searchable by name."
    ),
    "Reindexar": "Reindex",
    "Mover": "Move",
    "Mover ficheiro": "Move file",
    "A mover…": "Moving…",
    "Ficheiro movido": "File moved",
    "{name} está agora em {location}.": "{name} is now in {location}.",
    "Não foi possível mover": "Could not move",
    "Espera que as operações de ficheiros terminem antes de mover.": (
        "Wait for the file operations to finish before moving."
    ),
    "Escolhe outra disciplina ou outro tipo para mover.": (
        "Choose another subject or another type to move."
    ),
    "Este documento já não está no catálogo.": ("This document is no longer in the catalog."),
    "Não foi possível preparar o histórico do movimento.": ("Could not prepare the move history."),
    "O movimento ficou incompleto. O original e a cópia foram mantidos; revê ambos antes de continuar.": (
        "The move was left incomplete. The original and the copy were kept; "
        "review both before continuing."
    ),
    "Não foi possível atualizar o histórico. Revê os ficheiros antes de repetir.": (
        "Could not update the history. Review the files before retrying."
    ),
    "Origem de um movimento interrompido; não foi alterada no arranque.": (
        "Source of an interrupted move; it was not changed at startup."
    ),
    "Destino de um movimento interrompido; compara antes de continuar.": (
        "Destination of an interrupted move; compare before continuing."
    ),
    "A reindexar…": "Reindexing…",
    "A fila de indexação está ocupada; o documento será indexado assim que possível.": (
        "The indexing queue is busy; the document will be indexed as soon as possible."
    ),
    "Tenta organizar o ficheiro quando a atualização terminar.": (
        "Try organizing the file once the update finishes."
    ),
    "Tentar novamente": "Retry",
    "{count} documentos por indexar": "{count} documents pending indexing",
    "1 documento por indexar": "1 document pending indexing",
    "{count} documentos com falha na indexação": "{count} documents failed indexing",
    "1 documento com falha na indexação": "1 document failed indexing",
    "Reconhecer texto em PDFs digitalizados (OCR)": "Recognize text in scanned PDFs (OCR)",
    "Todas as disciplinas": "All subjects",
    "Todos os tipos": "All types",
    "Filtrar por disciplina": "Filter by subject",
    "Filtrar por tipo de documento": "Filter by document type",
    "{count} documentos": "{count} documents",
    "1 documento": "1 document",
    "{subject}  ·  {kind}": "{subject}  ·  {kind}",
}

ES_STRINGS: dict[str, str] = {
    "Notificação indisponível": "Notificación no disponible",
    "A notificação expirou ou algum ficheiro já não está disponível. Consulta os ficheiros na app.": "La notificación ha caducado o algún archivo ya no está disponible. Consulta tus archivos en la app.",
    "A terminar o Organizador": "Cerrando Organizador",
    "A concluir {count} operações de ficheiros antes de sair…": "Terminando {count} operaciones de archivos antes de salir…",
    "A concluir a cópia de segurança antes de sair…": (
        "Terminando la copia de seguridad antes de salir…"
    ),
    "Espera que as operações de ficheiros terminem antes de guardar.": "Espera a que terminen las operaciones de archivos antes de guardar.",
    "Atualização em espera": "Actualización en espera",
    "Espera que as operações de ficheiros terminem antes de atualizar.": "Espera a que terminen las operaciones de archivos antes de actualizar.",
    "Não foi possível preparar a recolha do ficheiro.": "No se pudo preparar el traslado del archivo a la bandeja de entrada.",
    "Download com recolha interrompida; o original foi mantido para revisão.": "Traslado de descarga interrumpido; se conservó el original para su revisión.",
    "Cópia por verificar; pode estar incompleta. Compara com o original em Downloads.": "Copia sin verificar; puede estar incompleta. Compárala con el original en Descargas.",
    "Ver existente": "Ver existente",
    "Substituir a versão anterior": "Sustituir la versión anterior",
    "A versão atual fica na pasta com o sufixo «versão anterior».": "La versión actual se queda en la carpeta con el sufijo «versión anterior».",
    "Já tens este ficheiro em {location}: {name}": "Ya tienes este archivo en {location}: {name}",
    "versão anterior": "versión anterior",
    "Renomeação de versão interrompida; o original foi mantido para revisão.": "Renombrado de versión interrumpido; se conservó el original para su revisión.",
    "Cópia da versão anterior por verificar; compara os ficheiros.": "Copia de la versión anterior sin verificar; compara los archivos.",
    " Os outros {count} ficam em Downloads para um próximo lote.": (
        " Los otros {count} se quedan en Descargas para otro lote."
    ),
    " bytes": " bytes",
    " dias": " días",
    "({count}) por organizar": "({count}) por organizar",
    "1 dia antes": "1 día antes",
    "1 resultado · os parênteses retos mostram a correspondência": (
        "1 resultado · los corchetes marcan la coincidencia"
    ),
    "1 semana antes": "1 semana antes",
    "2 dias antes": "2 días antes",
    "3 dias antes": "3 días antes",
    "A aplicação não conseguiu abrir o catálogo local. Consulta organizador.log antes de tentar novamente.\n\n{error}": (
        "La aplicación no pudo abrir el catálogo local. Consulta organizador.log "
        "antes de intentarlo de nuevo.\n\n{error}"
    ),
    "A app ainda não tem histórico. Organiza o primeiro ficheiro para começar.": (
        "La app aún no tiene historial. Organiza el primer archivo para empezar."
    ),
    "A caixa está vazia": "La bandeja está vacía",
    "A importar…": "Importando…",
    "A importação foi interrompida. Os ficheiros ainda não importados ficaram em Downloads.": (
        "La importación fue interrumpida. Los archivos aún no importados se quedaron en Descargas."
    ),
    "A iniciar…": "Iniciando…",
    "A janela fechou, mas Downloads continua a ser vigiado no tabuleiro do sistema.": (
        "La ventana se cerró, pero Descargas sigue vigilándose desde la bandeja del sistema."
    ),
    "A mostrar tarefas de {date}": "Mostrando tareas del {date}",
    "A ocorrência foi marcada como revista. O ficheiro não foi alterado.": (
        "La incidencia fue marcada como revisada. El archivo no fue alterado."
    ),
    "A pasta de dados da aplicação não está disponível. Nenhum ficheiro foi alterado.\n\n{error}": (
        "La carpeta de datos de la aplicación no está disponible. "
        "Ningún archivo fue alterado.\n\n{error}"
    ),
    "A pesquisa é local. Escreve duas ou mais letras para começar.": (
        "La búsqueda es local. Escribe dos o más letras para empezar."
    ),
    "A pesquisa é local. PDFs digitalizados só como imagem podem não ter texto pesquisável.": (
        "La búsqueda es local. Los PDF escaneados solo como imagen pueden no tener texto buscable."
    ),
    "A preparar a vigilância de Downloads…": "Preparando la vigilancia de Descargas…",
    "A verificar {count} ficheiros…": "Verificando {count} archivos…",
    "A verificar {count} ficheiro…": "Verificando {count} archivo…",
    "A vigiar Downloads": "Vigilando Descargas",
    "A vigilância de Downloads está desligada nas Definições.": (
        "La vigilancia de Descargas está desactivada en Ajustes."
    ),
    "Abre a Caixa de Entrada para rever.": "Abre la Bandeja de Entrada para revisar.",
    "Abrir": "Abrir",
    "Abrir Downloads": "Abrir Descargas",
    "Abrir Organizador": "Abrir Organizador",
    "Abrir Universidade": "Abrir carpeta Universidad",
    "Abrir pasta": "Abrir carpeta",
    "Abrir pasta Universidade": "Abrir carpeta Universidad",
    "Adiciona a próxima entrega acima ou cria-a ao organizar um documento.": (
        "Añade la próxima entrega arriba o créala al organizar un documento."
    ),
    "Adicionar": "Añadir",
    "Adicionar disciplina": "Añadir asignatura",
    "Adicionar à pesquisa sem mover o ficheiro": "Añadir a la búsqueda sin mover el archivo",
    "Adotar": "Adoptar",
    "Ainda não existe uma organização reversível.": ("Aún no existe una organización reversible."),
    "Ainda não há ficheiros organizados nesta disciplina.": (
        "Aún no hay archivos organizados en esta asignatura."
    ),
    "Ainda não há prazos. Cria uma tarefa ou associa-a quando organizares um ficheiro.": (
        "Aún no hay plazos. Crea una tarea o asóciala al organizar un archivo."
    ),
    "Ainda sem ficheiros organizados": "Aún sin archivos organizados",
    "Alterar a pasta Universidade afeta os próximos ficheiros; os já organizados não são movidos automaticamente.": (
        "Cambiar la carpeta Universidad afecta a los archivos futuros; "
        "los ya organizados no se mueven automáticamente."
    ),
    "Arquivada": "Archivada",
    "Arquivar": "Archivar",
    "Arquivar disciplina?": "¿Archivar asignatura?",
    "As palavras-chave ajudam a reconhecer ficheiros pelo nome.": (
        "Las palabras clave ayudan a reconocer archivos por su nombre."
    ),
    "Atrasada · {date}": "Atrasada · {date}",
    "Avisar prazos antes": "Avisar de plazos con antelación",
    "Aviso": "Aviso",
    "Caixa de Entrada": "Bandeja de Entrada",
    "Caixa de Entrada  {count}": "Bandeja de Entrada  {count}",
    "Caixa de Entrada ({count})": "Bandeja de Entrada ({count})",
    "Caixa de Entrada vazia": "Bandeja de Entrada vacía",
    "Caminho não encontrado": "Ruta no encontrada",
    "Cancelar": "Cancelar",
    "Com quantos dias de antecedência avisar prazos": (
        "Con cuántos días de antelación avisar de los plazos"
    ),
    "Começa por uma disciplina": "Empieza por una asignatura",
    "Começar a vigiar Downloads depois da configuração": (
        "Empezar a vigiar Descargas después de la configuración"
    ),
    "Conclui a configuração da aplicação antes de importar ficheiros.": (
        "Termina la configuración de la aplicación antes de importar archivos."
    ),
    "Controla exatamente quais ficheiros entram e onde ficam guardados.": (
        "Controla exactamente qué archivos entran y dónde se guardan."
    ),
    "Cor": "Color",
    "Cor da disciplina": "Color de la asignatura",
    "Cria outra disciplina antes de arquivar esta.": (
        "Crea otra asignatura antes de archivar esta."
    ),
    "Cria uma disciplina para a app saber onde guardar o próximo download.": (
        "Crea una asignatura para que la app sepa dónde guardar tu próxima descarga."
    ),
    "Criar a minha organização": "Crear mi organización",
    "Criar tarefa para cada ficheiro": "Crear una tarea para cada archivo",
    "Código": "Código",
    "Definições": "Ajustes",
    "Definições danificadas": "Ajustes dañados",
    "Definições guardadas.": "Ajustes guardados.",
    "Desfazer última organização": "Deshacer la última organización",
    "Destino de uma organização interrompida; compara antes de continuar.": (
        "Destino de una organización interrumpida; compara antes de continuar."
    ),
    "Destino em Downloads de uma devolução interrompida; compara os ficheiros.": (
        "Destino en Descargas de una devolución interrumpida; compara los archivos."
    ),
    "Devolver este ficheiro a Downloads": "Devolver este archivo a Descargas",
    "Disciplina": "Asignatura",
    "Disciplinas": "Asignaturas",
    "Documento registado que já não está no destino esperado.": (
        "Documento registrado que ya no está en el destino esperado."
    ),
    "Downloads arrumados\nantes de se perderem.": "Descargas organizadas\nantes de perderse.",
    "Downloads vigiado. Só os formatos de estudo configurados entram.": (
        "Descargas vigilada. Solo entran los formatos de estudio configurados."
    ),
    "Editar": "Editar",
    "Editar disciplina": "Editar asignatura",
    "Editar tarefa": "Editar tarea",
    "Elimina o filtro para ver todas as tarefas ou adiciona uma tarefa para este dia.": (
        "Quita el filtro para ver todas las tareas o añade una tarea para este día."
    ),
    "Eliminar": "Eliminar",
    "Encontrado numa disciplina sem registo. Não foi movido nem alterado.": (
        "Encontrado en una asignatura sin registro. No fue movido ni alterado."
    ),
    "Escolhe o teu ponto de partida": "Elige tu punto de partida",
    "Escolhe uma disciplina antes de organizar.": "Elige una asignatura antes de organizar.",
    "Escolhe uma opção": "Elige una opción",
    "Escolhe uma pasta para a Universidade.": "Elige una carpeta para la Universidad.",
    "Escolher pasta": "Elegir carpeta",
    "Escolher pasta Universidade": "Elegir carpeta Universidad",
    "Escolher…": "Examinar…",
    "Escreve o nome da disciplina para continuar.": "Escribe el nombre de la asignatura para continuar.",
    "Escreve o nome da primeira disciplina.": "Escribe el nombre de la primera asignatura.",
    "Escreve o título da tarefa para continuar.": "Escribe el título de la tarea para continuar.",
    "Escreve uma tarefa antes de adicionar.": "Escribe una tarea antes de añadir.",
    "Espera que a importação de Downloads termine antes de guardar.": (
        "Espera a que termine la importación de Descargas antes de guardar."
    ),
    "Espera que o lote atual termine antes de iniciar outro.": (
        "Espera a que termine el lote actual antes de iniciar otro."
    ),
    "Esta base de dados foi criada por uma versão mais recente do Organizador. Abre a versão mais recente da app. Nenhum ficheiro foi alterado.": (
        "Esta base de datos fue creada por una versión más reciente de Organizador. "
        "Abre la versión más reciente de la app. Ningún archivo fue alterado."
    ),
    "Ex.: Cálculo I": "Ej.: Cálculo I",
    "Ex.: MAT101": "Ej.: MAT101",
    "Ex.: MAT101 (opcional)": "Ej.: MAT101 (opcional)",
    "Ex.: cálculo, derivadas, integrais": "Ej.: cálculo, derivadas, integrales",
    "Ex.: regra da cadeia, normalização, Revolução Francesa…": (
        "Ej.: regla de la cadena, normalización, Revolución Francesa…"
    ),
    "Experimenta menos palavras ou confirma se o ficheiro aparece nos organizados recentes.": (
        "Prueba con menos palabras o comprueba si el archivo aparece en los organizados recientemente."
    ),
    "Extensões aceites": "Extensiones aceptadas",
    "Fechar": "Cerrar",
    "Ficheiro devolvido": "Archivo devuelto",
    "Ficheiro organizado": "Archivo organizado",
    "Ficheiro restaurado por uma operação de desfazer interrompida.": (
        "Archivo restaurado por una operación de deshacer interrumpida."
    ),
    "Ficheiros adotados": "Archivos adoptados",
    "Ficheiros de {name}": "Archivos de {name}",
    "Foram encontrados {total} ficheiros elegíveis. Serão verificados no máximo {selected} e movidos para a Caixa de Entrada.{remaining}\n\nCada ficheiro continuará a precisar da tua confirmação.": (
        "Se encontraron {total} archivos elegibles. Se verificarán como máximo {selected} "
        "y se moverán a la Bandeja de Entrada.{remaining}\n\nCada archivo seguirá necesitando tu confirmación."
    ),
    "Geral": "General",
    "Guardar definições": "Guardar ajustes",
    "Guardar disciplina": "Guardar asignatura",
    "Guardar tarefa": "Guardar tarea",
    "Idioma": "Idioma",
    "Importar de Downloads…": "Importar de Descargas…",
    "Importar ficheiros existentes?": "¿Importar archivos existentes?",
    "Importação de Downloads concluída": "Importación de Descargas terminada",
    "Importação em curso": "Importación en curso",
    "Importação indisponível": "Importación no disponible",
    "Iniciar o Organizador quando entro no Windows": (
        "Iniciar Organizador cuando entro en Windows"
    ),
    "Início": "Inicio",
    "Já existe uma disciplina ativa com o mesmo nome ou pasta: {names}. Edita-a primeiro para libertar o nome.": (
        "Ya existe una asignatura activa con el mismo nombre o carpeta: {names}. "
        "Edítala primero para liberar el nombre."
    ),
    "Já existe uma disciplina com esse nome.\n\n{error}": (
        "Ya existe una asignatura con ese nombre.\n\n{error}"
    ),
    "Já existe uma disciplina ou pasta com esse nome.\n\n{error}": (
        "Ya existe una asignatura o carpeta con ese nombre.\n\n{error}"
    ),
    "Mais tarde": "Más tarde",
    "Mais tarde em {count}s": "Más tarde en {count}s",
    "Mantém cada entrega junto da disciplina a que pertence.": (
        "Mantén cada entrega junto a la asignatura a la que pertenece."
    ),
    "Mantém uma disciplina ativa": "Mantén una asignatura activa",
    "Marcar revisto": "Marcar como revisado",
    "Modelo do nome": "Plantilla de nombre",
    "Mostrar arquivadas": "Mostrar archivadas",
    "Mostrar na pasta": "Mostrar en la carpeta",
    "Mostrar os ficheiros organizados nesta disciplina": (
        "Mostrar los archivos organizados en esta asignatura"
    ),
    "Nada para desfazer": "Nada que deshacer",
    "Nada para importar": "Nada que importar",
    "Nada é arquivado sem uma decisão. Organiza agora ou deixa para mais tarde.": (
        "Nada se archiva sin una decisión. Organiza ahora o déjalo para más tarde."
    ),
    "Nenhum ficheiro foi substituído ou apagado.": "Ningún archivo fue sobrescrito o borrado.",
    "Nenhum ficheiro foi substituído ou apagado. ": "Ningún archivo fue sobrescrito o borrado. ",
    "No dia": "El mismo día",
    "Nome": "Nombre",
    "Nome final do ficheiro": "Nombre final del archivo",
    "Nomes finais": "Nombres finales",
    "Nova disciplina": "Nueva asignatura",
    "Nova tarefa, por exemplo: entregar ficha 4": ("Nueva tarea, por ejemplo: entregar ficha 4"),
    "Novo material de estudo": "Nuevo material de estudio",
    "Novo material na Caixa de Entrada": "Nuevo material en la Bandeja de Entrada",
    "Não encontrei essa expressão": "No encontré esa expresión",
    "Não existem ficheiros elegíveis no nível principal de Downloads.": (
        "No hay archivos elegibles en el nivel principal de Descargas."
    ),
    "Não foi possível abrir": "No se pudo abrir",
    "Não foi possível abrir a pasta configurada: {error}": (
        "No se pudo abrir la carpeta configurada: {error}"
    ),
    "Não foi possível abrir as pastas": "No se pudieron abrir las carpetas",
    "Não foi possível abrir os dados": "No se pudieron abrir los datos",
    "Não foi possível adotar": "No se pudo adoptar",
    "Não foi possível criar": "No se pudo crear",
    "Não foi possível desfazer": "No se pudo deshacer",
    "Não foi possível devolver": "No se pudo devolver",
    "Não foi possível encontrar:\n{path}": "No se pudo encontrar:\n{path}",
    "Não foi possível guardar": "No se pudo guardar",
    "Não foi possível iniciar o registo": "No se pudo iniciar el registro",
    "Não foi possível ler as definições guardadas. A app abriu com valores seguros para poderes corrigi-las.\n\n{error}": (
        "No se pudieron leer los ajustes guardados. La app abrió con valores seguros "
        "para que puedas corregirlos.\n\n{error}"
    ),
    "Não foi possível mostrar": "No se pudo mostrar",
    "Não foi possível procurar": "No se pudo buscar",
    "Não foi possível recolher o ficheiro": "No se pudo recoger el archivo",
    "Não foi possível remover": "No se pudo eliminar",
    "Não foi possível restaurar": "No se pudo restaurar",
    "Não foi possível restaurar a cópia": "No se pudo restaurar la copia",
    "A cópia pedida não pôde ser restaurada e os dados atuais foram mantidos. Consulta organizador.log antes de tentar novamente.\n\n{error}": (
        "La copia solicitada no se pudo restaurar y los datos actuales se mantuvieron. "
        "Consulta organizador.log antes de intentarlo de nuevo.\n\n{error}"
    ),
    "Cópia restaurada": "Copia restaurada",
    "Os dados foram repostos a partir da cópia de {when}.": (
        "Los datos se restablecieron desde la copia de {when}."
    ),
    "Não foi possível rever o histórico local: {error}": (
        "No se pudo revisar el historial local: {error}"
    ),
    "Não é da universidade": "No es de la universidad",
    "Não é da universidade: devolve o ficheiro": ("No es de la universidad: devuelve el archivo"),
    "O caminho registado já não é um ficheiro normal. Não foi seguido nem alterado.": (
        "La ruta registrada ya no es un archivo normal. No fue seguida ni alterada."
    ),
    "Duas disciplinas partilham a mesma pasta no Windows. Os documentos podem misturar-se; arquiva uma delas se for um engano.": (
        "Dos asignaturas comparten la misma carpeta en Windows. Los documentos pueden "
        "mezclarse; archiva una de ellas si fue un error."
    ),
    "O ficheiro ou o registo mudou desde a verificação. Nada foi removido.": (
        "El archivo o el registro cambió desde la comprobación. Nada fue eliminado."
    ),
    "O idioma novo é aplicado ao reiniciar a app.": (
        "El nuevo idioma se aplica al reiniciar la app."
    ),
    "O primeiro documento organizado aparece aqui. A app não toca nos ficheiros antigos sem pedires.": (
        "El primer documento organizado aparece aquí. La app no toca los archivos antiguos sin que lo pidas."
    ),
    "O registo mudou desde que a página foi aberta. Nada foi removido.": (
        "El registro cambió desde que se abrió la página. Nada fue eliminado."
    ),
    "O teu semestre, arrumado.": "Tu semestre, organizado.",
    "Oculta a disciplina sem apagar os respetivos ficheiros": (
        "Oculta la asignatura sin borrar sus archivos"
    ),
    "Operação de desfazer interrompida; confirma as pastas antes de continuar.": (
        "Operación de deshacer interrumpida; confirma las carpetas antes de continuar."
    ),
    "Organizador": "Organizador",
    "Organizador continua ativo": "Organizador sigue activo",
    "Organizador v{version} · código MIT · componentes de terceiros com licenças próprias": (
        "Organizador v{version} · licencia MIT · componentes de terceros con sus propias licencias"
    ),
    "Organizador · a preparar": "Organizador · preparando",
    "Organizador · {state}": "Organizador · {state}",
    "Organizar": "Organizar",
    "Organizar ficheiro": "Organizar archivo",
    "Organizar seleção": "Organizar selección",
    "Organizar seleção ({count})": "Organizar selección ({count})",
    "Organizar {count} ficheiro": "Organizar {count} archivo",
    "Organizar {count} ficheiros": "Organizar {count} archivos",
    "Organizar com Organizador": "Organizar con Organizador",
    "Atualização em curso": "Actualización en curso",
    "A organizar {count} ficheiro…": "Organizando {count} archivo…",
    "A organizar {count} ficheiros…": "Organizando {count} archivos…",
    "Já existe uma organização em curso; espera que termine.": (
        "Ya hay una organización en curso; espera a que termine."
    ),
    "Não foi possível concluir a organização.": "No se pudo completar la organización.",
    "Não foi possível organizar o ficheiro.": "No se pudo organizar el archivo",
    "Organização desfeita": "Organización deshecha",
    "Organização que não pode ser desfeita enquanto o ficheiro estiver em falta.": (
        "Organización que no puede deshacerse mientras falte el archivo."
    ),
    "Origem de uma devolução interrompida; não foi alterada no arranque.": (
        "Origen de una devolución interrumpida; no fue alterada al arrancar."
    ),
    "Origem de uma operação de desfazer interrompida; não foi alterada no arranque.": (
        "Origen de una operación de deshacer interrumpida; no fue alterada al arrancar."
    ),
    "Origem de uma organização interrompida; não foi alterada no arranque.": (
        "Origen de una organización interrumpida; no fue alterada al arrancar."
    ),
    "Os códigos e palavras-chave tornam as sugestões de arquivo mais precisas.": (
        "Los códigos y palabras clave hacen las sugerencias de archivo más precisas."
    ),
    "Os downloads novos aparecem aqui antes de irem para uma disciplina.": (
        "Las descargas nuevas aparecen aquí antes de ir a una asignatura."
    ),
    "Os ficheiros elegíveis passam primeiro por uma Caixa de Entrada segura. Tu confirmas a disciplina e nada é substituído.": (
        "Los archivos elegibles pasan primero por una Bandeja de Entrada segura. "
        "Tú confirmas la asignatura y nada se sobrescribe."
    ),
    "Os ficheiros mudaram ou já estavam a ser processados e ficaram em Downloads.": (
        "Los archivos cambiaron o ya se estaban procesando y se quedaron en Descargas."
    ),
    "Padrão das Definições": "Predeterminado de Ajustes",
    "Palavras-chave": "Palabras clave",
    "Pasta Downloads": "Carpeta Descargas",
    "Pasta Universidade": "Carpeta Universidad",
    "Pasta: {name}": "Carpeta: {name}",
    "Pastas e vigilância": "Carpetas y vigilancia",
    "Pausar vigilância": "Pausar vigilancia",
    "Pesquisa": "Búsqueda",
    "Pesquisa nos documentos": "Búsqueda en documentos",
    "Pesquisar nos apontamentos": "Buscar en tus apuntes",
    "Podes alterar estas opções depois. Começa por criar uma disciplina.": (
        "Puedes cambiar estas opciones después. Empieza creando una asignatura."
    ),
    "Podes corrigir o nome; a extensão original é preservada": (
        "Puedes editar el nombre; la extensión original se conserva"
    ),
    "Prazo": "Plazo",
    "Prazo amanhã": "Vence mañana",
    "Prazo das tarefas": "Plazo de las tareas",
    "Prazo em {count} dias · {date}": "Vence en {count} días · {date}",
    "Prazo hoje": "Vence hoy",
    "Preparar o Organizador": "Preparar Organizador",
    "Primeira disciplina": "Primera asignatura",
    "Procura palavras dentro de PDFs, documentos Office, ficheiros de texto e notebooks já organizados.": (
        "Busca palabras dentro de PDFs, documentos Office, archivos de texto y "
        "notebooks ya organizados."
    ),
    "Próximos prazos": "Próximos plazos",
    "Quando terminares um download elegível, ele aparece aqui e num pequeno popup.": (
        "Cuando termine una descarga elegible, aparecerá aquí y en una pequeña ventana."
    ),
    "Reativar disciplina?": "¿Restaurar asignatura?",
    "Recuperação manual necessária  ·  {size}  ·  {when}": (
        "Recuperación manual necesaria  ·  {size}  ·  {when}"
    ),
    "Registo mantido": "Registro mantenido",
    "Remover apenas o registo local; nenhum ficheiro é apagado": (
        "Elimina solo el registro local; ningún archivo es borrado"
    ),
    "Remover do catálogo": "Quitar del catálogo",
    "Remover do catálogo?": "¿Quitar del catálogo?",
    "Remover registo": "Eliminar registro",
    "Remover registo em falta?": "¿Eliminar registro faltante?",
    "Restaurar": "Restaurar",
    "Cópias de segurança": "Copias de seguridad",
    "Ainda não há cópias de segurança.": "Todavía no hay copias de seguridad.",
    "Criar cópia agora": "Crear copia ahora",
    "Criar e exportar .zip…": "Crear y exportar .zip…",
    "Restaurar…": "Restaurar…",
    "As cópias guardam o catálogo e as definições. Os teus documentos não são alterados.": (
        "Las copias guardan el catálogo y las definiciones. Tus documentos no se modifican."
    ),
    "Última cópia: {when} · {size}": "Última copia: {when} · {size}",
    "Última cópia: {when} · {count} cópias · {size}": (
        "Última copia: {when} · {count} copias · {size}"
    ),
    "A processar a cópia de segurança…": "Procesando la copia de seguridad…",
    "Espera que as operações de ficheiros terminem antes de criar a cópia.": (
        "Espera a que terminen las operaciones de archivos antes de crear la copia."
    ),
    "Não foi possível concluir a cópia: {error}": "No se pudo completar la copia: {error}",
    "Cópia importada. Escolhe-a na lista para restaurar.": (
        "Copia importada. Elígela en la lista para restaurar."
    ),
    "Cópia exportada: {name}": "Copia exportada: {name}",
    "Cópia criada e exportada: {name}": "Copia creada y exportada: {name}",
    "Cópia de segurança criada.": "Copia de seguridad creada.",
    "Importar cópia de segurança": "Importar copia de seguridad",
    "Exportar cópia de segurança": "Exportar copia de seguridad",
    "Cópias de segurança (*.zip)": "Copias de seguridad (*.zip)",
    "Remover cópia": "Eliminar copia",
    "Remover a cópia de {when}? Esta ação não pode ser desfeita.": (
        "¿Eliminar la copia de {when}? Esta acción no se puede deshacer."
    ),
    "Restaurar cópia de segurança": "Restaurar copia de seguridad",
    "Os dados atuais serão substituídos pela cópia de {when} e a app vai reiniciar. Os teus documentos não são alterados. Continuar?": (
        "Los datos actuales serán sustituidos por la copia de {when} y la app se "
        "reiniciará. Tus documentos no se modifican. ¿Continuar?"
    ),
    "Espera que as operações de ficheiros terminem antes de restaurar.": (
        "Espera a que terminen las operaciones de archivos antes de restaurar."
    ),
    "Fecha e reabre o Organizador para concluir a reposição.": (
        "Cierra y vuelve a abrir Organizador para completar la restauración."
    ),
    "Restaurar substitui o catálogo e as definições atuais.": (
        "Restaurar sustituye el catálogo y las definiciones actuales."
    ),
    "Manual": "Manual",
    "Antes de atualizar": "Antes de actualizar",
    "Antes de restaurar": "Antes de restaurar",
    "Do sistema": "Del sistema",
    "{size} · esquema {version}": "{size} · esquema {version}",
    "Importar .zip…": "Importar .zip…",
    "Exportar": "Exportar",
    "Remover": "Eliminar",
    "Retomar vigilância": "Reanudar vigilancia",
    "Rever {name}": "Revisar {name}",
    "Revisão manual do histórico": "Revisión manual del historial",
    "Revê as Definições antes de ativar a vigilância.\n\n{error}": (
        "Revisa los Ajustes antes de activar la vigilancia.\n\n{error}"
    ),
    "Revê: {errors}.": "Revisa: {errors}.",
    "Sair": "Salir",
    "Sair da configuração?": "¿Salir de la configuración?",
    "Selecionar {name}": "Seleccionar {name}",
    "Sem palavras-chave": "Sin palabras clave",
    "Sem prazo": "Sin plazo",
    "Sem resultados. O documento pode ainda estar a ser indexado ou ser um PDF digitalizado.": (
        "Sin resultados. El documento puede seguir indexándose o ser un PDF escaneado."
    ),
    "Sem sugestão": "Sin sugerencia",
    "Sem tarefas neste dia": "Sin tareas este día",
    "Sem tarefas pendentes": "Sin tareas pendientes",
    "Sem uma disciplina, a app não começa a mover downloads. Podes voltar a configurar depois.": (
        "Sin una asignatura la app no empieza a mover descargas. Puedes configurarla después."
    ),
    "Será removido apenas o registo local e o índice de pesquisa. Nenhum ficheiro será apagado. Se o ficheiro reaparecer durante a operação, ficará visível para poder ser adotado novamente.": (
        "Solo se eliminará el registro local y el índice de búsqueda. Ningún archivo será "
        "borrado. Si el archivo reaparece durante la operación, quedará visible para poder "
        "ser adoptado de nuevo."
    ),
    "Sugestão {percent}%": "Sugerencia {percent}%",
    "Só a organização mais recente pode ser desfeita.": (
        "Solo la organización más reciente puede deshacerse."
    ),
    "Tamanho mínimo": "Tamaño mínimo",
    "Tarefa": "Tarea",
    "Tarefa geral": "Tarea general",
    "Tarefas": "Tareas",
    "Tarefas e prazos": "Tareas y plazos",
    "Tema": "Tema",
    "Tempo do popup": "Tiempo del popup",
    "Fechar o popup automaticamente": "Cerrar el popup automáticamente",
    "Sem esta opção, o popup fica aberto até escolheres uma ação.": (
        "Sin esta opción, el popup permanece abierto hasta que elijas una acción."
    ),
    "Tipo": "Tipo",
    "Tipo de documento": "Tipo de documento",
    "Todos vão para a mesma disciplina e tipo. Cada ficheiro mantém o seu próprio histórico; só a última organização pode ser desfeita.": (
        "Todos van a la misma asignatura y tipo. Cada archivo mantiene su propio "
        "historial; solo la última organización puede deshacerse."
    ),
    "Tokens: {tokens}. A extensão original é sempre preservada.": (
        "Tokens: {tokens}. La extensión original siempre se conserva."
    ),
    "Tranquilidade": "Tranquilidad",
    "Tudo fica neste computador. Nenhum documento é enviado para a internet.": (
        "Todo se queda en este ordenador. Ningún documento se envía a internet."
    ),
    "Tudo no lugar": "Todo en su sitio",
    "Título da tarefa": "Título de la tarea",
    "Ver ficheiros": "Ver archivos",
    "Ver todas": "Ver todas",
    "Verificação de segurança concluída": "Comprobación de seguridad terminada",
    "Verificação de segurança incompleta": "Comprobación de seguridad incompleta",
    "Verificação incompleta": "Comprobación incompleta",
    "Versão da base de dados mais recente": "Versión de base de datos más reciente",
    "Vigiar novos ficheiros em Downloads": "Vigilar nuevos archivos en Descargas",
    "Vigilância de Downloads desligada": "Vigilancia de Descargas desactivada",
    "Vigilância desligada": "Vigilancia desactivada",
    "Vigilância em pausa": "Vigilancia en pausa",
    "Vigilância em pausa. Os novos downloads ficam onde estão.": (
        "Vigilancia en pausa. Las descargas nuevas se quedan donde están."
    ),
    "Volta a mostrar a disciplina nas escolhas de arquivo": (
        "Vuelve a mostrar la asignatura en las opciones de archivo"
    ),
    "a verificação atingiu o limite de segurança": "la comprobación alcanzó su límite de seguridad",
    "alguns caminhos não puderam ser verificados": "algunas rutas no pudieron comprobarse",
    "diapositivo {page}": "diapositiva {page}",
    "documento": "documento",
    "e mais {count}": "y {count} más",
    "estudo local": "estudio local",
    "está atrasada": "está atrasada",
    "folha {page}": "hoja {page}",
    "página {page}": "página {page}",
    "vence amanhã": "vence mañana",
    "vence em {count} dias": "vence en {count} días",
    "vence hoje": "vence hoy",
    "verificação incompleta": "comprobación incompleta",
    "{count} arquivada": "{count} archivada",
    "{count} arquivadas": "{count} archivadas",
    "{count} colisão de nomes resolvida sem substituir nada": (
        "{count} colisión de nombres resuelta sin sobrescribir nada"
    ),
    "{count} colisões de nomes resolvidas sem substituir nada": (
        "{count} colisiones de nombres resueltas sin sobrescribir nada"
    ),
    "{count} com erro": "{count} con error",
    "{count} devolução a Downloads": "{count} devolución a Descargas",
    "{count} devoluções a Downloads": "{count} devoluciones a Descargas",
    "{count} disciplina ativa": "{count} asignatura activa",
    "{count} disciplinas ativas": "{count} asignaturas activas",
    "{count} ficheiro adotado sem mover": "{count} archivo adoptado sin mover",
    "{count} ficheiro organizado": "{count} archivo organizado",
    "{count} ficheiro por decidir": "{count} archivo por decidir",
    "{count} ficheiro por decidir · {recovery} precisam de recuperação": (
        "{count} archivo por decidir · {recovery} necesitan recuperación"
    ),
    "{count} ficheiro precisa de recuperação manual": (
        "{count} archivo necesita recuperación manual"
    ),
    "{count} ficheiro precisa de revisão manual": "{count} incidencia necesita revisión manual",
    "{count} ficheiro · {size}": "{count} archivo · {size}",
    "{count} ficheiros adotados sem mover": "{count} archivos adoptados sin mover",
    "{count} ficheiros organizados": "{count} archivos organizados",
    "{count} ficheiros por decidir": "{count} archivos por decidir",
    "{count} ficheiros por decidir · {recovery} precisam de recuperação": (
        "{count} archivos por decidir · {recovery} necesitan recuperación"
    ),
    "{count} ficheiros precisam de recuperação manual": (
        "{count} archivos necesitan recuperación manual"
    ),
    "{count} ficheiros precisam de revisão manual": "{count} incidencias necesitan revisión manual",
    "{count} ficheiros · {size}": "{count} archivos · {size}",
    "{count} ignorado": "{count} ignorado",
    "{count} ignorados": "{count} ignorados",
    "{count} importado": "{count} importado",
    "{count} importados": "{count} importados",
    "{count} não entraram neste lote e ficaram em Downloads.": (
        "{count} no entraron en este lote y se quedaron en Descargas."
    ),
    "{count} ocorrência do histórico precisa de revisão": (
        "{count} incidencia del historial necesita revisión"
    ),
    "{count} ocorrências do histórico precisam de revisão": (
        "{count} incidencias del historial necesitan revisión"
    ),
    "{count} operação interrompida recuperada": ("{count} operación interrumpida recuperada"),
    "{count} operações interrompidas recuperadas": (
        "{count} operaciones interrumpidas recuperadas"
    ),
    "{count} organizado, {failed} com erro. Revê: {errors}.": (
        "{count} organizado, {failed} con error. Revisa: {errors}."
    ),
    "{count} organizado.": "{count} organizado.",
    "{count} organizados, {failed} com erro. Revê: {errors}.": (
        "{count} organizados, {failed} con error. Revisa: {errors}."
    ),
    "{count} organizados.": "{count} organizados.",
    "{count} organização desfeita": "{count} organización deshecha",
    "{count} organizações desfeitas": "{count} organizaciones deshechas",
    "{count} registo da Caixa de Entrada foi revisto": (
        "{count} registro de la Bandeja de Entrada fue revisado"
    ),
    "{count} registos da Caixa de Entrada foram revistos": (
        "{count} registros de la Bandeja de Entrada fueron revisados"
    ),
    "{count} resultados · os parênteses retos mostram a correspondência": (
        "{count} resultados · los corchetes marcan la coincidencia"
    ),
    "{kind} · {size} · organizado {date}": "{kind} · {size} · organizado {date}",
    "{name} (arquivada)": "{name} (archivada)",
    "{name} deixa de aparecer nas escolhas. Os ficheiros e tarefas não são apagados.": (
        "{name} deja de aparecer en las opciones. Sus archivos y tareas no se borran."
    ),
    "{name} deixará de aparecer na pesquisa e nos recentes. O ficheiro permanecerá exatamente onde está.": (
        "{name} dejará de aparecer en la búsqueda y en recientes. El archivo se queda "
        "exactamente donde está."
    ),
    "{name} está pronto para organizar.": "{name} está listo para organizar.",
    "{name} foi adotado sem mover o ficheiro.": ("{name} fue adoptado sin mover el archivo."),
    "{name} foi guardado em {destination}.": "{name} se guardó en {destination}.",
    "{name} saiu do catálogo; o ficheiro ficou no lugar.": (
        "{name} salió del catálogo; el archivo se quedó en su sitio."
    ),
    "{name} volta a aparecer nas escolhas de arquivo. Os ficheiros e tarefas não foram alterados.": (
        "{name} vuelve a aparecer en las opciones de archivo. Los archivos y tareas no fueron alterados."
    ),
    "{name} voltou para {folder}.": "{name} volvió a {folder}.",
    "{name} voltou à Caixa de Entrada.": "{name} volvió a la Bandeja de Entrada.",
    "{size}  ·  recebido da pasta {folder}": "{size}  ·  recibido de la carpeta {folder}",
    "{size}  ·  {when}  ·  Sugestão: {suggestion} / {kind}": (
        "{size}  ·  {when}  ·  Sugerencia: {suggestion} / {kind}"
    ),
    "{subject}  ·  {due}": "{subject}  ·  {due}",
    "{subject}  ·  {kind}  ·  {location}": "{subject}  ·  {kind}  ·  {location}",
    "{subject}  ·  {kind}  ·  {size}": "{subject}  ·  {kind}  ·  {size}",
    "{subject} · {kind} · adotado sem mover": "{subject} · {kind} · adoptado sin mover",
    "{title} {when}.": "{title} {when}.",
    "Procurar atualizações…": "Buscar actualizaciones…",
    "Instalar atualização {version}": "Instalar actualización {version}",
    "Atualização disponível": "Actualización disponible",
    "Organizador {version} está disponível. Escolhe “Instalar atualização” no menu do tabuleiro.": (
        "Organizador {version} está disponible. Elige «Instalar actualización» en el menú de la bandeja."
    ),
    "A transferência da atualização falhou: {error}": (
        "La descarga de la actualización falló: {error}"
    ),
    "Não foi possível verificar a atualização: {error}": (
        "No se pudo verificar la actualización: {error}"
    ),
    "A verificação da atualização falhou; o ficheiro foi descartado.": (
        "La verificación de la actualización falló; el archivo fue descartado."
    ),
    "A atualização descarregada está corrompida.": "La actualización descargada está corrupta.",
    "A atualização não contém a aplicação completa.": (
        "La actualización no contiene la aplicación completa."
    ),
    "A instalar atualização…": "Instalando actualización…",
    "A transferir e a verificar Organizador {version}.": (
        "Descargando y verificando Organizador {version}."
    ),
    "A reiniciar para aplicar a atualização…": "Reiniciando para aplicar la actualización…",
    "Atualização falhou": "Actualización fallida",
    "Não foi possível instalar a atualização.": "No se pudo instalar la actualización.",
    "A atualização só se aplica à versão instalada.": (
        "Las actualizaciones solo se aplican a la versión instalada."
    ),
    "Sem atualizações nesta instalação": "Sin actualizaciones en esta instalación",
    "Ficheiros organizados": "Archivos organizados",
    "{count} ficheiros estão prontos para organizar.": (
        "{count} archivos están listos para organizar."
    ),
    "Silenciar notificações de arquivo": "Silenciar notificaciones de archivo",
    "Sem avisos de ficheiros organizados; erros e prazos continuam visíveis.": (
        "Sin avisos de archivos organizados; los errores y los plazos siguen visibles."
    ),
    "A app está a correr em modo de desenvolvimento; as atualizações aplicam-se apenas à versão instalada.": (
        "La app se ejecuta en modo de desarrollo; las actualizaciones solo se aplican a la versión instalada."
    ),
    "Procurar atualizações automaticamente": "Buscar actualizaciones automáticamente",
    "Atualização pronta": "Actualización lista",
    "A atualização extraída excede o limite permitido.": (
        "La actualización extraída supera el límite permitido."
    ),
    "Já existe uma instalação de atualização em curso: {owner}.": (
        "Ya hay una instalación de actualización en curso: {owner}."
    ),
    "A atualização contém caminhos duplicados.": "La actualización contiene rutas duplicadas.",
    "A atualização contém caminhos incompatíveis.": (
        "La actualización contiene rutas incompatibles."
    ),
    "A atualização contém demasiados ficheiros.": "La actualización contiene demasiados archivos.",
    "A atualização contém um caminho de ficheiro inseguro.": (
        "La actualización contiene una ruta de archivo insegura."
    ),
    "A atualização contém um ficheiro encriptado não suportado.": (
        "La actualización contiene un archivo cifrado no compatible."
    ),
    "A atualização contém um tipo de ficheiro não permitido.": (
        "La actualización contiene un tipo de archivo no permitido."
    ),
    "A pasta não contém uma instalação completa do Organizador.": (
        "La carpeta no contiene una instalación completa de Organizador."
    ),
    "Não foi possível iniciar o assistente de atualização.": (
        "No se pudo iniciar el asistente de actualización."
    ),
    "O ficheiro da atualização excede o limite permitido.": (
        "El archivo de la actualización supera el límite permitido."
    ),
    "O tamanho de um ficheiro da atualização é inválido.": (
        "El tamaño de un archivo de la actualización no es válido."
    ),
    "Um ficheiro da atualização excede o limite permitido.": (
        "Un archivo de la actualización supera el límite permitido."
    ),
    "A procurar atualizações…": "Buscando actualizaciones…",
    "A instalar atualização {version}…": "Instalando actualización {version}…",
    "Sem atualizações": "Sin actualizaciones",
    "O Organizador está atualizado.": "Organizador está actualizado.",
    "Não foi possível procurar atualizações.": "No se pudo buscar actualizaciones.",
    "A atualização transferida não corresponde à versão {version}.": (
        "La actualización descargada no corresponde a la versión {version}."
    ),
    "Atualização instalada": "Actualización instalada",
    "Atualização {version} instalada com sucesso.": (
        "Actualización {version} instalada correctamente."
    ),
    "Atualização instalada com sucesso.": "Actualización instalada correctamente.",
    "Atualização revertida": "Actualización revertida",
    "A atualização {version} falhou e a versão anterior foi restaurada.": (
        "La actualización {version} falló y se restauró la versión anterior."
    ),
    "A atualização falhou e a versão anterior foi restaurada.": (
        "La actualización falló y se restauró la versión anterior."
    ),
    "A atualização falhou e a reposição automática não foi concluída.": (
        "La actualización falló y la restauración automática no se completó."
    ),
    "A versão anterior foi mantida em: {path}.": "La versión anterior se conservó en: {path}.",
    "Atualização inválida": "Actualización no válida",
    "A atualização não corresponde a esta instalação. Nenhum ficheiro foi alterado.": (
        "La actualización no corresponde a esta instalación. No se modificó ningún archivo."
    ),
    "A atualização não pôde ser validada. Nenhum ficheiro foi alterado.": (
        "La actualización no pudo validarse. No se modificó ningún archivo."
    ),
    "Não foi possível concluir a atualização": "No se pudo completar la actualización",
    "Não foi possível recuperar os dados": "No se pudieron recuperar los datos",
    "Não foi possível atualizar os dados": "No se pudieron actualizar los datos",
    "Os argumentos da atualização estão incompletos. Nenhum ficheiro foi alterado.": (
        "Los argumentos de la actualización están incompletos. No se modificó ningún archivo."
    ),
    "Existe uma cópia de segurança de migração que não pôde ser restaurada automaticamente. Nenhum ficheiro foi alterado.\n\n{error}": (
        "Hay una copia de seguridad de migración que no pudo restaurarse automáticamente. "
        "No se modificó ningún archivo.\n\n{error}"
    ),
    "A aplicação não conseguiu preparar o catálogo local. Foi tentada a reposição da cópia de segurança.\n\n{error}": (
        "La aplicación no pudo preparar el catálogo local. "
        "Se intentó restaurar la copia de seguridad.\n\n{error}"
    ),
    "Os dados migrados não puderam ser validados. Foi tentada a reposição da cópia de segurança.\n\n{error}": (
        "Los datos migrados no pudieron validarse. "
        "Se intentó restaurar la copia de seguridad.\n\n{error}"
    ),
    "Os dados migrados não puderam ser validados. A versão anterior foi mantida para recuperação manual.": (
        "Los datos migrados no pudieron validarse. "
        "La versión anterior se conservó para una recuperación manual."
    ),
    "A nova versão não conseguiu arrancar. A versão anterior foi mantida para recuperação manual.": (
        "La nueva versión no pudo iniciarse. "
        "La versión anterior se conservó para una recuperación manual."
    ),
    "Não foi possível concluir o arranque": "No se pudo completar el arranque",
    "A aplicação não conseguiu concluir o arranque. Foi tentada a reposição da cópia de segurança.\n\n{error}": (
        "La aplicación no pudo completar el arranque. "
        "Se intentó restaurar la copia de seguridad.\n\n{error}"
    ),
    "A nova versão não conseguiu arrancar. Foi tentada a reposição da cópia de segurança.": (
        "La nueva versión no pudo iniciarse. Se intentó restaurar la copia de seguridad."
    ),
    "Não foi possível ler a pasta Downloads configurada.": (
        "No se pudo leer la carpeta de Descargas configurada."
    ),
    "Já não foi possível encontrar {name}.": "Ya no se pudo encontrar {name}.",
    "{name} ficou em {origin}, mas uma cópia incompleta pode ter ficado em {leftover}. Compara os ficheiros antes de a remover.": (
        "{name} se quedó en {origin}, pero es posible que haya una copia incompleta en "
        "{leftover}. Compara los archivos antes de eliminarla."
    ),
    "{name} mudou ou ainda está a ser usado e ficou em {origin}.": (
        "{name} cambió o sigue en uso y se quedó en {origin}."
    ),
    "Não foi possível registar {name}. O ficheiro ficou em {destination}.": (
        "No se pudo registrar {name}. El archivo se quedó en {destination}."
    ),
    "Não foi possível registar {name}; foi devolvido a {origin} como {returned}.": (
        "No se pudo registrar {name}; se devolvió a {origin} como {returned}."
    ),
    "Este ficheiro não pode ser recolhido. Confirma que não está já na Universidade e que a extensão é aceite.": (
        "Este archivo no se puede recoger. Comprueba que no esté ya en la "
        "Universidad y que la extensión sea aceptada."
    ),
    "Este ficheiro já não está na Caixa de Entrada.": (
        "Este archivo ya no está en la Bandeja de Entrada."
    ),
    "Escolhe uma disciplina ativa.": "Elige una asignatura activa.",
    "Escolhe um tipo de documento válido.": "Elige un tipo de documento válido.",
    "Não foi possível encontrar {name}.": "No se pudo encontrar {name}.",
    "Não foi possível preparar o histórico da organização.": (
        "No se pudo preparar el historial de organización."
    ),
    "A organização ficou incompleta. O original e a cópia foram mantidos; revê ambos na Caixa de Entrada antes de continuar.": (
        "La organización quedó incompleta. El original y la copia se conservaron; "
        "revísalos en la Bandeja de Entrada antes de continuar."
    ),
    "O ficheiro ainda está a ser usado por outra aplicação. Fecha-o e tenta novamente.": (
        "El archivo sigue en uso en otra aplicación. Ciérralo e inténtalo de nuevo."
    ),
    "O movimento foi revertido porque não foi possível atualizar o histórico.": (
        "El movimiento se revirtió porque no se pudo actualizar el historial."
    ),
    "Não foi possível atualizar o histórico. Revê a Caixa de Entrada antes de repetir.": (
        "No se pudo actualizar el historial. Revisa la Bandeja de Entrada antes de reintentar."
    ),
    "O ficheiro já não está disponível para devolver.": (
        "El archivo ya no está disponible para devolver."
    ),
    "Não foi possível preparar o histórico da devolução.": (
        "No se pudo preparar el historial de devolución."
    ),
    "A devolução ficou incompleta. O original e a cópia foram mantidos; revê a Caixa de Entrada e Downloads antes de continuar.": (
        "La devolución quedó incompleta. El original y la copia se conservaron; "
        "revisa la Bandeja de Entrada y Descargas antes de continuar."
    ),
    "Não foi possível devolver o ficheiro. Fecha-o noutras aplicações e tenta de novo.": (
        "No se pudo devolver el archivo. Ciérralo en otras aplicaciones e inténtalo de nuevo."
    ),
    "Não foi possível registar a devolução do ficheiro.": (
        "No se pudo registrar la devolución del archivo."
    ),
    "O último ficheiro organizado já não está no destino. O histórico não foi alterado.": (
        "El último archivo organizado ya no está en su destino. El historial no se modificó."
    ),
    "Não foi possível preparar o histórico para desfazer.": (
        "No se pudo preparar el historial para deshacer."
    ),
    "A operação de desfazer ficou incompleta. O original e a cópia foram mantidos; revê ambos na Caixa de Entrada antes de continuar.": (
        "La operación de deshacer quedó incompleta. El original y la copia se conservaron; "
        "revísalos en la Bandeja de Entrada antes de continuar."
    ),
    "Não foi possível desfazer porque o ficheiro está a ser usado.": (
        "No se pudo deshacer porque el archivo está en uso."
    ),
    "Não foi possível atualizar o histórico ao desfazer.": (
        "No se pudo actualizar el historial al deshacer."
    ),
    "Criar tarefa": "Crear tarea",
    "A cópia incompleta ficou em {path}.": "La copia incompleta se quedó en {path}.",
    "A pasta de destino não é segura: {path}.": "La carpeta de destino no es segura: {path}.",
    "Falha na indexação — o ficheiro continua pesquisável pelo nome.": (
        "La indexación falló — el archivo sigue siendo buscable por su nombre."
    ),
    "Reindexar": "Reindexar",
    "Mover": "Mover",
    "Mover ficheiro": "Mover archivo",
    "A mover…": "Moviendo…",
    "Ficheiro movido": "Archivo movido",
    "{name} está agora em {location}.": "{name} está ahora en {location}.",
    "Não foi possível mover": "No se pudo mover",
    "Espera que as operações de ficheiros terminem antes de mover.": (
        "Espera a que terminen las operaciones de archivos antes de mover."
    ),
    "Escolhe outra disciplina ou outro tipo para mover.": (
        "Elige otra asignatura u otro tipo para mover."
    ),
    "Este documento já não está no catálogo.": ("Este documento ya no está en el catálogo."),
    "Não foi possível preparar o histórico do movimento.": (
        "No se pudo preparar el historial del movimiento."
    ),
    "O movimento ficou incompleto. O original e a cópia foram mantidos; revê ambos antes de continuar.": (
        "El movimiento quedó incompleto. El original y la copia se mantuvieron; "
        "revísalos antes de continuar."
    ),
    "Não foi possível atualizar o histórico. Revê os ficheiros antes de repetir.": (
        "No se pudo actualizar el historial. Revisa los archivos antes de repetir."
    ),
    "Origem de um movimento interrompido; não foi alterada no arranque.": (
        "Origen de un movimiento interrumpido; no se modificó al arrancar."
    ),
    "Destino de um movimento interrompido; compara antes de continuar.": (
        "Destino de un movimiento interrumpido; compara antes de continuar."
    ),
    "A reindexar…": "Reindexando…",
    "A fila de indexação está ocupada; o documento será indexado assim que possível.": (
        "La cola de indexación está ocupada; el documento se indexará lo antes posible."
    ),
    "Tenta organizar o ficheiro quando a atualização terminar.": (
        "Intenta organizar el archivo cuando termine la actualización."
    ),
    "Tentar novamente": "Reintentar",
    "{count} documentos por indexar": "{count} documentos pendientes de indexación",
    "1 documento por indexar": "1 documento pendiente de indexación",
    "{count} documentos com falha na indexação": "{count} documentos con error de indexación",
    "1 documento com falha na indexação": "1 documento con error de indexación",
    "Reconhecer texto em PDFs digitalizados (OCR)": "Reconocer texto en PDF escaneados (OCR)",
    "Todas as disciplinas": "Todas las asignaturas",
    "Todos os tipos": "Todos los tipos",
    "Filtrar por disciplina": "Filtrar por asignatura",
    "Filtrar por tipo de documento": "Filtrar por tipo de documento",
    "{count} documentos": "{count} documentos",
    "1 documento": "1 documento",
    "{subject}  ·  {kind}": "{subject}  ·  {kind}",
}

FR_STRINGS: dict[str, str] = {
    "Notificação indisponível": "Notification indisponible",
    "A notificação expirou ou algum ficheiro já não está disponível. Consulta os ficheiros na app.": "La notification a expiré ou un fichier n'est plus disponible. Consultez vos fichiers dans l'application.",
    "A terminar o Organizador": "Fermeture d'Organizador",
    "A concluir {count} operações de ficheiros antes de sair…": "Fin de {count} opérations de fichiers avant la fermeture…",
    "A concluir a cópia de segurança antes de sair…": ("Fin de la sauvegarde avant la fermeture…"),
    "Espera que as operações de ficheiros terminem antes de guardar.": "Attendez la fin des opérations de fichiers avant d'enregistrer.",
    "Atualização em espera": "Mise à jour en attente",
    "Espera que as operações de ficheiros terminem antes de atualizar.": "Attendez la fin des opérations de fichiers avant la mise à jour.",
    "Não foi possível preparar a recolha do ficheiro.": "Impossible de préparer le transfert du fichier dans la boîte de réception.",
    "Download com recolha interrompida; o original foi mantido para revisão.": "Transfert du téléchargement interrompu ; l'original a été conservé pour vérification.",
    "Cópia por verificar; pode estar incompleta. Compara com o original em Downloads.": "Copie non vérifiée ; elle peut être incomplète. Comparez-la à l'original dans Téléchargements.",
    "Ver existente": "Voir l'existant",
    "Substituir a versão anterior": "Remplacer la version précédente",
    "A versão atual fica na pasta com o sufixo «versão anterior».": "La version actuelle reste dans le dossier avec le suffixe « version précédente ».",
    "Já tens este ficheiro em {location}: {name}": "Tu as déjà ce fichier dans {location} : {name}",
    "versão anterior": "version précédente",
    "Renomeação de versão interrompida; o original foi mantido para revisão.": "Renommage de version interrompu ; l'original a été conservé pour vérification.",
    "Cópia da versão anterior por verificar; compara os ficheiros.": "Copie de la version précédente non vérifiée ; comparez les fichiers.",
    " Os outros {count} ficam em Downloads para um próximo lote.": (
        " Les autres {count} restent dans Téléchargements pour un prochain lot."
    ),
    " bytes": " octets",
    " dias": " jours",
    "({count}) por organizar": "({count}) à organiser",
    "1 dia antes": "1 jour avant",
    "1 resultado · os parênteses retos mostram a correspondência": (
        "1 résultat · les crochets marquent la correspondance"
    ),
    "1 semana antes": "1 semaine avant",
    "2 dias antes": "2 jours avant",
    "3 dias antes": "3 jours avant",
    "A aplicação não conseguiu abrir o catálogo local. Consulta organizador.log antes de tentar novamente.\n\n{error}": (
        "L'application n'a pas pu ouvrir le catalogue local. Consulte organizador.log "
        "avant de réessayer.\n\n{error}"
    ),
    "A app ainda não tem histórico. Organiza o primeiro ficheiro para começar.": (
        "L'application n'a pas encore d'historique. Organise ton premier fichier pour commencer."
    ),
    "A caixa está vazia": "La boîte de réception est vide",
    "A importar…": "Importation…",
    "A importação foi interrompida. Os ficheiros ainda não importados ficaram em Downloads.": (
        "L'importation a été interrompue. Les fichiers non encore importés sont restés dans Téléchargements."
    ),
    "A iniciar…": "Démarrage…",
    "A janela fechou, mas Downloads continua a ser vigiado no tabuleiro do sistema.": (
        "La fenêtre s'est fermée, mais Téléchargements reste surveillé depuis la zone de notification."
    ),
    "A mostrar tarefas de {date}": "Affichage des tâches du {date}",
    "A ocorrência foi marcada como revista. O ficheiro não foi alterado.": (
        "Le signalement a été marqué comme examiné. Le fichier n'a pas été modifié."
    ),
    "A pasta de dados da aplicação não está disponível. Nenhum ficheiro foi alterado.\n\n{error}": (
        "Le dossier de données de l'application n'est pas disponible. "
        "Aucun fichier n'a été modifié.\n\n{error}"
    ),
    "A pesquisa é local. Escreve duas ou mais letras para começar.": (
        "La recherche est locale. Tape deux lettres ou plus pour commencer."
    ),
    "A pesquisa é local. PDFs digitalizados só como imagem podem não ter texto pesquisável.": (
        "La recherche est locale. Les PDF numérisés en image seule peuvent ne pas avoir de texte cherchable."
    ),
    "A preparar a vigilância de Downloads…": "Préparation de la surveillance de Téléchargements…",
    "A verificar {count} ficheiros…": "Vérification de {count} fichiers…",
    "A verificar {count} ficheiro…": "Vérification de {count} fichier…",
    "A vigiar Downloads": "Surveillance de Téléchargements",
    "A vigilância de Downloads está desligada nas Definições.": (
        "La surveillance de Téléchargements est désactivée dans les Paramètres."
    ),
    "Abre a Caixa de Entrada para rever.": "Ouvre la Boîte de réception pour vérifier.",
    "Abrir": "Ouvrir",
    "Abrir Downloads": "Ouvrir Téléchargements",
    "Abrir Organizador": "Ouvrir Organizador",
    "Abrir Universidade": "Ouvrir le dossier Université",
    "Abrir pasta": "Ouvrir le dossier",
    "Abrir pasta Universidade": "Ouvrir le dossier Université",
    "Adiciona a próxima entrega acima ou cria-a ao organizar um documento.": (
        "Ajoute ton prochain devoir ci-dessus, ou crée-le en organisant un document."
    ),
    "Adicionar": "Ajouter",
    "Adicionar disciplina": "Ajouter une matière",
    "Adicionar à pesquisa sem mover o ficheiro": "Ajouter à la recherche sans déplacer le fichier",
    "Adotar": "Adopter",
    "Ainda não existe uma organização reversível.": (
        "Il n'existe pas encore d'organisation réversible."
    ),
    "Ainda não há ficheiros organizados nesta disciplina.": (
        "Aucun fichier organisé dans cette matière pour l'instant."
    ),
    "Ainda não há prazos. Cria uma tarefa ou associa-a quando organizares um ficheiro.": (
        "Pas encore d'échéances. Crée une tâche ou associe-la en organisant un fichier."
    ),
    "Ainda sem ficheiros organizados": "Pas encore de fichiers organisés",
    "Alterar a pasta Universidade afeta os próximos ficheiros; os já organizados não são movidos automaticamente.": (
        "Changer le dossier Université affecte les fichiers futurs ; ceux déjà organisés "
        "ne sont pas déplacés automatiquement."
    ),
    "Arquivada": "Archivée",
    "Arquivar": "Archiver",
    "Arquivar disciplina?": "Archiver la matière ?",
    "As palavras-chave ajudam a reconhecer ficheiros pelo nome.": (
        "Les mots-clés aident à reconnaître les fichiers par leur nom."
    ),
    "Atrasada · {date}": "En retard · {date}",
    "Avisar prazos antes": "Rappeler les échéances à l'avance",
    "Aviso": "Rappel",
    "Caixa de Entrada": "Boîte de réception",
    "Caixa de Entrada  {count}": "Boîte de réception  {count}",
    "Caixa de Entrada ({count})": "Boîte de réception ({count})",
    "Caixa de Entrada vazia": "Boîte de réception vide",
    "Caminho não encontrado": "Chemin introuvable",
    "Cancelar": "Annuler",
    "Com quantos dias de antecedência avisar prazos": (
        "Combien de jours à l'avance prévenir des échéances"
    ),
    "Começa por uma disciplina": "Commence par une matière",
    "Começar a vigiar Downloads depois da configuração": (
        "Commencer à surveiller Téléchargements après la configuration"
    ),
    "Conclui a configuração da aplicação antes de importar ficheiros.": (
        "Termine la configuration de l'application avant d'importer des fichiers."
    ),
    "Controla exatamente quais ficheiros entram e onde ficam guardados.": (
        "Contrôle exactement quels fichiers entrent et où ils sont rangés."
    ),
    "Cor": "Couleur",
    "Cor da disciplina": "Couleur de la matière",
    "Cria outra disciplina antes de arquivar esta.": (
        "Crée une autre matière avant d'archiver celle-ci."
    ),
    "Cria uma disciplina para a app saber onde guardar o próximo download.": (
        "Crée une matière pour que l'application sache où ranger ton prochain téléchargement."
    ),
    "Criar a minha organização": "Créer mon organisation",
    "Criar tarefa para cada ficheiro": "Créer une tâche pour chaque fichier",
    "Código": "Code",
    "Definições": "Paramètres",
    "Definições danificadas": "Paramètres endommagés",
    "Definições guardadas.": "Paramètres enregistrés.",
    "Desfazer última organização": "Annuler le dernier rangement",
    "Destino de uma organização interrompida; compara antes de continuar.": (
        "Destination d'un rangement interrompu ; compare avant de continuer."
    ),
    "Destino em Downloads de uma devolução interrompida; compara os ficheiros.": (
        "Destination dans Téléchargements d'un retour interrompu ; compare les fichiers."
    ),
    "Devolver este ficheiro a Downloads": "Renvoyer ce fichier dans Téléchargements",
    "Disciplina": "Matière",
    "Disciplinas": "Matières",
    "Documento registado que já não está no destino esperado.": (
        "Document enregistré qui n'est plus à la destination prévue."
    ),
    "Downloads arrumados\nantes de se perderem.": "Téléchargements rangés\navant de se perdre.",
    "Downloads vigiado. Só os formatos de estudo configurados entram.": (
        "Téléchargements est surveillé. Seuls les formats d'étude configurés entrent."
    ),
    "Editar": "Modifier",
    "Editar disciplina": "Modifier la matière",
    "Editar tarefa": "Modifier la tâche",
    "Elimina o filtro para ver todas as tarefas ou adiciona uma tarefa para este dia.": (
        "Supprime le filtre pour voir toutes les tâches, ou ajoute une tâche pour ce jour."
    ),
    "Eliminar": "Supprimer",
    "Encontrado numa disciplina sem registo. Não foi movido nem alterado.": (
        "Trouvé dans une matière sans enregistrement. Il n'a été ni déplacé ni modifié."
    ),
    "Escolhe o teu ponto de partida": "Choisis ton point de départ",
    "Escolhe uma disciplina antes de organizar.": "Choisis une matière avant de ranger.",
    "Escolhe uma opção": "Choisis une option",
    "Escolhe uma pasta para a Universidade.": "Choisis un dossier pour l'Université.",
    "Escolher pasta": "Choisir un dossier",
    "Escolher pasta Universidade": "Choisir le dossier Université",
    "Escolher…": "Parcourir…",
    "Escreve o nome da disciplina para continuar.": "Tape le nom de la matière pour continuer.",
    "Escreve o nome da primeira disciplina.": "Tape le nom de la première matière.",
    "Escreve o título da tarefa para continuar.": "Tape le titre de la tâche pour continuer.",
    "Escreve uma tarefa antes de adicionar.": "Tape une tâche avant d'ajouter.",
    "Espera que a importação de Downloads termine antes de guardar.": (
        "Attends la fin de l'importation de Téléchargements avant d'enregistrer."
    ),
    "Espera que o lote atual termine antes de iniciar outro.": (
        "Attends la fin du lot en cours avant d'en commencer un autre."
    ),
    "Esta base de dados foi criada por uma versão mais recente do Organizador. Abre a versão mais recente da app. Nenhum ficheiro foi alterado.": (
        "Cette base de données a été créée par une version plus récente d'Organizador. "
        "Ouvre la version la plus récente de l'application. Aucun fichier n'a été modifié."
    ),
    "Ex.: Cálculo I": "ex. : Calcul I",
    "Ex.: MAT101": "ex. : MAT101",
    "Ex.: MAT101 (opcional)": "ex. : MAT101 (facultatif)",
    "Ex.: cálculo, derivadas, integrais": "ex. : calcul, dérivées, intégrales",
    "Ex.: regra da cadeia, normalização, Revolução Francesa…": (
        "ex. : règle de la chaîne, normalisation, Révolution française…"
    ),
    "Experimenta menos palavras ou confirma se o ficheiro aparece nos organizados recentes.": (
        "Essaie moins de mots, ou vérifie si le fichier apparaît dans les rangements récents."
    ),
    "Extensões aceites": "Extensions acceptées",
    "Fechar": "Fermer",
    "Ficheiro devolvido": "Fichier renvoyé",
    "Ficheiro organizado": "Fichier rangé",
    "Ficheiro restaurado por uma operação de desfazer interrompida.": (
        "Fichier restauré par une opération d'annulation interrompue."
    ),
    "Ficheiros adotados": "Fichiers adoptés",
    "Ficheiros de {name}": "Fichiers de {name}",
    "Foram encontrados {total} ficheiros elegíveis. Serão verificados no máximo {selected} e movidos para a Caixa de Entrada.{remaining}\n\nCada ficheiro continuará a precisar da tua confirmação.": (
        "{total} fichiers éligibles ont été trouvés. Au maximum {selected} seront vérifiés "
        "et déplacés vers la Boîte de réception.{remaining}\n\nChaque fichier continuera de "
        "nécessiter ta confirmation."
    ),
    "Geral": "Général",
    "Guardar definições": "Enregistrer les paramètres",
    "Guardar disciplina": "Enregistrer la matière",
    "Guardar tarefa": "Enregistrer la tâche",
    "Idioma": "Langue",
    "Importar de Downloads…": "Importer depuis Téléchargements…",
    "Importar ficheiros existentes?": "Importer les fichiers existants ?",
    "Importação de Downloads concluída": "Importation de Téléchargements terminée",
    "Importação em curso": "Importation en cours",
    "Importação indisponível": "Importation indisponible",
    "Iniciar o Organizador quando entro no Windows": (
        "Lancer Organizador à l'ouverture de Windows"
    ),
    "Início": "Accueil",
    "Já existe uma disciplina ativa com o mesmo nome ou pasta: {names}. Edita-a primeiro para libertar o nome.": (
        "Une matière active utilise déjà le même nom ou dossier : {names}. "
        "Modifie-la d'abord pour libérer le nom."
    ),
    "Já existe uma disciplina com esse nome.\n\n{error}": (
        "Une matière avec ce nom existe déjà.\n\n{error}"
    ),
    "Já existe uma disciplina ou pasta com esse nome.\n\n{error}": (
        "Une matière ou un dossier avec ce nom existe déjà.\n\n{error}"
    ),
    "Mais tarde": "Plus tard",
    "Mais tarde em {count}s": "Plus tard dans {count}s",
    "Mantém cada entrega junto da disciplina a que pertence.": (
        "Garde chaque devoir avec la matière à laquelle il appartient."
    ),
    "Mantém uma disciplina ativa": "Garde une matière active",
    "Marcar revisto": "Marquer comme examiné",
    "Modelo do nome": "Modèle de nom",
    "Mostrar arquivadas": "Afficher les archivées",
    "Mostrar na pasta": "Afficher dans le dossier",
    "Mostrar os ficheiros organizados nesta disciplina": (
        "Afficher les fichiers organisés dans cette matière"
    ),
    "Nada para desfazer": "Rien à annuler",
    "Nada para importar": "Rien à importer",
    "Nada é arquivado sem uma decisão. Organiza agora ou deixa para mais tarde.": (
        "Rien n'est classé sans une décision. Range maintenant ou laisse pour plus tard."
    ),
    "Nenhum ficheiro foi substituído ou apagado.": ("Aucun fichier n'a été écrasé ni supprimé."),
    "Nenhum ficheiro foi substituído ou apagado. ": ("Aucun fichier n'a été écrasé ni supprimé. "),
    "No dia": "Le jour même",
    "Nome": "Nom",
    "Nome final do ficheiro": "Nom final du fichier",
    "Nomes finais": "Noms finaux",
    "Nova disciplina": "Nouvelle matière",
    "Nova tarefa, por exemplo: entregar ficha 4": (
        "Nouvelle tâche, par exemple : rendre la fiche 4"
    ),
    "Novo material de estudo": "Nouveau matériel d'étude",
    "Novo material na Caixa de Entrada": "Nouveau matériel dans la Boîte de réception",
    "Não encontrei essa expressão": "Je n'ai pas trouvé cette expression",
    "Não existem ficheiros elegíveis no nível principal de Downloads.": (
        "Il n'y a pas de fichiers éligibles à la racine de Téléchargements."
    ),
    "Não foi possível abrir": "Impossible d'ouvrir",
    "Não foi possível abrir a pasta configurada: {error}": (
        "Impossible d'ouvrir le dossier configuré : {error}"
    ),
    "Não foi possível abrir as pastas": "Impossible d'ouvrir les dossiers",
    "Não foi possível abrir os dados": "Impossible d'ouvrir les données",
    "Não foi possível adotar": "Impossible d'adopter",
    "Não foi possível criar": "Impossible de créer",
    "Não foi possível desfazer": "Impossible d'annuler",
    "Não foi possível devolver": "Impossible de renvoyer",
    "Não foi possível encontrar:\n{path}": "Impossible de trouver :\n{path}",
    "Não foi possível guardar": "Impossible d'enregistrer",
    "Não foi possível iniciar o registo": "Impossible de démarrer la journalisation",
    "Não foi possível ler as definições guardadas. A app abriu com valores seguros para poderes corrigi-las.\n\n{error}": (
        "Impossible de lire les paramètres enregistrés. L'application a démarré avec des "
        "valeurs sûres pour que tu puisses les corriger.\n\n{error}"
    ),
    "Não foi possível mostrar": "Impossible d'afficher",
    "Não foi possível procurar": "Impossible de rechercher",
    "Não foi possível recolher o ficheiro": "Impossible de récupérer le fichier",
    "Não foi possível remover": "Impossible de supprimer",
    "Não foi possível restaurar": "Impossible de restaurer",
    "Não foi possível restaurar a cópia": "Impossible de restaurer la sauvegarde",
    "A cópia pedida não pôde ser restaurada e os dados atuais foram mantidos. Consulta organizador.log antes de tentar novamente.\n\n{error}": (
        "La sauvegarde demandée n'a pas pu être restaurée et les données actuelles ont été "
        "conservées. Consulte organizador.log avant de réessayer.\n\n{error}"
    ),
    "Cópia restaurada": "Sauvegarde restaurée",
    "Os dados foram repostos a partir da cópia de {when}.": (
        "Les données ont été restaurées à partir de la sauvegarde du {when}."
    ),
    "Não foi possível rever o histórico local: {error}": (
        "Impossible de consulter l'historique local : {error}"
    ),
    "Não é da universidade": "Pas pour l'université",
    "Não é da universidade: devolve o ficheiro": ("Pas pour l'université : renvoie le fichier"),
    "O caminho registado já não é um ficheiro normal. Não foi seguido nem alterado.": (
        "Le chemin enregistré n'est plus un fichier normal. Il n'a été ni suivi ni modifié."
    ),
    "Duas disciplinas partilham a mesma pasta no Windows. Os documentos podem misturar-se; arquiva uma delas se for um engano.": (
        "Deux matières partagent le même dossier sur Windows. Les documents peuvent se "
        "mélanger ; archive l'une d'elles s'il s'agit d'une erreur."
    ),
    "O ficheiro ou o registo mudou desde a verificação. Nada foi removido.": (
        "Le fichier ou l'enregistrement a changé depuis la vérification. Rien n'a été supprimé."
    ),
    "O idioma novo é aplicado ao reiniciar a app.": (
        "La nouvelle langue est appliquée au redémarrage de l'application."
    ),
    "O primeiro documento organizado aparece aqui. A app não toca nos ficheiros antigos sem pedires.": (
        "Ton premier document rangé apparaît ici. L'application ne touche pas aux anciens "
        "fichiers sans ta demande."
    ),
    "O registo mudou desde que a página foi aberta. Nada foi removido.": (
        "L'enregistrement a changé depuis l'ouverture de la page. Rien n'a été supprimé."
    ),
    "O teu semestre, arrumado.": "Ton semestre, bien rangé.",
    "Oculta a disciplina sem apagar os respetivos ficheiros": (
        "Masque la matière sans supprimer ses fichiers"
    ),
    "Operação de desfazer interrompida; confirma as pastas antes de continuar.": (
        "Opération d'annulation interrompue ; vérifie les dossiers avant de continuer."
    ),
    "Organizador": "Organizador",
    "Organizador continua ativo": "Organizador reste actif",
    "Organizador v{version} · código MIT · componentes de terceiros com licenças próprias": (
        "Organizador v{version} · licence MIT · composants tiers sous leurs propres licences"
    ),
    "Organizador · a preparar": "Organizador · préparation",
    "Organizador · {state}": "Organizador · {state}",
    "Organizar": "Ranger",
    "Organizar ficheiro": "Ranger le fichier",
    "Organizar seleção": "Ranger la sélection",
    "Organizar seleção ({count})": "Ranger la sélection ({count})",
    "Organizar {count} ficheiro": "Ranger {count} fichier",
    "Organizar {count} ficheiros": "Ranger {count} fichiers",
    "Organizar com Organizador": "Organiser avec Organizador",
    "Atualização em curso": "Mise à jour en cours",
    "A organizar {count} ficheiro…": "Rangement de {count} fichier…",
    "A organizar {count} ficheiros…": "Rangement de {count} fichiers…",
    "Já existe uma organização em curso; espera que termine.": (
        "Un rangement est déjà en cours ; attends qu'il se termine."
    ),
    "Não foi possível concluir a organização.": "Impossible de terminer le rangement.",
    "Não foi possível organizar o ficheiro.": "Impossible de ranger le fichier",
    "Organização desfeita": "Rangement annulé",
    "Organização que não pode ser desfeita enquanto o ficheiro estiver em falta.": (
        "Rangement impossible à annuler tant que le fichier est manquant."
    ),
    "Origem de uma devolução interrompida; não foi alterada no arranque.": (
        "Origine d'un retour interrompu ; non modifié au démarrage."
    ),
    "Origem de uma operação de desfazer interrompida; não foi alterada no arranque.": (
        "Origine d'une opération d'annulation interrompue ; non modifiée au démarrage."
    ),
    "Origem de uma organização interrompida; não foi alterada no arranque.": (
        "Origine d'un rangement interrompu ; non modifié au démarrage."
    ),
    "Os códigos e palavras-chave tornam as sugestões de arquivo mais precisas.": (
        "Les codes et mots-clés rendent les suggestions de rangement plus précises."
    ),
    "Os downloads novos aparecem aqui antes de irem para uma disciplina.": (
        "Les nouveaux téléchargements apparaissent ici avant d'aller dans une matière."
    ),
    "Os ficheiros elegíveis passam primeiro por uma Caixa de Entrada segura. Tu confirmas a disciplina e nada é substituído.": (
        "Les fichiers éligibles passent d'abord par une Boîte de réception sûre. Tu "
        "confirmes la matière et rien n'est écrasé."
    ),
    "Os ficheiros mudaram ou já estavam a ser processados e ficaram em Downloads.": (
        "Les fichiers ont changé ou étaient déjà en traitement et sont restés dans Téléchargements."
    ),
    "Padrão das Definições": "Valeur des Paramètres",
    "Palavras-chave": "Mots-clés",
    "Pasta Downloads": "Dossier Téléchargements",
    "Pasta Universidade": "Dossier Université",
    "Pasta: {name}": "Dossier : {name}",
    "Pastas e vigilância": "Dossiers et surveillance",
    "Pausar vigilância": "Mettre la surveillance en pause",
    "Pesquisa": "Recherche",
    "Pesquisa nos documentos": "Recherche dans les documents",
    "Pesquisar nos apontamentos": "Chercher dans tes notes",
    "Podes alterar estas opções depois. Começa por criar uma disciplina.": (
        "Tu pourras modifier ces options plus tard. Commence par créer une matière."
    ),
    "Podes corrigir o nome; a extensão original é preservada": (
        "Tu peux corriger le nom ; l'extension d'origine est conservée"
    ),
    "Prazo": "Échéance",
    "Prazo amanhã": "À rendre demain",
    "Prazo das tarefas": "Échéance des tâches",
    "Prazo em {count} dias · {date}": "Dans {count} jours · {date}",
    "Prazo hoje": "À rendre aujourd'hui",
    "Preparar o Organizador": "Configurer Organizador",
    "Primeira disciplina": "Première matière",
    "Procura palavras dentro de PDFs, documentos Office, ficheiros de texto e notebooks já organizados.": (
        "Cherche des mots dans les PDF, documents Office, fichiers texte et notebooks déjà organisés."
    ),
    "Próximos prazos": "Prochaines échéances",
    "Quando terminares um download elegível, ele aparece aqui e num pequeno popup.": (
        "Quand un téléchargement éligible se termine, il apparaît ici et dans une petite fenêtre."
    ),
    "Reativar disciplina?": "Restaurer la matière ?",
    "Recuperação manual necessária  ·  {size}  ·  {when}": (
        "Récupération manuelle nécessaire  ·  {size}  ·  {when}"
    ),
    "Registo mantido": "Enregistrement conservé",
    "Remover apenas o registo local; nenhum ficheiro é apagado": (
        "Supprime uniquement l'enregistrement local ; aucun fichier n'est supprimé"
    ),
    "Remover do catálogo": "Retirer du catalogue",
    "Remover do catálogo?": "Retirer du catalogue ?",
    "Remover registo": "Supprimer l'enregistrement",
    "Remover registo em falta?": "Supprimer l'enregistrement manquant ?",
    "Restaurar": "Restaurer",
    "Cópias de segurança": "Sauvegardes",
    "Ainda não há cópias de segurança.": "Il n'y a pas encore de sauvegardes.",
    "Criar cópia agora": "Créer une sauvegarde",
    "Criar e exportar .zip…": "Créer et exporter .zip…",
    "Restaurar…": "Restaurer…",
    "As cópias guardam o catálogo e as definições. Os teus documentos não são alterados.": (
        "Les sauvegardes contiennent le catalogue et les définitions. "
        "Tes documents ne sont pas modifiés."
    ),
    "Última cópia: {when} · {size}": "Dernière sauvegarde : {when} · {size}",
    "Última cópia: {when} · {count} cópias · {size}": (
        "Dernière sauvegarde : {when} · {count} sauvegardes · {size}"
    ),
    "A processar a cópia de segurança…": "Traitement de la sauvegarde…",
    "Espera que as operações de ficheiros terminem antes de criar a cópia.": (
        "Attends la fin des opérations sur les fichiers avant de créer la sauvegarde."
    ),
    "Não foi possível concluir a cópia: {error}": (
        "Impossible de terminer la sauvegarde : {error}"
    ),
    "Cópia importada. Escolhe-a na lista para restaurar.": (
        "Sauvegarde importée. Choisis-la dans la liste pour restaurer."
    ),
    "Cópia exportada: {name}": "Sauvegarde exportée : {name}",
    "Cópia criada e exportada: {name}": "Sauvegarde créée et exportée : {name}",
    "Cópia de segurança criada.": "Sauvegarde créée.",
    "Importar cópia de segurança": "Importer une sauvegarde",
    "Exportar cópia de segurança": "Exporter une sauvegarde",
    "Cópias de segurança (*.zip)": "Sauvegardes (*.zip)",
    "Remover cópia": "Supprimer la sauvegarde",
    "Remover a cópia de {when}? Esta ação não pode ser desfeita.": (
        "Supprimer la sauvegarde du {when} ? Cette action est irréversible."
    ),
    "Restaurar cópia de segurança": "Restaurer la sauvegarde",
    "Os dados atuais serão substituídos pela cópia de {when} e a app vai reiniciar. Os teus documentos não são alterados. Continuar?": (
        "Les données actuelles seront remplacées par la sauvegarde du {when} et "
        "l'app va redémarrer. Tes documents ne sont pas modifiés. Continuer ?"
    ),
    "Espera que as operações de ficheiros terminem antes de restaurar.": (
        "Attends la fin des opérations sur les fichiers avant de restaurer."
    ),
    "Fecha e reabre o Organizador para concluir a reposição.": (
        "Ferme et rouvre Organizador pour terminer la restauration."
    ),
    "Restaurar substitui o catálogo e as definições atuais.": (
        "La restauration remplace le catalogue et les définitions actuels."
    ),
    "Manual": "Manuelle",
    "Antes de atualizar": "Avant la mise à jour",
    "Antes de restaurar": "Avant la restauration",
    "Do sistema": "Système",
    "{size} · esquema {version}": "{size} · schéma {version}",
    "Importar .zip…": "Importer .zip…",
    "Exportar": "Exporter",
    "Remover": "Supprimer",
    "Retomar vigilância": "Reprendre la surveillance",
    "Rever {name}": "Réviser {name}",
    "Revisão manual do histórico": "Révision manuelle de l'historique",
    "Revê as Definições antes de ativar a vigilância.\n\n{error}": (
        "Vérifie les Paramètres avant d'activer la surveillance.\n\n{error}"
    ),
    "Revê: {errors}.": "À vérifier : {errors}.",
    "Sair": "Quitter",
    "Sair da configuração?": "Quitter la configuration ?",
    "Selecionar {name}": "Sélectionner {name}",
    "Sem palavras-chave": "Sans mots-clés",
    "Sem prazo": "Sans échéance",
    "Sem resultados. O documento pode ainda estar a ser indexado ou ser um PDF digitalizado.": (
        "Aucun résultat. Le document est peut-être encore en cours d'indexation "
        "ou s'agit-il d'un PDF numérisé."
    ),
    "Sem sugestão": "Aucune suggestion",
    "Sem tarefas neste dia": "Aucune tâche ce jour",
    "Sem tarefas pendentes": "Aucune tâche en attente",
    "Sem uma disciplina, a app não começa a mover downloads. Podes voltar a configurar depois.": (
        "Sans matière, l'application ne commence pas à déplacer les téléchargements. "
        "Tu pourras la configurer plus tard."
    ),
    "Será removido apenas o registo local e o índice de pesquisa. Nenhum ficheiro será apagado. Se o ficheiro reaparecer durante a operação, ficará visível para poder ser adotado novamente.": (
        "Seuls l'enregistrement local et l'index de recherche seront supprimés. Aucun "
        "fichier ne sera effacé. Si le fichier réapparaît pendant l'opération, il deviendra "
        "visible pour pouvoir être adopté de nouveau."
    ),
    "Sugestão {percent}%": "Suggestion {percent}%",
    "Só a organização mais recente pode ser desfeita.": (
        "Seul le rangement le plus récent peut être annulé."
    ),
    "Tamanho mínimo": "Taille minimale",
    "Tarefa": "Tâche",
    "Tarefa geral": "Tâche générale",
    "Tarefas": "Tâches",
    "Tarefas e prazos": "Tâches et échéances",
    "Tema": "Thème",
    "Tempo do popup": "Durée du popup",
    "Fechar o popup automaticamente": "Fermer le popup automatiquement",
    "Sem esta opção, o popup fica aberto até escolheres uma ação.": (
        "Sans cette option, le popup reste ouvert jusqu'à ce que tu choisisses une action."
    ),
    "Tipo": "Type",
    "Tipo de documento": "Type de document",
    "Todos vão para a mesma disciplina e tipo. Cada ficheiro mantém o seu próprio histórico; só a última organização pode ser desfeita.": (
        "Tous vont dans la même matière et le même type. Chaque fichier garde son propre "
        "historique ; seul le dernier rangement peut être annulé."
    ),
    "Tokens: {tokens}. A extensão original é sempre preservada.": (
        "Jetons : {tokens}. L'extension d'origine est toujours conservée."
    ),
    "Tranquilidade": "Tranquillité",
    "Tudo fica neste computador. Nenhum documento é enviado para a internet.": (
        "Tout reste sur cet ordinateur. Aucun document n'est envoyé sur internet."
    ),
    "Tudo no lugar": "Tout est en ordre",
    "Título da tarefa": "Titre de la tâche",
    "Ver ficheiros": "Voir les fichiers",
    "Ver todas": "Tout afficher",
    "Verificação de segurança concluída": "Vérification de sécurité terminée",
    "Verificação de segurança incompleta": "Vérification de sécurité incomplète",
    "Verificação incompleta": "Vérification incomplète",
    "Versão da base de dados mais recente": "Version de base de données plus récente",
    "Vigiar novos ficheiros em Downloads": "Surveiller les nouveaux fichiers dans Téléchargements",
    "Vigilância de Downloads desligada": "Surveillance de Téléchargements désactivée",
    "Vigilância desligada": "Surveillance désactivée",
    "Vigilância em pausa": "Surveillance en pause",
    "Vigilância em pausa. Os novos downloads ficam onde estão.": (
        "Surveillance en pause. Les nouveaux téléchargements restent où ils sont."
    ),
    "Volta a mostrar a disciplina nas escolhas de arquivo": (
        "Affiche de nouveau la matière dans les choix de rangement"
    ),
    "a verificação atingiu o limite de segurança": (
        "la vérification a atteint sa limite de sécurité"
    ),
    "alguns caminhos não puderam ser verificados": "certains chemins n'ont pas pu être vérifiés",
    "diapositivo {page}": "diapositive {page}",
    "documento": "document",
    "e mais {count}": "et {count} de plus",
    "estudo local": "étude locale",
    "está atrasada": "est en retard",
    "folha {page}": "feuille {page}",
    "página {page}": "page {page}",
    "vence amanhã": "à rendre demain",
    "vence em {count} dias": "à rendre dans {count} jours",
    "vence hoje": "à rendre aujourd'hui",
    "verificação incompleta": "vérification incomplète",
    "{count} arquivada": "{count} archivée",
    "{count} arquivadas": "{count} archivées",
    "{count} colisão de nomes resolvida sem substituir nada": (
        "{count} collision de noms résolue sans rien écraser"
    ),
    "{count} colisões de nomes resolvidas sem substituir nada": (
        "{count} collisions de noms résolues sans rien écraser"
    ),
    "{count} com erro": "{count} en erreur",
    "{count} devolução a Downloads": "{count} renvoi vers Téléchargements",
    "{count} devoluções a Downloads": "{count} renvois vers Téléchargements",
    "{count} disciplina ativa": "{count} matière active",
    "{count} disciplinas ativas": "{count} matières actives",
    "{count} ficheiro adotado sem mover": "{count} fichier adopté sans déplacement",
    "{count} ficheiro organizado": "{count} fichier rangé",
    "{count} ficheiro por decidir": "{count} fichier à décider",
    "{count} ficheiro por decidir · {recovery} precisam de recuperação": (
        "{count} fichier à décider · {recovery} nécessitent une récupération"
    ),
    "{count} ficheiro precisa de recuperação manual": (
        "{count} fichier nécessite une récupération manuelle"
    ),
    "{count} ficheiro precisa de revisão manual": (
        "{count} signalement nécessite une révision manuelle"
    ),
    "{count} ficheiro · {size}": "{count} fichier · {size}",
    "{count} ficheiros adotados sem mover": "{count} fichiers adoptés sans déplacement",
    "{count} ficheiros organizados": "{count} fichiers rangés",
    "{count} ficheiros por decidir": "{count} fichiers à décider",
    "{count} ficheiros por decidir · {recovery} precisam de recuperação": (
        "{count} fichiers à décider · {recovery} nécessitent une récupération"
    ),
    "{count} ficheiros precisam de recuperação manual": (
        "{count} fichiers nécessitent une récupération manuelle"
    ),
    "{count} ficheiros precisam de revisão manual": (
        "{count} signalements nécessitent une révision manuelle"
    ),
    "{count} ficheiros · {size}": "{count} fichiers · {size}",
    "{count} ignorado": "{count} ignoré",
    "{count} ignorados": "{count} ignorés",
    "{count} importado": "{count} importé",
    "{count} importados": "{count} importés",
    "{count} não entraram neste lote e ficaram em Downloads.": (
        "{count} n'ont pas rejoint ce lot et sont restés dans Téléchargements."
    ),
    "{count} ocorrência do histórico precisa de revisão": (
        "{count} signalement de l'historique nécessite une révision"
    ),
    "{count} ocorrências do histórico precisam de revisão": (
        "{count} signalements de l'historique nécessitent une révision"
    ),
    "{count} operação interrompida recuperada": ("{count} opération interrompue récupérée"),
    "{count} operações interrompidas recuperadas": ("{count} opérations interrompues récupérées"),
    "{count} organizado, {failed} com erro. Revê: {errors}.": (
        "{count} rangé, {failed} en erreur. À vérifier : {errors}."
    ),
    "{count} organizado.": "{count} rangé.",
    "{count} organizados, {failed} com erro. Revê: {errors}.": (
        "{count} rangés, {failed} en erreur. À vérifier : {errors}."
    ),
    "{count} organizados.": "{count} rangés.",
    "{count} organização desfeita": "{count} rangement annulé",
    "{count} organizações desfeitas": "{count} rangements annulés",
    "{count} registo da Caixa de Entrada foi revisto": (
        "{count} enregistrement de la Boîte de réception a été examiné"
    ),
    "{count} registos da Caixa de Entrada foram revistos": (
        "{count} enregistrements de la Boîte de réception ont été examinés"
    ),
    "{count} resultados · os parênteses retos mostram a correspondência": (
        "{count} résultats · les crochets marquent la correspondance"
    ),
    "{kind} · {size} · organizado {date}": "{kind} · {size} · rangé le {date}",
    "{name} (arquivada)": "{name} (archivée)",
    "{name} deixa de aparecer nas escolhas. Os ficheiros e tarefas não são apagados.": (
        "{name} n'apparaît plus dans les choix. Ses fichiers et tâches ne sont pas supprimés."
    ),
    "{name} deixará de aparecer na pesquisa e nos recentes. O ficheiro permanecerá exatamente onde está.": (
        "{name} n'apparaîtra plus dans la recherche ni dans les récents. Le fichier reste "
        "exactement où il est."
    ),
    "{name} está pronto para organizar.": "{name} est prêt à être rangé.",
    "{name} foi adotado sem mover o ficheiro.": ("{name} a été adopté sans déplacer le fichier."),
    "{name} foi guardado em {destination}.": "{name} a été enregistré dans {destination}.",
    "{name} saiu do catálogo; o ficheiro ficou no lugar.": (
        "{name} a quitté le catalogue ; le fichier est resté en place."
    ),
    "{name} volta a aparecer nas escolhas de arquivo. Os ficheiros e tarefas não foram alterados.": (
        "{name} réapparaît dans les choix de rangement. Fichiers et tâches n'ont pas été modifiés."
    ),
    "{name} voltou para {folder}.": "{name} est retourné dans {folder}.",
    "{name} voltou à Caixa de Entrada.": "{name} est revenu dans la Boîte de réception.",
    "{size}  ·  recebido da pasta {folder}": "{size}  ·  reçu du dossier {folder}",
    "{size}  ·  {when}  ·  Sugestão: {suggestion} / {kind}": (
        "{size}  ·  {when}  ·  Suggestion : {suggestion} / {kind}"
    ),
    "{subject}  ·  {due}": "{subject}  ·  {due}",
    "{subject}  ·  {kind}  ·  {location}": "{subject}  ·  {kind}  ·  {location}",
    "{subject}  ·  {kind}  ·  {size}": "{subject}  ·  {kind}  ·  {size}",
    "{subject} · {kind} · adotado sem mover": "{subject} · {kind} · adopté sans déplacement",
    "{title} {when}.": "{title} {when}.",
    "Procurar atualizações…": "Rechercher des mises à jour…",
    "Instalar atualização {version}": "Installer la mise à jour {version}",
    "Atualização disponível": "Mise à jour disponible",
    "Organizador {version} está disponível. Escolhe “Instalar atualização” no menu do tabuleiro.": (
        "Organizador {version} est disponible. Choisis « Installer la mise à jour » "
        "dans le menu de la zone de notification."
    ),
    "A transferência da atualização falhou: {error}": (
        "Le téléchargement de la mise à jour a échoué : {error}"
    ),
    "Não foi possível verificar a atualização: {error}": (
        "Impossible de vérifier la mise à jour : {error}"
    ),
    "A verificação da atualização falhou; o ficheiro foi descartado.": (
        "La vérification de la mise à jour a échoué ; le fichier a été écarté."
    ),
    "A atualização descarregada está corrompida.": ("La mise à jour téléchargée est corrompue."),
    "A atualização não contém a aplicação completa.": (
        "La mise à jour ne contient pas l'application complète."
    ),
    "A instalar atualização…": "Installation de la mise à jour…",
    "A transferir e a verificar Organizador {version}.": (
        "Téléchargement et vérification d'Organizador {version}."
    ),
    "A reiniciar para aplicar a atualização…": "Redémarrage pour appliquer la mise à jour…",
    "Atualização falhou": "Échec de la mise à jour",
    "Não foi possível instalar a atualização.": "Impossible d'installer la mise à jour.",
    "A atualização só se aplica à versão instalada.": (
        "Les mises à jour ne s'appliquent qu'à la version installée."
    ),
    "Sem atualizações nesta instalação": "Aucune mise à jour pour cette installation",
    "Ficheiros organizados": "Fichiers rangés",
    "{count} ficheiros estão prontos para organizar.": (
        "{count} fichiers sont prêts à être rangés."
    ),
    "Silenciar notificações de arquivo": "Silencier les notifications de rangement",
    "Sem avisos de ficheiros organizados; erros e prazos continuam visíveis.": (
        "Pas d'avis de fichiers rangés ; les erreurs et les échéances restent visibles."
    ),
    "A app está a correr em modo de desenvolvimento; as atualizações aplicam-se apenas à versão instalada.": (
        "L'application tourne en mode développement ; les mises à jour ne s'appliquent "
        "qu'à la version installée."
    ),
    "Procurar atualizações automaticamente": "Rechercher les mises à jour automatiquement",
    "Atualização pronta": "Mise à jour prête",
    "A atualização extraída excede o limite permitido.": (
        "La mise à jour extraite dépasse la limite autorisée."
    ),
    "Já existe uma instalação de atualização em curso: {owner}.": (
        "Une installation de mise à jour est déjà en cours : {owner}."
    ),
    "A atualização contém caminhos duplicados.": "La mise à jour contient des chemins dupliqués.",
    "A atualização contém caminhos incompatíveis.": (
        "La mise à jour contient des chemins incompatibles."
    ),
    "A atualização contém demasiados ficheiros.": "La mise à jour contient trop de fichiers.",
    "A atualização contém um caminho de ficheiro inseguro.": (
        "La mise à jour contient un chemin de fichier dangereux."
    ),
    "A atualização contém um ficheiro encriptado não suportado.": (
        "La mise à jour contient un fichier chiffré non pris en charge."
    ),
    "A atualização contém um tipo de ficheiro não permitido.": (
        "La mise à jour contient un type de fichier interdit."
    ),
    "A pasta não contém uma instalação completa do Organizador.": (
        "Le dossier ne contient pas une installation complète d'Organizador."
    ),
    "Não foi possível iniciar o assistente de atualização.": (
        "Impossible de démarrer l'assistant de mise à jour."
    ),
    "O ficheiro da atualização excede o limite permitido.": (
        "Le fichier de mise à jour dépasse la limite autorisée."
    ),
    "O tamanho de um ficheiro da atualização é inválido.": (
        "La taille d'un fichier de la mise à jour est invalide."
    ),
    "Um ficheiro da atualização excede o limite permitido.": (
        "Un fichier de la mise à jour dépasse la limite autorisée."
    ),
    "A procurar atualizações…": "Recherche de mises à jour…",
    "A instalar atualização {version}…": "Installation de la mise à jour {version}…",
    "Sem atualizações": "Aucune mise à jour",
    "O Organizador está atualizado.": "Organizador est à jour.",
    "Não foi possível procurar atualizações.": "Impossible de rechercher des mises à jour.",
    "A atualização transferida não corresponde à versão {version}.": (
        "La mise à jour téléchargée ne correspond pas à la version {version}."
    ),
    "Atualização instalada": "Mise à jour installée",
    "Atualização {version} instalada com sucesso.": (
        "Mise à jour {version} installée avec succès."
    ),
    "Atualização instalada com sucesso.": "Mise à jour installée avec succès.",
    "Atualização revertida": "Mise à jour annulée",
    "A atualização {version} falhou e a versão anterior foi restaurada.": (
        "La mise à jour {version} a échoué et la version précédente a été restaurée."
    ),
    "A atualização falhou e a versão anterior foi restaurada.": (
        "La mise à jour a échoué et la version précédente a été restaurée."
    ),
    "A atualização falhou e a reposição automática não foi concluída.": (
        "La mise à jour a échoué et la restauration automatique n'a pas abouti."
    ),
    "A versão anterior foi mantida em: {path}.": (
        "La version précédente a été conservée ici : {path}."
    ),
    "Atualização inválida": "Mise à jour invalide",
    "A atualização não corresponde a esta instalação. Nenhum ficheiro foi alterado.": (
        "La mise à jour ne correspond pas à cette installation. Aucun fichier n'a été modifié."
    ),
    "A atualização não pôde ser validada. Nenhum ficheiro foi alterado.": (
        "La mise à jour n'a pas pu être validée. Aucun fichier n'a été modifié."
    ),
    "Não foi possível concluir a atualização": "Impossible de terminer la mise à jour",
    "Não foi possível recuperar os dados": "Impossible de récupérer les données",
    "Não foi possível atualizar os dados": "Impossible de mettre à jour les données",
    "Os argumentos da atualização estão incompletos. Nenhum ficheiro foi alterado.": (
        "Les arguments de la mise à jour sont incomplets. Aucun fichier n'a été modifié."
    ),
    "Existe uma cópia de segurança de migração que não pôde ser restaurada automaticamente. Nenhum ficheiro foi alterado.\n\n{error}": (
        "Il existe une sauvegarde de migration qui n'a pas pu être restaurée automatiquement. "
        "Aucun fichier n'a été modifié.\n\n{error}"
    ),
    "A aplicação não conseguiu preparar o catálogo local. Foi tentada a reposição da cópia de segurança.\n\n{error}": (
        "L'application n'a pas pu préparer le catalogue local. "
        "La restauration de la sauvegarde a été tentée.\n\n{error}"
    ),
    "Os dados migrados não puderam ser validados. Foi tentada a reposição da cópia de segurança.\n\n{error}": (
        "Les données migrées n'ont pas pu être validées. "
        "La restauration de la sauvegarde a été tentée.\n\n{error}"
    ),
    "Os dados migrados não puderam ser validados. A versão anterior foi mantida para recuperação manual.": (
        "Les données migrées n'ont pas pu être validées. "
        "La version précédente a été conservée pour une récupération manuelle."
    ),
    "A nova versão não conseguiu arrancar. A versão anterior foi mantida para recuperação manual.": (
        "La nouvelle version n'a pas pu démarrer. "
        "La version précédente a été conservée pour une récupération manuelle."
    ),
    "Não foi possível concluir o arranque": "Impossible de terminer le démarrage",
    "A aplicação não conseguiu concluir o arranque. Foi tentada a reposição da cópia de segurança.\n\n{error}": (
        "L'application n'a pas pu terminer le démarrage. "
        "La restauration de la sauvegarde a été tentée.\n\n{error}"
    ),
    "A nova versão não conseguiu arrancar. Foi tentada a reposição da cópia de segurança.": (
        "La nouvelle version n'a pas pu démarrer. La restauration de la sauvegarde a été tentée."
    ),
    "Não foi possível ler a pasta Downloads configurada.": (
        "Impossible de lire le dossier Téléchargements configuré."
    ),
    "Já não foi possível encontrar {name}.": "Impossible de retrouver {name}.",
    "{name} ficou em {origin}, mas uma cópia incompleta pode ter ficado em {leftover}. Compara os ficheiros antes de a remover.": (
        "{name} est resté dans {origin}, mais une copie incomplète se trouve "
        "peut-être ici : {leftover}. Compare les fichiers avant de la supprimer."
    ),
    "{name} mudou ou ainda está a ser usado e ficou em {origin}.": (
        "{name} a changé ou est encore utilisé et est resté dans {origin}."
    ),
    "Não foi possível registar {name}. O ficheiro ficou em {destination}.": (
        "Impossible d'enregistrer {name}. Le fichier est resté ici : {destination}."
    ),
    "Não foi possível registar {name}; foi devolvido a {origin} como {returned}.": (
        "Impossible d'enregistrer {name} ; il a été renvoyé dans {origin} sous le nom {returned}."
    ),
    "Este ficheiro não pode ser recolhido. Confirma que não está já na Universidade e que a extensão é aceite.": (
        "Ce fichier ne peut pas être récupéré. Vérifie qu'il n'est pas déjà dans "
        "l'Université et que son extension est acceptée."
    ),
    "Este ficheiro já não está na Caixa de Entrada.": (
        "Ce fichier n'est plus dans la Boîte de réception."
    ),
    "Escolhe uma disciplina ativa.": "Choisis une matière active.",
    "Escolhe um tipo de documento válido.": "Choisis un type de document valide.",
    "Não foi possível encontrar {name}.": "Impossible de trouver {name}.",
    "Não foi possível preparar o histórico da organização.": (
        "Impossible de préparer l'historique de rangement."
    ),
    "A organização ficou incompleta. O original e a cópia foram mantidos; revê ambos na Caixa de Entrada antes de continuar.": (
        "Le rangement est resté incomplet. L'original et la copie ont été conservés ; "
        "vérifie-les dans la Boîte de réception avant de continuer."
    ),
    "O ficheiro ainda está a ser usado por outra aplicação. Fecha-o e tenta novamente.": (
        "Le fichier est encore utilisé par une autre application. Ferme-la et réessaie."
    ),
    "O movimento foi revertido porque não foi possível atualizar o histórico.": (
        "Le déplacement a été annulé car l'historique n'a pas pu être mis à jour."
    ),
    "Não foi possível atualizar o histórico. Revê a Caixa de Entrada antes de repetir.": (
        "Impossible de mettre à jour l'historique. "
        "Vérifie la Boîte de réception avant de réessayer."
    ),
    "O ficheiro já não está disponível para devolver.": ("Le fichier ne peut plus être renvoyé."),
    "Não foi possível preparar o histórico da devolução.": (
        "Impossible de préparer l'historique de renvoi."
    ),
    "A devolução ficou incompleta. O original e a cópia foram mantidos; revê a Caixa de Entrada e Downloads antes de continuar.": (
        "Le renvoi est resté incomplet. L'original et la copie ont été conservés ; "
        "vérifie la Boîte de réception et Téléchargements avant de continuer."
    ),
    "Não foi possível devolver o ficheiro. Fecha-o noutras aplicações e tenta de novo.": (
        "Impossible de renvoyer le fichier. Ferme-le dans les autres applications et réessaie."
    ),
    "Não foi possível registar a devolução do ficheiro.": (
        "Impossible d'enregistrer le renvoi du fichier."
    ),
    "O último ficheiro organizado já não está no destino. O histórico não foi alterado.": (
        "Le dernier fichier rangé n'est plus à sa destination. L'historique n'a pas été modifié."
    ),
    "Não foi possível preparar o histórico para desfazer.": (
        "Impossible de préparer l'historique pour annuler."
    ),
    "A operação de desfazer ficou incompleta. O original e a cópia foram mantidos; revê ambos na Caixa de Entrada antes de continuar.": (
        "L'annulation est restée incomplète. L'original et la copie ont été conservés ; "
        "vérifie-les dans la Boîte de réception avant de continuer."
    ),
    "Não foi possível desfazer porque o ficheiro está a ser usado.": (
        "Impossible d'annuler car le fichier est utilisé."
    ),
    "Não foi possível atualizar o histórico ao desfazer.": (
        "Impossible de mettre à jour l'historique pendant l'annulation."
    ),
    "Criar tarefa": "Créer une tâche",
    "A cópia incompleta ficou em {path}.": "La copie incomplète est restée ici : {path}.",
    "A pasta de destino não é segura: {path}.": "Le dossier de destination n'est pas sûr : {path}.",
    "Falha na indexação — o ficheiro continua pesquisável pelo nome.": (
        "L'indexation a échoué — le fichier reste trouvable par son nom."
    ),
    "Reindexar": "Réindexer",
    "Mover": "Déplacer",
    "Mover ficheiro": "Déplacer le fichier",
    "A mover…": "Déplacement…",
    "Ficheiro movido": "Fichier déplacé",
    "{name} está agora em {location}.": "{name} est maintenant dans {location}.",
    "Não foi possível mover": "Impossible de déplacer",
    "Espera que as operações de ficheiros terminem antes de mover.": (
        "Attends la fin des opérations sur les fichiers avant de déplacer."
    ),
    "Escolhe outra disciplina ou outro tipo para mover.": (
        "Choisis une autre matière ou un autre type pour déplacer."
    ),
    "Este documento já não está no catálogo.": ("Ce document n'est plus dans le catalogue."),
    "Não foi possível preparar o histórico do movimento.": (
        "Impossible de préparer l'historique du déplacement."
    ),
    "O movimento ficou incompleto. O original e a cópia foram mantidos; revê ambos antes de continuar.": (
        "Le déplacement est resté incomplet. L'original et la copie ont été "
        "conservés ; vérifie-les avant de continuer."
    ),
    "Não foi possível atualizar o histórico. Revê os ficheiros antes de repetir.": (
        "Impossible de mettre à jour l'historique. Vérifie les fichiers avant de réessayer."
    ),
    "Origem de um movimento interrompido; não foi alterada no arranque.": (
        "Origine d'un déplacement interrompu ; elle n'a pas été modifiée au démarrage."
    ),
    "Destino de um movimento interrompido; compara antes de continuar.": (
        "Destination d'un déplacement interrompu ; compare avant de continuer."
    ),
    "A reindexar…": "Réindexation…",
    "A fila de indexação está ocupada; o documento será indexado assim que possível.": (
        "La file d'indexation est occupée ; le document sera indexé dès que possible."
    ),
    "Tenta organizar o ficheiro quando a atualização terminar.": (
        "Essaie d'organiser le fichier une fois la mise à jour terminée."
    ),
    "Tentar novamente": "Réessayer",
    "{count} documentos por indexar": "{count} documents en attente d'indexation",
    "1 documento por indexar": "1 document en attente d'indexation",
    "{count} documentos com falha na indexação": "{count} documents en échec d'indexation",
    "1 documento com falha na indexação": "1 document en échec d'indexation",
    "Reconhecer texto em PDFs digitalizados (OCR)": "Reconnaître le texte des PDF numérisés (OCR)",
    "Todas as disciplinas": "Toutes les matières",
    "Todos os tipos": "Tous les types",
    "Filtrar por disciplina": "Filtrer par matière",
    "Filtrar por tipo de documento": "Filtrer par type de document",
    "{count} documentos": "{count} documents",
    "1 documento": "1 document",
    "{subject}  ·  {kind}": "{subject}  ·  {kind}",
}

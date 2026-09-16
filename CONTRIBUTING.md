# Contribuir

Como desenvolver, construir e publicar o Organizador. Para a descrição da
aplicação e as instruções de instalação, vê o [README](README.md).

## Desenvolvimento

Requisitos: Windows 11 e Python 3.11 ou superior. Os builds oficiais usam
Python 3.13.

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
.\.venv\Scripts\python.exe -m organizador.main
```

Validação individual (a mesma ordem que o CI):

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests scripts
.\.venv\Scripts\python.exe -m ruff format --check src tests scripts
.\.venv\Scripts\python.exe -m mypy src\organizador
.\.venv\Scripts\python.exe -m pytest
```

## Build local

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build.ps1
```

O script executa lint, verificação de formato, mypy, testes, PyInstaller e um
arranque de diagnóstico do pacote. Depois adiciona as licenças e produz:

- `artifacts\Organizador\Organizador.exe`
- `artifacts\releases\Organizador-<versão>-windows-x64.zip`
- `artifacts\releases\Organizador-<versão>-windows-x64.zip.sha256`

Para o instalador, o primeiro comando descarrega uma vez um compilador Inno
Setup fixo e verificado (edição não comercial):

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\setup_installer.ps1
powershell -ExecutionPolicy Bypass -File .\scripts\build_installer.ps1
```

que acrescenta:

- `artifacts\releases\Organizador-<versão>-Setup.exe`
- `artifacts\releases\Organizador-<versão>-Setup.exe.sha256`

O build local não substitui uma cópia já instalada nem altera os ícones
guardados no código. Usa `-OutputRoot <pasta>` para escolher outra pasta de
saída.

Para o detalhe do instalador — compilador fixo, assinatura futura e aceitação
da release numa conta Windows descartável — vê
[docs/windows-installation.md](docs/windows-installation.md).

As dependências exatas da versão são fixadas em `constraints-release.txt`.
`pyproject.toml` é a fonte única das dependências diretas. `defusedxml` é mantido
explicitamente porque o `openpyxl` o ativa para proteger a leitura de folhas de
cálculo XML não confiáveis.

## Publicação

Tags no formato `vMAJOR.MINOR.PATCH` ativam o workflow de release; a tag tem de
coincidir com `organizador.__version__`. O workflow recria o ambiente a partir
de `constraints-release.txt`, executa toda a validação, constrói o ZIP e o
Setup e compila e testa o instalador numa conta Windows descartável antes de
publicar quatro ficheiros com SHA-256: o ZIP, o Setup e os respetivos
`.sha256`.

Antes de publicar, o workflow executa a atualização real com o código exato da
versão anterior (`scripts\run_update_release_e2e.ps1`) contra os bytes do
candidato, incluindo uma verificação de cópia de segurança e reposição com o
executável final. Depois de publicar, volta a descarregar os ficheiros
públicos, confirma os hashes e repete a atualização real a partir da versão
base antiga.

A release é criada como prerelease e só é promovida a estável manualmente,
depois de confirmada a transição a partir da base instalada. Uma release já
publicada nunca é substituída por uma repetição do workflow.

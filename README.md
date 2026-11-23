# 🎮 GameHub — Buscador & Agregador Multi-Sites Modular

**GameHub** é uma aplicação desktop desenvolvida em Python e [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter) com interface moderna em Dark Mode para pesquisar, filtrar e obter links de jogos e ROMs de múltiplas fontes simultaneamente.

---

## ✨ Funcionalidades Principais

* **🔍 Busca Multi-Sites Unificada:** Consulta paralela e agregada em múltiplos sites de jogos e emulação.
  * **DLPSGame** (PlayStation 3/4/5, Switch, PC) com decodificação de payloads e links protegidos.
  * **ROMSLab** (Nintendo Switch, Switch 2, PC, PS5).
  * **ROMSFun** (ROMs retrô e bibliotecas clássicas: GBA, SNES, NES, PS1, PS2, etc.).
  * **FitGirl Repacks** (Repacks de PC) com extração em segundo plano das capas oficiais de cada título.
* **🎯 Filtros Dinâmicos na Interface:**
  * Filtro por **Console / Plataforma** (ex: *Switch, PS4, PS5, PC, Retrô, etc.*).
  * Filtro por **Site / Origem** (*DLPSGame, FitGirl, ROMSLab, ROMSFun*).
  * Contador dinâmico de resultados em tempo real.
* **📦 Classificador Inteligente de Links:**
  * Separação visual por tipo: *🎮 Jogo Base*, *🔄 Atualização / Update*, *🎁 DLC / Extra*, *🧲 Torrent / Magnet*, *🔗 Servidor / Mirror*.
  * Identificação de provedores e servidores (*Mediafire, Mega, Google Drive, DataNodes, 1Fichier, Torrent*, etc.).
  * Identificação automática de partes numeradas (*[Parte 1]*, *[Parte 2]*).
* **⚙️ Gerenciador de Sites:**
  * Modal visual para ativar/desativar sites ativos, alterar endpoints e adicionar novas fontes personalizadas salvas em `sites_config.json`.
* **🚀 Executável Standalone:**
  * Compilável em arquivo `.exe` único e independente, sem exigir que o usuário final tenha Python instalado na máquina.

---

## 🚀 Como Executar pelo Código-Fonte

### Pré-requisitos
* Python 3.10 ou superior instalado no Windows.

### 1. Clonar o repositório
```bash
git clone https://github.com/printfFriendo/GameHub.git
cd GameHub
```

### 2. Instalar dependências
```bash
pip install -r requirements.txt
```

### 3. Iniciar o programa
```bash
python main.py
```

---

## 🛠️ Como Gerar o Executável (.exe)

O projeto inclui um script automatizado [build_exe.bat](build_exe.bat) para compilar o executável portátil usando o PyInstaller:

1. Dê dois cliques em `build_exe.bat` (ou execute via terminal):
```cmd
build_exe.bat
```
2. Ao finalizar, o executável autônomo estará pronto na pasta raiz como `GameHub.exe` e na pasta `dist/GameHub.exe`.

---

## 📁 Estrutura do Projeto

```text
GameHub/
├── main.py                  # Aplicação principal (GUI CustomTkinter e Motor Scraper)
├── scrapers/
│   ├── __init__.py
│   └── anti_bot_scraper.py  # Extratores anti-bot (DLPS, ROMSLab, ROMSFun, FitGirl)
├── sites_config.json        # Configuração modular e editável dos sites suportados
├── requirements.txt         # Dependências do projeto
├── build_exe.bat            # Script para compilar o executável com PyInstaller
├── run_gamehub.bat          # Atalho para execução rápida via Python
└── README.md                # Documentação do projeto
```

---

## 📜 Licença

Distribuído sob a licença MIT. Consulte `LICENSE` para mais informações.

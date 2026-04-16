# 🎬 Telegram Video Bot

Bot para hospedar vídeos no Telegram e gerar links de player que abrem no navegador.

## ✨ Funcionalidades

- 📤 Recebe vídeos via Telegram e faz forward para canal privado
- 🔗 Gera link de player web (`https://seu-app.railway.app/player/ID`)
- 🗄️ Armazena todos os links no PostgreSQL
- 💾 Backup e restore completo das configurações
- 🔔 Notificação automática quando um link fica offline
- 📊 Estatísticas de views e status

---

## 🚀 Setup Completo (Passo a Passo)

### 1. Criar o Bot no Telegram

1. Abra o Telegram e procure por **@BotFather**
2. Envie `/newbot`
3. Escolha um nome e username para o bot
4. Guarde o **Token** gerado (formato: `123456789:AAxxxxxx`)

### 2. Criar o Canal Privado

1. No Telegram, crie um novo canal privado
2. Vá em **Configurações do Canal > Administradores**
3. Adicione seu bot como administrador com permissão para **postar mensagens**
4. Para descobrir o ID do canal:
   - Adicione o bot [@getidsbot](https://t.me/getidsbot) ao canal
   - Ele vai mostrar o ID (começa com `-100`)

### 3. Descobrir seu ID de Admin

Envie uma mensagem para **@userinfobot** no Telegram para ver seu ID numérico.

### 4. Subir no GitHub

```bash
git init
git add .
git commit -m "first commit"
git branch -M main
git remote add origin https://github.com/SEU_USER/SEU_REPO.git
git push -u origin main
```

### 5. Criar o Projeto no Railway

1. Acesse [railway.app](https://railway.app) e faça login
2. Clique em **New Project > Deploy from GitHub repo**
3. Selecione o repositório que você criou
4. Aguarde o deploy inicial (vai falhar, está faltando as variáveis)

### 6. Adicionar o PostgreSQL

1. No projeto do Railway, clique em **New > Database > Add PostgreSQL**
2. O Railway vai criar o banco e gerar a variável `DATABASE_URL` automaticamente

### 7. Configurar as Variáveis de Ambiente

No Railway, vá em **seu serviço > Variables** e adicione:

| Variável | Valor | Exemplo |
|----------|-------|---------|
| `BOT_TOKEN` | Token do @BotFather | `1234567890:AAxxxxx` |
| `BOT_USERNAME` | Username do bot sem @ | `meuvideobot` |
| `CHANNEL_ID` | ID do canal privado | `-1001234567890` |
| `ADMIN_IDS` | Seus IDs separados por vírgula | `123456789` |
| `BASE_URL` | URL do seu deploy no Railway | `https://video-bot-production.up.railway.app` |

> ⚠️ `DATABASE_URL` é gerado automaticamente pelo plugin do PostgreSQL, não precisa adicionar.

### 8. Fazer o Deploy

Após configurar as variáveis, o Railway vai fazer o redeploy automaticamente.
Acesse os **Logs** para verificar se o bot iniciou corretamente.

---

## 🤖 Comandos do Bot

| Comando | Descrição |
|---------|-----------|
| `/start` | Menu inicial |
| `/list` | Lista todos os vídeos com links |
| `/backup` | Exporta backup JSON de todos os dados |
| `/restore` | Importa backup JSON |
| `/check` | Verifica quais links estão offline |
| `/stats` | Estatísticas gerais |
| `/delete <id>` | Remove um vídeo |

### Enviar um Vídeo

Simplesmente envie um arquivo de vídeo diretamente para o bot. Você pode adicionar uma legenda para usar como título. O bot irá:

1. Fazer forward para o canal privado
2. Gerar um link de player: `https://seu-app.railway.app/player/abc123`
3. Retornar o link para você

---

## 💾 Backup e Restore

### Fazer Backup

```
/backup
```

O bot vai enviar um arquivo `backup_YYYYMMDD_HHMMSS.json` com todos os vídeos e configurações.

### Restaurar em Nova Conta Railway

1. Crie novo projeto no Railway (seguindo os passos acima)
2. Configure as variáveis de ambiente
3. Envie `/restore` para o bot
4. Envie o arquivo `.json` de backup

> ✅ Todos os links anteriores continuarão funcionando desde que o `BASE_URL` seja o mesmo, ou você pode atualizar o `.env` com a nova URL.

---

## 🔔 Monitoramento de Links

O bot verifica automaticamente todos os links a cada **1 hora**.

Se algum link ficar offline, você receberá uma notificação no Telegram:

```
🚨 Alerta: 1 link(s) offline!

❌ Meu Vídeo
   🆔 abc123def456
   🔗 https://seu-app.railway.app/player/abc123def456
```

Para verificar manualmente: `/check`

---

## 🔗 Formato dos Links

- **Link do Player** (abre no navegador):
  `https://seu-app.railway.app/player/abc123`

- **Link do Telegram** (abre no app):
  `https://t.me/c/CHANNEL_ID/MESSAGE_ID`

O link do player incorpora o widget de post do Telegram, que exibe o vídeo diretamente no navegador.

---

## 📁 Estrutura do Projeto

```
telegram-video-bot/
├── bot/
│   ├── main.py          # Entrypoint (bot + servidor web)
│   ├── bot.py           # Lógica do bot Telegram
│   ├── database.py      # Acesso ao PostgreSQL
│   ├── server.py        # Servidor FastAPI + player HTML
│   └── requirements.txt
├── Dockerfile
├── railway.toml
├── .env.example
└── README.md
```

---

## ⚠️ Importante

- O canal **deve ser privado** para que os links funcionem corretamente
- O bot deve ter permissão de **admin** no canal para fazer forward de mensagens
- Os links do player **abrem no navegador**, não dentro do Telegram
- O widget do Telegram no player requer que o canal seja público **OU** que o usuário já esteja no canal

### Se o player não mostrar o vídeo:

1. Verifique se o bot é admin no canal
2. Confirme o `CHANNEL_ID` (deve ter o `-100` no início)
3. Certifique-se que a `BASE_URL` no Railway está correta e sem barra no final

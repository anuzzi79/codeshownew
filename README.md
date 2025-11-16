# CodeShowNew

Repository pubblico contenente il file pubblico dell'app.

## Configurazione
1. Copia .env.example in .env
2. Aggiungi la tua DEEPSEEK_API_KEY in .env
3. Avvia lo script Python che usa la variabile

### Esempio (.env)
`
DEEPSEEK_API_KEY=YOUR_KEY_HERE
# DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions
`

### Windows PowerShell
`powershell
copy .\.env.example .\.env
`

## Note
- Non committare il file .env: Ã¨ ignorato tramite .gitignore.
- La chiave Ã¨ letta dal codice tramite os.getenv("DEEPSEEK_API_KEY").

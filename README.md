# CodeShowNew

A public repository containing the exported public file of the app.

## Setup (English)
1. Copy `.env.example` to `.env`
2. Add your `DEEPSEEK_API_KEY` to `.env`
3. Run the Python script that uses the variable

### Example (.env)
```env
DEEPSEEK_API_KEY=YOUR_KEY_HERE
# DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions
```

### Windows PowerShell
```powershell
copy .\.env.example .\.env
```

### Notes
- Do not commit the .env file; it is ignored via .gitignore.
- The key is read in code via os.getenv("DEEPSEEK_API_KEY").

---

## Configuração (Português)
1. Copie `.env.example` para `.env`
2. Adicione sua `DEEPSEEK_API_KEY` no `.env`
3. Execute o script Python que usa a variável

### Exemplo (.env)
```env
DEEPSEEK_API_KEY=SUA_CHAVE_AQUI
# DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions
```

### Windows PowerShell
```powershell
copy .\.env.example .\.env
```

### Notas
- Não faça commit do arquivo .env; ele já está ignorado no .gitignore.
- A chave é lida no código usando os.getenv("DEEPSEEK_API_KEY").
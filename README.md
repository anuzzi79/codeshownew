# CodeShowNew

This project was originally designed to use an embedded LLM inside the app’s header UI.
With the advent of Cursor, that feature became unnecessary and is now considered obsolete.

However, the app still supports a convenient “Prompt mode”.

## Prompt mode
Press the “Prompt” button to generate a prompt that summarizes your current files and their contents.
The prompt is automatically copied to your clipboard. You can paste it into any browser‑based AI assistant to ask questions or request changes with the full project context.

Basic flow:
1) Open the app and select your working directory.
2) Load or adjust the set of files you want to include.
3) Click “Prompt” (or “Reload + Prompt” to refresh file contents first).
4) Paste the generated prompt into your AI tool in the browser.

That’s it—no embedded model needed.

## Optional API integration (obsolete)
If you want to call an external API (e.g., DeepSeek) from the app:
- Copy `.env.example` to `.env`
- Add your `DEEPSEEK_API_KEY`
- Run the app

Example `.env`:
```env
DEEPSEEK_API_KEY=YOUR_KEY_HERE
# DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions
```

Note: Do not commit the `.env` file; it is ignored via `.gitignore`.

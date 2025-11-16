import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import pyperclip  # Libreria per gestire la clipboard
import requests   # per chiamare l'API DeepSeek
import re         # per parsare i blocchi file restituiti dal modello

# ==========================
# Configura la tua API key da .env (nessun hardcode)
# ==========================

def _load_dotenv_into_environ():
    """Carica chiavi da un file .env nella root del progetto (se presente)."""
    try:
        base_dir = os.path.dirname(__file__)
        env_path = os.path.join(base_dir, ".env")
        if os.path.isfile(env_path):
            with open(env_path, "r", encoding="utf-8") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key and value and key not in os.environ:
                        os.environ[key] = value
    except Exception:
        # Silenzia errori di caricamento .env; fallback a variabili d'ambiente del sistema
        pass


_load_dotenv_into_environ()
API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# Variabili globali
MAX_COLUMNS = 100
COLUMN_TEXT_HEIGHT = 15  # era 20: -25% di altezza per mostrare le Output preference
columns = []
file_paths = {}
truncated_files = {}
truncated_files_label = None
# Frame delle opzioni prompt (verrà creato più avanti)
prompt_mode_frame = None

# Lista completa dei file trovati nella dir
all_files = []
selected_files = set()  # file selezionati dall’utente

# Percorsi helper (riempiti dopo la scelta della directory)
selected_dir = ""
file_set_dir = ""  # <selected_dir>/file_set


# ========================== FUNZIONI SUPPORTO FILE_SET ==========================

def ensure_file_set_dir():
    """Assicura che esista la cartella <selected_dir>/file_set."""
    global file_set_dir
    file_set_dir = os.path.join(selected_dir, "file_set")
    if not os.path.isdir(file_set_dir):
        try:
            os.makedirs(file_set_dir, exist_ok=True)
        except Exception as e:
            messagebox.showerror(
                "Errore", f"Impossibile creare la cartella file_set:\n{e}")


def list_existing_file_sets():
    """Ritorna lista di tuple (path_assoluto, N) dei file_set esistenti, ordinati per N crescente."""
    if not os.path.isdir(file_set_dir):
        return []
    result = []
    for name in os.listdir(file_set_dir):
        # pattern: file_set_tony_N.json
        if name.startswith("file_set_tony_") and name.lower().endswith(".json"):
            # rimuove prefisso e ".json"
            middle = name[len("file_set_tony_"):-5]
            try:
                n = int(middle)
                result.append((os.path.join(file_set_dir, name), n))
            except ValueError:
                continue
    result.sort(key=lambda x: x[1])  # per N crescente
    return result


def get_next_fileset_index():
    """Restituisce N successivo per il prossimo salvataggio (1 se nessuno esiste)."""
    items = list_existing_file_sets()
    if not items:
        return 1
    return items[-1][1] + 1


def get_latest_fileset_path():
    """Restituisce (path, N) dell’ultimo file_set, oppure (None, None) se non presente."""
    items = list_existing_file_sets()
    if not items:
        return None, None
    return items[-1]


def save_current_selection_as_fileset(selected_rel_paths):
    """
    Salva l’insieme dei file selezionati (percorsi RELATIVI) in file_set/file_set_tony_N.json.
    """
    ensure_file_set_dir()
    n = get_next_fileset_index()
    out_path = os.path.join(file_set_dir, f"file_set_tony_{n}.json")
    data = {
        "base_dir": selected_dir,
        "files": sorted(selected_rel_paths)
    }
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return out_path, n
    except Exception as e:
        messagebox.showerror(
            "Errore", f"Impossibile salvare il file_set:\n{e}")
        return None, None


def load_fileset_from_path(path):
    """
    Carica un file_set da path, filtra i file che non esistono più e aggiorna selected_files.
    """
    global selected_files
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        rels = data.get("files", [])
        # Tieni solo quelli che esistono ancora
        filtered = []
        for rel in rels:
            abs_path = os.path.join(selected_dir, rel)
            if os.path.isfile(abs_path):
                filtered.append(rel)
        if not filtered:
            messagebox.showwarning(
                "File set vuoto", "Nessuno dei file salvati esiste più.")
            return False
        selected_files = set(filtered)
        return True
    except Exception as e:
        messagebox.showerror(
            "Errore", f"Impossibile caricare il file_set:\n{e}")
        return False


def maybe_autoload_latest_fileset():
    """
    Se esiste <selected_dir>/file_set con almeno un file_set, carica automaticamente l’ultimo.
    """
    ensure_file_set_dir()
    path, n = get_latest_fileset_path()
    if path:
        ok = load_fileset_from_path(path)
        if ok:
            print(
                f"[INFO] Caricato automaticamente file_set più recente: file_set_tony_{n}.json")
        else:
            print(
                "[WARN] Impossibile caricare automaticamente l’ultimo file_set; uso selezione completa.")
    else:
        print("[INFO] Nessun file_set trovato; uso selezione completa.")


# ========================== FUNZIONI DI GESTIONE FILE ==========================

def update_truncated_files_label():
    global truncated_files_label
    if truncated_files_label:
        truncated_files_label.config(text="")


def upload_file(entry, text_widget, file_path_var, file_path=None, refresh_button=None):
    global file_paths, truncated_files
    if not file_path:
        return
    file_paths[file_path_var] = file_path
    rel_path = os.path.relpath(file_path, selected_dir)
    entry.delete(0, tk.END)
    entry.insert(0, rel_path)

    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
            lines = file.readlines()
        content = "".join(lines)
        text_widget.configure(bg=TEXT_BG)
        if file_path_var in truncated_files:
            del truncated_files[file_path_var]
        if refresh_button:
            refresh_button.config(state="disabled")

        text_widget.delete("1.0", tk.END)
        text_widget.insert("1.0", content)
        update_truncated_files_label()
    except Exception as e:
        print(f"[ERRORE] Impossibile leggere il file: {e}")


def save_file(text_widget, file_path_var):
    global file_paths
    file_path = file_paths.get(file_path_var)
    if file_path:
        try:
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(text_widget.get("1.0", tk.END))
            print(f"[INFO] File salvato in: {file_path}")
        except Exception as e:
            print(f"[ERRORE] Impossibile salvare il file: {e}")


def refresh_single(file_path_var, entry, text_widget, refresh_button):
    global file_paths, truncated_files
    file_path = file_paths.get(file_path_var)
    if not file_path:
        return
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as file:
            content = file.read()
        rel_path = os.path.relpath(file_path, selected_dir)
        entry.delete(0, tk.END)
        entry.insert(0, rel_path)
        text_widget.delete("1.0", tk.END)
        text_widget.insert("1.0", content)
        text_widget.configure(bg=TEXT_BG)
        refresh_button.config(state="disabled")
        if file_path_var in truncated_files:
            del truncated_files[file_path_var]
        update_truncated_files_label()
    except Exception as e:
        print(f"[ERRORE] Impossibile ricaricare il file {file_path}: {e}")


# ========================== GESTIONE COLONNE ==========================

def add_column(default_path=None):
    global columns
    if len(columns) >= MAX_COLUMNS:
        return
    column_index = len(columns) + 1
    frame = ttk.Frame(main_frame, padding="5", relief="sunken")
    frame.grid(row=0, column=column_index - 1, sticky=(tk.W, tk.E, tk.N, tk.S))

    file_label = ttk.Label(frame, text=f"Nome file {column_index}:")
    file_label.pack(anchor="w")

    entry = ttk.Entry(frame, width=40)
    entry.pack(side="top", fill="x", expand=True)

    text_area = tk.Text(frame, wrap="none", width=40, height=COLUMN_TEXT_HEIGHT,
                        bg=TEXT_BG, fg=FG_TEXT, insertbackground=FG_TEXT,
                        selectbackground=TEXT_SELECT, selectforeground=FG_TEXT,
                        relief="flat", borderwidth=1, highlightthickness=1,
                        highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_BLUE,
                        font=('Consolas', 10))
    text_area.pack(fill="both", expand=True)

    button_frame = ttk.Frame(frame)
    button_frame.pack(side="top", fill="x", pady=5)

    refresh_button = ttk.Button(frame, text="dummy")

    upload_button = ttk.Button(
        button_frame,
        text="Upload",
        command=lambda e=entry, t=text_area, f=f"file{column_index}": upload_file(
            e, t, f, default_path, refresh_button)
    )
    upload_button.pack(side="left", padx=5)

    save_button = ttk.Button(
        button_frame, text="Salva",
        command=lambda t=text_area, f=f"file{column_index}": save_file(t, f)
    )
    save_button.pack(side="left", padx=5)

    remove_button = ttk.Button(
        button_frame, text="×",
        command=lambda f=frame: remove_column(f)
    )
    remove_button.pack(side="left", padx=5)

    refresh_button = ttk.Button(
        button_frame, text="Refresh Slot", state="disabled"
    )
    refresh_button.config(
        command=lambda f=f"file{column_index}", e=entry, t=text_area, rb=refresh_button:
        refresh_single(f, e, t, rb)
    )
    refresh_button.pack(side="left", padx=5)

    columns.append(
        (frame, entry, text_area, f"file{column_index}", refresh_button))
    if default_path:
        upload_file(entry, text_area,
                    f"file{column_index}", default_path, refresh_button)


def remove_column(frame):
    global columns
    for i, (f, entry, text_area, file_path_var, refresh_button) in enumerate(columns):
        if f == frame:
            f.destroy()
            columns.pop(i)
            if file_path_var in file_paths:
                del file_paths[file_path_var]
            if file_path_var in truncated_files:
                del truncated_files[file_path_var]
            break
    for i, (f, entry, _, _, _) in enumerate(columns):
        entry_label = f.winfo_children()[0]
        entry_label.config(text=f"Nome file {i+1}:")
    update_truncated_files_label()


# ========================== RICOSTRUISCI COLONNE ==========================

def rebuild_columns():
    """Ricostruisce tutte le colonne nel main_frame in base ai file selezionati"""
    global columns

    # cancella tutte le colonne attuali
    for (frame, _, _, _, _) in columns:
        frame.destroy()
    columns.clear()

    # ricostruisce solo i file selezionati
    for rel_path in sorted(selected_files):
        file_path = os.path.join(selected_dir, rel_path)
        add_column(default_path=file_path)

    # riallinea i frame secondari (request, explanation, bottoni)
    num_columns = len(columns)
    request_frame.grid_forget()
    request_frame.grid(
        row=1, column=0, columnspan=num_columns, sticky=(tk.W, tk.E))

    explanation_frame.grid_forget()
    explanation_frame.grid(row=1, column=num_columns,
                           sticky=(tk.W, tk.E, tk.N, tk.S))

    button_frame.grid_forget()
    button_frame.grid(
        row=2, column=0, columnspan=num_columns + 1, sticky=(tk.W, tk.E))

    # riallinea anche il frame delle opzioni prompt (se già creato)
    global prompt_mode_frame
    if prompt_mode_frame is not None:
        prompt_mode_frame.grid_forget()
        prompt_mode_frame.grid(
            row=3, column=0, columnspan=num_columns + 1, sticky=(tk.W, tk.E)
        )


# ========================== FINESTRA "GESTISCI FILE" ==========================

def open_manage_files():
    global all_files, selected_files

    win = tk.Toplevel(root)
    win.title("Gestisci File")
    win.geometry("700x550")
    win.configure(bg=BG_DARK)

    # barra ricerca
    search_var = tk.StringVar()

    def update_list(*args):
        filter_text = search_var.get().lower()
        for cb, rel_path in checkboxes:
            if filter_text in rel_path.lower():
                cb.pack(anchor="w")
            else:
                cb.pack_forget()

    search_entry = ttk.Entry(win, textvariable=search_var)
    search_entry.pack(fill="x", padx=5, pady=5)
    search_var.trace("w", update_list)

    # canvas + scrollbar
    canvas_m = tk.Canvas(win, bg=BG_DARK, highlightthickness=0)
    scroll_y = ttk.Scrollbar(win, orient="vertical", command=canvas_m.yview)
    frame_m = ttk.Frame(canvas_m)
    frame_m.bind("<Configure>", lambda e: canvas_m.configure(
        scrollregion=canvas_m.bbox("all")))
    canvas_m.create_window((0, 0), window=frame_m, anchor="nw")
    canvas_m.configure(yscrollcommand=scroll_y.set)
    canvas_m.pack(side="left", fill="both", expand=True)
    scroll_y.pack(side="right", fill="y")

    checkboxes = []
    vars_map = {}

    for rel_path in sorted(all_files):
        var = tk.BooleanVar(value=(rel_path in selected_files))
        cb = ttk.Checkbutton(frame_m, text=rel_path, variable=var)
        cb.pack(anchor="w")
        vars_map[rel_path] = var
        checkboxes.append((cb, rel_path))

    # --- funzioni di selezione rapida ---
    def select_all():
        for v in vars_map.values():
            v.set(True)

    def deselect_all():
        for v in vars_map.values():
            v.set(False)

    # pulsanti selezione rapida
    quick_frame = ttk.Frame(win)
    quick_frame.pack(fill="x", pady=5)
    ttk.Button(quick_frame, text="Seleziona Tutti",
               command=select_all).pack(side="left", padx=5)
    ttk.Button(quick_frame, text="Deseleziona Tutti",
               command=deselect_all).pack(side="left", padx=5)

    # --- salvataggio file_set ---
    action_frame = ttk.Frame(win)
    action_frame.pack(fill="x", pady=5)

    def on_save_fileset():
        # costruisci l’insieme selezionato (relativi)
        chosen = sorted([rel for rel, v in vars_map.items() if v.get()])
        if not chosen:
            messagebox.showwarning(
                "Nessun file", "Seleziona almeno un file da salvare.")
            return
        out_path, n = save_current_selection_as_fileset(chosen)
        if out_path:
            messagebox.showinfo("Salvato",
                                f"File set salvato come file_set_tony_{n}.json\n\n{out_path}")
            # riabilita Carica (potrebbe non esserci prima)
            load_btn.configure(state="normal")

    ttk.Button(action_frame, text="Save File_set",
               command=on_save_fileset).pack(side="left", padx=5)

    # --- caricamento file_set ---
    def on_load_fileset():
        ensure_file_set_dir()
        existing = list_existing_file_sets()
        if not existing:
            messagebox.showinfo("Nessun file_set",
                                "Non ci sono file_set salvati.")
            return

        # dialogo semplice con lista e pulsante Usa
        chooser = tk.Toplevel(win)
        chooser.title("Carica File_set")
        chooser.geometry("420x300")
        chooser.configure(bg=BG_DARK)

        ttk.Label(chooser, text="Seleziona una configurazione salvata:").pack(
            anchor="w", padx=8, pady=8)

        lb = tk.Listbox(chooser, height=10, 
                        bg=TEXT_BG, fg=FG_TEXT,
                        selectbackground=ACCENT_BLUE, selectforeground="white",
                        relief="flat", borderwidth=1, highlightthickness=1,
                        highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_BLUE,
                        font=('Segoe UI', 10))
        lb.pack(fill="both", expand=True, padx=8, pady=8)

        # Mostra in ordine decrescente (più recente in alto)
        items_desc = list(reversed(existing))  # (path, n)
        for p, n in items_desc:
            lb.insert(tk.END, f"file_set_tony_{n}.json")

        def use_selected():
            sel = lb.curselection()
            if not sel:
                messagebox.showwarning(
                    "Nessuna scelta", "Seleziona un file_set dall’elenco.")
                return
            index = sel[0]
            path, n = items_desc[index]
            ok = load_fileset_from_path(path)
            if ok:
                rebuild_columns()
                chooser.destroy()
                # opzionalmente chiudere anche "Gestisci File"
                # win.destroy()

        ttk.Button(chooser, text="Usa", command=use_selected).pack(pady=5)

    load_btn = ttk.Button(
        action_frame, text="Carica File_set", command=on_load_fileset)
    # disabilita se non esistono file_set
    load_btn_state = "normal" if list_existing_file_sets() else "disabled"
    load_btn.configure(state=load_btn_state)
    load_btn.pack(side="left", padx=5)

    # --- applica selezione manuale corrente ---
    def apply_selection():
        global selected_files
        selected_files = {rel for rel, v in vars_map.items() if v.get()}
        rebuild_columns()
        win.destroy()

    ttk.Button(win, text="OK", command=apply_selection).pack(pady=5)


# ========================== PROMPT E API (DeepSeek) ==========================

def get_prompt_tail():
    """
    Restituisce il finale del prompt in base all'opzione selezionata.
    Ordine di priorità: patches (2) > explanation (3) > full code (1 default).
    """
    # Se esiste la variabile vuol dire che l'UI è stata creata.
    # In fase di bootstrap, se non ancora creata, fallback all'opzione 1.
    try:
        if prompt_mode_var2.get():
            return (
                "DO NOT return the full, updated content of the files involved. "
                "YOU MUST provide a precise and specific list of the changes to be implemented. "
                "SPECIFY clearly the name of the file/s to be edited (e.g., file1.js). "
                "INDICATE the specific action/s to perform (e.g., Replace, Insert, Delete etc etc). "
                "DEFINE the exact location/s in the code/s. "
                "PROVIDE the exact code to be used for the change. "
                "Execute the following request, providing only the changes as described above:\n"
            )
        if prompt_mode_var3.get():
            return "I want to ask you something about this application, read here my request:"
    except NameError:
        pass
    # Default (opzione 1)
    return (
        "Please return the fully updated code of the files involved to fulfill the following request.  \n"
        "If, to fulfill the following request, for example, it is necessary to edit file 1 and file 3 (for example), \n"
        "return the fully updated files for file 1 and file 3.\n"
        "Follow the request:"
    )


def generate_prompt():
    global columns
    file_names = [entry.get() for _, entry, _, _, _ in columns]
    file_contents = [text_area.get("1.0", tk.END).strip()
                     for _, _, text_area, _, _ in columns]
    prompt_text = "User has these files:\n"
    for name in file_names:
        prompt_text += f"{name}\n"
    prompt_text += "\nContents of the files are:\n"
    for name, content in zip(file_names, file_contents):
        prompt_text += f"{name}\n{content}\n\n"
    prompt_text += get_prompt_tail()
    pyperclip.copy(prompt_text)
    print("[INFO] Prompt copiato nella clipboard.")


def run_refresh_then_prompt():
    refresh_files()
    generate_prompt()


def parse_deepseek_files(content: str):
    """
    Estrae un dizionario {filename -> file_content} dal testo del modello.
    Supporta due formati comuni:
      1) Filename su una riga + blocco ``` ... ```
      2) Filename su una riga + corpo fino al prossimo filename o fine testo
    Ritorna anche una stringa 'explanations' con l'eventuale testo non parsato.
    """
    files_map = {}
    consumed_spans = []

    # --- Passo 1: filename + fenced code block
    # Esempio:
    #   path/to/file.py
    #   ```python
    #   ...code...
    #   ```
    pattern_fenced = re.compile(
        r'(?m)^\s*([^\n\r]+?\.[A-Za-z0-9]{1,10})\s*\n```[^`\n]*\n(.*?)\n```',
        re.DOTALL
    )
    for m in pattern_fenced.finditer(content):
        fname = m.group(1).strip()
        body = m.group(2)
        files_map[fname] = body
        consumed_spans.append((m.start(), m.end()))

    # --- Passo 2: filename + blocco plain fino al prossimo filename
    # Ma evita di riparsare aree già consumate
    def is_consumed(i):
        for a, b in consumed_spans:
            if a <= i < b:
                return True
        return False

    # Candidati filename: linee che terminano con .ext
    pattern_plain_header = re.compile(
        r'(?m)^\s*([^\n\r]+?\.[A-Za-z0-9]{1,10})\s*$')
    matches = list(pattern_plain_header.finditer(content))
    for idx, m in enumerate(matches):
        start = m.start()
        if is_consumed(start):
            continue
        fname = m.group(1).strip()

        # Limita al prossimo header non consumato
        end_pos = len(content)
        for j in range(idx + 1, len(matches)):
            nxt = matches[j]
            if is_consumed(nxt.start()):
                continue
            end_pos = nxt.start()
            break

        # Corpo è tra fine linea header e end_pos
        # taglia un eventuale \n iniziale
        body = content[m.end():end_pos]
        if body.startswith("\n"):
            body = body[1:]
        body = body.strip()
        if body:
            files_map[fname] = body
            consumed_spans.append((m.start(), end_pos))

    # Spiegazioni = tutto ciò che non è stato consumato
    # (per semplicità, se parsing ha trovato almeno un file, mostriamo cmq explanations=resto)
    explanations_parts = []
    last = 0
    for a, b in sorted(consumed_spans):
        if last < a:
            explanations_parts.append(content[last:a])
        last = b
    if last < len(content):
        explanations_parts.append(content[last:])
    explanations_text = "\n".join(p.strip()
                                  for p in explanations_parts if p.strip())

    return files_map, explanations_text


def send_to_deepseek():
    """
    Esegue la chiamata a DeepSeek, mostra l'output in 'Spiegazioni',
    e APPLICA le modifiche ai rispettivi slot dei file (match per path relativo o basename).
    Non salva su disco automaticamente (usa il pulsante 'Salva' per ciascun slot).
    """
    try:
        # Costruzione prompt (come generate_prompt, ma includendo anche la richiesta utente)
        file_names = [entry.get() for _, entry, _, _, _ in columns]
        file_contents = [text_area.get("1.0", tk.END).strip()
                         for _, _, text_area, _, _ in columns]

        prompt_text = "User has these files:\n"
        for name in file_names:
            prompt_text += f"{name}\n"
        prompt_text += "\nContents of the files are:\n"
        for name, content in zip(file_names, file_contents):
            prompt_text += f"{name}\n{content}\n\n"

        prompt_text += get_prompt_tail() + "\n"

        user_request = request_entry.get("1.0", tk.END).strip()
        if not user_request:
            user_request = "(Nessuna richiesta specificata dall'utente.)"
        prompt_text += user_request

        if not API_KEY or not isinstance(API_KEY, str):
            messagebox.showerror(
                "Errore DeepSeek", "API key mancante o non valida (variabile DEEPSEEK_API_KEY).")
            return

        headers = {
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an expert developer assistant. "
                        "When the user asks to modify files, always return only the fully updated file contents, "
                        "each preceded by the file name (exact path or exact name), preferably followed by a fenced code block with the file content."
                    ),
                },
                {"role": "user", "content": prompt_text},
            ],
            "temperature": 0.2,
        }

        print("[INFO] Chiamata a DeepSeek in corso...")
        resp = requests.post(
            DEEPSEEK_API_URL, headers=headers, json=payload, timeout=90)
        resp.raise_for_status()
        data = resp.json()

        content = ""
        try:
            content = data.get("choices", [{}])[0].get(
                "message", {}).get("content", "")
        except Exception:
            content = ""

        if not content:
            content = f"[WARN] Nessun contenuto nella risposta DeepSeek.\nPayload risposta:\n{json.dumps(data, ensure_ascii=False, indent=2)}"

        # --- Parsing dei file restituiti
        files_map, extra_explanations = parse_deepseek_files(content)

        # --- Applica modifiche agli slot
        # Crea mappe ausiliarie per match:
        #   - path relativo esatto (quello che c'è nella Entry)
        #   - basename del file
        slot_by_rel = {}
        slot_by_base = {}
        for (frame, entry, text_area, file_path_var, refresh_btn) in columns:
            rel = entry.get().strip()
            base = os.path.basename(rel) if rel else ""
            slot_by_rel[rel] = (entry, text_area)
            if base:
                slot_by_base.setdefault(base, []).append((entry, text_area))

        updated_count = 0
        created_count = 0

        for fname_from_ai, new_body in files_map.items():
            fname_from_ai = fname_from_ai.strip()
            base_ai = os.path.basename(fname_from_ai)

            target_entry = None
            target_text = None

            # 1) Match su path relativo esatto
            if fname_from_ai in slot_by_rel:
                target_entry, target_text = slot_by_rel[fname_from_ai]
            # 2) Match su basename
            elif base_ai in slot_by_base and len(slot_by_base[base_ai]) == 1:
                target_entry, target_text = slot_by_base[base_ai][0]
            elif base_ai in slot_by_base and len(slot_by_base[base_ai]) > 1:
                # Ambiguità: prova match per suffisso path
                candidates = slot_by_base[base_ai]
                chosen = None
                for (e, t) in candidates:
                    if e.get().endswith(fname_from_ai):
                        chosen = (e, t)
                        break
                if not chosen:
                    # fallback: primo con basename
                    chosen = candidates[0]
                target_entry, target_text = chosen

            if target_text is not None:
                # Aggiorna slot esistente
                target_text.delete("1.0", tk.END)
                target_text.insert("1.0", new_body)
                target_text.configure(bg=TEXT_BG)
                updated_count += 1
            else:
                # Nessuno slot corrispondente: crea uno slot nuovo e inserisci contenuto
                add_column(default_path=None)
                # lo slot appena creato è l'ultimo della lista
                _, entry_new, text_new, _, _ = columns[-1]
                entry_new.delete(0, tk.END)
                entry_new.insert(0, fname_from_ai)
                text_new.delete("1.0", tk.END)
                text_new.insert("1.0", new_body)
                text_new.configure(bg=TEXT_BG)
                created_count += 1

        # --- Aggiorna riquadro Spiegazioni
        exp_full = []
        if extra_explanations:
            exp_full.append(
                "=== Notes / Explanations ===\n" + extra_explanations)
        if files_map:
            exp_full.append(
                f"\n=== Summary ===\nUpdated slots: {updated_count} | New slots: {created_count}")
        explanations_text = "\n\n".join(exp_full).strip() or content

        explanations.delete("1.0", tk.END)
        explanations.insert("1.0", explanations_text)
        pyperclip.copy(content)

        print(
            f"[INFO] DeepSeek: aggiornati {updated_count} slot, creati {created_count} slot.")
        messagebox.showinfo("DeepSeek",
                            f"Risposta ricevuta.\nAggiornati {updated_count} slot.\nCreati {created_count} slot nuovi (se necessario).")
    except requests.HTTPError as he:
        try:
            err_json = he.response.json()
            err_text = json.dumps(err_json, ensure_ascii=False, indent=2)
        except Exception:
            err_text = he.response.text if he.response is not None else str(he)
        messagebox.showerror("Errore DeepSeek (HTTP)",
                             f"{he}\n\nDettagli:\n{err_text}")
    except Exception as e:
        messagebox.showerror(
            "Errore DeepSeek", f"Non è stato possibile completare la richiesta:\n{e}")


def clear_all():
    for (frame, _, _, _, _) in columns:
        frame.destroy()
    columns.clear()
    selected_files.clear()
    for _ in range(3):
        add_column()


def refresh_files():
    for frame, entry, text_area, file_path_var, refresh_button in columns:
        if file_path_var in file_paths:
            if str(refresh_button['state']) == "normal":
                refresh_single(file_path_var, entry, text_area, refresh_button)
            else:
                upload_file(entry, text_area, file_path_var,
                            file_path=file_paths[file_path_var], refresh_button=refresh_button)


# ========================== AVVIO INTERFACCIA ==========================

root = tk.Tk()
root.title("Editor con AI")

root.withdraw()
selected_dir = filedialog.askdirectory(title="Seleziona la directory di lavoro",
                                       initialdir="C:/Users/Antonio Nuzzi/Trust Gym")
if not selected_dir:
    selected_dir = "C:/Users/Antonio Nuzzi/Trust Gym"
print(f"[INFO] Directory selezionata: {selected_dir}")
root.deiconify()
root.state("zoomed")

# ========================== DARK STUDIO THEME ==========================
# Colori Dark Studio
BG_DARK = "#1e1e1e"           # Background principale
BG_DARKER = "#252526"         # Background più scuro
BG_LIGHTER = "#2d2d30"        # Background chiaro per frame
FG_TEXT = "#d4d4d4"           # Testo principale
FG_SECONDARY = "#858585"      # Testo secondario
ACCENT_BLUE = "#007acc"       # Accento blu
ACCENT_GREEN = "#4ec9b0"      # Accento verde
BORDER_COLOR = "#3e3e42"      # Bordi
TEXT_BG = "#1e1e1e"           # Background text widget
TEXT_SELECT = "#264f78"       # Selezione testo

# Configura root window
root.configure(bg=BG_DARK)

# Configura ttk Style
style = ttk.Style(root)
style.theme_use('clam')  # Base theme

# Frame styles
style.configure("TFrame", background=BG_DARK)
style.configure("TLabelframe", background=BG_LIGHTER, bordercolor=BORDER_COLOR, 
                foreground=FG_TEXT)
style.configure("TLabelframe.Label", background=BG_LIGHTER, foreground=FG_TEXT)

# Label styles
style.configure("TLabel", background=BG_DARK, foreground=FG_TEXT, 
                font=('Segoe UI', 9))

# Button styles
style.configure("TButton", 
                background=BG_LIGHTER, 
                foreground=FG_TEXT, 
                bordercolor=BORDER_COLOR,
                focuscolor=ACCENT_BLUE,
                font=('Segoe UI', 9))
style.map("TButton", 
          background=[("active", "#3e3e42"), ("pressed", "#007acc")],
          foreground=[("active", "#ffffff")])

# Green button style (per "Ricarica + Prompt")
style.configure("Green.TButton", 
                foreground="white", 
                background=ACCENT_GREEN, 
                bordercolor=ACCENT_GREEN,
                font=('Segoe UI', 10, 'bold'))
style.map("Green.TButton", 
          background=[("active", "#5dd4b8"), ("pressed", "#3ea88f")])

# Entry style
style.configure("TEntry", 
                fieldbackground=TEXT_BG, 
                background=TEXT_BG,
                foreground=FG_TEXT, 
                bordercolor=BORDER_COLOR,
                insertcolor=FG_TEXT)

# Checkbutton style
style.configure("TCheckbutton", 
                background=BG_DARK, 
                foreground=FG_TEXT,
                font=('Segoe UI', 9))
style.map("TCheckbutton",
          background=[("active", BG_DARK)],
          foreground=[("active", ACCENT_BLUE)])

# Scrollbar style
style.configure("TScrollbar", 
                background=BG_LIGHTER,
                troughcolor=BG_DARKER,
                bordercolor=BORDER_COLOR,
                arrowcolor=FG_TEXT)
style.map("TScrollbar",
          background=[("active", "#3e3e42")])

# prepara path cartella file_set
file_set_dir = os.path.join(selected_dir, "file_set")

# scan ricorsiva di tutti i file
all_files = []
for root_dir, _, files in os.walk(selected_dir):
    for f in files:
        rel_path = os.path.relpath(os.path.join(root_dir, f), selected_dir)
        all_files.append(rel_path)

# default: carico tutti, ma se esiste un file_set recente lo uso
selected_files = set(all_files)
maybe_autoload_latest_fileset()

container = ttk.Frame(root)
container.pack(fill="both", expand=True)

canvas = tk.Canvas(container, bg=BG_DARK, highlightthickness=0)
scroll_x = ttk.Scrollbar(container, orient="horizontal", command=canvas.xview)
canvas.configure(xscrollcommand=scroll_x.set)
scroll_x.pack(side="bottom", fill="x")
canvas.pack(side="top", fill="both", expand=True)


def shift_scroll(event):
    canvas.xview_scroll(-1 * int(event.delta/120), "units")


canvas.bind("<Shift-MouseWheel>", shift_scroll)

main_frame = ttk.Frame(canvas, padding="10")
canvas.create_window((0, 0), window=main_frame, anchor="nw")
main_frame.bind("<Configure>", lambda e: canvas.configure(
    scrollregion=canvas.bbox("all")))

# carico i file selezionati (eventualmente da file_set)
for rel_path in sorted(selected_files):
    file_path = os.path.join(selected_dir, rel_path)
    add_column(default_path=file_path)

# frames secondari
request_frame = ttk.Frame(main_frame, padding="5", relief="sunken")
request_frame.grid(row=1, column=0, columnspan=len(
    columns), sticky=(tk.W, tk.E))
request_label = ttk.Label(request_frame, text="Fai una richiesta:")
request_label.pack(anchor="w")
request_entry = tk.Text(request_frame, wrap="word", height=5,
                        bg=TEXT_BG, fg=FG_TEXT, insertbackground=FG_TEXT,
                        selectbackground=TEXT_SELECT, selectforeground=FG_TEXT,
                        relief="flat", borderwidth=1, highlightthickness=1,
                        highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_BLUE,
                        font=('Segoe UI', 10))
request_entry.pack(fill="both", expand=True)

explanation_frame = ttk.Frame(main_frame, padding="5", relief="sunken")
explanation_frame.grid(row=1, column=len(
    columns), sticky=(tk.W, tk.E, tk.N, tk.S))
explanations_label = ttk.Label(explanation_frame, text="Spiegazioni:")
explanations_label.pack(anchor="w")
explanations = tk.Text(explanation_frame, wrap="word", width=40, height=5,
                       bg=TEXT_BG, fg=FG_TEXT, insertbackground=FG_TEXT,
                       selectbackground=TEXT_SELECT, selectforeground=FG_TEXT,
                       relief="flat", borderwidth=1, highlightthickness=1,
                       highlightbackground=BORDER_COLOR, highlightcolor=ACCENT_BLUE,
                       font=('Segoe UI', 10))
explanations.pack(fill="both", expand=True)

button_frame = ttk.Frame(main_frame, padding="5")
button_frame.grid(row=2, column=0, columnspan=len(
    columns) + 1, sticky=(tk.W, tk.E))
process_button = ttk.Button(
    button_frame, text="Esegui", command=send_to_deepseek)
process_button.pack(side="left", padx=5)
prompt_button = ttk.Button(
    button_frame, text="Prompt", command=generate_prompt)
prompt_button.pack(side="left", padx=5)
add_column_button = ttk.Button(button_frame, text="+", command=add_column)
add_column_button.pack(side="left", padx=5)
clear_all_button = ttk.Button(
    button_frame, text="Clear All", command=clear_all)
clear_all_button.pack(side="left", padx=5)
refresh_button_global = ttk.Button(
    button_frame, text="Ricarica Tutti", command=refresh_files)
refresh_button_global.pack(side="left", padx=5)
combo_button = ttk.Button(
    button_frame, text="Ricarica + Prompt", command=run_refresh_then_prompt, style="Green.TButton")
combo_button.pack(side="left", padx=5)
manage_button = ttk.Button(
    button_frame, text="Gestisci File", command=open_manage_files)
manage_button.pack(side="left", padx=5)

truncated_files_label = ttk.Label(root, text="", foreground="#f48771", background=BG_DARK)
truncated_files_label.pack(side="bottom", fill="x", pady=5)

# === Prompt mode (checkbox esclusivi) ===
# Variabili stato (default: opzione 1 attiva)
prompt_mode_var1 = tk.IntVar(value=1)
prompt_mode_var2 = tk.IntVar(value=0)
prompt_mode_var3 = tk.IntVar(value=0)

def set_prompt_mode(which):
    """Rende mutuamente esclusivi i tre checkbox."""
    if which == 1:
        prompt_mode_var1.set(1); prompt_mode_var2.set(0); prompt_mode_var3.set(0)
    elif which == 2:
        prompt_mode_var1.set(0); prompt_mode_var2.set(1); prompt_mode_var3.set(0)
    elif which == 3:
        prompt_mode_var1.set(0); prompt_mode_var2.set(0); prompt_mode_var3.set(1)

# Frame posizionato subito sotto i bottoni
prompt_mode_frame = ttk.Frame(main_frame, padding="5")
prompt_mode_frame.grid(row=3, column=0, columnspan=len(columns) + 1, sticky=(tk.W, tk.E))
ttk.Label(prompt_mode_frame, text="Output preference:").pack(anchor="w")
cb1 = ttk.Checkbutton(
    prompt_mode_frame,
    text="Return the fully updated code of the files",
    variable=prompt_mode_var1,
    command=lambda: set_prompt_mode(1)
)
cb1.pack(anchor="w", pady=(2, 0))
cb2 = ttk.Checkbutton(
    prompt_mode_frame,
    text="Give me the patches one by one",
    variable=prompt_mode_var2,
    command=lambda: set_prompt_mode(2)
)
cb2.pack(anchor="w")
cb3 = ttk.Checkbutton(
    prompt_mode_frame,
    text="Give me an explanation or an opinion",
    variable=prompt_mode_var3,
    command=lambda: set_prompt_mode(3)
)
cb3.pack(anchor="w")

root.bind("<Control-Return>", lambda e: run_refresh_then_prompt())

print("[INFO] Interfaccia inizializzata con successo.")
root.mainloop()

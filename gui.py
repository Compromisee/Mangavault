#!/usr/bin/env python3
"""
MangaForge GUI - Simple tkinter-based manga downloader.
Features: search, preview, download by volume/chapter, metadata editor.
No emojis, clean interface, pastel color scheme.
"""

import os
import sys
import threading
import time
import re
from pathlib import Path
from tkinter import *
from tkinter import ttk, filedialog, messagebox, scrolledtext
from PIL import Image, ImageTk
import io

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import MangaDownloader, sanitize_filename, download_image

try:
    import requests
    from PIL import Image, ImageTk
    PILLOW_AVAIL = True
except:
    PILLOW_AVAIL = False


# ============================
# COLOR SCHEME
# ============================

COLORS = {
    'bg': '#1a1a2e',
    'bg2': '#16213e',
    'bg3': '#0f3460',
    'accent': '#7ec8e3',
    'accent2': '#a8e6cf',
    'accent3': '#f4aeba',
    'accent4': '#c3aed6',
    'accent5': '#ffd3b6',
    'text': '#e0e0e0',
    'text2': '#a0a0a0',
    'success': '#a8e6cf',
    'error': '#ff6b6b',
    'warning': '#ffd93d',
    'btn': '#0f3460',
    'btn_hover': '#1a4a8a',
    'entry_bg': '#0d1b3e',
}


class MangaForgeGUI:
    """Main tkinter application."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("MangaForge")
        self.root.geometry("1100x750")
        self.root.configure(bg=COLORS['bg'])
        
        # Set icon
        try:
            self.root.iconbitmap(default='')
        except:
            pass
        
        self.downloader = MangaDownloader()
        self.current_results = []
        self.current_manga = None
        self.current_cover = None
        self.cover_photo = None
        
        # Settings
        self.settings = {
            'format': StringVar(value='epub'),
            'crop': BooleanVar(value=False),
            'quality': IntVar(value=85),
            'output_dir': StringVar(value=os.path.join(os.path.expanduser('~'), 'MangaForgeDownloads')),
            'lang': StringVar(value='en'),
            'rating': StringVar(value='any'),
            'concurrent': IntVar(value=3),
            'split': BooleanVar(value=True),
            'sources': {
                'mangadex': BooleanVar(value=True),
                'asurascans': BooleanVar(value=True),
                'webtoons': BooleanVar(value=False),
                'hitomi': BooleanVar(value=False),
            }
        }
        
        self.setup_styles()
        self.build_ui()
    
    def setup_styles(self):
        """Configure ttk styles."""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure custom styles
        style.configure('TFrame', background=COLORS['bg'])
        style.configure('TLabel', background=COLORS['bg'], foreground=COLORS['text'])
        style.configure('TButton', background=COLORS['btn'], foreground=COLORS['text'],
                       borderwidth=1, focuscolor='none')
        style.map('TButton',
                  background=[('active', COLORS['btn_hover'])],
                  foreground=[('active', COLORS['accent'])])
        
        style.configure('TMenubutton', background=COLORS['btn'], foreground=COLORS['text'])
        style.configure('TEntry', fieldbackground=COLORS['entry_bg'], foreground=COLORS['text'])
        
        # Progress bar
        style.configure('TProgressbar', background=COLORS['accent'],
                       troughcolor=COLORS['bg2'], bordercolor=COLORS['bg3'],
                       lightcolor=COLORS['accent'], darkcolor=COLORS['accent'])
        
        style.configure('Accent.TButton', background=COLORS['accent'], foreground=COLORS['bg'])
        style.map('Accent.TButton',
                  background=[('active', COLORS['accent2'])])
    
    def build_ui(self):
        """Build the main UI."""
        # Menu bar
        self.create_menu()
        
        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=BOTH, expand=True, padx=10, pady=10)
        
        # Top search bar
        self.create_search_bar()
        
        # Content area (notebook)
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=BOTH, expand=True, pady=(10, 0))
        
        # Results tab
        self.results_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.results_frame, text='  Search Results  ')
        self.create_results_view()
        
        # Downloads tab
        self.downloads_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.downloads_frame, text='  Downloads  ')
        self.create_downloads_view()
        
        # Settings tab
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text='  Settings  ')
        self.create_settings_view()
        
        # Status bar
        self.create_status_bar()
    
    def create_menu(self):
        """Create menu bar."""
        menubar = Menu(self.root, bg=COLORS['bg2'], fg=COLORS['text'],
                      activebackground=COLORS['accent'], activeforeground=COLORS['bg'])
        
        # File menu
        file_menu = Menu(menubar, tearoff=0, bg=COLORS['bg2'], fg=COLORS['text'],
                        activebackground=COLORS['accent'], activeforeground=COLORS['bg'])
        file_menu.add_command(label='Open Output Folder', command=self.open_output)
        file_menu.add_separator()
        file_menu.add_command(label='Exit', command=self.root.quit)
        menubar.add_cascade(label='File', menu=file_menu)
        
        # Download menu
        dl_menu = Menu(menubar, tearoff=0, bg=COLORS['bg2'], fg=COLORS['text'],
                      activebackground=COLORS['accent'], activeforeground=COLORS['bg'])
        dl_menu.add_command(label='Download by URL', command=self.show_url_dialog)
        dl_menu.add_command(label='Bulk Download', command=self.show_bulk_dialog)
        menubar.add_cascade(label='Download', menu=dl_menu)
        
        # Help
        help_menu = Menu(menubar, tearoff=0, bg=COLORS['bg2'], fg=COLORS['text'],
                        activebackground=COLORS['accent'], activeforeground=COLORS['bg'])
        help_menu.add_command(label='About', command=self.show_about)
        menubar.add_cascade(label='Help', menu=help_menu)
        
        self.root.config(menu=menubar)
    
    def create_search_bar(self):
        """Create the top search bar."""
        search_frame = ttk.Frame(self.main_frame)
        search_frame.pack(fill=X)
        
        # Search entry
        self.search_var = StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, font=('Segoe UI', 12))
        search_entry.pack(side=LEFT, fill=X, expand=True, ipady=5)
        search_entry.bind('<Return>', lambda e: self.perform_search())
        
        # Search button
        search_btn = ttk.Button(search_frame, text='  Search  ', command=self.perform_search,
                               style='Accent.TButton')
        search_btn.pack(side=LEFT, padx=(5, 0))
        
        # Source checkbuttons
        src_frame = ttk.Frame(search_frame)
        src_frame.pack(side=LEFT, padx=(10, 0))
        
        ttk.Label(src_frame, text='Sources:', font=('Segoe UI', 8)).pack(side=LEFT)
        for src_name, src_var in self.settings['sources'].items():
            cb = ttk.Checkbutton(src_frame, text=src_name.capitalize(), variable=src_var)
            cb.pack(side=LEFT, padx=2)
    
    def create_results_view(self):
        """Create the search results view."""
        # Left: list
        left_frame = ttk.Frame(self.results_frame)
        left_frame.pack(side=LEFT, fill=BOTH, expand=True)
        
        # Treeview for results
        columns = ('title', 'source', 'info')
        self.results_tree = ttk.Treeview(left_frame, columns=columns, show='headings',
                                        selectmode='browse')
        self.results_tree.heading('title', text='Title')
        self.results_tree.heading('source', text='Source')
        self.results_tree.heading('info', text='Info')
        self.results_tree.column('title', width=300)
        self.results_tree.column('source', width=100)
        self.results_tree.column('info', width=150)
        
        scrollbar = ttk.Scrollbar(left_frame, orient=VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        
        self.results_tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        self.results_tree.bind('<<TreeviewSelect>>', self.on_result_select)
        self.results_tree.bind('<Double-1>', self.on_result_double_click)
        
        # Right: details panel
        right_frame = ttk.Frame(self.results_frame, width=300)
        right_frame.pack(side=RIGHT, fill=BOTH, padx=(10, 0))
        right_frame.pack_propagate(False)
        
        # Cover art
        self.cover_label = ttk.Label(right_frame, text='Cover Art\n(select a result)', 
                                     background=COLORS['bg3'], anchor=CENTER)
        self.cover_label.pack(fill=X, pady=(0, 10), ipady=60)
        
        # Details
        self.details_text = Text(right_frame, height=12, wrap=WORD,
                                bg=COLORS['bg2'], fg=COLORS['text'],
                                relief=FLAT, borderwidth=0,
                                font=('Segoe UI', 9))
        self.details_text.pack(fill=BOTH, expand=True)
        self.details_text.insert(END, 'Select a result to view details')
        self.details_text.config(state=DISABLED)
    
    def create_downloads_view(self):
        """Create the downloads view."""
        # Top controls
        ctrl_frame = ttk.Frame(self.downloads_frame)
        ctrl_frame.pack(fill=X, pady=(0, 10))
        
        ttk.Label(ctrl_frame, text='Format:').pack(side=LEFT)
        fmt_combo = ttk.Combobox(ctrl_frame, textvariable=self.settings['format'],
                                values=['epub', 'cbz', 'pdf'], width=8)
        fmt_combo.pack(side=LEFT, padx=5)
        
        ttk.Label(ctrl_frame, text='Quality:').pack(side=LEFT, padx=(10, 0))
        q_spin = ttk.Spinbox(ctrl_frame, from_=10, to=100, textvariable=self.settings['quality'], width=5)
        q_spin.pack(side=LEFT, padx=5)
        
        ttk.Checkbutton(ctrl_frame, text='Split', variable=self.settings['split']).pack(side=LEFT, padx=10)
        ttk.Checkbutton(ctrl_frame, text='Crop', variable=self.settings['crop']).pack(side=LEFT, padx=5)
        
        # Output dir
        ttk.Label(ctrl_frame, text='Output:').pack(side=LEFT, padx=(10, 0))
        out_entry = ttk.Entry(ctrl_frame, textvariable=self.settings['output_dir'], width=30)
        out_entry.pack(side=LEFT, fill=X, expand=True, padx=5)
        ttk.Button(ctrl_frame, text='Browse', command=self.browse_output).pack(side=LEFT)
        
        # Download queue
        ttk.Label(self.downloads_frame, text='Download Queue:').pack(anchor=W)
        
        self.queue_tree = ttk.Treeview(self.downloads_frame, columns=('item', 'status', 'progress'),
                                       show='headings', height=8)
        self.queue_tree.heading('item', text='Item')
        self.queue_tree.heading('status', text='Status')
        self.queue_tree.heading('progress', text='Progress')
        self.queue_tree.column('item', width=400)
        self.queue_tree.column('status', width=150)
        self.queue_tree.column('progress', width=200)
        self.queue_tree.pack(fill=BOTH, expand=True)
        
        # Progress bar
        self.dl_progress = ttk.Progressbar(self.downloads_frame, mode='determinate')
        self.dl_progress.pack(fill=X, pady=5)
        
        self.dl_status = ttk.Label(self.downloads_frame, text='Ready')
        self.dl_status.pack(anchor=W)
    
    def create_settings_view(self):
        """Create settings view."""
        canvas = Canvas(self.settings_frame, bg=COLORS['bg'], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.settings_frame, orient=VERTICAL, command=canvas.yview)
        scroll_frame = ttk.Frame(canvas)
        
        scroll_frame.bind('<Configure>', lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.create_window((0, 0), window=scroll_frame, anchor=NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        row = 0
        
        # Download settings section
        ttk.Label(scroll_frame, text='Download Settings', font=('Segoe UI', 12, 'bold'),
                 foreground=COLORS['accent']).grid(row=row, column=0, columnspan=2, sticky=W, pady=(10, 5))
        row += 1
        
        ttk.Label(scroll_frame, text='Default Format:').grid(row=row, column=0, sticky=W, pady=2)
        fmt_frame = ttk.Frame(scroll_frame)
        fmt_frame.grid(row=row, column=1, sticky=W, pady=2)
        for fmt in ['epub', 'cbz', 'pdf']:
            ttk.Radiobutton(fmt_frame, text=fmt.upper(), variable=self.settings['format'],
                           value=fmt).pack(side=LEFT, padx=2)
        row += 1
        
        ttk.Label(scroll_frame, text='Image Quality:').grid(row=row, column=0, sticky=W, pady=2)
        q_scale = ttk.Scale(scroll_frame, from_=10, to=100, variable=self.settings['quality'],
                           orient=HORIZONTAL, length=200)
        q_scale.grid(row=row, column=1, sticky=W, pady=2)
        ttk.Label(scroll_frame, textvariable=self.settings['quality']).grid(row=row, column=2, padx=5)
        row += 1
        
        ttk.Checkbutton(scroll_frame, text='Enable Cropping (disabled by default)',
                       variable=self.settings['crop']).grid(row=row, column=0, columnspan=2, sticky=W, pady=2)
        row += 1
        
        ttk.Label(scroll_frame, text='Output Directory:').grid(row=row, column=0, sticky=W, pady=2)
        out_frame = ttk.Frame(scroll_frame)
        out_frame.grid(row=row, column=1, sticky=EW, pady=2, columnspan=2)
        ttk.Entry(out_frame, textvariable=self.settings['output_dir'], width=40).pack(side=LEFT)
        ttk.Button(out_frame, text='Browse', command=self.browse_output).pack(side=LEFT, padx=5)
        row += 1
        
        ttk.Label(scroll_frame, text='Concurrent Downloads:').grid(row=row, column=0, sticky=W, pady=2)
        ttk.Spinbox(scroll_frame, from_=1, to=10, textvariable=self.settings['concurrent'],
                   width=5).grid(row=row, column=1, sticky=W, pady=2)
        row += 1
        
        ttk.Checkbutton(scroll_frame, text='Split downloads by chapter/volume',
                       variable=self.settings['split']).grid(row=row, column=0, columnspan=2, sticky=W, pady=2)
        row += 1
        
        # Language & Rating
        ttk.Label(scroll_frame, text='Language:').grid(row=row, column=0, sticky=W, pady=2)
        lang_combo = ttk.Combobox(scroll_frame, textvariable=self.settings['lang'],
                                 values=['en', 'jp', 'ko', 'zh', 'fr', 'de', 'es'], width=5)
        lang_combo.grid(row=row, column=1, sticky=W, pady=2)
        row += 1
        
        ttk.Label(scroll_frame, text='Content Rating:').grid(row=row, column=0, sticky=W, pady=2)
        rating_combo = ttk.Combobox(scroll_frame, textvariable=self.settings['rating'],
                                   values=['any', 'safe', 'suggestive', 'erotica', 'pornographic'], width=15)
        rating_combo.grid(row=row, column=1, sticky=W, pady=2)
        row += 1
        
        # Sources
        ttk.Label(scroll_frame, text='', font=('Segoe UI', 12, 'bold'),
                 foreground=COLORS['accent']).grid(row=row, column=0, columnspan=2, sticky=W, pady=(20, 5))
        row += 1
        
        ttk.Label(scroll_frame, text='Active Sources:').grid(row=row, column=0, sticky=W, pady=2)
        src_frame = ttk.Frame(scroll_frame)
        src_frame.grid(row=row, column=1, sticky=W, pady=2)
        for src_name, src_var in self.settings['sources'].items():
            ttk.Checkbutton(src_frame, text=src_name.capitalize(), variable=src_var).pack(side=LEFT, padx=5)
        row += 1
        
        # Metadata section
        ttk.Label(scroll_frame, text='', font=('Segoe UI', 12, 'bold'),
                 foreground=COLORS['accent']).grid(row=row, column=0, columnspan=2, sticky=W, pady=(20, 5))
        row += 1
        
        ttk.Label(scroll_frame, text='EPUB Metadata:').grid(row=row, column=0, sticky=NW, pady=2)
        meta_frame = ttk.Frame(scroll_frame)
        meta_frame.grid(row=row, column=1, sticky=W, pady=2, columnspan=2)
        
        self.meta_title = StringVar()
        self.meta_author = StringVar()
        self.meta_publisher = StringVar()
        
        ttk.Label(meta_frame, text='Title:').grid(row=0, column=0, sticky=W, pady=1)
        ttk.Entry(meta_frame, textvariable=self.meta_title, width=30).grid(row=0, column=1, pady=1)
        ttk.Label(meta_frame, text='Author:').grid(row=1, column=0, sticky=W, pady=1)
        ttk.Entry(meta_frame, textvariable=self.meta_author, width=30).grid(row=1, column=1, pady=1)
        ttk.Label(meta_frame, text='Publisher:').grid(row=2, column=0, sticky=W, pady=1)
        ttk.Entry(meta_frame, textvariable=self.meta_publisher, width=30).grid(row=2, column=1, pady=1)
        
        row += 1
        
        # Naming scheme
        ttk.Label(scroll_frame, text='Naming Scheme:').grid(row=row, column=0, sticky=W, pady=2)
        self.naming_var = StringVar(value='{title}_ch{chapter}')
        ttk.Entry(scroll_frame, textvariable=self.naming_var, width=40).grid(row=row, column=1, sticky=W, pady=2)
        ttk.Label(scroll_frame, text='Variables: {title}, {chapter}, {volume}, {source}',
                 foreground=COLORS['text2']).grid(row=row+1, column=1, sticky=W)
        row += 2
    
    def create_status_bar(self):
        """Create status bar."""
        self.status_bar = ttk.Label(self.root, text='Ready', relief=SUNKEN,
                                   anchor=W, background=COLORS['bg2'],
                                   foreground=COLORS['text2'])
        self.status_bar.pack(side=BOTTOM, fill=X)
    
    # ============================
    # ACTIONS
    # ============================
    
    def perform_search(self):
        """Execute search."""
        query = self.search_var.get().strip()
        if not query:
            return
        
        self.set_status(f'Searching: {query}')
        
        # Clear results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        # Get active sources
        sources = [name for name, var in self.settings['sources'].items() if var.get()]
        if not sources:
            sources = None
        
        def search_thread():
            results = self.downloader.search_all(
                query, limit=20,
                rating=self.settings['rating'].get(),
                sources=sources
            )
            self.current_results = results
            
            self.root.after(0, self.display_results, results)
        
        threading.Thread(target=search_thread, daemon=True).start()
    
    def display_results(self, results):
        """Display search results in treeview."""
        self.results_tree.delete(*self.results_tree.get_children())
        
        for i, r in enumerate(results):
            title = r.get('title', 'Unknown')[:60]
            source = r.get('source', '?').upper()
            info = r.get('year', '') or r.get('rating', '') or ''
            self.results_tree.insert('', END, iid=str(i), values=(title, source, info))
        
        self.set_status(f'Found {len(results)} results')
    
    def on_result_select(self, event):
        """Handle result selection."""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        idx = int(selection[0])
        if idx >= len(self.current_results):
            return
        
        manga = self.current_results[idx]
        self.current_manga = manga
        
        # Update details
        self.details_text.config(state=NORMAL)
        self.details_text.delete(1.0, END)
        
        title = manga.get('title', 'Unknown')
        source = manga.get('source', '?')
        mid = manga.get('id', '')
        desc = manga.get('description', 'No description')
        rating = manga.get('rating', '')
        year = manga.get('year', '')
        status = manga.get('status', '')
        tags = manga.get('tags', [])
        
        info = f"""
Title: {title}
Source: {source.upper()}
ID: {mid[:24]}...
Rating: {rating}
Year: {year}
Status: {status}
Tags: {', '.join(tags[:5])}

Description:
{desc[:500]}
"""
        self.details_text.insert(END, info)
        self.details_text.config(state=DISABLED)
        
        # Load cover
        cover_url = manga.get('cover_url', '')
        if cover_url:
            threading.Thread(target=self.load_cover, args=(cover_url,), daemon=True).start()
    
    def load_cover(self, url):
        """Load cover image from URL."""
        try:
            data = download_image(url)
            if data:
                img = Image.open(io.BytesIO(data))
                # Resize to fit
                img.thumbnail((280, 300), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.root.after(0, self.update_cover, photo)
        except:
            pass
    
    def update_cover(self, photo):
        """Update cover display."""
        self.cover_photo = photo
        self.cover_label.config(image=photo, text='')
    
    def on_result_double_click(self, event):
        """Handle double click to show download dialog."""
        selection = self.results_tree.selection()
        if not selection:
            return
        
        idx = int(selection[0])
        if idx >= len(self.current_results):
            return
        
        self.show_manga_dialog(self.current_results[idx])
    
    def show_manga_dialog(self, manga):
        """Show dialog for downloading manga."""
        dialog = Toplevel(self.root)
        dialog.title(f"Download: {manga.get('title', 'Unknown')[:40]}")
        dialog.geometry("600x500")
        dialog.configure(bg=COLORS['bg'])
        dialog.transient(self.root)
        dialog.grab_set()
        
        title = manga.get('title', 'Unknown')
        mid = manga.get('id', '')
        source = manga.get('source', 'mangadex')
        
        ttk.Label(dialog, text=title, font=('Segoe UI', 14, 'bold'),
                 foreground=COLORS['accent']).pack(pady=(10, 5))
        
        # Fetch chapters
        status_label = ttk.Label(dialog, text='Fetching chapters...')
        status_label.pack()
        
        # Info frame
        info_frame = ttk.Frame(dialog)
        info_frame.pack(fill=X, padx=20, pady=10)
        
        ttk.Label(info_frame, text=f'Source: {source.upper()}').pack(anchor=W)
        ttk.Label(info_frame, text=f'ID: {mid[:32]}...').pack(anchor=W)
        
        # Download options
        opt_frame = ttk.LabelFrame(dialog, text='Download Options', padding=10)
        opt_frame.pack(fill=X, padx=20, pady=10)
        
        ttk.Label(opt_frame, text='Mode:').grid(row=0, column=0, sticky=W)
        mode_var = StringVar(value='all')
        ttk.Radiobutton(opt_frame, text='All Chapters', variable=mode_var, value='all').grid(row=0, column=1, sticky=W)
        ttk.Radiobutton(opt_frame, text='By Volume', variable=mode_var, value='volumes').grid(row=0, column=2, sticky=W)
        ttk.Radiobutton(opt_frame, text='By Chapter', variable=mode_var, value='chapters').grid(row=0, column=3, sticky=W)
        
        ttk.Label(opt_frame, text='Format:').grid(row=1, column=0, sticky=W, pady=(5, 0))
        fmt_var = StringVar(value=self.settings['format'].get())
        fmt_combo = ttk.Combobox(opt_frame, textvariable=fmt_var,
                                values=['epub', 'cbz', 'pdf'], width=8)
        fmt_combo.grid(row=1, column=1, sticky=W, pady=(5, 0))
        
        ttk.Checkbutton(opt_frame, text='Split by chapter', variable=self.settings['split']).grid(
            row=1, column=2, columnspan=2, sticky=W, pady=(5, 0))
        
        # Selection list (populated after fetch)
        list_frame = ttk.LabelFrame(dialog, text='Selection', padding=10)
        list_frame.pack(fill=BOTH, expand=True, padx=20, pady=5)
        
        listbox = Listbox(list_frame, selectmode=MULTIPLE,
                         bg=COLORS['entry_bg'], fg=COLORS['text'],
                         selectbackground=COLORS['accent'],
                         selectforeground=COLORS['bg'],
                         relief=FLAT, borderwidth=0,
                         font=('Consolas', 9))
        scrollbar = ttk.Scrollbar(list_frame, orient=VERTICAL, command=listbox.yview)
        listbox.configure(yscrollcommand=scrollbar.set)
        listbox.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        # Download button
        dl_btn = ttk.Button(dialog, text='Start Download', style='Accent.TButton',
                           command=lambda: self.start_download_from_dialog(
                               mid, source, title, mode_var.get(), fmt_var.get(),
                               listbox, dialog))
        dl_btn.pack(pady=10)
        
        # Fetch chapters in background
        def fetch():
            chapters = self.downloader.get_chapters(mid, source, self.settings['lang'].get())
            self.root.after(0, lambda: populate_list(listbox, chapters, status_label))
        
        def populate_list(lb, chapters, sl):
            sl.config(text=f'{len(chapters)} chapters found')
            if not chapters:
                return
            
            vols = {}
            for c in chapters:
                v = c.get('volume', '?')
                if v not in vols:
                    vols[v] = []
                vols[v].append(c)
            
            for v in sorted(vols.keys()):
                chs = vols[v]
                lb.insert(END, f'── Volume {v} ({len(chs)} chapters) ──')
                for c in chs:
                    ch = c.get('chapter', '?')
                    ctitle = c.get('title', f'Chapter {ch}')
                    lb.insert(END, f'  Ch.{ch} - {ctitle[:50]}')
        
        threading.Thread(target=fetch, daemon=True).start()
    
    def start_download_from_dialog(self, mid, source, title, mode, fmt, listbox, dialog):
        """Start download from the dialog."""
        dialog.destroy()
        
        # Get chapters
        chapters = self.downloader.get_chapters(mid, source, self.settings['lang'].get())
        
        self.settings['format'].set(fmt)
        
        # Download
        threading.Thread(target=self.execute_download, args=(mid, source, title, chapters),
                        daemon=True).start()
    
    def execute_download(self, mid, source, title, chapters):
        """Execute the download."""
        if not chapters:
            return
        
        output_dir = self.settings['output_dir'].get()
        os.makedirs(output_dir, exist_ok=True)
        
        def cb(status, current, total, msg=""):
            if status == "progress":
                self.root.after(0, lambda: self.dl_progress.config(
                    value=(current / total) * 100))
                self.root.after(0, lambda: self.set_status(
                    f'Downloading: {current}/{total} - {msg}'))
            elif status == "error":
                self.root.after(0, lambda: self.set_status(f'Error: {msg}'))
        
        self.root.after(0, lambda: self.set_status(f'Starting download of {len(chapters)} chapters...'))
        
        results = self.downloader.download_manga(
            manga_id=mid,
            source=source,
            mode="all",
            lang=self.settings['lang'].get(),
            output_dir=output_dir,
            fmt=self.settings['format'].get(),
            manga_title=title,
            crop=self.settings['crop'].get(),
            quality=self.settings['quality'].get(),
            split=self.settings['split'].get(),
            max_concurrent=self.settings['concurrent'].get(),
            progress_callback=cb,
        )
        
        # Update queue
        for r in results:
            self.queue_tree.insert('', END, values=(os.path.basename(r), 'Complete', '100%'))
        
        self.root.after(0, lambda: self.dl_progress.config(value=100))
        self.root.after(0, lambda: self.set_status(f'Complete! {len(results)} files saved to {output_dir}'))
        self.root.after(0, lambda: messagebox.showinfo('Download Complete',
                                                        f'{len(results)} files saved to:\n{output_dir}'))
    
    def show_url_dialog(self):
        """Show dialog for URL download."""
        dialog = Toplevel(self.root)
        dialog.title('Download by URL')
        dialog.geometry('500x200')
        dialog.configure(bg=COLORS['bg'])
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text='Enter Manga URL:', font=('Segoe UI', 11)).pack(pady=(20, 5))
        
        url_var = StringVar()
        url_entry = ttk.Entry(dialog, textvariable=url_var, font=('Segoe UI', 11), width=50)
        url_entry.pack(pady=5, ipady=3)
        
        ttk.Label(dialog, text='Supported: MangaDex, AsuraScans, Webtoons, Hitomi',
                 foreground=COLORS['text2']).pack()
        
        ttk.Button(dialog, text='Download', style='Accent.TButton',
                  command=lambda: self.download_url(url_var.get(), dialog)).pack(pady=10)
    
    def download_url(self, url, dialog):
        """Download from URL."""
        if not url:
            return
        
        from cli import parse_url
        source, mid = parse_url(url)
        
        if not source:
            messagebox.showerror('Error', 'Could not parse URL. Supported: MangaDex, AsuraScans, Webtoons, Hitomi')
            return
        
        dialog.destroy()
        
        def fetch_and_dl():
            info = self.downloader.get_manga_info(mid, source)
            title = info.get('title', mid) if info else mid
            chapters = self.downloader.get_chapters(mid, source, self.settings['lang'].get())
            
            self.root.after(0, lambda: self.set_status(f'Downloading: {title}'))
            self.execute_download(mid, source, title, chapters)
        
        threading.Thread(target=fetch_and_dl, daemon=True).start()
    
    def show_bulk_dialog(self):
        """Show bulk download dialog."""
        dialog = Toplevel(self.root)
        dialog.title('Bulk Download')
        dialog.geometry('600x400')
        dialog.configure(bg=COLORS['bg'])
        dialog.transient(self.root)
        dialog.grab_set()
        
        ttk.Label(dialog, text='Paste URLs (one per line) or load from file:',
                 font=('Segoe UI', 11)).pack(pady=(10, 5))
        
        text_frame = ttk.Frame(dialog)
        text_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        
        text_widget = Text(text_frame, bg=COLORS['entry_bg'], fg=COLORS['text'],
                          insertbackground=COLORS['accent'],
                          relief=FLAT, borderwidth=0,
                          font=('Consolas', 10), wrap=WORD)
        scrollbar = ttk.Scrollbar(text_frame, orient=VERTICAL, command=text_widget.yview)
        text_widget.configure(yscrollcommand=scrollbar.set)
        text_widget.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        btn_frame = ttk.Frame(dialog)
        btn_frame.pack(fill=X, padx=10, pady=5)
        
        ttk.Button(btn_frame, text='Load from File',
                  command=lambda: self.load_bulk_file(text_widget)).pack(side=LEFT)
        
        ttk.Label(btn_frame, text='Concurrent:').pack(side=LEFT, padx=(20, 5))
        concurrent_var = IntVar(value=self.settings['concurrent'].get())
        concurrent_spin = ttk.Spinbox(btn_frame, from_=1, to=10, textvariable=concurrent_var, width=5)
        concurrent_spin.pack(side=LEFT)
        
        ttk.Button(btn_frame, text='Start Bulk Download', style='Accent.TButton',
                  command=lambda: self.start_bulk(text_widget, concurrent_var.get(), dialog)).pack(side=RIGHT)
    
    def load_bulk_file(self, text_widget):
        """Load URLs from file into text widget."""
        path = filedialog.askopenfilename(filetypes=[('Text files', '*.txt'), ('All files', '*.*')])
        if path:
            try:
                with open(path, 'r') as f:
                    text_widget.delete(1.0, END)
                    text_widget.insert(END, f.read())
            except Exception as e:
                messagebox.showerror('Error', str(e))
    
    def start_bulk(self, text_widget, concurrent, dialog):
        """Start bulk download."""
        content = text_widget.get(1.0, END).strip()
        if not content:
            return
        
        urls = [line.strip() for line in content.split('\n') if line.strip()]
        dialog.destroy()
        
        def bulk_thread():
            from cli import parse_url
            completed = 0
            
            for url in urls:
                source, mid = parse_url(url)
                if source:
                    try:
                        info = self.downloader.get_manga_info(mid, source)
                        title = info.get('title', mid) if info else mid
                        chapters = self.downloader.get_chapters(mid, source, self.settings['lang'].get())
                        
                        self.root.after(0, lambda: self.set_status(f'Bulk: {title}'))
                        self.execute_download(mid, source, title, chapters)
                        completed += 1
                    except Exception as e:
                        self.root.after(0, lambda u=url: self.set_status(f'Failed: {u[:40]}'))
            
            self.root.after(0, lambda: messagebox.showinfo('Bulk Complete',
                                                            f'Processed {completed}/{len(urls)} URLs'))
        
        threading.Thread(target=bulk_thread, daemon=True).start()
    
    def browse_output(self):
        """Browse for output directory."""
        path = filedialog.askdirectory(initialdir=self.settings['output_dir'].get())
        if path:
            self.settings['output_dir'].set(path)
    
    def open_output(self):
        """Open output directory in file manager."""
        path = self.settings['output_dir'].get()
        if os.path.exists(path):
            import subprocess
            if sys.platform == 'win32':
                os.startfile(path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
    
    def set_status(self, text):
        """Set status bar text."""
        self.status_bar.config(text=text)
    
    def show_about(self):
        """Show about dialog."""
        messagebox.showinfo('About MangaForge',
            'MangaForge v1.0\n'
            'Ultimate Manga Downloader\n\n'
            'Supports:\n'
            '- MangaDex\n'
            '- AsuraScans\n'
            '- Webtoons\n'
            '- Hitomi\n\n'
            'Download as EPUB, CBZ, or PDF\n'
            'No cropping by default')


def main():
    root = Tk()
    app = MangaForgeGUI(root)
    
    # Set dark title bar (Windows 10+)
    try:
        from ctypes import windll, byref, sizeof, c_int
        HWND = windll.user32.GetParent(root.winfo_id())
        windll.dwmapi.DwmSetWindowAttribute(HWND, 20, byref(c_int(2)), sizeof(c_int))
    except:
        pass
    
    root.mainloop()


if __name__ == '__main__':
    main()

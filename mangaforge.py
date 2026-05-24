#!/usr/bin/env python3
"""
MangaForge - Ultimate Manga Downloader Launcher
Choose your interface: CLI, TUI, GUI, or Flask Web.

Usage:
    python mangaforge.py cli      # Command-line interface
    python mangaforge.py tui      # Interactive terminal UI
    python mangaforge.py gui      # Desktop GUI
    python mangaforge.py web      # Flask web server
    python mangaforge.py docs     # Open documentation
"""

import os
import sys
import subprocess


def main():
    if len(sys.argv) < 2:
        print_banner()
        print("\n  Available interfaces:")
        print("    python mangaforge.py cli     - Command Line Interface")
        print("    python mangaforge.py tui     - Interactive Terminal UI")
        print("    python mangaforge.py gui     - Desktop GUI (tkinter)")
        print("    python mangaforge.py web     - Flask Web Server")
        print("    python mangaforge.py docs    - Open documentation")
        print("\n  Examples:")
        print("    python mangaforge.py cli search 'One Piece'")
        print("    python mangaforge.py cli download --id <id> --format epub")
        print("    python mangaforge.py tui")
        print("    python mangaforge.py gui")
        print("    python mangaforge.py web")
        return

    interface = sys.argv[1].lower()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    if interface == 'cli':
        # Pass remaining args to CLI
        cmd = [sys.executable, os.path.join(script_dir, 'cli.py')] + sys.argv[2:]
        os.execvp(cmd[0], cmd)
    
    elif interface == 'tui':
        cmd = [sys.executable, os.path.join(script_dir, 'tui.py')]
        os.execvp(cmd[0], cmd)
    
    elif interface == 'gui':
        cmd = [sys.executable, os.path.join(script_dir, 'gui.py')]
        os.execvp(cmd[0], cmd)
    
    elif interface == 'web':
        cmd = [sys.executable, os.path.join(script_dir, 'flask_app', 'app.py')]
        os.execvp(cmd[0], cmd)
    
    elif interface == 'docs':
        docs_path = os.path.join(script_dir, 'docs.html')
        if sys.platform == 'win32':
            os.startfile(docs_path)
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', docs_path])
        else:
            subprocess.Popen(['xdg-open', docs_path])
    
    else:
        print(f"Unknown interface: {interface}")
        print("Available: cli, tui, gui, web, docs")


def print_banner():
    try:
        import pyfiglet
        from termcolor import cprint
        fig = pyfiglet.Figlet(font='ansi_shadow')
        banner = fig.renderText('MangaForge')
        for i, line in enumerate(banner.split('\n')):
            colors = ['cyan', 'blue', 'magenta', 'yellow', 'green']
            cprint(line, colors[i % len(colors)], attrs=['bold'])
    except ImportError:
        print("=" * 50)
        print("  MANGA FORGE - Ultimate Manga Downloader")
        print("=" * 50)


if __name__ == '__main__':
    main()

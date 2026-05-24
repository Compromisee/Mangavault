#!/usr/bin/env python3
"""MangaForge TUI - Interactive Terminal UI with rich colors, gradient effects, menus."""
import os,sys,time,threading
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from core import MangaDownloader, sanitize_filename, download_image
try:
    import pyfiglet
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
    from rich.text import Text
    from rich.style import Style
    from rich.prompt import Prompt, IntPrompt, Confirm
    from rich.markdown import Markdown
    from rich import box
    RICH=True
except:
    RICH=False; print("Install: pip install rich pyfiglet"); sys.exit(1)

console=Console()
C=Style(color="#7ec8e3",bold=True)
G=Style(color="#a8e6cf",bold=True)
P=Style(color="#f4aeba",bold=True)
PU=Style(color="#c3aed6",bold=True)
Y=Style(color="#ffd3b6",bold=True)

def clear(): console.clear()

def banner():
    clear()
    try:
        fig=pyfiglet.Figlet(font='ansi_shadow',width=100)
        art=fig.renderText('MangaForge')
        cols=["#7ec8e3","#a7c7e7","#c3aed6","#f4aeba","#ffd3b6","#a8e6cf"]
        for i,l in enumerate(art.split('\n')):
            console.print(Text(l,style=Style(color=cols[i%len(cols)],bold=True)))
    except:
        console.print(Text("MANGA FORGE",style=C),justify="center")
    console.print(Text("="*70,style="dim"),justify="center")
    console.print(Text("  TUI v1.0  ",style=Style(color="#888888")),justify="center")
    console.print(Text("="*70,style="dim"),justify="center")
    console.print()

class TUIApp:
    def __init__(self):
        self.dl=MangaDownloader()
        self.settings={"format":"epub","crop":False,"quality":85,"output_dir":"downloads",
                       "lang":"en","rating":"any","concurrent":3,"split":True}
        self.current=None
    
    def run(self):
        while True: self.main_menu()
    
    def main_menu(self):
        banner()
        for k,v in [("1","Search Manga",C),("2","Download by URL",G),("3","Bulk Download",P),
                      ("4","Settings",Y),("5","Help",PU),("0","Exit",Style(color="#ff6b6b"))]:
            console.print(f"  [bold {v[1] if isinstance(v,tuple) else 'white'}]{k}[/]  {v[0] if isinstance(v,tuple) else v}")
        console.print()
        ch=Prompt.ask("  Option",choices=["0","1","2","3","4","5"],default="1")
        {"1":self.search,"2":self.url_dl,"3":self.bulk,"4":self.settings_menu,"5":self.help,"0":self.exit}.get(ch,lambda:None)()
    
    def search(self):
        banner()
        console.print(Panel("[bold #7ec8e3]Search[/]",box=box.ROUNDED))
        q=Prompt.ask("  Query")
        if not q: return
        console.print("  Sources: [cyan]1[/] mangadex [green]2[/] asurascans [pink]3[/] webtoons [purple]4[/] hitomi")
        sc=Prompt.ask("  Sources",default="all")
        srcs=["mangadex","asurascans","webtoons","hitomi"] if sc=="all" else [{"1":"mangadex","2":"asurascans","3":"webtoons","4":"hitomi"}.get(s.strip(),s.strip()) for s in sc.split(",")]
        lang=Prompt.ask("  Lang",default=self.settings["lang"])
        with console.status("[#7ec8e3]Searching..."):
            results=self.dl.search_all(q,limit=15,rating=self.settings["rating"],sources=srcs)
        if not results: console.print("[red]None[/]");time.sleep(1);return
        t=Table(box=box.ROUNDED,border_style="dim",header_style="bold #7ec8e3")
        t.add_column("#",width=3); t.add_column("Source",width=12); t.add_column("Title",width=50)
        for i,r in enumerate(results[:20],1): t.add_row(str(i),f"[bold]{r.get('source','?').upper()}[/]",r.get('title','Unknown')[:50])
        console.print(t)
        ch=Prompt.ask("  Select number",default="1")
        if ch.lower()=='q': return
        try:
            idx=int(ch)-1
            if 0<=idx<len(results): self.current=results[idx]; self.manga_actions()
        except: pass
    
    def manga_actions(self):
        if not self.current: return
        m=self.current
        banner()
        console.print(Panel(f"[bold #7ec8e3]{m.get('title','?')}[/]\n[dim]Source:[/] [#f4aeba]{m.get('source','?').upper()}[/]",box=box.ROUNDED))
        with console.status("Fetching..."):
            chs=self.dl.get_chapters(m['id'],m['source'],self.settings["lang"])
            vols={}
            for c in chs: v=c.get('volume','?'); vols.setdefault(v,[]).append(c)
        console.print(f"\n[bold #a8e6cf]{len(chs)} chapters[/]  [bold #ffd3b6]{len(vols)} volumes[/]")
        console.print("\n[cyan]1[/] All  [green]2[/] Volumes  [pink]3[/] Chapters  [yellow]4[/] List  [dim]0[/] Back")
        ch=Prompt.ask("",choices=["0","1","2","3","4"],default="1")
        if ch=="1": self.do_download(m['id'],m['source'],m.get('title','Manga'),chs)
        elif ch=="2":
            for v in sorted(vols):
                console.print(f"  Vol {v} ({len(vols[v])} ch)")
            vc=Prompt.ask("Volumes (comma, or 'all')",default="all")
            sel=[c for c in chs if vc=='all' or c.get('volume','') in [x.strip() for x in vc.split(",")]]
            if sel: self.do_download(m['id'],m['source'],m.get('title','Manga'),sel)
        elif ch=="3":
            cc=Prompt.ask("Chapters (e.g. 1,2,3 or 1-5)",default="all")
            if cc=='all': sel=chs
            else:
                sel=[]
                for p in cc.split(","):
                    p=p.strip()
                    if '-' in p:
                        try: s,e=map(int,p.split('-')); sel.extend(c for c in chs if c.get('chapter','').isdigit() and s<=int(c['chapter'])<=e)
                        except: pass
                    else: sel.extend(c for c in chs if c.get('chapter')==p)
            if sel: self.do_download(m['id'],m['source'],m.get('title','Manga'),sel)
        elif ch=="4":
            for c in chs: console.print(f"  V{c.get('volume','?')} Ch.{c.get('chapter','?'):<6} {c.get('title','')[:50]}")
            Prompt.ask("\n  Enter")
    
    def do_download(self,mid,source,title,chapters):
        if not chapters: return
        fmt=self.settings["format"]; crop=self.settings["crop"]; q=self.settings["quality"]
        od=self.settings["output_dir"]; spl=self.settings["split"]; conc=self.settings["concurrent"]
        console.print(f"\n[bold #a8e6cf]Downloading {len(chapters)} chapters[/]")
        console.print(f"  {fmt.upper()} | Crop:{crop} | Quality:{q}")
        with Progress(TextColumn("[progress.description]{task.description}"),
                      BarColumn(complete_style="#7ec8e3",finished_style="#a8e6cf"),
                      TextColumn("{task.percentage:>3.0f}%"),TimeElapsedColumn(),console=console) as pr:
            task=pr.add_task(f"[#7ec8e3]Downloading...",total=len(chapters))
            def cb(s,cur,tot,msg=""):
                if s=="progress": pr.update(task,completed=cur)
                elif s=="error": console.print(f"  [red]{msg}[/]")
                elif s=="done": pr.update(task,completed=tot)
            res=self.dl.download_manga(manga_id=mid,source=source,lang=self.settings["lang"],
                output_dir=od,fmt=fmt,manga_title=title,crop=crop,quality=q,split=spl,
                max_concurrent=conc,progress_callback=cb)
        console.print(f"\n[bold green]Complete! {len(res)} files[/]")
        for r in res: console.print(f"  [dim]{r}[/]")
        Prompt.ask("\n  Enter to continue")
    
    def url_dl(self):
        banner()
        console.print(Panel("[bold #a8e6cf]URL Download[/]",box=box.ROUNDED))
        url=Prompt.ask("  URL")
        from cli import parse_url
        src,mid=parse_url(url)
        if not src: console.print("[red]Cannot parse URL[/]"); time.sleep(2); return
        with console.status("Fetching..."):
            info=self.dl.get_manga_info(mid,src)
            title=info.get('title',mid) if info else mid
            chs=self.dl.get_chapters(mid,src,self.settings["lang"])
        console.print(f"[bold #7ec8e3]{title}[/] - {len(chs) if chs else 1} chapters")
        self.current={"id":mid,"title":title,"source":src}
        if chs: self.do_download(mid,src,title,chs)
        else: console.print("[yellow]No chapters[/]"); time.sleep(1)
    
    def bulk(self):
        banner()
        console.print(Panel("[bold #f4aeba]Bulk Download[/]",box=box.ROUNDED))
        ch=Prompt.ask("  [1] Paste URLs  [2] File",choices=["1","2"],default="1")
        urls=[]
        if ch=="1":
            console.print("[yellow]Paste URLs (empty line to finish):[/]")
            while True:
                l=Prompt.ask(""); 
                if not l: break
                urls.append(l.strip())
        else:
            p=Prompt.ask("  File path")
            try:
                with open(p) as f: urls=[l.strip() for l in f if l.strip()]
            except: console.print("[red]File not found[/]"); time.sleep(1); return
        if not urls: return
        from cli import parse_url
        with Progress(TextColumn("[progress.description]{task.description}"),
                      BarColumn(complete_style="#f4aeba"),console=console) as pr:
            task=pr.add_task(f"[#f4aeba]Processing {len(urls)}...",total=len(urls))
            for url in urls:
                src,mid=parse_url(url)
                if src:
                    try:
                        info=self.dl.get_manga_info(mid,src)
                        title=info.get('title',mid) if info else mid
                        self.dl.download_manga(manga_id=mid,source=src,output_dir=self.settings["output_dir"],
                            fmt=self.settings["format"],manga_title=title)
                    except: pass
                pr.update(task,advance=1)
        console.print(f"[green]Bulk complete![/]")
        Prompt.ask("\n  Enter")
    
    def settings_menu(self):
        while True:
            banner()
            console.print(Panel("[bold #ffd3b6]Settings[/]",box=box.ROUNDED))
            s=self.settings
            console.print(f"\n  [cyan]1[/] Format: [bold]{s['format'].upper()}[/]")
            console.print(f"  [green]2[/] Quality: [bold]{s['quality']}[/]")
            console.print(f"  [pink]3[/] Crop: [bold]{'ON' if s['crop'] else 'OFF'}[/]")
            console.print(f"  [yellow]4[/] Output: [bold]{s['output_dir']}[/]")
            console.print(f"  [purple]5[/] Lang: [bold]{s['lang']}[/]")
            console.print(f"  [cyan]6[/] Rating: [bold]{s['rating']}[/]")
            console.print(f"  [green]7[/] Concurrent: [bold]{s['concurrent']}[/]")
            console.print(f"  [pink]8[/] Split: [bold]{'YES' if s['split'] else 'NO'}[/]")
            console.print(f"  [dim]0[/] Back")
            ch=Prompt.ask("",choices=["0","1","2","3","4","5","6","7","8"],default="0")
            if ch=="1": s['format']=Prompt.ask("",choices=["epub","cbz","pdf"],default=s['format'])
            elif ch=="2": s['quality']=IntPrompt.ask("",default=s['quality'])
            elif ch=="3": s['crop']=Confirm.ask("",default=s['crop'])
            elif ch=="4": s['output_dir']=Prompt.ask("",default=s['output_dir'])
            elif ch=="5": s['lang']=Prompt.ask("",default=s['lang'])
            elif ch=="6": s['rating']=Prompt.ask("",choices=["any","safe","suggestive","erotica","pornographic"],default=s['rating'])
            elif ch=="7": s['concurrent']=IntPrompt.ask("",default=s['concurrent'])
            elif ch=="8": s['split']=Confirm.ask("",default=s['split'])
            elif ch=="0": break
    
    def help(self):
        banner()
        console.print(Markdown("""# MangaForge TUI
- Search manga across Mangadex, AsuraScans, Webtoons, Hitomi
- Download as EPUB, CBZ, or PDF
- No cropping by default
- Bulk download from URLs
- Settings: format, quality, lang, rating, concurrent, split"""))
        Prompt.ask("\n  Enter")
    
    def exit(self):
        console.print("\n[bold #7ec8e3]Goodbye![/]")
        sys.exit(0)

if __name__=='__main__':
    try: TUIApp().run()
    except KeyboardInterrupt: console.print("\n[red]Exiting...[/]"); sys.exit(0)
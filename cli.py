#!/usr/bin/env python3
"""MangaForge CLI - pyfiglet headers, gradient colors, progress bars."""
import os,sys,json,argparse,time
sys.path.insert(0,os.path.dirname(os.path.abspath(__file__)))
from core import MangaDownloader, sanitize_filename
try:
    import pyfiglet
    from termcolor import colored, cprint
    PFIG=True
except:
    PFIG=False

def print_header():
    os.system('cls' if os.name=='nt' else 'clear')
    if PFIG:
        try:
            fig=pyfiglet.Figlet(font='ansi_shadow')
            art=fig.renderText('MangaForge')
            colors=['cyan','blue','magenta','yellow','green']
            for i,l in enumerate(art.split('\n')):
                cprint(l,colors[i%len(colors)],attrs=['bold'])
        except:
            cprint("MANGA FORGE",'cyan',attrs=['bold'])
    else:
        print("="*50+"\n  MANGA FORGE - Ultimate Manga Downloader\n"+"="*50)
    cprint("="*60,'dark_grey')
    cprint("  CLI v1.0 | python cli.py <command> --help",'white',attrs=['bold'])
    cprint("="*60+'\n','dark_grey')

def c(text,color='cyan'): cprint(f"  > {text}",color,attrs=['bold'])
def i(text): cprint(f"    {text}",'white')
def s(text): cprint(f"  [+] {text}",'green',attrs=['bold'])
def e(text): cprint(f"  [!] {text}",'red',attrs=['bold'])
def w(text): cprint(f"  [?] {text}",'yellow',attrs=['bold'])

class ProgressCB:
    def __call__(self,status,cur,total,msg=""):
        if status=='start': c(f"Starting {total} items...",'yellow')
        elif status=='progress': 
            pct=int((cur/total)*100) if total else 0
            bar='#'*(pct//2)+'.'*(50-pct//2)
            cprint(f"  [{bar}] {pct}%",'green')
        elif status=='error': e(msg)
        elif status=='done': s(f"Complete! {cur} files.")

def parse_url(url, hint=None):
    url=url.lower()
    import re
    if 'mangadex.org' in url or hint=='mangadex':
        m=re.search(r'/(?:title|manga)/([a-f0-9\-]{36})',url)
        if m: return ('mangadex',m.group(1))
    if 'asuracomic.net' in url or hint=='asurascans':
        m=re.search(r'/manga/([\w\-]+)',url)
        if m: return ('asurascans',m.group(1))
    if 'webtoons.com' in url or hint=='webtoons':
        m=re.search(r'/episode/(\d+)',url)
        if m: return ('webtoons',m.group(1))
        m=re.search(r'title_no=(\d+)',url)
        if m: return ('webtoons',m.group(1))
    if 'hitomi.la' in url or hint=='hitomi':
        m=re.search(r'/reader/(\d+)',url)
        if m: return ('hitomi',m.group(1))
    return (None,None)

def cmd_search(args):
    print_header()
    c(f"Searching: '{args.query}'")
    dl=MangaDownloader()
    results=dl.search_all(args.query,limit=args.limit,rating=args.rating,
                         sources=[s.strip() for s in args.sources.split(',')] if args.sources else None)
    if not results: e("No results."); return
    s(f"Found {len(results)}:\n")
    for i,r in enumerate(results,1):
        src=r.get('source','?').upper()
        title=r.get('title','Unknown')[:70]
        tags=', '.join(r.get('tags',[])[:3])
        cprint(f"  [{i:3d}] [{src:<12}] {title}",'white',attrs=['bold'])
        if tags: cprint(f"         Tags: {tags}",'dark_grey')

def cmd_info(args):
    dl=MangaDownloader()
    if args.url:
        src,mid=parse_url(args.url)
        if not src: e("Could not parse URL."); return
        args.source=src; args.id=mid
    if not args.id: e("Manga ID required."); return
    print_header()
    c(f"Fetching info for {args.id[:16]}... from {args.source}")
    info=dl.get_manga_info(args.id,args.source)
    if not info: e("Not found."); return
    cprint(f"\n{'='*60}",'dark_grey')
    cprint(f"  {info.get('title','Unknown')}",'cyan',attrs=['bold'])
    cprint(f"{'='*60}",'dark_grey')
    cprint(f"  Source: {args.source.upper()}  ID: {args.id[:24]}...",'white')
    if info.get('author'): cprint(f"  Author: {info['author']}",'white')
    if info.get('year'): cprint(f"  Year: {info['year']}  Status: {info.get('status','')}",'white')
    if info.get('rating'): cprint(f"  Rating: {info['rating']}",'white')
    if info.get('tags'): cprint(f"  Tags: {', '.join(info['tags'][:8])}",'white')
    if info.get('description'):
        cprint(f"\n  Description:",'yellow',attrs=['bold'])
        cprint(f"    {info['description'][:500]}",'white')
    chs=dl.get_chapters(args.id,args.source,args.lang)
    if chs:
        vol_count={}
        for c in chs:
            v=c.get('volume','?')
            vol_count[v]=vol_count.get(v,0)+1
        cprint(f"\n  Chapters: {len(chs)}  Volumes: {len(vol_count)}",'green',attrs=['bold'])
        cprint(f"  Volumes: {', '.join(f'Vol {v} ({n})' for v,n in sorted(vol_count.items()))}",'white')
        if args.list:
            cprint("\n  Chapter List:",'cyan')
            for c in chs:
                cprint(f"    V{c.get('volume','?')} Ch.{c.get('chapter','?'):<6} {c.get('title','')[:50]}",'white')

def cmd_download(args):
    dl=MangaDownloader()
    if args.url:
        src,mid=parse_url(args.url)
        if not src: e("Could not parse URL."); return
        args.source=src; args.id=mid
    if not args.id: e("Manga ID required."); return
    print_header()
    cprint('='*60,'dark_grey')
    c(f"Fetching {args.source}...")
    info=dl.get_manga_info(args.id,args.source)
    title=info.get('title',args.id) if info else args.id
    cprint(f"  Title: {title}",'cyan',attrs=['bold'])
    cprint(f"  Format: {args.format.upper()}  Quality: {args.quality}  Crop: {args.crop}",'white')
    cprint(f"  Output: {args.output_dir}/  Split: {args.split}  Concurrent: {args.concurrent}",'white')
    cprint('='*60+'\n','dark_grey')
    chs=dl.get_chapters(args.id,args.source,args.lang)
    if not chs: e("No chapters."); return
    c(f"Found {len(chs)} chapters",'green')
    if args.chapters:
        cl=[x.strip() for x in args.chapters.split(',')]
        selected=[c for c in chs if c.get('chapter') in cl or c['id'][:8] in cl]
    elif args.volumes:
        vl=[x.strip() for x in args.volumes.split(',')]
        selected=[c for c in chs if c.get('volume','') in vl]
    else:
        selected=chs
    if not selected: e("No matches."); return
    c(f"Downloading {len(selected)} chapters...")
    results=dl.download_manga(manga_id=args.id,source=args.source,
        lang=args.lang,output_dir=args.output_dir,fmt=args.format,
        manga_title=title,crop=args.crop,quality=args.quality,
        split=args.split,max_concurrent=args.concurrent,
        progress_callback=ProgressCB())
    s(f"\nDownloaded {len(results)} file(s) to {args.output_dir}/")
    for r in results: cprint(f"    {r}",'green')

def cmd_bulk(args):
    dl=MangaDownloader()
    print_header()
    c("Bulk Download Mode",'yellow')
    urls=[]
    if args.file:
        with open(args.file) as f: urls=[l.strip() for l in f if l.strip()]
    elif args.urls:
        urls=[u.strip() for u in args.urls.split(',')]
    else: e("Provide --file or --urls"); return
    c(f"Processing {len(urls)} URLs...")
    for i,url in enumerate(urls):
        src,mid=parse_url(url)
        if not src: w(f"Skipping {i+1}: {url[:40]}..."); continue
        c(f"[{i+1}/{len(urls)}] {src}: {mid[:16]}...")
        try:
            info=dl.get_manga_info(mid,src)
            title=info.get('title',mid) if info else mid
            dl.download_manga(manga_id=mid,source=src,output_dir=args.output_dir,
                fmt=args.format,manga_title=title,lang=args.lang,
                split=True,max_concurrent=2)
        except Exception as ex: e(str(ex))
    s(f"Bulk complete!")

def main():
    p=argparse.ArgumentParser(description='MangaForge CLI',formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  search "One Piece" --sources mangadex,asurascans
  info --id <id> --source mangadex --list
  download --id <id> --format epub --split
  download --url "https://mangadex.org/title/uuid" --format cbz
  bulk --file urls.txt --concurrent 3""")
    p.add_argument('--format',choices=['epub','cbz','pdf'],default='epub')
    p.add_argument('-o','--output-dir',default='downloads')
    p.add_argument('--lang',default='en')
    p.add_argument('--rating',choices=['safe','suggestive','erotica','pornographic','any'],default='any')
    p.add_argument('--crop',action='store_true')
    p.add_argument('--quality',type=int,default=85)
    p.add_argument('--concurrent',type=int,default=3)
    p.add_argument('--sources',default='')
    p.add_argument('--limit',type=int,default=20)
    sp=p.add_subparsers(dest='command')
    ps=sp.add_parser('search',help='Search manga')
    ps.add_argument('query'); ps.set_defaults(func=cmd_search)
    pi=sp.add_parser('info',help='Manga info')
    pi.add_argument('--id'); pi.add_argument('--url'); pi.add_argument('--source',default='mangadex')
    pi.add_argument('--list',action='store_true'); pi.set_defaults(func=cmd_info)
    pd=sp.add_parser('download',help='Download manga')
    pd.add_argument('--id'); pd.add_argument('--url'); pd.add_argument('--source',default='mangadex')
    pd.add_argument('--chapters'); pd.add_argument('--volumes')
    pd.add_argument('--split',action='store_true',default=True)
    pd.add_argument('--no-split',action='store_false',dest='split')
    pd.set_defaults(func=cmd_download)
    pb=sp.add_parser('bulk',help='Bulk download')
    pb.add_argument('--file'); pb.add_argument('--urls')
    pb.set_defaults(func=cmd_bulk)
    args=p.parse_args()
    if hasattr(args,'func'): args.func(args)
    else: print_header(); p.print_help()

if __name__=='__main__':
    main()
# Core Manga Downloader Library
import requests, os, json, re, zipfile, shutil, io, hashlib, time
from pathlib import Path
from urllib.parse import urlparse, quote
from concurrent.futures import ThreadPoolExecutor, as_completed
from PIL import Image

def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name).strip().replace(' ', '_')[:200]

def ensure_dir(path):
    Path(path).mkdir(parents=True, exist_ok=True)
    return path

def download_image(url, timeout=30):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.content
    except:
        return None

def create_cbz(images_data, output_path, progress_callback=None):
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i, img_data in enumerate(images_data):
            if img_data:
                zf.writestr(f"{i:04d}.jpg", img_data)
            if progress_callback:
                progress_callback(i+1, len(images_data))

def create_epub_from_images(images_data, output_path, title="Manga", author="Unknown",
                            cover_data=None, progress_callback=None):
    total = len(images_data)
    mimetype_content = b'application/epub+zip'
    container_xml = '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>'''
    
    opf = f'''<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
    <dc:identifier id="bookid">urn:uuid:{hashlib.md5(title.encode()).hexdigest()}</dc:identifier>
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:language>en</dc:language>
    <meta name="cover" content="cover-image"/>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
'''
    if cover_data:
        opf += '    <item id="cover-image" href="cover.jpg" media-type="image/jpeg"/>\n'
    
    spine_items = ''
    for i in range(total):
        item_id = f"img_{i:04d}"
        opf += f'    <item id="{item_id}" href="images/{i:04d}.jpg" media-type="image/jpeg"/>\n'
        spine_items += f'    <itemref idref="{item_id}"/>\n'
    
    opf += '  </manifest>\n  <spine toc="ncx">\n'
    if cover_data:
        opf += '    <itemref idref="cover"/>\n'
    opf += spine_items
    opf += '  </spine>\n</package>'
    
    ncx = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN" "http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="urn:uuid:{hashlib.md5(title.encode()).hexdigest()}"/><meta name="dtb:depth" content="1"/></head>
  <docTitle><text>{title}</text></docTitle>
  <navMap>
    <navPoint id="chap1" playOrder="1">
      <navLabel><text>Chapter 1</text></navLabel>
      <content src="content.xhtml"/>
    </navPoint>
  </navMap>
</ncx>'''
    
    content_parts = ['<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml">\n<head><title>Content</title></head>\n<body>']
    for i in range(total):
        content_parts.append(f'<div style="page-break-after:always;"><img src="images/{i:04d}.jpg" alt="Page {i+1}" style="width:100%;"/></div>')
    content_parts.append('</body>\n</html>')
    content_xhtml = '\n'.join(content_parts)
    
    cover_xhtml = '''<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE html>\n<html xmlns="http://www.w3.org/1999/xhtml">\n<head><title>Cover</title></head>\n<body><div style="text-align:center;"><img src="cover.jpg" alt="Cover" style="height:100%;"/></div></body>\n</html>'''
    
    with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('mimetype', mimetype_content, compress_type=zipfile.ZIP_STORED)
        zf.writestr('META-INF/container.xml', container_xml)
        zf.writestr('OEBPS/content.opf', opf)
        zf.writestr('OEBPS/toc.ncx', ncx)
        zf.writestr('OEBPS/content.xhtml', content_xhtml)
        if cover_data:
            zf.writestr('OEBPS/cover.jpg', cover_data)
            zf.writestr('OEBPS/cover.xhtml', cover_xhtml)
        for i, img_data in enumerate(images_data):
            if img_data:
                zf.writestr(f'OEBPS/images/{i:04d}.jpg', img_data)
            if progress_callback:
                progress_callback(i+1, total)
    return output_path


class MangaSource:
    name = "base"
    def search(self, query, limit=20): raise NotImplementedError
    def get_manga_info(self, manga_id): raise NotImplementedError
    def get_chapters(self, manga_id, lang=None): raise NotImplementedError
    def get_chapter_pages(self, chapter_id): raise NotImplementedError
    def get_manga_cover(self, manga_id): raise NotImplementedError


class MangaDex(MangaSource):
    name = "mangadex"
    base_url = "https://api.mangadex.org"
    
    def search(self, query, limit=20, rating=None):
        url = f"{self.base_url}/manga"
        ratings = ["safe","suggestive","erotica","pornographic"] if (rating == "any" or not rating) else [rating]
        params = {"title": query, "limit": min(limit, 100), "includes[]": ["cover_art"],
                  "contentRating[]": ratings}
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json()
            results = []
            for item in data.get("data", []):
                attrs = item.get("attributes", {})
                title_data = attrs.get("title", {})
                title = title_data.get("en") or (list(title_data.values())[0] if title_data else "Unknown")
                desc = attrs.get("description", {})
                description = desc.get("en") or (list(desc.values())[0] if desc else "")
                cover_url = ""
                for rel in item.get("relationships", []):
                    if rel.get("type") == "cover_art":
                        fn = rel.get("attributes", {}).get("fileName", "")
                        if fn:
                            cover_url = f"https://uploads.mangadex.org/covers/{item['id']}/{fn}"
                results.append({"id": item["id"], "title": title, "description": description[:500],
                                "cover_url": cover_url, "source": "mangadex", "year": attrs.get("year",""),
                                "status": attrs.get("status",""),
                                "tags": [t.get("attributes",{}).get("name",{}).get("en","") for t in attrs.get("tags",[])],
                                "rating": attrs.get("contentRating","")})
            return results
        except:
            return []
    
    def get_manga_info(self, manga_id):
        url = f"{self.base_url}/manga/{manga_id}"
        params = {"includes[]": ["cover_art","author","artist"]}
        try:
            r = requests.get(url, params=params, timeout=30)
            r.raise_for_status()
            data = r.json().get("data", {})
            attrs = data.get("attributes", {})
            td = attrs.get("title", {})
            title = td.get("en") or (list(td.values())[0] if td else "Unknown")
            dd = attrs.get("description", {})
            desc = dd.get("en") or (list(dd.values())[0] if dd else "")
            cover_url = ""; author = "Unknown"
            for rel in data.get("relationships", []):
                if rel.get("type") == "cover_art":
                    fn = rel.get("attributes",{}).get("fileName","")
                    if fn: cover_url = f"https://uploads.mangadex.org/covers/{manga_id}/{fn}"
                if rel.get("type") == "author":
                    author = rel.get("attributes",{}).get("name","Unknown")
            return {"id":manga_id,"title":title,"description":desc,"cover_url":cover_url,
                    "author":author,"source":"mangadex","year":attrs.get("year",""),
                    "status":attrs.get("status",""),
                    "tags":[t.get("attributes",{}).get("name",{}).get("en","") for t in attrs.get("tags",[])],
                    "rating":attrs.get("contentRating","")}
        except:
            return None
    
    def get_chapters(self, manga_id, lang="en"):
        chapters = []
        offset = 0
        limit = 500
        while True:
            url = f"{self.base_url}/manga/{manga_id}/feed"
            params = {"translatedLanguage[]": [lang], "order[chapter]": "asc",
                      "limit": limit, "offset": offset, "includes[]": ["scanlation_group"]}
            try:
                r = requests.get(url, params=params, timeout=30)
                r.raise_for_status()
                data = r.json()
                items = data.get("data", [])
                if not items: break
                for item in items:
                    attrs = item.get("attributes", {})
                    group = "Unknown"
                    for rel in item.get("relationships", []):
                        if rel.get("type") == "scanlation_group":
                            group = rel.get("attributes",{}).get("name","Unknown")
                    chapters.append({"id":item["id"],"chapter":attrs.get("chapter",""),
                                     "volume":attrs.get("volume",""),"title":attrs.get("title",""),
                                     "group":group,"pages":attrs.get("pages",0),
                                     "publish_date":attrs.get("publishAt","")})
                total = data.get("total",0)
                offset += limit
                if offset >= total: break
            except:
                break
        return chapters
    
    def get_chapter_pages(self, chapter_id):
        url = f"{self.base_url}/at-home/server/{chapter_id}"
        try:
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            data = r.json()
            base = data.get("baseUrl","")
            ch = data.get("chapter",{})
            h = ch.get("hash","")
            pages = ch.get("data",[])
            return [f"{base}/data/{h}/{p}" for p in pages]
        except:
            return []
    
    def get_manga_cover(self, manga_id):
        info = self.get_manga_info(manga_id)
        if info and info.get("cover_url"):
            return download_image(info["cover_url"])
        return None
    
    def get_volumes(self, manga_id, lang="en"):
        chapters = self.get_chapters(manga_id, lang)
        volumes = {}
        for c in chapters:
            v = c.get("volume","") or "0"
            if v not in volumes: volumes[v] = []
            volumes[v].append(c)
        return volumes


class AsuraScans(MangaSource):
    name = "asurascans"
    def search(self, query, limit=20, rating=None):
        url = f"https://asuracomic.net/api/search?q={quote(query)}"
        try:
            r = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=30)
            r.raise_for_status()
            data = r.json()
            return [{"id":item.get("id",""),"title":item.get("title","Unknown"),
                     "description":item.get("description",""),
                     "cover_url":item.get("thumbnail",""),"source":"asurascans",
                     "rating":item.get("rating","")} for item in (data[:limit] if isinstance(data,list) else [])]
        except:
            return []
    
    def get_manga_info(self, manga_id):
        url = f"https://asuracomic.net/api/manga/{manga_id}"
        try:
            r = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=30)
            r.raise_for_status()
            d = r.json()
            return {"id":manga_id,"title":d.get("title","Unknown"),"description":d.get("description",""),
                    "cover_url":d.get("thumbnail",""),"author":d.get("author","Unknown"),"source":"asurascans"}
        except:
            return None
    
    def get_chapters(self, manga_id, lang=None):
        url = f"https://asuracomic.net/api/manga/{manga_id}/chapters"
        try:
            r = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=30)
            r.raise_for_status()
            data = r.json()
            return [{"id":item.get("id",""),"chapter":item.get("chapter",""),
                     "title":item.get("title",f"Chapter {item.get('chapter','')}"),
                     "pages":item.get("pageCount",0)} for item in (data if isinstance(data,list) else [])]
        except:
            return []
    
    def get_chapter_pages(self, chapter_id):
        url = f"https://asuracomic.net/api/chapter/{chapter_id}"
        try:
            r = requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=30)
            r.raise_for_status()
            pages = r.json().get("pages",[])
            return [p.get("url","") for p in pages if isinstance(p,dict)]
        except:
            return []
    
    def get_manga_cover(self, manga_id):
        info = self.get_manga_info(manga_id)
        if info and info.get("cover_url"):
            return download_image(info["cover_url"])
        return None


class Webtoons(MangaSource):
    name = "webtoons"
    def search(self, query, limit=20, rating=None):
        url = "https://www.webtoons.com/en/search"
        params = {"keyword": query}
        try:
            r = requests.get(url, params=params, headers={'User-Agent':'Mozilla/5.0'}, timeout=30)
            r.raise_for_status()
            from html.parser import HTMLParser
            class P(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.current = {}; self.results = []; self.in_title=False; self.in_author=False; self.in_card=False; self.link=""
                def handle_starttag(self,tag,attrs):
                    d=dict(attrs)
                    if tag=='li' and 'card_item' in d.get('class',''): self.in_card=True; self.current={}
                    if self.in_card:
                        if tag=='a' and 'href' in d: self.current['url']=d['href']
                        if tag=='img' and 'src' in d: self.current['cover_url']=d['src']
                        if tag=='p' and 'subj' in d.get('class',''): self.in_title=True
                        if tag=='p' and 'author' in d.get('class',''): self.in_author=True
                def handle_endtag(self,tag):
                    if tag=='li' and self.current: self.results.append(self.current); self.in_card=False
                    if tag=='p': self.in_title=False; self.in_author=False
                def handle_data(self,data):
                    if self.in_title: self.current['title']=data.strip()
                    if self.in_author: self.current['author']=data.strip()
            parser=P()
            parser.feed(r.text)
            results=[]
            for item in parser.results[:limit]:
                url_parts=item.get('url','').split('?')[0].strip('/').split('/')
                wid=url_parts[-1] if url_parts else ""
                results.append({"id":wid,"title":item.get('title','Unknown'),"description":"",
                                "cover_url":item.get('cover_url',''),"source":"webtoons",
                                "url":item.get('url',''),"author":item.get('author','Unknown')})
            return results
        except:
            return []
    
    def get_manga_info(self, manga_id):
        return {"id":manga_id,"title":manga_id,"source":"webtoons"}
    def get_chapters(self, manga_id, lang=None): return []
    def get_chapter_pages(self, chapter_id): return []
    def get_manga_cover(self, manga_id): return None


class Hitomi(MangaSource):
    name = "hitomi"
    def search(self, query, limit=20, rating=None):
        results=[]
        try:
            url=f"https://hitomi.la/search.html?{quote(query)}"
            r=requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=30)
            r.raise_for_status()
            galleries=list(set(re.findall(r'/reader/(\d+)\.html',r.text)))[:limit]
            for gid in galleries:
                try:
                    gr=requests.get(f"https://hitomi.la/reader/{gid}.html",
                                    headers={'User-Agent':'Mozilla/5.0'}, timeout=15)
                    gr.raise_for_status()
                    tm=re.search(r'<title>(.*?)</title>',gr.text)
                    title=tm.group(1).replace(' | Hitomi.la','') if tm else f"Gallery {gid}"
                    cm=re.search(r'<meta property="og:image" content="(.*?)"',gr.text)
                    cv=cm.group(1) if cm else ""
                    results.append({"id":gid,"title":title.strip(),"description":"","cover_url":cv,"source":"hitomi","url":f"https://hitomi.la/reader/{gid}.html"})
                except: continue
        except: pass
        return results
    
    def get_manga_info(self, manga_id):
        url=f"https://hitomi.la/reader/{manga_id}.html"
        try:
            r=requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=15)
            r.raise_for_status()
            tm=re.search(r'<title>(.*?)</title>',r.text)
            title=tm.group(1).replace(' | Hitomi.la','') if tm else f"Gallery {manga_id}"
            return {"id":manga_id,"title":title.strip(),"description":"","source":"hitomi","url":url}
        except: return None
    
    def get_chapters(self, manga_id, lang=None):
        return [{"id":manga_id,"chapter":"1","title":"Full","pages":0}]
    
    def get_chapter_pages(self, chapter_id):
        url=f"https://hitomi.la/reader/{chapter_id}.html"
        try:
            r=requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=15)
            r.raise_for_status()
            files=re.findall(r'"(\d+\.[a-z]+)"',r.text)
            if files:
                base=f"https://a.hitomi.la/galleries/{chapter_id}/"
                return [f"{base}{f}" for f in files]
            jm=re.search(r'var galleryinfo = (\{.*?\});',r.text,re.DOTALL)
            if jm:
                import json as jl
                try:
                    gal=jl.loads(jm.group(1))
                    files=gal.get('files',[])
                    base=f"https://a.hitomi.la/galleries/{chapter_id}/"
                    return [f"{base}{f.get('name',f)}" for f in files]
                except: pass
            return []
        except: return []
    
    def get_manga_cover(self, manga_id):
        return download_image(f"https://a.hitomi.la/galleries/{manga_id}/cover.jpg")


class MangaDownloader:
    def __init__(self):
        self.sources = {"mangadex": MangaDex(), "webtoons": Webtoons(), "asurascans": AsuraScans(), "hitomi": Hitomi()}
    
    def get_source(self, name):
        return self.sources.get(name.lower())
    
    def search_all(self, query, limit=10, rating="any", sources=None):
        results = []
        src_list = sources if sources else list(self.sources.keys())
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {executor.submit(self.get_source(s).search, query, limit, rating): s for s in src_list if self.get_source(s)}
            for f in as_completed(futures):
                try: results.extend(f.result())
                except: pass
        seen = set()
        unique = []
        for r in results:
            key = r.get('title','').lower().strip()
            if key and key not in seen: seen.add(key); unique.append(r)
        return unique
    
    def get_manga_info(self, manga_id, source="mangadex"):
        src = self.get_source(source)
        return src.get_manga_info(manga_id) if src else None
    
    def get_chapters(self, manga_id, source="mangadex", lang="en"):
        src = self.get_source(source)
        return src.get_chapters(manga_id, lang) if src else []
    
    def get_volumes(self, manga_id, source="mangadex", lang="en"):
        src = self.get_source(source)
        if isinstance(src, MangaDex): return src.get_volumes(manga_id, lang)
        chapters = self.get_chapters(manga_id, source, lang)
        volumes = {}
        for c in chapters:
            v = c.get("volume","") or "0"
            if v not in volumes: volumes[v] = []
            volumes[v].append(c)
        return volumes
    
    def download_chapter(self, chapter_id, source="mangadex", output_dir="downloads",
                         fmt="epub", manga_title="Manga", crop=False, quality=85, progress_callback=None):
        src = self.get_source(source)
        if not src: return None
        pages = src.get_chapter_pages(chapter_id)
        if not pages: return None
        img_data = []
        for i, url in enumerate(pages):
            if progress_callback: progress_callback("downloading", i+1, len(pages), f"Page {i+1}/{len(pages)}")
            data = download_image(url)
            if data:
                if not crop: img_data.append(data)
                else:
                    try:
                        img = Image.open(io.BytesIO(data))
                        buf = io.BytesIO()
                        img.save(buf, format='JPEG', quality=quality)
                        img_data.append(buf.getvalue())
                    except: img_data.append(data)
        if not img_data: return None
        clean_title = sanitize_filename(manga_title)
        ensure_dir(output_dir)
        cover = src.get_manga_cover(manga_id) if hasattr(src,'get_manga_cover') else None
        output_path = os.path.join(output_dir, f"{clean_title}_ch{chapter_id[:8]}.{fmt}")
        if fmt == "cbz":
            create_cbz(img_data, output_path, lambda i,t: progress_callback("converting",i,t,"CBZ") if progress_callback else None)
        else:
            create_epub_from_images(img_data, output_path, title=manga_title, author="Unknown",
                                    cover_data=cover, progress_callback=lambda i,t: progress_callback("converting",i,t,"EPUB") if progress_callback else None)
        return output_path
    
    def download_manga(self, manga_id, source="mangadex", mode="all", volumes=None,
                       chapters=None, lang="en", output_dir="downloads", fmt="epub",
                       manga_title="Manga", crop=False, quality=85, split=True,
                       progress_callback=None, max_concurrent=3):
        src = self.get_source(source)
        if not src: return []
        manga_info = self.get_manga_info(manga_id, source)
        title = manga_info.get('title', manga_title) if manga_info else manga_title
        all_chapters = self.get_chapters(manga_id, source, lang)
        if not all_chapters: return []
        if mode == "chapters" and chapters:
            selected = [c for c in all_chapters if c.get('chapter') in chapters or c['id'] in chapters]
        elif mode == "volumes" and volumes:
            selected = [c for c in all_chapters if c.get('volume','') in volumes]
        else:
            selected = all_chapters
        if not selected: return []
        if progress_callback: progress_callback("start",0,len(selected),f"Downloading {len(selected)} chapters")
        results = []
        if split:
            completed = 0
            with ThreadPoolExecutor(max_workers=max_concurrent) as executor:
                futures = []
                for ch in selected:
                    ch_title = f"{title} - Chapter {ch.get('chapter','?')}"
                    futures.append(executor.submit(self.download_chapter, ch['id'], source, output_dir, fmt,
                                                   ch_title, crop, quality,
                                                   lambda s,i,t,msg: progress_callback(s,i,t,msg) if progress_callback else None))
                for f in as_completed(futures):
                    try:
                        path = f.result()
                        if path: results.append(path)
                        completed += 1
                        if progress_callback: progress_callback("progress",completed,len(selected),f"Completed {completed}/{len(selected)}")
                    except Exception as e:
                        completed += 1
                        if progress_callback: progress_callback("error",completed,len(selected),str(e))
        else:
            all_images = []
            for ch in selected:
                pages = src.get_chapter_pages(ch['id'])
                for url in pages:
                    data = download_image(url)
                    if data: all_images.append(data)
            if not all_images: return []
            clean_title = sanitize_filename(title)
            ensure_dir(output_dir)
            output_path = os.path.join(output_dir, f"{clean_title}_complete.{fmt}")
            cover = src.get_manga_cover(manga_id)
            if fmt == "cbz":
                create_cbz(all_images, output_path, lambda i,t: progress_callback("converting",i,t,"CBZ") if progress_callback else None)
            else:
                create_epub_from_images(all_images, output_path, title=title,
                                        author=manga_info.get('author','Unknown') if manga_info else "Unknown",
                                        cover_data=cover, progress_callback=lambda i,t: progress_callback("converting",i,t,"EPUB") if progress_callback else None)
            results.append(output_path)
        if progress_callback: progress_callback("done",len(results),len(selected),"Download complete!")
        return results
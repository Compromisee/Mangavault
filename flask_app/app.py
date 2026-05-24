#!/usr/bin/env python3
"""
MangaForge Flask Web Application
Features: trending, search, download by volume/chapter, animated backgrounds,
settings, metadata editor, URL download, bulk download.
"""

import os
import sys
import json
import threading
import time
from pathlib import Path

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for
from core import MangaDownloader, sanitize_filename, download_image

app = Flask(__name__)
app.secret_key = 'mangaforge-secret-key-2024'
app.config['DOWNLOAD_FOLDER'] = os.path.join(os.path.expanduser('~'), 'MangaForgeDownloads')

downloader = MangaDownloader()

# In-memory download queue
download_queue = []
download_progress = {}


# ============================
# ROUTES
# ============================

@app.route('/')
def index():
    """Home page with trending and search."""
    trending = session.get('trending', [])
    if not trending:
        # Fetch some trending/popular from MangaDex
        try:
            trending = downloader.search_all('', limit=12, rating='any', sources=['mangadex'])
            session['trending'] = trending[:12]
        except:
            trending = []
    
    settings = session.get('settings', get_default_settings())
    return render_template('index.html', trending=trending, settings=settings)


@app.route('/search')
def search():
    """Search page."""
    query = request.args.get('q', '')
    sources = request.args.getlist('sources') or ['mangadex', 'asurascans']
    rating = request.args.get('rating', 'any')
    
    if not query:
        return render_template('search.html', results=[], query='')
    
    results = downloader.search_all(query, limit=30, rating=rating, sources=sources)
    return render_template('search.html', results=results, query=query, sources=sources)


@app.route('/api/search')
def api_search():
    """Search API endpoint."""
    query = request.args.get('q', '')
    sources = request.args.getlist('sources') or ['mangadex', 'asurascans']
    rating = request.args.get('rating', 'any')
    
    results = downloader.search_all(query, limit=20, rating=rating, sources=sources)
    return jsonify(results)


@app.route('/manga/<source>/<manga_id>')
def manga_detail(source, manga_id):
    """Manga detail page."""
    info = downloader.get_manga_info(manga_id, source)
    if not info:
        return render_template('error.html', message='Manga not found'), 404
    
    chapters = downloader.get_chapters(manga_id, source, session.get('settings', {}).get('lang', 'en'))
    volumes = {}
    for c in chapters:
        v = c.get('volume', '0')
        if v not in volumes:
            volumes[v] = []
        volumes[v].append(c)
    
    settings = session.get('settings', get_default_settings())
    return render_template('manga.html', manga=info, chapters=chapters, 
                          volumes=volumes, source=source, settings=settings)


@app.route('/api/manga/<source>/<manga_id>')
def api_manga_detail(source, manga_id):
    """Manga detail API."""
    info = downloader.get_manga_info(manga_id, source)
    chapters = downloader.get_chapters(manga_id, source, 
                                       session.get('settings', {}).get('lang', 'en'))
    return jsonify({'info': info, 'chapters': chapters})


@app.route('/download', methods=['POST'])
def start_download():
    """Start a download."""
    data = request.get_json() or request.form
    
    manga_id = data.get('manga_id')
    source = data.get('source', 'mangadex')
    title = data.get('title', 'Manga')
    mode = data.get('mode', 'all')
    chapters = data.get('chapters', '').split(',') if data.get('chapters') else None
    volumes = data.get('volumes', '').split(',') if data.get('volumes') else None
    fmt = data.get('format', session.get('settings', {}).get('format', 'epub'))
    split = data.get('split', 'true') == 'true'
    crop = data.get('crop', 'false') == 'true'
    
    settings = session.get('settings', get_default_settings())
    output_dir = settings.get('output_dir', app.config['DOWNLOAD_FOLDER'])
    quality = settings.get('quality', 85)
    concurrent = settings.get('concurrent', 3)
    lang = settings.get('lang', 'en')
    
    dl_id = f"{manga_id}_{int(time.time())}"
    
    def progress_cb(status, current, total, msg=""):
        download_progress[dl_id] = {
            'status': status,
            'current': current,
            'total': total,
            'message': msg,
            'title': title,
        }
    
    def download_thread():
        download_progress[dl_id] = {'status': 'starting', 'message': 'Starting...', 'title': title}
        try:
            results = downloader.download_manga(
                manga_id=manga_id,
                source=source,
                mode=mode,
                chapters=chapters,
                volumes=volumes,
                lang=lang,
                output_dir=output_dir,
                fmt=fmt,
                manga_title=title,
                crop=crop,
                quality=quality,
                split=split,
                max_concurrent=concurrent,
                progress_callback=progress_cb,
            )
            download_progress[dl_id] = {
                'status': 'complete',
                'message': f'Complete! {len(results)} files',
                'results': results,
                'title': title,
            }
        except Exception as e:
            download_progress[dl_id] = {
                'status': 'error',
                'message': str(e),
                'title': title,
            }
    
    threading.Thread(target=download_thread, daemon=True).start()
    
    return jsonify({'download_id': dl_id, 'status': 'started'})


@app.route('/download/url', methods=['POST'])
def download_by_url():
    """Download from URL."""
    data = request.get_json() or request.form
    url = data.get('url', '')
    
    from cli import parse_url
    source, mid = parse_url(url)
    
    if not source:
        return jsonify({'error': 'Could not parse URL'}), 400
    
    info = downloader.get_manga_info(mid, source)
    title = info.get('title', mid) if info else mid
    
    # Trigger download
    dl_id = f"{mid}_{int(time.time())}"
    settings = session.get('settings', get_default_settings())
    output_dir = settings.get('output_dir', app.config['DOWNLOAD_FOLDER'])
    
    def dl_thread():
        download_progress[dl_id] = {'status': 'starting', 'message': 'Fetching...', 'title': title}
        try:
            chapters = downloader.get_chapters(mid, source, settings.get('lang', 'en'))
            results = downloader.download_manga(
                manga_id=mid, source=source,
                output_dir=output_dir,
                fmt=settings.get('format', 'epub'),
                manga_title=title,
                lang=settings.get('lang', 'en'),
                split=settings.get('split', True),
                max_concurrent=settings.get('concurrent', 3),
            )
            download_progress[dl_id] = {
                'status': 'complete', 'message': f'Done! {len(results)} files',
                'results': results, 'title': title,
            }
        except Exception as e:
            download_progress[dl_id] = {'status': 'error', 'message': str(e), 'title': title}
    
    threading.Thread(target=dl_thread, daemon=True).start()
    return jsonify({'download_id': dl_id, 'status': 'started'})


@app.route('/download/bulk', methods=['POST'])
def bulk_download():
    """Bulk download from URLs."""
    data = request.get_json() or request.form
    urls_text = data.get('urls', '')
    concurrent = int(data.get('concurrent', 3))
    
    urls = [u.strip() for u in urls_text.split('\n') if u.strip()]
    
    from cli import parse_url
    settings = session.get('settings', get_default_settings())
    output_dir = settings.get('output_dir', app.config['DOWNLOAD_FOLDER'])
    
    bulk_id = f"bulk_{int(time.time())}"
    
    def bulk_thread():
        download_progress[bulk_id] = {'status': 'starting', 'message': f'Processing {len(urls)} URLs...'}
        completed = 0
        
        for i, url in enumerate(urls):
            source, mid = parse_url(url)
            if source:
                try:
                    info = downloader.get_manga_info(mid, source)
                    title = info.get('title', mid) if info else mid
                    
                    results = downloader.download_manga(
                        manga_id=mid, source=source,
                        output_dir=output_dir,
                        fmt=settings.get('format', 'epub'),
                        manga_title=title,
                        lang=settings.get('lang', 'en'),
                    )
                    completed += 1
                except:
                    pass
            
            download_progress[bulk_id] = {
                'status': 'progress',
                'message': f'Completed {i+1}/{len(urls)}',
                'current': i+1,
                'total': len(urls),
            }
        
        download_progress[bulk_id] = {
            'status': 'complete',
            'message': f'Processed {completed}/{len(urls)} URLs',
        }
    
    threading.Thread(target=bulk_thread, daemon=True).start()
    return jsonify({'download_id': bulk_id, 'status': 'started'})


@app.route('/download/progress/<dl_id>')
def get_progress(dl_id):
    """Get download progress."""
    progress = download_progress.get(dl_id, {'status': 'unknown'})
    return jsonify(progress)


@app.route('/download/<path:filename>')
def download_file(filename):
    """Download a completed file."""
    return send_file(filename, as_attachment=True)


@app.route('/settings', methods=['GET', 'POST'])
def settings_page():
    """Settings page."""
    if request.method == 'POST':
        settings = {
            'format': request.form.get('format', 'epub'),
            'crop': request.form.get('crop') == 'on',
            'quality': int(request.form.get('quality', 85)),
            'output_dir': request.form.get('output_dir', app.config['DOWNLOAD_FOLDER']),
            'lang': request.form.get('lang', 'en'),
            'rating': request.form.get('rating', 'any'),
            'concurrent': int(request.form.get('concurrent', 3)),
            'split': request.form.get('split') == 'on',
            'naming_scheme': request.form.get('naming_scheme', '{title}_ch{chapter}'),
        }
        session['settings'] = settings
        return redirect(url_for('index'))
    
    settings = session.get('settings', get_default_settings())
    return render_template('settings.html', settings=settings)


@app.route('/docs')
def docs():
    """Documentation page."""
    return render_template('docs.html')


# ============================
# HELPERS
# ============================

def get_default_settings():
    return {
        'format': 'epub',
        'crop': False,
        'quality': 85,
        'output_dir': app.config['DOWNLOAD_FOLDER'],
        'lang': 'en',
        'rating': 'any',
        'concurrent': 3,
        'split': True,
        'naming_scheme': '{title}_ch{chapter}',
    }


if __name__ == '__main__':
    print("MangaForge Flask App starting...")
    print(f"Output directory: {app.config['DOWNLOAD_FOLDER']}")
    app.run(debug=True, host='0.0.0.0', port=5000)

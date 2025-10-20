# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import shutil
import fnmatch
from beets.plugins import BeetsPlugin
from beets import util

class ExtraFilesPlugin(BeetsPlugin):
    """Gestione file extra (cue, booklet, artwork, ecc.) durante import."""

    def __init__(self):
        super().__init__()
        # Config: patterns e path per categoria
        self.config.add({
            'patterns': {},   # es: {"artwork": ["cover.*", "folder.jpg"]}
            'paths': {},      # es: {"artwork": "$albumpath/artwork"}
        })
        self.register_listener('cli_exit', self.on_cli_exit)

    def on_cli_exit(self, lib):
        files = self.gather_files(lib)
        self.process_items(files, self._move_file)

    def gather_files(self, lib):
        files = []
        for album in lib.albums():
            album_dir = getattr(album, 'path', None)
            if not album_dir:
                continue
            for root, _, filenames in os.walk(album_dir):
                for filename in filenames:
                    category = self.match_category(filename)
                    if not category:
                        continue
                    relpath = os.path.join(root, filename)
                    meta = dict(album)
                    destpath = self.get_destination(relpath, category, meta)
                    if destpath:
                        files.append((relpath, destpath))
        return files

    def get_destination(self, relpath, category, meta):
        """Restituisce il path finale del file extra."""
        albumpath = str(meta.get('path', meta.get('album', 'UnknownAlbum')))
        path_template = self.config['paths'].get(category, '$albumpath')
        path_template = str(path_template).replace('$albumpath', albumpath)
        return os.path.join(path_template, os.path.basename(relpath))

    def match_category(self, filename):
        """Ritorna la categoria secondo i pattern definiti in config."""
        if isinstance(filename, bytes):
            filename = filename.decode('utf-8', errors='ignore')
        for category, patterns in self.config['patterns'].items():
            for pattern in patterns.as_str_seq():
                if any(ch in pattern for ch in '*?[]') and not pattern.startswith('^'):
                    if fnmatch.fnmatch(filename, pattern):
                        return category
                else:
                    try:
                        import re
                        if re.match(pattern, filename, re.IGNORECASE):
                            return category
                    except re.error as e:
                        self._log.error(f"Pattern non valido '{pattern}' ({category}): {e}")
        return None

    def process_items(self, files, action):
        for src, dest in files:
            action(src, dest)

    def _move_file(self, src, dest):
        self._log.debug(f"Spostamento file extra: {src} → {dest}")
        dest_dir = os.path.dirname(dest)
        if dest_dir:
            util.mkdirall(dest_dir)
        try:
            shutil.move(src, dest)
        except Exception as e:
            self._log.error(f"Errore nello spostamento di {src}: {e}")
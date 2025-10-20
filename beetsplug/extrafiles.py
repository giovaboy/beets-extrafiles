# -*- coding: utf-8 -*-
from __future__ import annotations
import os
import shutil
import re
import fnmatch
from beets.plugins import BeetsPlugin
from beets import util
from beets.library import Item, Album


class ExtraFilesPlugin(BeetsPlugin):
    """
    Plugin per gestire file aggiuntivi (booklet, artwork, cue, ecc.)
    solo sugli album appena importati.
    """

    def __init__(self):
        super().__init__()
        self.config.add({
            "patterns": {},
            "paths": {},
        })

        # Registriamo il listener sull'evento "import_task_files"
        self.register_listener("import_task_files", self.on_import)

    def on_import(self, session=None, task=None, items=None, albums=None, **kwargs):
        """Viene chiamato per ogni import task. Processa solo gli album importati."""
        if not albums:
            return

        files = self.gather_files(albums)
        self.process_items(files, action=self._move_file)

    def gather_files(self, albums):
        files = []
        for album in albums:
            album_dir = getattr(album, 'path', None)
            if not album_dir:
                continue

            for root, _, filenames in os.walk(album_dir):
                for filename in filenames:
                    relpath = os.path.join(root, filename)
                    category = self.match_category(filename)
                    if not category:
                        continue

                    meta = dict(album)
                    destpath = self.get_destination(relpath, category, meta)
                    if destpath:
                        files.append((relpath, destpath))
        return files

    def get_destination(self, relpath, category, meta):
        """Ritorna il path finale del file extra."""
        albumpath = str(meta.get('path', 'UnknownAlbum'))

        path_template = self.config['paths'].get(category)
        if path_template:
            path_template = str(path_template).replace('$albumpath', albumpath)
        else:
            path_template = albumpath

        return os.path.join(path_template, os.path.basename(relpath))

    def match_category(self, filename):
        """Compatibile con vecchie configurazioni (glob + regex miste)."""
        if isinstance(filename, bytes):
            filename = filename.decode('utf-8', errors='ignore')

        for category, patterns in self.config["patterns"].items():
            for pattern in patterns.as_str_seq():
                # Glob semplice
                if any(ch in pattern for ch in ['*', '?', '[', ']']) and not pattern.startswith('^'):
                    if fnmatch.fnmatch(filename, pattern):
                        return category

                # Slash nel pattern → match path
                elif '/' in pattern and re.search(pattern, filename, re.IGNORECASE):
                    return category

                # Regex standard
                else:
                    try:
                        if re.match(pattern, filename, re.IGNORECASE):
                            return category
                    except re.error as e:
                        self._log.error(f"Pattern non valido in '{pattern}' ({category}): {e}")
        return None

    def process_items(self, files, action):
        """Applica l'azione a tutti i file trovati."""
        for source, destination in files:
            action(source, destination)

    def _move_file(self, source, destination):
        """Sposta fisicamente il file extra."""
        # Converti entrambi in str
        if isinstance(source, bytes):
            source = source.decode('utf-8', errors='ignore')
        if isinstance(destination, bytes):
            destination = destination.decode('utf-8', errors='ignore')
    
        self._log.debug(f"Spostamento file extra: {source} → {destination}")
        dest_dir = os.path.dirname(destination)
        if dest_dir:
            util.mkdirall(dest_dir)
        try:
            shutil.move(source, destination)
        except Exception as e:
            self._log.error(f"Errore nel movimento di {source}: {e}")
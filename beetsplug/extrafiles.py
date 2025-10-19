# -*- coding: utf-8 -*-
# This file is part of beets-extrafiles.
# https://github.com/giovaboy/beets-extrafiles
#
# Licensed under the MIT license.

from __future__ import annotations
import os
import shutil
import re
import fnmatch
from beets.plugins import BeetsPlugin
from beets import util
import beets.library
import beets.ui


class ExtraFilesPlugin(BeetsPlugin):
    """
    Plugin per gestire file aggiuntivi (come booklet, log, cue, ecc.)
    associati agli album durante l'import in beets.
    """

    def __init__(self):
        super().__init__()
        self.config.add({
            "patterns": {
                "booklet": [r"^(?i).*booklet.*\.pdf$"],
                "log": [r"^(?i).*\.log$"],
                "cue": [r"^(?i).*\.cue$"],
                "cover": [r"^(?i).*cover.*\.(jpg|jpeg|png)$"],
            },
            "paths": {
                "booklet": "$albumpath/extra/",
                "log": "$albumpath/extra/",
                "cue": "$albumpath/extra/",
                "cover": "$albumpath/extra/",
            },
        })

        self.register_listener("cli_exit", self.on_cli_exit)

    def on_cli_exit(self, lib):
        """Quando termina il comando CLI, elabora eventuali extra file."""
        files = self.gather_files(lib)
        self.process_items(files, action=self._move_file)

    def gather_files(self, lib):
        """Cerca i file extra associati agli album nella libreria."""
        files = []
        for album in lib.albums():
            album_dir = os.path.dirname(album.item_dir())
            for root, _, filenames in os.walk(album_dir):
                for filename in filenames:
                    relpath = os.path.join(root, filename)
                    category = self.match_category(filename)
                    if not category:
                        continue
                    meta = album.item_template_fields()
                    destpath = self.get_destination(relpath, category, meta)
                    if destpath:
                        files.append((relpath, destpath))
        return files

    def get_destination(self, relpath, category, meta):
        """Crea il percorso di destinazione usando le template functions moderne."""
        try:
            from beets import templating
            funcs = templating.DefaultTemplateFunctions().functions()
        except ImportError:
            from beets.library import Library
            funcs = Library()._get_template_functions()

        tmpl = self.config["paths"].get(category).get()
        desttmpl = beets.library.Template(tmpl, funcs)
        destpath = desttmpl.substitute(meta)
        return util.bytestring_path(destpath)

    def match_category(self, filename):
        """Compatibile con vecchie configurazioni (glob + regex miste)."""
        if isinstance(filename, bytes):
            filename = filename.decode('utf-8', errors='ignore')

        for category, patterns in self.config["patterns"].items():
            for pattern in patterns.as_str_seq():
                # 1️⃣ Se contiene caratteri glob ma non è regex pura, usa fnmatch
                if any(ch in pattern for ch in ['*', '?', '[', ']']) and not pattern.startswith('^'):
                    if fnmatch.fnmatch(filename, pattern):
                        return category
    
                # 2️⃣ Se contiene slash (es: scans/), controlla se il path li contiene
                elif '/' in pattern and re.search(pattern, filename, re.IGNORECASE):
                    return category
    
                # 3️⃣ Altrimenti, fallback su regex standard
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
        self._log.debug(f"Spostamento file extra: {source} → {destination}")
        util.mkdirall(destination)
        try:
            shutil.move(source, destination)
        except Exception as e:
            self._log.error(f"Errore nel movimento di {source}: {e}")
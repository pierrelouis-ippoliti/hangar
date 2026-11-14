"""
The parse stage: from downloaded files to canonical texts and passages.

Each document format has its parser. Every parser normalises its text the
same way and builds its passages with ``assemble``, so every parsed document
follows the same rules whatever its format.
"""

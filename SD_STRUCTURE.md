# microSD structure

Format: FAT32.

Use two-digit folder names and three-digit track names:

```text
SD CARD
├── 01
│   ├── 001.mp3
│   ├── 002.mp3
│   ├── 003.mp3
│   └── ...
├── 02
│   ├── 001.mp3
│   ├── 002.mp3
│   └── ...
└── 03
    ├── 001.mp3
    ├── 002.mp3
    └── ...
```

DFPlayer supports numbered folders and `playFolder(folder, file)`. The firmware uses that addressing mode instead of global `next()` / `previous()`, because global navigation could leave the active album.

Recommended album size: 10-15 tracks.

Do not put unrelated audio files in the numbered folders.

# Distributing FluxDFT

You can package FluxDFT as a standalone executable for Windows (`.exe`) or Linux (binary) using PyInstaller.

## Prerequisites

Install PyInstaller in your python environment:
```bash
pip install pyinstaller
```

## Building for Windows (.exe)

Run this command in the project root (where `fluxdft.spec` is):

```powershell
pyinstaller fluxdft.spec
```

-   The executable will be created in the `dist/` folder: `dist/FluxDFT.exe`.
-   You can zip this single file and distribute it. Users do NOT need Python installed.

## Building for Linux (Ubuntu)

Run the **same command** on your Ubuntu machine:

```bash
pyinstaller fluxdft.spec
```

-   The executable will be created in `dist/FluxDFT`.
-   This is a standalone binary. You can double-click it or run it from the terminal `./dist/FluxDFT`.
-   It functions exactly like a Windows `.exe` but for Linux.

## Notes

-   **Cross-compilation:** You cannot build the Linux binary on Windows or vice-versa. You must run the build command on the target OS.
-   **Dependencies:** The build process automatically bundles all installed Python libraries (PyQt6, Matplotlib, etc.) into the executable.

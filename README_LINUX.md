# FluxDFT on Ubuntu/Linux

FluxDFT is designed to be cross-platform. Follow these steps to run it on Ubuntu.

## 1. Prerequisites

Ensure you have Python 3.10+ installed:
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

You also need Quantum ESPRESSO installed and available in your PATH:
```bash
sudo apt install quantum-espresso
# Verify installation
which pw.x
```

## 2. Setup

1.  **Extract the project** to a folder.
2.  **Create a virtual environment** (recommended):
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```
3.  **Install dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    *If `requirements.txt` is missing, install the core packages:*
    ```bash
    pip install PyQt6 matplotlib numpy qtawesome
    ```

## 3. Configuration

FluxDFT will automatically look for `pw.x` in `/usr/local/bin` or your system `$PATH`.
If your QE binary is in a custom location, you can set it in the Settings dialog within the app.

## 4. Running

Execute the application:
```bash
python3 -m fluxdft.main
```

## Troubleshooting

-   **"xcb" plugin error:** If you see an error about the Qt platform plugin "xcb", install the required libraries:
    ```bash
    sudo apt install libxcb-cursor0 libegl1
    ```
-   **Icons missing:** Ensure `qtawesome` is installed (`pip install qtawesome`).

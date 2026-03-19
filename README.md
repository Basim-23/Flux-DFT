<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Qt6-PyQt6-41CD52?style=for-the-badge&logo=qt&logoColor=white" alt="PyQt6"/>
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"/>
  <img src="https://img.shields.io/badge/Version-2.0.0-brightgreen?style=for-the-badge" alt="Version"/>
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-lightgrey?style=for-the-badge" alt="Platform"/>
</p>

<h1 align="center">⚛️ FluxDFT</h1>

<p align="center">
  <strong>A modern, intelligent desktop application that makes Density Functional Theory (DFT) calculations accessible, efficient, and visually intuitive.</strong>
</p>

<p align="center">
  <a href="gallery.md"><strong>🖼️ View the Screenshot Gallery</strong></a>
</p>

<p align="center">
  FluxDFT bridges the gap between the power of <a href="https://www.quantum-espresso.org/">Quantum ESPRESSO</a> and the ease of a modern graphical interface.<br/>
  Designed for <strong>researchers</strong>, <strong>professors</strong>, and <strong>students</strong> in computational physics and materials science.
</p>

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Screenshot Gallery](gallery.md)
- [Key Features](#-key-features)
- [Getting Started](#-getting-started)
- [Usage](#-usage)
- [Project Structure](#-project-structure)
- [Keyboard Shortcuts](#️-keyboard-shortcuts)
- [Configuration](#️-configuration)
- [Contributing](#-contributing)
- [License](#-license)
- [Acknowledgments](#-acknowledgments)

---

## 🎬 Overview

FluxDFT provides an **end-to-end workflow** for Density Functional Theory simulations — from crystal structure import to publication-ready analysis:

1. **Import** crystal structures from CIF, XYZ, POSCAR, XSF, or QE input files.
2. **Configure** calculation parameters with physics-aware validation and smart defaults.
3. **Run** calculations locally or on remote HPC clusters via built-in SSH.
4. **Analyze** results with interactive, publication-quality electronic structure plots.
5. **Report** findings in professionally formatted Markdown, HTML, or PDF.

### Who is FluxDFT for?

| Audience | Value Proposition |
|---|---|
| **Graduate Students** | Reduce the learning curve of Quantum ESPRESSO with guided input generation, real-time validation, and AI-powered explanations. |
| **Researchers** | Accelerate workflows with automated convergence testing, HPC job management, and one-click report generation. |
| **Professors & Educators** | Use as a teaching tool with instant visualization of DFT concepts and interactive structure viewers. |

---

## ✨ Key Features

### 🧠 FluxAI Intelligence
- **Physics Explainer** — Ask FluxAI to explain complex DFT parameters and physics concepts directly in the context of your project.
- **Error Analytics** — Intelligent crash-log analysis that identifies root causes and suggests specific fixes.
- **Methodology Assistant** — Automated drafting of technical methodology sections for research papers.

### 🧪 Smart Input Editor
- **Live Validation** — Real-time syntax highlighting with physics-aware error detection.
- **Auto-Fix Suggestions** — One-click correction for common formatting and parameter errors.
- **Project-Aware Defaults** — Automatic detection of metallic vs. insulating behavior to recommend optimal smearing and broadening parameters.
- **K-Point Recommendation** — Advanced k-mesh suggestions based on lattice vectors and target density.
- **DFT+U Support** — Easy configuration of Hubbard U parameters for transition-metal systems.
- **DEF Schema Parser** — Parses the official Quantum ESPRESSO DEF schema to provide accurate parameter validation and documentation.

### 🔬 3D Structure & Visualization
- **High-Fidelity Viewer** — Scientific 3D rendering powered by [PyVista](https://docs.pyvista.org/) with PBR (physically based rendering) materials.
- **Supercell Generator** — Build and visualize supercells of any dimension with real-time preview.
- **Format Conversion** — Seamlessly convert between CIF, XYZ, POSCAR, XSF, and QE Input using [ASE](https://wiki.fysik.dtu.dk/ase/).
- **Interactive SCF Tracking** — Real-time convergence monitoring with live-updating plots.

### ⚙️ Job & Workflow Management
- **HPC Connectivity** — Built-in SSH client for job submission to **SLURM**, **PBS**, and **SGE** cluster schedulers.
- **Execution Engine** — Monitor local and remote jobs with real-time output streaming.
- **Automated Workflows** — Dedicated pipelines for SCF, geometry optimization (relax/vc-relax), band structure, DOS, and phonon dispersion.
- **Convergence Testing** — Automated convergence studies for cutoff energy and k-point mesh density.
- **Project Explorer** — Manage files, inputs, and results with a structured, intuitive file browser.

### 📊 Advanced Electronic Structure Analysis
- **Band Structure** — High-symmetry k-path generation with automatic symmetry detection.
- **Density of States** — Total DOS and projected DOS (PDOS) with orbital decomposition.
- **Fat Bands** — Orbital-resolved band structure with atomic character weighting.
- **Effective Mass** — Parabolic and advanced effective mass extraction at band extrema.
- **Fermi Surface** — 3D Fermi surface visualization for metallic systems.
- **Optical Properties** — Dielectric function and optical absorption spectra.
- **Composite Plots** — Side-by-side band structure and DOS plots for publication.

### 🔊 Phonon Analysis
- **Phonon Dispersion** — Phonon band structure along high-symmetry paths.
- **Phonon DOS** — Phonon density of states and thermodynamic properties.
- **Automated Phonon Workflow** — End-to-end pipeline from structure to phonon spectra.

### 🌐 Materials Project Integration
- **Reference Data** — Compare your calculated results against reference data from the [Materials Project API](https://materialsproject.org/).
- **Local Caching** — Intelligent caching to minimize API calls and enable offline comparison.
- **Structure Import** — Directly import crystal structures from the Materials Project database.

### 📝 Reporting Suite
- **Multi-Format Export** — Generate comprehensive reports in **PDF**, **HTML**, and **Markdown**.
- **Publication-Quality Plots** — All plots use Matplotlib with custom scientific styling, ready for journal submission.
- **Automated Report Content** — Pre-populated methodology, results tables, and figure captions.

### ☁️ Flux Cloud & User Experience
- **Cloud Integration** — User authentication and profile management via [Supabase](https://supabase.com/).
- **Premium Interface** — Modern dark theme with glassmorphism-inspired components and animated splash screen.
- **Global Shortcuts** — Intuitive keyboard shortcuts with a built-in shortcuts overlay (press `?` to toggle).
- **Desktop Notifications** — System alerts for job completions and critical events.

---

## 🚀 Getting Started

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| **Python** | 3.10+ | [Download](https://www.python.org/downloads/) |
| **Quantum ESPRESSO** | 7.0+ | [Installation Guide](https://www.quantum-espresso.org/Doc/user_guide/) — must be in `$PATH` |
| **Git** | Any | For cloning the repository |

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/Basim-23/Flux-DFT.git
cd Flux-DFT

# 2. Create and activate a virtual environment (recommended)
python -m venv venv

# Linux / macOS
source venv/bin/activate

# Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Install FluxDFT in development (editable) mode
pip install -e .
```

### Running

```bash
# Using the installed entry point
fluxdft

# Or run directly as a module
python -m fluxdft.main
```

> **Windows Quick Launch:** Double-click `FluxDFT.bat` to launch the application without opening a terminal.

### Building a Standalone Executable

FluxDFT can be packaged as a self-contained executable (no Python required) using [PyInstaller](https://pyinstaller.org/):

```bash
pip install pyinstaller
pyinstaller fluxdft.spec
```

The executable is created in `dist/FluxDFT.exe` (Windows) or `dist/FluxDFT` (Linux). See [DISTRIBUTION.md](DISTRIBUTION.md) for full build instructions.

---

## 💡 Usage

### Typical Workflow

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  Import      │────▶│  Configure       │────▶│  Run             │
│  Structure   │     │  Calculation     │     │  Calculation     │
│  (CIF/XYZ/   │     │  (Smart Editor   │     │  (Local or       │
│   POSCAR)    │     │   + Validation)  │     │   HPC/SSH)       │
└──────────────┘     └──────────────────┘     └────────┬─────────┘
                                                       │
                     ┌──────────────────┐     ┌────────▼─────────┐
                     │  Export          │◀────│  Analyze         │
                     │  Report          │     │  Results         │
                     │  (PDF/HTML/MD)   │     │  (Bands/DOS/     │
                     └──────────────────┘     │   Phonons)       │
                                              └──────────────────┘
```

1. **Import a structure** — Open a CIF, XYZ, POSCAR, or QE input file from the File menu or Project Explorer.
2. **Configure parameters** — Use the Smart Input Editor with live validation. FluxDFT will suggest optimal k-points, smearing, and pseudopotentials.
3. **Run the calculation** — Execute locally or submit to a remote HPC cluster via the built-in SSH client.
4. **Monitor progress** — Watch SCF convergence in real-time from the Convergence Monitor panel.
5. **Analyze results** — Visualize band structures, DOS, fat bands, and phonon spectra from the Analysis tabs.
6. **Generate a report** — Export your results to a formatted PDF, HTML, or Markdown report.

### Materials Project Comparison

FluxDFT can compare your calculated results against reference data from the Materials Project. To enable this feature:

1. Obtain a free API key from [materialsproject.org](https://materialsproject.org/api).
2. Run the setup script:
   ```bash
   python scripts/setup_mp_key.py
   ```
3. Use the **MP Comparison Panel** in the application to compare band structures and properties.

---

## 📁 Project Structure

```
Flux-DFT/
├── src/
│   └── fluxdft/              # Main package
│       ├── main.py            # Application entry point & splash screen
│       ├── ai/                # FluxAI (OpenAI-powered assistance)
│       ├── analysis/          # Charge density & bonding analysis
│       ├── cloud/             # Supabase cloud integration
│       ├── core/              # Structure loading, input building, output parsing,
│       │                      #   pseudopotential management, job runner, SSH/HPC
│       ├── electronic/        # Band structure, DOS, effective mass, Fermi surface,
│       │                      #   fat bands, optical properties
│       ├── execution/         # Local/remote execution engine
│       ├── integrations/      # Atomate2, Custodian, Materials Project client
│       ├── intelligence/      # Validation, error detection, scoring, custodian
│       ├── io/                # QE input/output file parsing & generation
│       ├── materials_project/ # MP API client, data caching, comparator
│       ├── phonon/            # Phonon dispersion, DOS, thermodynamics
│       ├── plotting/          # Matplotlib plotters (band, DOS, fat band, composite)
│       ├── postprocessing/    # Charge analysis & post-processing tools
│       ├── reporting/         # PDF/HTML/Markdown report generator
│       ├── resources/         # QSS stylesheets & static assets
│       ├── symmetry/          # High-symmetry k-path generation
│       ├── ui/                # PyQt6 GUI (main window, editor, viewer, panels)
│       ├── utils/             # Configuration & physical constants
│       ├── visualization/     # 3D structure viewer (PyVista)
│       └── workflows/         # Task/workflow engine, convergence wizard,
│                              #   phonon workflow, SLURM/PBS scheduler
├── tests/                     # Unit tests (pytest)
├── scripts/                   # Utility & verification scripts
├── pseudo/                    # Pseudopotential files (user-downloaded)
├── convergence_test/          # Convergence test workspace
├── pyproject.toml             # Project metadata & dependencies
├── requirements.txt           # Pip requirements
├── fluxdft.spec               # PyInstaller build spec
├── FluxDFT.bat                # Windows quick-launch script
├── LICENSE                    # MIT License
├── CONTRIBUTING.md            # Contribution guidelines
├── CODE_OF_CONDUCT.md         # Community code of conduct
├── CHANGELOG.md               # Version history
├── SECURITY.md                # Security policy
├── DISTRIBUTION.md            # Build & packaging instructions
└── README_LINUX.md            # Linux-specific setup instructions
```

---

## ⌨️ Keyboard Shortcuts

| Shortcut | Action |
|:---|:---|
| `?` | Show/hide keyboard shortcuts overlay |
| `Ctrl+N` | New project |
| `Ctrl+O` | Open file |
| `Ctrl+S` | Save current file |
| `Ctrl+R` | Run calculation |
| `Ctrl+W` | Close current tab |
| `F11` | Toggle fullscreen mode |

---

## ⚙️ Configuration

### Quantum ESPRESSO Path

FluxDFT automatically searches for `pw.x` in your system `$PATH`. If Quantum ESPRESSO is installed in a custom location, configure the path in **Settings** within the application.

### Pseudopotentials

FluxDFT includes a built-in **Pseudopotential Manager** that can download and organize pseudopotential files from [Materials Cloud SSSP](https://www.materialscloud.org/discover/sssp). Downloaded files are stored in the `pseudo/` directory.

### Optional API Keys

| Service | Purpose | Setup |
|---|---|---|
| **Materials Project** | Reference data comparison | `python scripts/setup_mp_key.py` |
| **OpenAI** | FluxAI intelligent assistant | Configure in application Settings |
| **Supabase** | Cloud profile sync | Configure in application Settings |

---

## 🤝 Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on how to submit issues, feature requests, and pull requests.

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Quantum ESPRESSO](https://www.quantum-espresso.org/) — Open-source DFT simulation suite.
- [Materials Project](https://materialsproject.org/) — Materials reference database and API.
- [Materials Cloud](https://www.materialscloud.org/) — Standard solid-state pseudopotentials (SSSP).
- [PyVista](https://docs.pyvista.org/) — 3D scientific visualization engine.
- [ASE](https://wiki.fysik.dtu.dk/ase/) — Atomic Simulation Environment for structure manipulation.
- [Matplotlib](https://matplotlib.org/) — Publication-quality scientific plotting.
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) — Cross-platform GUI framework.

---

<p align="center">
  <em>Built with ❤️ for the computational materials science community</em><br/>
  <em>© 2026 FluxDFT</em>
</p>

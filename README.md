<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Qt6-PyQt6-41CD52?style=for-the-badge&logo=qt&logoColor=white" alt="PyQt6"/>
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="License"/>
  <img src="https://img.shields.io/badge/Version-2.0.0-brightgreen?style=for-the-badge" alt="Version"/>
</p>

# ⚛️ FluxDFT — Professional GUI for Quantum ESPRESSO

**A modern, intelligent desktop application that makes Density Functional Theory (DFT) calculations accessible, efficient, and visually intuitive.**

FluxDFT bridges the gap between the power of [Quantum ESPRESSO](https://www.quantum-espresso.org/) and the ease of a modern graphical interface. It is designed for **researchers**, **professors**, and **students** in computational physics and materials science who want to focus on science — not command-line syntax.

---

## 🎬 Overview

FluxDFT provides an end-to-end workflow for DFT simulations:

1. **Import** crystal structures (CIF, XYZ, POSCAR, QE input)
2. **Configure** calculation parameters with smart validation
3. **Run** calculations locally or on HPC clusters
4. **Analyze** results with publication-quality plots
5. **Report** findings in Markdown, HTML, or PDF

---

## ✨ Key Features

### 🧪 Smart Input Editor
- Syntax-highlighted editor with **live validation** and **auto-fix**
- Automatic detection of metals vs. insulators for smearing settings
- DFT+U parameter generation for transition metals and rare earths
- K-point mesh recommendations based on lattice geometry
- Templates for SCF, relaxation, vc-relax, NSCF, bands, and DOS

### 🔬 3D Structure Viewer
- Interactive visualization powered by **PyVista** with PBR rendering
- Import from CIF, XYZ, XSF, POSCAR, and Quantum ESPRESSO input files
- Supercell creation with real-time preview
- Element-aware coloring with CPK convention
- Export structures to multiple formats

### 📦 Smart Pseudopotential Manager
- **Project-aware**: automatically detects elements from loaded structures
- One-click **Auto-Fix** to download all missing pseudopotentials
- Downloads from **Materials Cloud SSSP** libraries
- Interactive periodic table with installation status
- Recommended energy cutoffs (`ecutwfc`, `ecutrho`) per element

### ⚙️ Job Management & HPC
- **Local execution** with real-time output streaming
- **SSH-based HPC submission** to SLURM, PBS, and SGE clusters
- Job queue with status tracking (running, completed, failed)
- Quick actions: view results, open plots, browse output folder
- Configurable Quantum ESPRESSO binary paths

### 📊 Visualization & Analysis
- **SCF Convergence** monitoring with interactive plots
- **Band Structure** diagrams with high-symmetry labels
- **Density of States** (total and projected)
- Convergence testing wizard for ecutwfc, K-points, and degauss
- All plots are publication-quality via Matplotlib

### 🔗 Materials Project Integration
- Search any material by formula
- Compare calculated results against reference data
- View properties: band gap, formation energy, volume, density
- Works with or without API key (includes demo mode)

### 🔊 Phonon Workflows
- Complete pipeline: `SCF → ph.x → q2r.x → matdyn.x`
- Phonon dispersion and DOS calculation
- Automatic high-symmetry path generation
- Imaginary frequency detection for stability analysis

### 📝 Report Generator
- Export to **Markdown**, **HTML**, and **PDF**
- Customizable sections (input parameters, results, validation)
- Embedded figures and tables
- Publication-ready formatting

### 🎨 Premium UI/UX
- Dark theme with glassmorphism-inspired design
- Keyboard shortcuts overlay (`?` to show)
- Drag-and-drop file support
- Desktop notifications for job events
- Single-instance tabs for clean workspace management

---

## 🏗️ Architecture

```
fluxdft/
├── core/               # Structure loading, input building, output parsing
│   ├── input_builder    # QE input file generation
│   ├── output_parser    # QE output file parsing
│   ├── pseudo_manager   # Pseudopotential management
│   ├── smart_pseudo     # Project-aware pseudo intelligence
│   ├── scf_generator    # Scientific SCF parameter generation
│   └── job_runner       # Local/remote job execution
├── ui/                 # PyQt6 user interface
│   ├── main_window      # Application shell & navigation
│   ├── input_editor     # Smart input editor with validation
│   ├── structure_viewer # 3D crystal structure viewer
│   ├── pseudo_manager_panel  # Periodic table & downloads
│   ├── job_manager      # Job queue & monitoring
│   ├── visualization    # SCF, Bands, DOS plotting
│   └── workflows_page   # Workflow launcher
├── workflows/          # Automated calculation workflows
│   ├── convergence      # Convergence testing
│   ├── phonon_workflow  # Phonon calculations
│   └── engine           # Workflow execution engine
├── integrations/       # External service connectors
│   └── mp_client        # Materials Project API
├── reporting/          # Report generation (MD/HTML/PDF)
├── intelligence/       # Validation & error detection
├── electronic/         # Band structure & DOS analysis
├── phonon/             # Phonon analysis tools
├── symmetry/           # K-path & space group analysis
└── plotting/           # Publication-quality plot recipes
```

---

## 🚀 Getting Started

### Prerequisites

- **Python** 3.10 or higher
- **Quantum ESPRESSO** 7.0+ ([installation guide](https://www.quantum-espresso.org/Doc/user_guide/))

### Installation

```bash
# Clone the repository
git clone https://github.com/YOUR_USERNAME/fluxdft.git
cd fluxdft

# Create a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# Install dependencies
pip install -r requirements.txt

# Install FluxDFT in development mode
pip install -e .
```

### Running

```bash
# Using the entry point
fluxdft

# Or directly
python -m fluxdft.main
```

### Windows Quick Launch

Double-click `FluxDFT.bat` to start the application.

---

## 📦 Building Standalone Executable

FluxDFT can be packaged as a standalone `.exe` (Windows) or binary (Linux) using PyInstaller:

```bash
pip install pyinstaller
pyinstaller fluxdft.spec
```

The executable will appear in `dist/`. No Python installation is needed to run it.

---

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| **GUI Framework** | PyQt6 6.5+ |
| **3D Rendering** | PyVista + VTK |
| **Plotting** | Matplotlib 3.7+ |
| **Numerical** | NumPy 1.24+ |
| **Structure I/O** | ASE (Atomic Simulation Environment) |
| **HPC Connectivity** | Paramiko (SSH) |
| **Icons** | QtAwesome (Font Awesome) |
| **Materials Data** | Materials Project API |

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `?` | Show shortcuts overlay |
| `Ctrl+N` | New project |
| `Ctrl+O` | Open file |
| `Ctrl+S` | Save |
| `Ctrl+R` | Run calculation |
| `Ctrl+W` | Close tab |
| `Ctrl+Tab` | Next tab |
| `F11` | Toggle fullscreen |

---

## 📁 Supported File Formats

| Format | Import | Export | Description |
|--------|:------:|:------:|-------------|
| `.cif` | ✅ | ✅ | Crystallographic Information File |
| `.xyz` | ✅ | ✅ | XYZ atomic coordinates |
| `.xsf` | ✅ | — | XCrysDen format |
| `.in` / `.pw` | ✅ | ✅ | Quantum ESPRESSO input |
| `.out` / `.log` | ✅ | — | QE output (for analysis) |
| `.gnu` | ✅ | — | GNUplot band data |
| `.dos` / `.dat` | ✅ | — | DOS data files |
| POSCAR | ✅ | ✅ | VASP structure format |

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## 👥 Authors

- **Dr. Sherif Yahya** — Physics & scientific methodology
- **Basim Nasser** — Software architecture & development

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

- [Quantum ESPRESSO](https://www.quantum-espresso.org/) — The leading open-source DFT simulation suite
- [Materials Cloud SSSP](https://www.materialscloud.org/discover/sssp) — Standard Solid-State Pseudopotentials
- [Materials Project](https://materialsproject.org/) — Reference materials data
- [PyVista](https://docs.pyvista.org/) — 3D scientific visualization
- [ASE](https://wiki.fysik.dtu.dk/ase/) — Atomic Simulation Environment

---

<p align="center">
  <em>Built with ❤️ for the computational materials science community</em>
</p>

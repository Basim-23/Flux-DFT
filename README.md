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

1.  **Import** crystal structures (CIF, XYZ, POSCAR, QE input)
2.  **Configure** calculation parameters with smart validation
3.  **Run** calculations locally or on HPC clusters
4.  **Analyze** results with publication-quality plots
5.  **Report** findings in Markdown, HTML, or PDF

---

## ✨ Key Features

### 🧠 FluxAI Intelligence
-   **Physics Explainer**: Ask FluxAI to explain complex DFT parameters or physics concepts directly in the context of your project.
-   **Error Analytics**: Intelligent crash log analysis that identifies root causes and suggests specific fixes.
-   **Methodology Assistant**: Automated drafting of technical methodology sections for your research papers.

### 🧪 Smart Input Editor
-   **Live Validation**: Real-time syntax highlighting and physics-aware error detection.
-   **Auto-Fix Suggestions**: One-click correction for common formatting and parameter errors.
-   **Project-Aware Defaults**: Automatic detection of metallic vs. insulating behavior to recommend optimal smearing.
-   **K-Point Recommendation**: Advanced mesh suggestions based on lattice vectors and target density.
-   **DFT+U Support**: Easy configuration for hubbard parameters in transition metals.

### 🔬 3D Structure & Visualization
-   **High-Fidelity Viewer**: Scientific 3D rendering powered by **PyVista** with PBR materials.
-   **Supercell Generator**: Build and visualize supercells with real-time preview.
-   **Format Conversion**: Seamlessly convert between CIF, XYZ, POSCAR, XSF, and QE Input.
-   **Interactive Plots**: Real-time SCF convergence tracking and interactive electronic structure diagrams.

### ⚙️ Job & Workflow Management
-   **HPC Connectivity**: Built-in SSH client for job submission to **SLURM, PBS, and SGE** clusters.
-   **Execution Engine**: Monitor local and remote jobs with real-time output streaming.
-   **Automated Workflows**: Dedicated pipelines for SCF, geometry optimization (relax/vc-relax), and phonon dispersion.
-   **Project Explorer**: Manage files and results with a structured, intuitive interface.

### 📊 Advanced Post-Processing
-   **Composite Visualizations**: Side-by-side Band Structure and Density of States (DOS/PDOS) plots.
-   **Materials Project Integration**: Compare your results against reference data from the Materials Project API.
-   **Reporting Suite**: Export comprehensive results to professionally formatted **PDF, HTML, and Markdown** reports.

### ☁️ Flux Cloud & UX
-   **Cloud Integration**: User authentication and profile management via Supabase.
-   **Premium Interface**: Modern dark theme with glassmorphism-inspired components.
-   **Global Shortcuts**: Intuitive keyboard control with a built-in shortcuts overlay (`?` to toggle).
-   **Notifications**: Desktop alerts for job completions and critical events.

---

## 🚀 Getting Started

### Prerequisites

-   **Python** 3.10 or higher
-   **Quantum ESPRESSO** 7.0+ ([installation guide](https://www.quantum-espresso.org/Doc/user_guide/))

### Installation

```bash
# Clone the repository
git clone https://github.com/Basim-23/Flux-DFT
cd Flux-DFT

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

---

## ⌨️ Keyboard Shortcuts

| Key | Action |
| :--- | :--- |
| `?` | Show shortcuts overlay |
| `Ctrl+N` | New project |
| `Ctrl+O` | Open file |
| `Ctrl+S` | Save |
| `Ctrl+R` | Run calculation |
| `Ctrl+W` | Close tab |
| `F11` | Toggle fullscreen |

---

## 🤝 Contributing

Contributions are welcome! If you have suggestions or find bugs, please open an issue or submit a pull request on the [GitHub repository](https://github.com/Basim-23/Flux-DFT).

---

## 👤 Author

-   **Basim Nasser** — Software Architecture & Development

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgments

-   [Quantum ESPRESSO](https://www.quantum-espresso.org/) — Leading open-source DFT suite.
-   [Materials Project](https://materialsproject.org/) — Reference materials database.
-   [Materials Cloud](https://www.materialscloud.org/) — Standard solid-state pseudopotentials.
-   [PyVista](https://docs.pyvista.org/) — 3D scientific visualization infrastructure.

---

<p align="center">
  <em>Built with ❤️ for the computational materials science community | © 2026 FluxDFT</em>
</p>

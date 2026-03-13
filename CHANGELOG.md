# Changelog

All notable changes to FluxDFT will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [2.0.0] — 2026-03-13

### Added

- **FluxAI Assistant** — AI-powered physics explainer, error analytics, and methodology drafting via OpenAI integration.
- **3D Structure Viewer** — High-fidelity crystal structure visualization with PyVista PBR rendering and supercell generation.
- **Electronic Structure Suite** — Band structure, DOS/PDOS, fat bands, effective mass, Fermi surface, and optical properties analysis.
- **Phonon Analysis** — Phonon dispersion, phonon DOS, and thermodynamic property calculations.
- **Convergence Wizard** — Automated convergence testing for cutoff energy and k-point mesh density.
- **Composite Plotter** — Side-by-side band structure and DOS plots for publication.
- **Materials Project Integration** — API client with local caching for reference data comparison and structure import.
- **HPC Job Management** — Built-in SSH client for job submission to SLURM, PBS, and SGE schedulers.
- **Workflow Engine** — Task-based workflow system with scheduling, dependency tracking, and automated pipelines.
- **Reporting Suite** — Export results to professionally formatted PDF, HTML, and Markdown reports.
- **Cloud Integration** — User authentication and profile management via Supabase.
- **Intelligence Module** — Validation engine, error detection and fix suggestions, scoring, and custodian integration.
- **Integrations** — Atomate2 and Custodian compatibility for workflow interoperability.
- **Charge Analysis** — Bader charge and bonding analysis post-processing tools.
- **Symmetry Module** — Automatic k-path generation with space group detection.
- **Smart Input Editor** — Physics-aware validation, auto-fix suggestions, DFT+U support, and DEF schema parsing.
- **Pseudopotential Manager** — Built-in UI for downloading and organizing pseudopotentials from Materials Cloud SSSP.
- **Input Format Conversion** — Convert between CIF, XYZ, POSCAR, XSF, and QE Input formats via ASE.
- **Premium UI** — Modern dark theme with glassmorphism-inspired components, animated splash screen, and notification system.
- **Keyboard Shortcuts** — Global shortcut system with a built-in overlay (`?` to toggle).
- **Standalone Build** — PyInstaller spec for packaging as a single executable on Windows and Linux.
- **Cross-Platform Support** — Full support for Windows and Ubuntu/Linux.

---

## [1.0.0] — 2025-01-01

### Added

- Initial release with basic QE input generation, local job execution, and output parsing.

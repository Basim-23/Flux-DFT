"""
Report Generator for FluxDFT.

Generates publication-ready reports in PDF and Markdown formats.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ReportSection:
    """A section in the report."""
    title: str
    content: str
    subsections: List["ReportSection"] = field(default_factory=list)
    figures: List[Path] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CalculationReport:
    """Complete calculation report."""
    title: str
    formula: str
    calculation_type: str
    timestamp: datetime
    
    # Sections
    input_parameters: Dict[str, Any] = field(default_factory=dict)
    results: Dict[str, Any] = field(default_factory=dict)
    validation: Dict[str, Any] = field(default_factory=dict)
    
    # Figures
    figures: List[Path] = field(default_factory=list)
    
    # Raw data
    input_file: Optional[str] = None
    output_file: Optional[str] = None


class ReportBuilder:
    """
    Builds reports from calculation data.
    
    Usage:
        builder = ReportBuilder()
        builder.set_title("Silicon SCF Calculation")
        builder.set_formula("Si")
        builder.add_input_parameters({'ecutwfc': 50, 'kpoints': '6x6x6'})
        builder.add_results({'total_energy': -7.89, 'band_gap': 1.11})
        
        # Generate reports
        builder.to_markdown("report.md")
        builder.to_pdf("report.pdf")
    """
    
    def __init__(self):
        self.report = CalculationReport(
            title="Calculation Report",
            formula="",
            calculation_type="scf",
            timestamp=datetime.now()
        )
    
    def set_title(self, title: str) -> "ReportBuilder":
        self.report.title = title
        return self
    
    def set_formula(self, formula: str) -> "ReportBuilder":
        self.report.formula = formula
        return self
    
    def set_calculation_type(self, calc_type: str) -> "ReportBuilder":
        self.report.calculation_type = calc_type
        return self
    
    def add_input_parameters(self, params: Dict[str, Any]) -> "ReportBuilder":
        self.report.input_parameters.update(params)
        return self
    
    def add_results(self, results: Dict[str, Any]) -> "ReportBuilder":
        self.report.results.update(results)
        return self
    
    def add_validation(self, validation: Dict[str, Any]) -> "ReportBuilder":
        self.report.validation.update(validation)
        return self
    
    def add_figure(self, path: Path) -> "ReportBuilder":
        self.report.figures.append(path)
        return self
    
    def set_input_file(self, content: str) -> "ReportBuilder":
        self.report.input_file = content
        return self
    
    def set_output_file(self, content: str) -> "ReportBuilder":
        self.report.output_file = content
        return self
    
    def to_markdown(self, output_path: Optional[Path] = None) -> str:
        """
        Generate Markdown report.
        
        Returns markdown string and optionally writes to file.
        """
        r = self.report
        
        lines = []
        
        # Header
        lines.append(f"# {r.title}")
        lines.append("")
        lines.append(f"**Formula:** {r.formula}")
        lines.append(f"**Calculation Type:** {r.calculation_type}")
        lines.append(f"**Generated:** {r.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
        # Input Parameters
        if r.input_parameters:
            lines.append("## Input Parameters")
            lines.append("")
            lines.append("| Parameter | Value |")
            lines.append("|-----------|-------|")
            for key, value in r.input_parameters.items():
                lines.append(f"| {key} | {value} |")
            lines.append("")
        
        # Results
        if r.results:
            lines.append("## Results")
            lines.append("")
            
            # Key results as cards
            for key, value in r.results.items():
                if isinstance(value, float):
                    lines.append(f"- **{key}:** {value:.6f}")
                else:
                    lines.append(f"- **{key}:** {value}")
            lines.append("")
        
        # Validation
        if r.validation:
            lines.append("## Validation")
            lines.append("")
            
            score = r.validation.get('score', 0)
            status = "✓ PASSED" if score >= 80 else "⚠ WARNING" if score >= 50 else "✗ FAILED"
            lines.append(f"**Status:** {status} (Score: {score}/100)")
            lines.append("")
            
            items = r.validation.get('items', [])
            if items:
                for item in items:
                    icon = "✓" if item.get('status') == 'pass' else "⚠" if item.get('status') == 'warning' else "✗"
                    lines.append(f"- {icon} {item.get('name', '')}: {item.get('message', '')}")
            lines.append("")
        
        # Figures
        if r.figures:
            lines.append("## Figures")
            lines.append("")
            for i, fig_path in enumerate(r.figures, 1):
                lines.append(f"![Figure {i}]({fig_path})")
                lines.append("")
        
        # Input File
        if r.input_file:
            lines.append("## Input File")
            lines.append("")
            lines.append("```fortran")
            lines.append(r.input_file[:2000])  # Truncate if too long
            if len(r.input_file) > 2000:
                lines.append("... (truncated)")
            lines.append("```")
            lines.append("")
        
        # Footer
        lines.append("---")
        lines.append("")
        lines.append("*Generated by FluxDFT*")
        
        markdown = "\n".join(lines)
        
        if output_path:
            Path(output_path).write_text(markdown)
        
        return markdown
    
    def to_html(self, output_path: Optional[Path] = None) -> str:
        """
        Generate HTML report.
        
        First generates markdown, then converts to HTML.
        """
        try:
            import markdown
            md_content = self.to_markdown()
            html_content = markdown.markdown(md_content, extensions=['tables', 'fenced_code'])
            
            # Wrap in HTML template
            html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{self.report.title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 40px;
            background: #f5f5f5;
            color: #333;
        }}
        h1 {{ color: #2563eb; }}
        h2 {{ color: #1e40af; border-bottom: 2px solid #e5e7eb; padding-bottom: 8px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
        th {{ background: #f0f0f0; }}
        code {{ background: #1e1e2e; color: #cdd6f4; padding: 2px 6px; border-radius: 4px; }}
        pre {{ background: #1e1e2e; color: #cdd6f4; padding: 16px; border-radius: 8px; overflow-x: auto; }}
        img {{ max-width: 100%; }}
    </style>
</head>
<body>
{html_content}
</body>
</html>"""
            
            if output_path:
                Path(output_path).write_text(html)
            
            return html
            
        except ImportError:
            logger.warning("markdown package not installed")
            return self.to_markdown(output_path)
    
    def to_pdf(self, output_path: Path) -> bool:
        """
        Generate PDF report.
        
        Requires weasyprint or reportlab.
        """
        try:
            from weasyprint import HTML
            
            html_content = self.to_html()
            HTML(string=html_content).write_pdf(str(output_path))
            return True
            
        except ImportError:
            logger.warning("weasyprint not installed. Trying alternative...")
            
            try:
                # Try markdown + pdfkit
                import pdfkit
                html_content = self.to_html()
                pdfkit.from_string(html_content, str(output_path))
                return True
            except ImportError:
                logger.error("No PDF generator available. Install weasyprint or pdfkit.")
                return False
        except Exception as e:
            logger.error(f"PDF generation failed: {e}")
            return False
    
    def to_json(self, output_path: Optional[Path] = None) -> str:
        """Export report data as JSON."""
        data = {
            'title': self.report.title,
            'formula': self.report.formula,
            'calculation_type': self.report.calculation_type,
            'timestamp': self.report.timestamp.isoformat(),
            'input_parameters': self.report.input_parameters,
            'results': self.report.results,
            'validation': self.report.validation,
            'figures': [str(p) for p in self.report.figures]
        }
        
        json_str = json.dumps(data, indent=2)
        
        if output_path:
            Path(output_path).write_text(json_str)
        
        return json_str


def generate_quick_report(
    input_file: Path,
    output_file: Path,
    results: Dict[str, Any],
    output_path: Path
) -> Path:
    """
    Quick helper to generate a report from calculation files.
    
    Returns path to generated markdown report.
    """
    builder = ReportBuilder()
    
    # Extract formula from input file name
    formula = input_file.stem.split('.')[0].upper()
    
    builder.set_title(f"{formula} Calculation Report")
    builder.set_formula(formula)
    
    # Read input file
    if input_file.exists():
        builder.set_input_file(input_file.read_text())
    
    # Add results
    builder.add_results(results)
    
    # Generate
    md_path = output_path / f"{formula}_report.md"
    builder.to_markdown(md_path)
    
    return md_path

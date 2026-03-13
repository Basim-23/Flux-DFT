"""
FluxDFT Main Entry Point
Copyright (c) 2026 Basim Nasser. MIT License.
"""

import sys
import os
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QSplashScreen, QMessageBox, QWidget
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QRect, pyqtProperty, QPoint
from PyQt6.QtGui import (
    QPixmap, QFont, QPainter, QColor, QLinearGradient, 
    QRadialGradient, QPen, QPainterPath, QBrush, QFontDatabase
)
import math
import random


class FluxSplashScreen(QWidget):
    """
    Premium animated splash screen for FluxDFT.
    Features: Animated particles, pulsing glow effects, smooth progress bar,
    glass-morphism design, and modern typography.
    """
    
    def __init__(self):
        super().__init__()
        
        # Window setup
        self.setWindowFlags(
            Qt.WindowType.SplashScreen | 
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(700, 450)
        
        # Animation state
        self._progress = 0.0
        self._glow_phase = 0.0
        self._message = "Initializing..."
        self._particles = []
        self._init_particles()
        
        # Animation timers
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate)
        self._animation_timer.start(16)  # ~60 FPS
        
        # Center on screen
        self._center_on_screen()
    
    def _center_on_screen(self):
        """Center the splash screen on the primary monitor."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geo = screen.geometry()
            x = (screen_geo.width() - self.width()) // 2
            y = (screen_geo.height() - self.height()) // 2
            self.move(x, y)
    
    def _init_particles(self):
        """Initialize floating particle system."""
        self._particles = []
        for _ in range(25):
            self._particles.append({
                'x': random.uniform(0, 700),
                'y': random.uniform(0, 450),
                'vx': random.uniform(-0.3, 0.3),
                'vy': random.uniform(-0.5, -0.1),
                'size': random.uniform(2, 5),
                'alpha': random.uniform(0.1, 0.4),
                'color_index': random.randint(0, 2)
            })
    
    def _animate(self):
        """Update animation state."""
        self._glow_phase += 0.03
        
        # Update particles
        for p in self._particles:
            p['x'] += p['vx']
            p['y'] += p['vy']
            
            # Wrap around
            if p['y'] < -10:
                p['y'] = 460
                p['x'] = random.uniform(0, 700)
            if p['x'] < -10:
                p['x'] = 710
            elif p['x'] > 710:
                p['x'] = -10
        
        self.update()
    
    def setProgress(self, value: float):
        """Set the progress bar value (0.0 to 1.0)."""
        self._progress = max(0.0, min(1.0, value))
        self.update()
    
    def showMessage(self, message: str):
        """Show a loading message on the splash screen."""
        self._message = message
        self.update()
    
    def paintEvent(self, event):
        """Render the premium splash screen."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        
        w, h = self.width(), self.height()
        
        # === BACKGROUND WITH DEPTH ===
        # Outer glow/shadow
        for i in range(8):
            opacity = 0.02 * (8 - i)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, int(opacity * 255)))
            painter.drawRoundedRect(i, i, w - 2*i, h - 2*i, 24 - i, 24 - i)
        
        # Main background gradient - ULTRA DARK
        bg_gradient = QLinearGradient(0, 0, w, h)
        bg_gradient.setColorAt(0.0, QColor("#050508"))
        bg_gradient.setColorAt(0.3, QColor("#080810"))
        bg_gradient.setColorAt(0.7, QColor("#060609"))
        bg_gradient.setColorAt(1.0, QColor("#030305"))
        painter.setBrush(bg_gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(0, 0, w, h, 20, 20)
        
        # Subtle noise/texture overlay via gradient spots
        for i in range(3):
            cx = 100 + i * 250
            cy = 100 + (i % 2) * 200
            radial = QRadialGradient(cx, cy, 200)
            phase_offset = self._glow_phase + i * 2.1
            pulse = 0.015 + 0.01 * math.sin(phase_offset)  # Subtle pulse
            
            colors = [
                QColor(89, 130, 200, int(pulse * 255)),   # Muted blue
                QColor(140, 120, 180, int(pulse * 255)),  # Muted purple
                QColor(180, 100, 130, int(pulse * 255)),  # Muted pink
            ]
            radial.setColorAt(0, colors[i % 3])
            radial.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setBrush(radial)
            painter.drawEllipse(int(cx - 200), int(cy - 200), 400, 400)
        
        # === FLOATING PARTICLES ===
        particle_colors = [
            QColor(137, 180, 250),  # Blue
            QColor(203, 166, 247),  # Purple
            QColor(166, 227, 161),  # Green
        ]
        for p in self._particles:
            color = particle_colors[p['color_index']]
            color.setAlphaF(p['alpha'])
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(
                int(p['x'] - p['size']/2), 
                int(p['y'] - p['size']/2),
                int(p['size']), 
                int(p['size'])
            )
        
        # === BORDER GLOW ===
        glow_intensity = 0.4 + 0.2 * math.sin(self._glow_phase)
        border_gradient = QLinearGradient(0, 0, w, 0)
        border_gradient.setColorAt(0.0, QColor(137, 180, 250, int(glow_intensity * 80)))
        border_gradient.setColorAt(0.5, QColor(203, 166, 247, int(glow_intensity * 120)))
        border_gradient.setColorAt(1.0, QColor(243, 139, 168, int(glow_intensity * 80)))
        
        pen = QPen(QBrush(border_gradient), 2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(1, 1, w - 2, h - 2, 20, 20)
        
        # === LOGO / TITLE ===
        # Draw glowing accent lines behind title
        line_y = 175
        accent_glow = QLinearGradient(80, 0, w - 80, 0)
        glow_alpha = int((0.6 + 0.3 * math.sin(self._glow_phase * 1.5)) * 255)
        accent_glow.setColorAt(0.0, QColor(137, 180, 250, 0))
        accent_glow.setColorAt(0.15, QColor(137, 180, 250, glow_alpha))
        accent_glow.setColorAt(0.5, QColor(203, 166, 247, glow_alpha))
        accent_glow.setColorAt(0.85, QColor(243, 139, 168, glow_alpha))
        accent_glow.setColorAt(1.0, QColor(243, 139, 168, 0))
        
        # Glow halo for accent line
        for offset in range(6, 0, -1):
            painter.setPen(Qt.PenStyle.NoPen)
            glow_rect_gradient = QLinearGradient(80, 0, w - 80, 0)
            base_alpha = int((glow_alpha / 255) * 20 * (7 - offset))
            glow_rect_gradient.setColorAt(0.0, QColor(137, 180, 250, 0))
            glow_rect_gradient.setColorAt(0.2, QColor(137, 180, 250, base_alpha))
            glow_rect_gradient.setColorAt(0.5, QColor(203, 166, 247, base_alpha))
            glow_rect_gradient.setColorAt(0.8, QColor(243, 139, 168, base_alpha))
            glow_rect_gradient.setColorAt(1.0, QColor(243, 139, 168, 0))
            painter.setBrush(glow_rect_gradient)
            painter.drawRect(80, line_y - offset, w - 160, 3 + offset * 2)
        
        # Main accent line
        painter.setBrush(accent_glow)
        painter.drawRect(80, line_y, w - 160, 3)
        
        # === TITLE TEXT ===
        # Title glow
        title_font = QFont("Segoe UI", 52, QFont.Weight.Bold)
        painter.setFont(title_font)
        
        # Multi-layer glow effect
        glow_colors = [
            (QColor(137, 180, 250, 30), 6),
            (QColor(137, 180, 250, 50), 4),
            (QColor(180, 200, 255, 80), 2),
        ]
        title_rect = QRect(0, 70, w, 100)
        for color, offset in glow_colors:
            painter.setPen(color)
            for dx in range(-offset, offset + 1, offset if offset else 1):
                for dy in range(-offset, offset + 1, offset if offset else 1):
                    painter.drawText(
                        title_rect.adjusted(dx, dy, dx, dy),
                        Qt.AlignmentFlag.AlignCenter,
                        "FluxDFT"
                    )
        
        # Main title with gradient
        title_gradient = QLinearGradient(0, 70, 0, 170)
        title_gradient.setColorAt(0.0, QColor("#ffffff"))
        title_gradient.setColorAt(0.5, QColor("#e0e6f4"))
        title_gradient.setColorAt(1.0, QColor("#b4befe"))
        painter.setPen(QPen(QBrush(title_gradient), 1))
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, "FluxDFT")
        
        # === TAGLINE ===
        tagline_font = QFont("Segoe UI", 13)
        tagline_font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 1.5)
        painter.setFont(tagline_font)
        painter.setPen(QColor("#8892b0"))
        painter.drawText(
            QRect(0, 195, w, 40),
            Qt.AlignmentFlag.AlignCenter,
            "Professional GUI for Quantum ESPRESSO"
        )
        
        # === PROGRESS BAR ===
        bar_y = 320
        bar_height = 4
        bar_margin = 100
        bar_width = w - 2 * bar_margin
        
        # Progress track (background)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(30, 30, 50, 180))
        painter.drawRoundedRect(bar_margin, bar_y, bar_width, bar_height, 2, 2)
        
        # Progress fill
        if self._progress > 0:
            fill_width = int(bar_width * self._progress)
            
            # Glow under progress bar
            progress_glow = QLinearGradient(bar_margin, 0, bar_margin + fill_width, 0)
            progress_glow.setColorAt(0. , QColor(137, 180, 250, 100))
            progress_glow.setColorAt(1.0, QColor(203, 166, 247, 100))
            painter.setBrush(progress_glow)
            painter.drawRoundedRect(bar_margin, bar_y - 3, fill_width, bar_height + 6, 4, 4)
            
            # Main progress bar
            progress_gradient = QLinearGradient(bar_margin, 0, bar_margin + fill_width, 0)
            progress_gradient.setColorAt(0.0, QColor("#89b4fa"))
            progress_gradient.setColorAt(0.5, QColor("#cba6f7"))
            progress_gradient.setColorAt(1.0, QColor("#f38ba8"))
            painter.setBrush(progress_gradient)
            painter.drawRoundedRect(bar_margin, bar_y, fill_width, bar_height, 2, 2)
            
            # Shimmer effect
            shimmer_x = (self._glow_phase * 100) % (fill_width + 60) - 30 + bar_margin
            if shimmer_x < bar_margin + fill_width:
                shimmer = QLinearGradient(shimmer_x - 30, 0, shimmer_x + 30, 0)
                shimmer.setColorAt(0.0, QColor(255, 255, 255, 0))
                shimmer.setColorAt(0.5, QColor(255, 255, 255, 100))
                shimmer.setColorAt(1.0, QColor(255, 255, 255, 0))
                painter.setBrush(shimmer)
                painter.drawRoundedRect(
                    int(max(bar_margin, shimmer_x - 30)), bar_y,
                    min(60, int(bar_margin + fill_width - shimmer_x + 30)), bar_height, 2, 2
                )
        
        # === STATUS MESSAGE ===
        status_font = QFont("Segoe UI", 11)
        painter.setFont(status_font)
        painter.setPen(QColor("#89b4fa"))
        painter.drawText(
            QRect(0, bar_y + 15, w, 30),
            Qt.AlignmentFlag.AlignCenter,
            self._message
        )
        
        # === FOOTER ===
        footer_font = QFont("Segoe UI", 10)
        painter.setFont(footer_font)
        painter.setPen(QColor("#2a2a3a"))  # Darker footer
        
        # Copyright
        painter.drawText(
            QRect(25, h - 40, 200, 25),
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
            "© 2026 FluxDFT"
        )
        
        # Version with subtle styling
        painter.drawText(
            QRect(w - 150, h - 40, 125, 25),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "Version 2.0.0"
        )
        
        painter.end()
    
    def close(self):
        """Clean up and close."""
        self._animation_timer.stop()
        super().close()




def main():
    """Main entry point for FluxDFT."""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    
    app = QApplication(sys.argv)
    app.setApplicationName("FluxDFT")
    app.setOrganizationName("FluxDFT")
    app.setApplicationVersion("2.0.0")
    
    # Apply Premium Scientific Theme
    try:
        from pathlib import Path
        theme_path = Path(__file__).parent / "ui" / "styles" / "scientific.qss"
        if theme_path.exists():
            with open(theme_path, "r") as f:
                app.setStyleSheet(f.read())
        else:
            # Fallback
            from .ui.theme import theme_manager
            theme_manager.apply_theme(app)
    except Exception as e:
        print(f"Failed to apply scientific theme: {e}")
    
    # Show splash screen
    splash = FluxSplashScreen()
    splash.show()
    splash.setProgress(0.1)
    splash.showMessage("Initializing...")
    app.processEvents()
    
    # Brief pause for visual effect
    import time
    time.sleep(0.3)
    
    splash.setProgress(0.4)
    splash.showMessage("Loading components...")
    app.processEvents()
    
    # Import main window (imports here to show splash during load)
    splash.setProgress(0.6)
    splash.showMessage("Loading interface...")
    app.processEvents()
    
    from .ui.main_window import MainWindow
    
    splash.setProgress(0.85)
    splash.showMessage("Starting FluxDFT...")
    app.processEvents()
    
    window = MainWindow()
    
    splash.setProgress(1.0)
    splash.showMessage("Ready!")
    app.processEvents()
    time.sleep(0.3)
    
    # Close splash and show main window maximized
    QTimer.singleShot(300, lambda: (splash.close(), window.showMaximized()))
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

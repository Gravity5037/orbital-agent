import os

# 1. Update orbital_vision.py with true Liquid Glass shaders & clipping
vision_code = """import sys, cv2
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtCore import QTimer, Qt, QRectF
from PyQt6.QtGui import QImage, QPainter, QPainterPath, QColor, QPen, QLinearGradient, QFont

class LiquidGlassLens(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(700, 500)
        self.setMinimumSize(340, 260)
        self.cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not self.cap.isOpened(): self.cap = cv2.VideoCapture(0)
        self.qr = cv2.QRCodeDetector()
        self.curr_frame, self.drag_start, self.hover_btn = None, None, None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.read_cam)
        self.timer.start(30)
        self.setMouseTracking(True)

    def read_cam(self):
        if not self.cap.isOpened(): return
        ret, frame = self.cap.read()
        if ret:
            val, pts, _ = self.qr.detectAndDecode(frame)
            if val and pts is not None:
                p = pts[0].astype(int)
                for i in range(len(p)): cv2.line(frame, tuple(p[i]), tuple(p[(i+1)%len(p)]), (0, 229, 255), 2)
                cv2.putText(frame, f'CODE: {val[:24]}', (p[0][0], max(25, p[0][1]-8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 229, 255), 2)
            self.curr_frame = frame
            self.update()

    def get_btn_rects(self):
        w = self.width()
        return {'close': QRectF(w-42, 14, 20, 20), 'max': QRectF(w-70, 14, 20, 20), 'min': QRectF(w-98, 14, 20, 20)}

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = QRectF(8, 8, self.width()-16, self.height()-16)
        path = QPainterPath()
        path.addRoundedRect(rect, 34.0, 34.0)
        p.save()
        p.setClipPath(path)

        bg = QLinearGradient(0, 0, 0, self.height())
        bg.setColorAt(0.0, QColor(255, 255, 255, 65))
        bg.setColorAt(0.09, QColor(16, 22, 34, 225))
        bg.setColorAt(1.0, QColor(8, 11, 18, 248))
        p.fillPath(path, bg)

        if self.curr_frame is not None:
            v_rect = QRectF(14, 48, self.width()-28, self.height()-62)
            vp = QPainterPath()
            vp.addRoundedRect(v_rect, 24.0, 24.0)
            p.save()
            p.setClipPath(vp)
            rgb = cv2.cvtColor(self.curr_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb.shape
            qimg = QImage(rgb.data, w, h, ch * w, QImage.Format.Format_RGB888)
            p.drawImage(v_rect, qimg)
            p.restore()
            p.strokePath(vp, QPen(QColor(255, 255, 255, 40), 1.2))

        pill = QRectF(22, 12, 195, 26)
        pill_p = QPainterPath()
        pill_p.addRoundedRect(pill, 13, 13)
        p_grad = QLinearGradient(0, 12, 0, 38)
        p_grad.setColorAt(0, QColor(255, 255, 255, 50))
        p_grad.setColorAt(1, QColor(255, 255, 255, 12))
        p.fillPath(pill_p, p_grad)
        p.strokePath(pill_p, QPen(QColor(255, 255, 255, 60), 1))
        p.setFont(QFont('Segoe UI', 8, QFont.Weight.DemiBold))
        p.setPen(QColor(255, 255, 255, 235))
        p.drawText(pill, Qt.AlignmentFlag.AlignCenter, '● OPTICAL LENS // EYE')

        btns = self.get_btn_rects()
        for name, r in btns.items():
            bp = QPainterPath()
            bp.addRoundedRect(r, 10, 10)
            hov = (self.hover_btn == name)
            col = (255, 80, 100) if name == 'close' else (255, 255, 255)
            p.fillPath(bp, QColor(col[0], col[1], col[2], 85 if hov else 35))
            p.strokePath(bp, QPen(QColor(col[0], col[1], col[2], 180 if hov else 70), 1))
            p.setPen(QColor(col[0], col[1], col[2], 245 if hov else 190))
            p.setFont(QFont('Segoe UI', 8, QFont.Weight.Bold))
            glyph = '–' if name == 'min' else ('⚲' if name == 'max' else '✕')
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, glyph)

        p.restore()
        glass_border = QLinearGradient(0, 0, 0, self.height())
        glass_border.setColorAt(0.0, QColor(255, 255, 255, 200))
        glass_border.setColorAt(0.18, QColor(255, 255, 255, 80))
        glass_border.setColorAt(0.85, QColor(0, 229, 255, 60))
        glass_border.setColorAt(1.0, QColor(0, 229, 255, 140))
        p.strokePath(path, QPen(glass_border, 1.8))

    def mousePressEvent(self, ev):
        pos = ev.position()
        btns = self.get_btn_rects()
        if btns['close'].contains(pos): self.close(); return
        elif btns['max'].contains(pos): self.showNormal() if self.isMaximized() else self.showMaximized(); return
        elif btns['min'].contains(pos): self.showMinimized(); return
        if pos.y() <= 48: self.drag_start = ev.globalPosition().toPoint()

    def mouseMoveEvent(self, ev):
        pos = ev.position()
        hovered = next((n for n, r in self.get_btn_rects().items() if r.contains(pos)), None)
        if hovered != self.hover_btn: self.hover_btn = hovered; self.update()
        if self.drag_start and ev.buttons() == Qt.MouseButton.LeftButton:
            delta = ev.globalPosition().toPoint() - self.drag_start
            self.move(self.pos() + delta)
            self.drag_start = ev.globalPosition().toPoint()

    def mouseReleaseEvent(self, ev): self.drag_start = None
    def closeEvent(self, ev):
        self.timer.stop()
        if self.cap.isOpened(): self.cap.release()
        ev.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    w = LiquidGlassLens()
    w.show()
    sys.exit(app.exec())
"""

with open(r"C:\Orbital\orbital_vision.py", "w", encoding="utf-8") as f:
    f.write(vision_code)
print("[✔] orbital_vision.py updated with Liquid Glass UI.")

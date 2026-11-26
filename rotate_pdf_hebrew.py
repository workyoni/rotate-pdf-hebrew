import io
import os
import re
import shutil
import sys
import threading
import tkinter as tk
import urllib.request
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import fitz  # PyMuPDF
from PIL import Image, ImageStat, ImageTk
import pytesseract

# אופציונלי: כתובת ישירה לקובץ ZIP מוכן של Tesseract ל-Windows (למשל מ-GitHub Releases)
TESSERACT_WIN_ZIP_URL = ""
HEB_TRAINEDDATA_URL = "https://github.com/tesseract-ocr/tessdata_fast/raw/main/heb.traineddata"


def get_app_data_dir() -> Path:
    """מחזיר תיקיית נתונים קבועה למשתמש ב-Windows או macOS."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path.home() / "Library" / "Application Support"
    app_dir = base / "RotatePdfHebrew"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def _set_tesseract_from_dir(tess_dir: Path) -> bool:
    """מגדיר tesseract ואת tessdata מתוך תיקייה קיימת אם הם קיימים."""
    exe_name = "tesseract.exe" if sys.platform == "win32" else "tesseract"
    exe_path = tess_dir / exe_name
    tessdata_dir = tess_dir / "tessdata"
    if exe_path.exists():
        pytesseract.pytesseract.tesseract_cmd = str(exe_path)
        if tessdata_dir.exists():
            os.environ["TESSDATA_PREFIX"] = str(tessdata_dir)
        return True
    return False


def _find_existing_tesseract() -> bool:
    """בודק אם Tesseract כבר הורד לתיקיית האפליקציה או מותקן במערכת."""
    if _set_tesseract_from_dir(get_app_data_dir() / "tesseract"):
        return True

    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    if _set_tesseract_from_dir(base_path / "tesseract_bundle"):
        return True

    if shutil.which("tesseract"):
        return True

    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        "/opt/homebrew/bin/tesseract",
        "/usr/local/bin/tesseract",
    ]
    for path in candidates:
        if os.path.exists(path):
            pytesseract.pytesseract.tesseract_cmd = path
            tessdata_guess = Path(path).parent / "tessdata"
            if tessdata_guess.exists() and "TESSDATA_PREFIX" not in os.environ:
                os.environ["TESSDATA_PREFIX"] = str(tessdata_guess)
            return True

    return False


def ensure_tesseract_available() -> None:
    """מוודא שיש מנוע OCR זמין; אם חסר, מציע להוריד אותו פעם אחת."""
    if _find_existing_tesseract():
        return

    answer = messagebox.askyesno(
        "הורדת מנוע זיהוי טקסט (OCR)",
        "מנוע זיהוי הטקסט בעברית (Tesseract) לא נמצא במחשב.\n"
        "האם להוריד ולהתקין אותו כעת לתיקיית המשתמש (פעם אחת בלבד)?",
    )
    if not answer:
        return

    target_dir = get_app_data_dir() / "tesseract"
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        if sys.platform == "win32" and TESSERACT_WIN_ZIP_URL:
            zip_path = get_app_data_dir() / "tesseract_win.zip"
            urllib.request.urlretrieve(TESSERACT_WIN_ZIP_URL, zip_path)
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(target_dir)
            zip_path.unlink(missing_ok=True)
            _set_tesseract_from_dir(target_dir)
        else:
            tessdata_dir = target_dir / "tessdata"
            tessdata_dir.mkdir(parents=True, exist_ok=True)
            urllib.request.urlretrieve(HEB_TRAINEDDATA_URL, tessdata_dir / "heb.traineddata")
            os.environ["TESSDATA_PREFIX"] = str(tessdata_dir)

        messagebox.showinfo("הושלם", "ההורדה הסתיימה בהצלחה.")
    except Exception as exc:
        messagebox.showwarning(
            "שגיאה בהורדה",
            f"לא ניתן להוריד את חבילת ה-OCR כעת:\n{exc}\n\n"
            "התוכנה עדיין תפעל, אך סיבוב ידני יידרש לעמודים ללא זיהוי אוטומטי.",
        )


def is_blank_page(img: Image.Image, white_threshold: int = 245, non_white_ratio_limit: float = 0.003) -> bool:
    """
    בודק אם הדף חלק (לבן כמעט לחלוטין).
    מתעלם מ-2% שוליים כדי שלא יוטעה ממסגרות סריקה דקות.
    """
    gray = img.convert("L")
    w, h = gray.size
    margin_x = int(w * 0.02)
    margin_y = int(h * 0.02)
    if w > 40 and h > 40:
        gray = gray.crop((margin_x, margin_y, w - margin_x, h - margin_y))

    stat = ImageStat.Stat(gray)
    # אם סטיית התקן אפסית והממוצע בהיר מאוד — הדף חלק לגמרי
    if stat.stddev[0] < 3.0 and stat.mean[0] > 240:
        return True

    hist = gray.histogram()
    total_pixels = sum(hist)
    if total_pixels == 0:
        return True

    dark_pixels = sum(hist[:white_threshold])
    return (dark_pixels / total_pixels) < non_white_ratio_limit


def ensure_portrait_angle(page: fitz.Page) -> int:
    """
    מחזיר 90 אם העמוד כרגע לרוחב (Landscape) כדי להעמיד אותו למצב אנכי (Portrait),
    או 0 אם העמוד כבר אנכי.
    """
    rect = page.rect  # כבר משקלל את page.rotation הקיים בקובץ
    if rect.width > rect.height:
        return 90
    return 0


def count_readable_chars(img: Image.Image) -> int:
    """סופר תווים קריאים בעברית או באנגלית ב-OCR מהיר."""
    try:
        txt = pytesseract.image_to_string(img, lang="heb+eng", config="--psm 6")
        return len(re.findall(r"[\u0590-\u05FFA-Za-z0-9]", txt))
    except pytesseract.TesseractError:
        try:
            txt = pytesseract.image_to_string(img, lang="heb", config="--psm 6")
            return len(re.findall(r"[\u0590-\u05FF0-9]", txt))
        except pytesseract.TesseractError:
            return 0


def count_hebrew_chars(img: Image.Image) -> int:
    """סופר כמה תווים בעברית מזוהים ב-OCR מהיר."""
    try:
        txt = pytesseract.image_to_string(img, lang="heb", config="--psm 6")
        return len(re.findall(r"[\u0590-\u05FF]", txt))
    except pytesseract.TesseractError:
        return 0


def detect_rotation_angle(page: fitz.Page, dpi: int = 220) -> int:
    """
    מזהה כמה מעלות בכיוון השעון יש לסובב את העמוד כדי ליישר אותו.
    אם הדף חלק או שלא מזוהה כיוון אותיות ברור — מיישר למצב אנכי (Portrait).
    מחזיר 0, 90, 180 או 270.
    """
    pix = page.get_pixmap(dpi=dpi)
    img = Image.open(io.BytesIO(pix.tobytes("png")))

    # 1. בדיקת דף חלק -> יישור למצב אנכי
    if is_blank_page(img):
        return ensure_portrait_angle(page)

    # 2. ניסיון זיהוי OSD מובנה של Tesseract
    osd_text = ""
    for lang in ("heb+eng", "eng", None):
        try:
            osd_text = (
                pytesseract.image_to_osd(img, lang=lang)
                if lang
                else pytesseract.image_to_osd(img)
            )
            if osd_text:
                break
        except pytesseract.TesseractError:
            continue

    match = re.search(r"Rotate:\s*(\d+)", osd_text) if osd_text else None
    if match:
        angle = int(match.group(1)) % 360
        rotated_candidate = img if angle == 0 else img.rotate(-angle, expand=True)

        # מוודא שאכן יש טקסט קריא בכיוון שזוהה (כדי למנוע זיהוי שגוי על קווים/חתימות)
        if count_readable_chars(rotated_candidate) >= 5:
            if angle in (0, 180):
                rot_0 = count_hebrew_chars(img)
                rot_180 = count_hebrew_chars(img.rotate(180, expand=True))
                if rot_180 > rot_0 * 1.3 and rot_180 >= 5:
                    return 180
                return 0
            return angle

    # 3. גיבוי: בדיקת 4 כיוונים לפי כמות תווים קריאים
    best_angle = 0
    best_score = -1
    for candidate in (0, 90, 180, 270):
        rotated = img if candidate == 0 else img.rotate(-candidate, expand=True)
        score = count_readable_chars(rotated)
        if score > best_score:
            best_score = score
            best_angle = candidate

    # אם לא זוהו מספיק אותיות ברורות -> מיישר למצב אנכי
    if best_score < 5:
        return ensure_portrait_angle(page)

    return best_angle


class PdfStraightenerApp:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("מיישר קבצי PDF בעברית")
        self.root.geometry("1120x740")
        self.root.minsize(900, 620)

        ensure_tesseract_available()

        self.files_data: list[dict] = []
        self.current_file_idx: int = 0
        self.current_page_idx: int = 0
        self.tk_photo: ImageTk.PhotoImage | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        top_frame = ttk.Frame(self.root, padding=10)
        top_frame.pack(fill=tk.X)

        ttk.Button(top_frame, text="בחר קובץ PDF", command=self.pick_file).pack(side=tk.RIGHT, padx=4)
        ttk.Button(top_frame, text="בחר תיקייה", command=self.pick_folder).pack(side=tk.RIGHT, padx=4)
        self.btn_auto = ttk.Button(
            top_frame, text="יישר הכל אוטומטית", command=self.start_auto_straighten, state=tk.DISABLED
        )
        self.btn_auto.pack(side=tk.RIGHT, padx=10)

        self.btn_save = ttk.Button(
            top_frame, text="שמור קבצים מיושרים", command=self.save_all, state=tk.DISABLED
        )
        self.btn_save.pack(side=tk.LEFT, padx=4)

        status_frame = ttk.Frame(self.root, padding=(10, 0, 10, 6))
        status_frame.pack(fill=tk.X)
        self.status_var = tk.StringVar(value="בחר קובץ PDF או תיקייה כדי להתחיל.")
        ttk.Label(status_frame, textvariable=self.status_var, anchor="e").pack(side=tk.RIGHT)
        self.progress = ttk.Progressbar(status_frame, mode="determinate", length=260)
        self.progress.pack(side=tk.LEFT)

        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        preview_panel = ttk.Frame(main_pane, padding=8)
        main_pane.add(preview_panel, weight=3)

        self.page_info_var = tk.StringVar(value="אין עמוד מוצג")
        ttk.Label(preview_panel, textvariable=self.page_info_var, font=("Arial", 11, "bold")).pack(pady=(0, 6))

        self.canvas = tk.Canvas(preview_panel, bg="#2b2b2b", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", lambda _e: self.render_preview())

        controls_frame = ttk.Frame(preview_panel, padding=(0, 8, 0, 0))
        controls_frame.pack(fill=tk.X)

        ttk.Button(controls_frame, text="עמוד קודם ◄", command=self.prev_page).pack(side=tk.RIGHT, padx=4)
        ttk.Button(controls_frame, text="► עמוד הבא", command=self.next_page).pack(side=tk.RIGHT, padx=4)

        ttk.Separator(controls_frame, orient=tk.VERTICAL).pack(side=tk.RIGHT, fill=tk.Y, padx=10)

        ttk.Button(controls_frame, text="סובב 90° שמאלה ↺", command=lambda: self.rotate_current(-90)).pack(
            side=tk.RIGHT, padx=4
        )
        ttk.Button(controls_frame, text="סובב 90° ימינה ↻", command=lambda: self.rotate_current(90)).pack(
            side=tk.RIGHT, padx=4
        )
        ttk.Button(controls_frame, text="הפוך 180°", command=lambda: self.rotate_current(180)).pack(
            side=tk.RIGHT, padx=4
        )
        ttk.Button(controls_frame, text="אפס עמוד (0°)", command=self.reset_current_page).pack(
            side=tk.LEFT, padx=4
        )

        right_panel = ttk.Frame(main_pane, padding=8)
        main_pane.add(right_panel, weight=1)

        ttk.Label(right_panel, text="קבצי PDF:", font=("Arial", 10, "bold")).pack(anchor="e")
        self.file_listbox = tk.Listbox(right_panel, height=10, exportselection=False)
        self.file_listbox.pack(fill=tk.X, pady=(2, 10))
        self.file_listbox.bind("<<ListboxSelect>>", self.on_file_select)

        ttk.Label(right_panel, text="עמודים בקובץ הנבחר:", font=("Arial", 10, "bold")).pack(anchor="e")
        self.page_listbox = tk.Listbox(right_panel, exportselection=False)
        self.page_listbox.pack(fill=tk.BOTH, expand=True, pady=(2, 0))
        self.page_listbox.bind("<<ListboxSelect>>", self.on_page_select)

    def _clear_docs(self) -> None:
        for item in self.files_data:
            try:
                item["doc"].close()
            except Exception:
                pass
        self.files_data.clear()
        self.file_listbox.delete(0, tk.END)
        self.page_listbox.delete(0, tk.END)
        self.canvas.delete("all")
        self.page_info_var.set("אין עמוד מוצג")

    def _load_paths(self, paths: list[Path]) -> None:
        self._clear_docs()
        valid_pdfs: list[Path] = []
        for p in sorted(paths):
            if p.is_file() and p.suffix.lower() == ".pdf":
                valid_pdfs.append(p)
            elif p.is_dir():
                valid_pdfs.extend(sorted(p.rglob("*.pdf")))

        if not valid_pdfs:
            messagebox.showwarning("לא נמצאו קבצים", "לא נמצאו קבצי PDF תקינים בבחירה.")
            return

        for pdf_path in valid_pdfs:
            try:
                doc = fitz.open(pdf_path)
                self.files_data.append(
                    {
                        "path": pdf_path,
                        "doc": doc,
                        "rotations": [0] * len(doc),
                    }
                )
                self.file_listbox.insert(tk.END, f"{pdf_path.name} ({len(doc)} עמ')")
            except Exception as exc:
                messagebox.showerror("שגיאת פתיחה", f"לא ניתן לפתוח את {pdf_path.name}:\n{exc}")

        if self.files_data:
            self.current_file_idx = 0
            self.current_page_idx = 0
            self.file_listbox.selection_set(0)
            self._refresh_page_listbox()
            self.render_preview()
            self.btn_auto.config(state=tk.NORMAL)
            self.btn_save.config(state=tk.NORMAL)
            self.status_var.set(f"נטענו {len(self.files_data)} קבצי PDF. אפשר ליישר אוטומטית או לעבור לעמודים.")

    def pick_file(self) -> None:
        file_str = filedialog.askopenfilename(
            title="בחר קובץ PDF",
            filetypes=[("PDF Files", "*.pdf"), ("All Files", "*.*")],
        )
        if file_str:
            self._load_paths([Path(file_str)])

    def pick_folder(self) -> None:
        folder_str = filedialog.askdirectory(title="בחר תיקייה עם קבצי PDF")
        if folder_str:
            self._load_paths([Path(folder_str)])

    def _refresh_page_listbox(self) -> None:
        self.page_listbox.delete(0, tk.END)
        if not self.files_data:
            return
        fdata = self.files_data[self.current_file_idx]
        for idx, rot in enumerate(fdata["rotations"]):
            rot_label = f" [+{rot}°]" if rot % 360 != 0 else ""
            self.page_listbox.insert(tk.END, f"עמוד {idx + 1}{rot_label}")
        if fdata["rotations"]:
            self.page_listbox.selection_set(self.current_page_idx)
            self.page_listbox.see(self.current_page_idx)

    def on_file_select(self, _event: object) -> None:
        sel = self.file_listbox.curselection()
        if not sel:
            return
        self.current_file_idx = sel[0]
        self.current_page_idx = 0
        self._refresh_page_listbox()
        self.render_preview()

    def on_page_select(self, _event: object) -> None:
        sel = self.page_listbox.curselection()
        if not sel:
            return
        self.current_page_idx = sel[0]
        self.render_preview()

    def prev_page(self) -> None:
        if not self.files_data:
            return
        total = len(self.files_data[self.current_file_idx]["doc"])
        if self.current_page_idx > 0:
            self.current_page_idx -= 1
            self._refresh_page_listbox()
            self.render_preview()
        elif total > 0:
            self.current_page_idx = total - 1
            self._refresh_page_listbox()
            self.render_preview()

    def next_page(self) -> None:
        if not self.files_data:
            return
        total = len(self.files_data[self.current_file_idx]["doc"])
        if self.current_page_idx < total - 1:
            self.current_page_idx += 1
        else:
            self.current_page_idx = 0
        self._refresh_page_listbox()
        self.render_preview()

    def rotate_current(self, delta_deg: int) -> None:
        if not self.files_data:
            return
        rots = self.files_data[self.current_file_idx]["rotations"]
        rots[self.current_page_idx] = (rots[self.current_page_idx] + delta_deg) % 360
        self._refresh_page_listbox()
        self.render_preview()

    def reset_current_page(self) -> None:
        if not self.files_data:
            return
        self.files_data[self.current_file_idx]["rotations"][self.current_page_idx] = 0
        self._refresh_page_listbox()
        self.render_preview()

    def render_preview(self) -> None:
        if not self.files_data:
            return
        fdata = self.files_data[self.current_file_idx]
        doc = fdata["doc"]
        if len(doc) == 0:
            return

        page = doc[self.current_page_idx]
        extra_rot = fdata["rotations"][self.current_page_idx]
        total_visual_rot = (page.rotation + extra_rot) % 360

        pix = page.get_pixmap(dpi=130)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        if extra_rot != 0:
            img = img.rotate(-extra_rot, expand=True)

        cw = max(self.canvas.winfo_width(), 200)
        ch = max(self.canvas.winfo_height(), 200)
        img.thumbnail((cw - 20, ch - 20), Image.Resampling.LANCZOS)

        self.tk_photo = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(cw // 2, ch // 2, anchor=tk.CENTER, image=self.tk_photo)

        self.page_info_var.set(
            f"{fdata['path'].name}  |  עמוד {self.current_page_idx + 1} מתוך {len(doc)}  |  "
            f"סיבוב ידני: +{extra_rot}° (סה\"כ כיוון עמוד: {total_visual_rot}°)"
        )

    def start_auto_straighten(self) -> None:
        if not self.files_data:
            return
        self.btn_auto.config(state=tk.DISABLED)
        self.btn_save.config(state=tk.DISABLED)
        threading.Thread(target=self._auto_straighten_worker, daemon=True).start()

    def _auto_straighten_worker(self) -> None:
        total_pages = sum(len(f["doc"]) for f in self.files_data)
        self.root.after(0, lambda: self.progress.config(maximum=max(total_pages, 1), value=0))

        done = 0
        for f_idx, fdata in enumerate(self.files_data):
            doc = fdata["doc"]
            for p_idx in range(len(doc)):
                done += 1
                page_label = f"{fdata['path'].name} - עמוד {p_idx + 1}/{len(doc)}"
                self.root.after(0, lambda lbl=page_label, val=done: (
                    self.status_var.set(f"מזהה

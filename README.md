# מיישר קבצי PDF בעברית (MeyasherPDF)

תוכנת שולחן עבודה ל-Windows ליישור אוטומטי של קובצי PDF בעברית למצב קריאה, עם תצוגה מקדימה לסיבוב ידני של עמודים שפוספסו. מיועדת למשתמשים ללא ידע טכני.

## תכונות עיקריות

* **יישור אוטומטי בעברית:** זיהוי כיוון (0°, 90°, 180°, 270°) עם מנגנון גיבוי לעמודים בעברית או עם מעט טקסט.
* **קובץ בודד או תיקייה מלאה:** טעינת קובץ PDF יחיד או תיקייה (כולל תתי-תיקיות).
* **תצוגה מקדימה וסיבוב ידני:** מעבר בין קבצים ועמודים, סיבוב ב-90° שמאלה/ימינה, הפיכה ב-180° או איפוס לפני השמירה.
* **שמירה ללא אובדן איכות:** סיבוב דפי ה-PDF ושמירת קבצים חדשים (`_straightened.pdf`).

## התקנה והפעלה (משתמשי קצה ב-Windows)

1. הורד את קובץ ההפעלה `MeyasherPDF.exe` (או חלץ אותו מתוך קובץ ה-ZIP).
2. אם Windows SmartScreen מציג אזהרת אבטחה לקובץ חדש, לחץ על **More info** ואז על **Run anyway**.
3. הפעל את `MeyasherPDF.exe` בלחיצה כפולה — אין צורך להתקין Python או כלי עזר נוספים.

## הרצה מפתחים / הרצה מקוד המקור

```powershell
pip install pymupdf pillow pytesseract
python meyasher_pdf.py

```

*(ודא ש-Tesseract OCR מותקן במערכת עם חבילת השפה העברית `heb`.)*

## דוגמאות שימוש

* **דוגמה 1 – מסמך סרוק בודד הפוך:** לחץ על **בחר קובץ PDF**, בחר את המסמך, לחץ על **יישר הכל אוטומטית**, בדוק בתצוגה המקדימה ותקן עמוד שפוספס בעזרת כפתורי הסיבוב (`90° שמאלה` / `90° ימינה` / `הפוך 180°`). לבסוף לחץ על **שמור קבצים מיושרים**.
* **דוגמה 2 – תיקייה עם עשרות סריקות משרדיות:** לחץ על **בחר תיקייה** ובחר תיקייה הכוללת תתי-תיקיות של קובצי PDF. הרץ **יישר הכל אוטומטית**, עבור בין הקבצים ברשימה הימנית לוידוא שכל העמודים ישרים, ושמור את כל הקבצים המיושרים לתיקיית יעד.

---

# Hebrew PDF Straightener (MeyasherPDF)

A Windows desktop app that automatically rotates Hebrew PDF pages into a readable orientation and provides a visual preview for manually rotating missed pages. Built for non-technical users.

## Key Features

* **Hebrew-aware auto-rotation:** Detects page orientation (0°, 90°, 180°, 270°) with a Hebrew character fallback for tricky or low-text pages.
* **Single file or full folder:** Load an individual PDF or a folder (including subfolders).
* **Visual preview and manual rotation:** Browse files and pages, rotate 90° left/right, flip 180°, or reset before saving.
* **Clean PDF output:** Rotates pages and saves new files with the `_straightened.pdf` suffix.

## Installation & Usage (Non-Technical Windows Users)

1. Download `MeyasherPDF.exe` (or extract it from the downloaded ZIP archive).
2. If Windows SmartScreen displays a warning on first launch, click **More info** and then **Run anyway**.
3. Double-click `MeyasherPDF.exe` to open—no Python or extra installations required.

## Running from Source (Developers)

```powershell
pip install pymupdf pillow pytesseract
python meyasher_pdf.py

```

*(Ensure Tesseract OCR is installed along with the Hebrew language pack `heb`.)*

## Usage Examples

* **Example 1 – Single rotated scan:** Click **בחר קובץ PDF**, select your file, click **יישר הכל אוטומטית**, inspect the preview, manually rotate any missed page (`90° שמאלה`, `90° ימינה`, or `הפוך 180°`), and click **שמור קבצים מיושרים**.
* **Example 2 – Batch folder of scanned PDFs:** Click **בחר תיקייה** and choose a folder containing PDFs and subfolders. Run **יישר הכל אוטומטית**, switch between files in the right-hand list to verify pages, and save all straightened files to an output folder.

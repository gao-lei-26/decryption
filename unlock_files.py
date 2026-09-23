# -*- coding: utf-8 -*-
"""
批量文件去密码工具
支持：PDF / MS Office / WPS / OpenDocument / ZIP / 7Z / RAR
用法：把多个文件一起拖到 批量解密文件.bat 上，或直接运行本脚本后点“添加文件”。
"""

import sys
import os
import shutil

# ---------- 依赖检查 ----------
try:
    import fitz  # PyMuPDF
    HAVE_PDF = True
except ImportError:
    HAVE_PDF = False

try:
    import msoffcrypto
    HAVE_OFFICE = True
except ImportError:
    HAVE_OFFICE = False

try:
    import pyzipper
    HAVE_ZIP = True
except ImportError:
    HAVE_ZIP = False

try:
    import py7zr
    HAVE_7Z = True
except ImportError:
    HAVE_7Z = False

try:
    import rarfile
    HAVE_RAR = True
except ImportError:
    HAVE_RAR = False

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter.scrolledtext import ScrolledText


# ---------- 格式分类 ----------
PDF_EXTS = {".pdf"}
MS_OFFICE_EXTS = {".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls"}
WPS_EXTS = {".wps", ".et", ".dps"}
ODF_EXTS = {".odt", ".ods", ".odp"}
OFFICE_EXTS = MS_OFFICE_EXTS | WPS_EXTS | ODF_EXTS
ZIP_EXTS = {".zip"}
SEVEN_Z_EXTS = {".7z"}
RAR_EXTS = {".rar"}
ARCHIVE_EXTS = ZIP_EXTS | SEVEN_Z_EXTS | RAR_EXTS
ALL_EXTS = PDF_EXTS | OFFICE_EXTS | ARCHIVE_EXTS


def detect_type(path):
    ext = os.path.splitext(path)[1].lower()
    if ext in PDF_EXTS:
        return "pdf"
    if ext in MS_OFFICE_EXTS:
        return "office"
    if ext in WPS_EXTS:
        return "wps"
    if ext in ODF_EXTS:
        return "odf"
    if ext in ZIP_EXTS:
        return "zip"
    if ext in SEVEN_Z_EXTS:
        return "7z"
    if ext in RAR_EXTS:
        return "rar"
    return None


def _unique_path(path):
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    i = 1
    while True:
        new = f"{base}({i}){ext}"
        if not os.path.exists(new):
            return new
        i += 1


def _unique_dir(path):
    if not os.path.exists(path):
        return path
    i = 1
    while True:
        new = f"{path}({i})"
        if not os.path.exists(new):
            return new
        i += 1


def _safe_extract_zip(zf, out_dir):
    """安全解压 zip，防止路径遍历"""
    abs_out = os.path.abspath(out_dir)
    for member in zf.namelist():
        member_path = os.path.join(out_dir, member)
        abs_member = os.path.abspath(member_path)
        if not abs_member.startswith(abs_out + os.sep) and abs_member != abs_out:
            raise Exception(f"检测到不安全的路径: {member}")
    zf.extractall(out_dir)


def _safe_extract_7z(z, out_dir):
    """安全解压 7z"""
    abs_out = os.path.abspath(out_dir)
    for member in z.getnames():
        member_path = os.path.join(out_dir, member)
        abs_member = os.path.abspath(member_path)
        if not abs_member.startswith(abs_out + os.sep) and abs_member != abs_out:
            raise Exception(f"检测到不安全的路径: {member}")
    z.extractall(path=out_dir)


def _safe_extract_rar(rf, out_dir):
    """安全解压 rar"""
    abs_out = os.path.abspath(out_dir)
    for member in rf.namelist():
        member_path = os.path.join(out_dir, member)
        abs_member = os.path.abspath(member_path)
        if not abs_member.startswith(abs_out + os.sep) and abs_member != abs_out:
            raise Exception(f"检测到不安全的路径: {member}")
    rf.extractall(out_dir)


# ---------- 各类型解密 ----------

def unlock_pdf(path, password, out_path):
    doc = fitz.open(path)
    try:
        if doc.needs_pass:
            if not doc.authenticate(password):
                return False, "密码错误或为空"
        doc.save(out_path, encryption=fitz.PDF_ENCRYPT_NONE)
    finally:
        doc.close()
    return True, "成功"


def unlock_office_like(path, password, out_path):
    """MS Office / WPS / ODF 统一走 msoffcrypto 尝试"""
    with open(path, "rb") as f:
        office = msoffcrypto.OfficeFile(f)
        if not office.is_encrypted():
            shutil.copy2(path, out_path)
            return True, "未加密，已复制"
        try:
            office.load_key(password=password, verify_password=True)
        except Exception as e:
            return False, f"密码错误或格式不受支持: {e.__class__.__name__}"
        with open(out_path, "wb") as out:
            office.decrypt(out)
    return True, "成功"


def unlock_zip(path, password, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    try:
        with pyzipper.AESZipFile(path, "r") as zf:
            zf.pwd = password.encode("utf-8")
            names = zf.namelist()
            test_file = None
            for n in names:
                if not n.endswith('/'):
                    test_file = n
                    break
            if test_file:
                try:
                    zf.read(test_file)
                except RuntimeError as e:
                    return False, f"密码错误或压缩包损坏: {e}"
            _safe_extract_zip(zf, out_dir)
    except Exception as e:
        return False, f"解压失败: {e.__class__.__name__}: {e}"
    return True, f"已解压到 {os.path.basename(out_dir)}"


def unlock_7z(path, password, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    try:
        with py7zr.SevenZipFile(path, mode="r", password=password) as z:
            _safe_extract_7z(z, out_dir)
    except Exception as e:
        return False, f"密码错误或解压失败: {e.__class__.__name__}: {e}"
    return True, f"已解压到 {os.path.basename(out_dir)}"


def unlock_rar(path, password, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    try:
        with rarfile.RarFile(path) as rf:
            rf.setpassword(password)
            _safe_extract_rar(rf, out_dir)
    except rarfile.BadRarFile:
        return False, "不是有效的 RAR 文件"
    except rarfile.PasswordRequired:
        return False, "密码错误或为空"
    except rarfile.NeedFirstVolume:
        return False, "这是分卷压缩包，请提供第一卷"
    except Exception as e:
        return False, f"解压失败（可能需要安装 unrar）: {e.__class__.__name__}: {e}"
    return True, f"已解压到 {os.path.basename(out_dir)}"


# ---------- 统一入口 ----------

def unlock_one(path, password):
    kind = detect_type(path)
    if kind is None:
        return False, "不支持的文件类型", None

    base, ext = os.path.splitext(path)

    try:
        if kind in ("pdf", "office", "wps", "odf"):
            out_path = _unique_path(base + "_无密码" + ext)
            if kind == "pdf":
                if not HAVE_PDF:
                    return False, "未安装 PyMuPDF", None
                ok, msg = unlock_pdf(path, password, out_path)
            else:
                if not HAVE_OFFICE:
                    return False, "未安装 msoffcrypto-tool", None
                ok, msg = unlock_office_like(path, password, out_path)
            if ok:
                return True, "成功", out_path
            return False, msg, None

        if kind == "zip":
            if not HAVE_ZIP:
                return False, "未安装 pyzipper", None
            out_dir = _unique_dir(base)
            ok, msg = unlock_zip(path, password, out_dir)
            return ok, msg, out_dir if ok else None

        if kind == "7z":
            if not HAVE_7Z:
                return False, "未安装 py7zr", None
            out_dir = _unique_dir(base)
            ok, msg = unlock_7z(path, password, out_dir)
            return ok, msg, out_dir if ok else None

        if kind == "rar":
            if not HAVE_RAR:
                return False, "未安装 rarfile", None
            out_dir = _unique_dir(base)
            ok, msg = unlock_rar(path, password, out_dir)
            return ok, msg, out_dir if ok else None

    except Exception as e:
        return False, f"异常: {e.__class__.__name__}: {e}", None

    return False, "未知错误", None


# ---------- GUI ----------

TYPE_LABEL = {
    "pdf": "PDF",
    "office": "Office",
    "wps": "WPS",
    "odf": "ODF",
    "zip": "ZIP",
    "7z": "7Z",
    "rar": "RAR",
}


class UnlockApp:
    def __init__(self, root, files):
        self.root = root
        self.root.title("批量文件去密码（PDF / Word / PPT / Excel / WPS / ODF / 压缩包）")
        self.root.geometry("1020x640")
        self.rows = []

        self._build_ui()

        for f in files:
            self._add_row(f)
        self._update_status()

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)
        ttk.Label(
            top,
            text="为每个文件输入密码（打开不需要密码的可留空）",
            font=("Microsoft YaHei", 11, "bold")
        ).pack(anchor=tk.W)

        btns = ttk.Frame(self.root, padding=(10, 0))
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="添加文件...", command=self.add_files).pack(side=tk.LEFT)
        ttk.Button(btns, text="添加文件夹...", command=self.add_folder).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="清空列表", command=self.clear_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="全部显示密码", command=self.show_all).pack(side=tk.LEFT, padx=5)
        ttk.Button(btns, text="全部隐藏密码", command=self.hide_all).pack(side=tk.LEFT, padx=5)

        header = ttk.Frame(self.root, padding=(10, 5))
        header.pack(fill=tk.X)
        ttk.Label(header, text="类型", width=8, anchor=tk.W,
                  font=("Microsoft YaHei", 9, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, text="文件名", width=34, anchor=tk.W,
                  font=("Microsoft YaHei", 9, "bold")).pack(side=tk.LEFT)
        ttk.Label(header, text="密码", width=28, anchor=tk.W,
                  font=("Microsoft YaHei", 9, "bold")).pack(side=tk.LEFT, padx=5)
        ttk.Label(header, text="所在文件夹", anchor=tk.W,
                  font=("Microsoft YaHei", 9, "bold")).pack(side=tk.LEFT, padx=5)

        container = ttk.Frame(self.root)
        container.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.scroll_frame = ttk.Frame(canvas)
        self.scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        bottom = ttk.Frame(self.root, padding=10)
        bottom.pack(fill=tk.X, side=tk.BOTTOM)
        self.status = ttk.Label(bottom, text="共 0 个文件")
        self.status.pack(side=tk.LEFT)
        self.start_btn = ttk.Button(bottom, text="开始解密", command=self.start)
        self.start_btn.pack(side=tk.RIGHT)

    def _add_row(self, path):
        path = os.path.abspath(path)
        for p, _, _ in self.rows:
            if os.path.abspath(p) == path:
                return
        kind = detect_type(path)
        if kind is None:
            return

        row = ttk.Frame(self.scroll_frame)
        row.pack(fill=tk.X, pady=3)

        ttk.Label(row, text=TYPE_LABEL[kind], width=8, anchor=tk.W,
                  foreground="#0078d4").pack(side=tk.LEFT)

        name = os.path.basename(path)
        ttk.Label(row, text=name, width=34, anchor=tk.W).pack(side=tk.LEFT)

        var = tk.StringVar()
        ent = ttk.Entry(row, textvariable=var, width=28, show="●")
        ent.pack(side=tk.LEFT, padx=5)

        show_var = tk.BooleanVar(value=False)
        def toggle(e=ent, v=show_var):
            e.config(show="" if v.get() else "●")
        ttk.Checkbutton(row, text="显示", variable=show_var, command=toggle).pack(side=tk.LEFT)

        ttk.Label(row, text=os.path.dirname(path), foreground="gray").pack(side=tk.LEFT, padx=5)

        self.rows.append((path, var, row))

    def add_files(self):
        paths = filedialog.askopenfilenames(
            title="选择要解密的文件",
            filetypes=[
                ("支持的文件",
                 "*.pdf *.docx *.doc *.pptx *.ppt *.xlsx *.xls "
                 "*.wps *.et *.dps *.odt *.ods *.odp *.zip *.7z *.rar"),
                ("PDF", "*.pdf"),
                ("Word", "*.docx *.doc *.wps *.odt"),
                ("PPT", "*.pptx *.ppt *.dps *.odp"),
                ("Excel", "*.xlsx *.xls *.et *.ods"),
                ("压缩包", "*.zip *.7z *.rar"),
                ("所有文件", "*.*"),
            ]
        )
        for p in paths:
            self._add_row(p)
        self._update_status()

    def add_folder(self):
        folder = filedialog.askdirectory(title="选择文件夹（会递归扫描）")
        if not folder:
            return
        for root_dir, _, files in os.walk(folder):
            for f in files:
                if os.path.splitext(f)[1].lower() in ALL_EXTS:
                    self._add_row(os.path.join(root_dir, f))
        self._update_status()

    def clear_all(self):
        for w in self.scroll_frame.winfo_children():
            w.destroy()
        self.rows = []
        self._update_status()

    def show_all(self):
        for child in self.scroll_frame.winfo_children():
            for sub in child.winfo_children():
                if isinstance(sub, ttk.Entry):
                    sub.config(show="")

    def hide_all(self):
        for child in self.scroll_frame.winfo_children():
            for sub in child.winfo_children():
                if isinstance(sub, ttk.Entry):
                    sub.config(show="●")

    def _update_status(self):
        self.status.config(text=f"共 {len(self.rows)} 个文件")

    def start(self):
        if not self.rows:
            messagebox.showinfo("提示", "请先添加文件")
            return

        self.start_btn.config(state=tk.DISABLED)
        self.root.update_idletasks()

        results = []
        ok = fail = 0
        for path, var, _ in self.rows:
            pw = var.get()
            success, msg, out = unlock_one(path, pw)
            if success:
                ok += 1
                results.append(f"[成功] {os.path.basename(path)}  →  {msg}")
            else:
                fail += 1
                results.append(f"[失败] {os.path.basename(path)}  →  {msg}")

        self.start_btn.config(state=tk.NORMAL)

        win = tk.Toplevel(self.root)
        win.title("处理结果")
        win.geometry("780x480")
        ttk.Label(
            win,
            text=f"完成：成功 {ok} 个，失败 {fail} 个",
            font=("Microsoft YaHei", 11, "bold"),
            padding=10
        ).pack(anchor=tk.W)
        txt = ScrolledText(win, wrap=tk.WORD, font=("Consolas", 10))
        txt.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        txt.insert(tk.END, "\n".join(results))
        txt.config(state=tk.DISABLED)

        def save_log():
            fp = filedialog.asksaveasfilename(
                title="保存日志",
                defaultextension=".txt",
                filetypes=[("文本文件", "*.txt")]
            )
            if fp:
                with open(fp, "w", encoding="utf-8") as f:
                    f.write("\n".join(results))
                messagebox.showinfo("提示", "日志已保存")

        ttk.Button(win, text="保存日志", command=save_log).pack(pady=8)


def main():
    files = []
    for f in sys.argv[1:]:
        f = f.strip('"').strip("'")
        if os.path.isdir(f):
            for root_dir, _, fs in os.walk(f):
                for name in fs:
                    if os.path.splitext(name)[1].lower() in ALL_EXTS:
                        files.append(os.path.join(root_dir, name))
        elif os.path.isfile(f):
            files.append(f)

    root = tk.Tk()
    UnlockApp(root, files)
    root.mainloop()


if __name__ == "__main__":
    main()
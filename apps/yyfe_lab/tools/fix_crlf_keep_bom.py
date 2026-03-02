from pathlib import Path

TEXT_EXTS = {".py",".ps1",".txt",".md",".json",".yml",".yaml",".toml",".ini",".cfg",".csv"}

def fix_crlf_keep_bom(p: Path) -> bool:
    b = p.read_bytes()
    has_bom = b.startswith(b"\xef\xbb\xbf")
    try:
        txt = (b[3:].decode("utf-8") if has_bom else b.decode("utf-8"))
    except UnicodeDecodeError:
        return False

    new = txt.replace("\r\n", "\n")
    if new == txt:
        return False

    out = (b"\xef\xbb\xbf" + new.encode("utf-8")) if has_bom else new.encode("utf-8")
    p.write_bytes(out)
    return True

def main():
    changed = 0
    roots = [Path("src"), Path("tools"), Path(".tools"), Path("tasks"), Path("docs")]
    for root in roots:
        if not root.exists():
            continue
        for p in root.rglob("*"):
            if p.is_file() and p.suffix.lower() in TEXT_EXTS:
                if fix_crlf_keep_bom(p):
                    print("LF_FIXED:", p.as_posix())
                    changed += 1
    print("LF_FIX_OK:", changed, "file(s)")

if __name__ == "__main__":
    main()
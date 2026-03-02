from __future__ import annotations

def main(argv=None) -> int:
    # yyfe paketindeki gerçek CLI sys.argv üzerinden çalışıyor
    from yyfe.cli import main as _main
    return _main()

if __name__ == '__main__':
    raise SystemExit(main())

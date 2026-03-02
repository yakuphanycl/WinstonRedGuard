def _main():
    # Lazy import avoids runpy "found in sys.modules" warning when running `-m workspace_inspector.cli.main`
    from workspace_inspector.cli.main import main
    raise SystemExit(main())

if __name__ == "__main__":
    _main()

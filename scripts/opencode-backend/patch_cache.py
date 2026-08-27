p = "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/server.py"
src = open(p).read()
old = '''    app.router.add_static(
        "/assets",
        dist_dir / "assets" if (dist_dir / "assets").is_dir() else dist_dir,
        show_index=False,
        append_version=True,
    )'''
new = '''    app.router.add_static(
        "/assets",
        dist_dir / "assets" if (dist_dir / "assets").is_dir() else dist_dir,
        show_index=False,
        append_version=True,
        max_age=0,
    )'''
assert old in src, "anchor missing"
open(p, "w").write(src.replace(old, new, 1))
print("CACHE HEADERS PATCHED")

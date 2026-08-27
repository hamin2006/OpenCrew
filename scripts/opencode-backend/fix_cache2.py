p = "/home/harsh-amin/.kiro/crew-venv/lib/python3.12/site-packages/kiro_crew/dashboard/server.py"
src = open(p).read()

# 1. Revert the max_age=0 line
old = '''        show_index=False,
        append_version=True,
        max_age=0,
    )'''
new = '''        show_index=False,
        append_version=True,
    )'''
assert old in src, "revert anchor missing"
src = src.replace(old, new, 1)

# 2. Set Cache-Control: no-cache on /assets responses via the no_cache middleware
old2 = '''        resp = await handler(request)  # type: ignore[operator]
        if hasattr(resp, "headers"):
            _apply_security_headers(resp, request.app, request.path, request)
        return resp  # type: ignore[return-value]'''
new2 = '''        resp = await handler(request)  # type: ignore[operator]
        if hasattr(resp, "headers"):
            _apply_security_headers(resp, request.app, request.path, request)
            # Never cache hashed assets: patched bundles must surface on
            # reload, not sit in the browser's max-age window.
            if request.path.startswith("/assets/"):
                resp.headers["Cache-Control"] = "no-cache"
        return resp  # type: ignore[return-value]'''
assert old2 in src, "middleware anchor missing"
src = src.replace(old2, new2, 1)

open(p, "w").write(src)
print("SERVER.PY FIXED")

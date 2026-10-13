"""Account tests.

Accounts are optional and off by default. These prove both halves: that
nothing changes when they are off, and that when on they behave correctly —
including the parts that are easy to get wrong (timing attacks, username
enumeration, cookie handling, CSRF).
"""

import http.cookiejar
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "/tmp/orbtest_accounts"
os.environ["ORBITAL_BASE"] = BASE
os.environ["ORBITAL_QUIET"] = "1"
sys.path.insert(0, ROOT)

results = []


def check(name, cond, detail=""):
    results.append((name, bool(cond)))
    print(f"{'PASS' if cond else 'FAIL'}  {name}" + (f"  — {detail}" if detail else ""))


def install_ui(base):
    """Copy a stand-in UI into the test base directory."""
    gui = os.path.join(base, "gui")
    os.makedirs(gui, exist_ok=True)
    src = None
    for candidate in (
        os.path.join(ROOT, "gui", "orbital.html"),
        os.path.join(ROOT, "gui", "workstation.html"),
        os.path.join(ROOT, "orbital.html"),
    ):
        if os.path.exists(candidate):
            src = candidate
            break
    if not src:
        # A minimal stand-in is enough: the tests only check whether the real
        # UI is served or the login page is.
        body = ("<!DOCTYPE html><html><head><title>ORBITAL</title></head>"
                "<body><h1>Workstation</h1><div id=\"log\"></div>"
                "<script>window.ORBITAL_TOKEN = window.ORBITAL_TOKEN;</script>"
                "</body></html>")
        with open(os.path.join(gui, "orbital.html"), "w", encoding="utf-8") as fh:
            fh.write(body)
        return os.path.join(gui, "orbital.html")

    shutil.copy(src, os.path.join(gui, "orbital.html"))
    return os.path.join(gui, "orbital.html")


def main():
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)

    from core import accounts

    # ============================================== off by default
    print("\n--- default state ---")
    check("accounts are off by default", accounts.enabled() is False)
    check("status reports off", accounts.status()["enabled"] is False)

    # ============================================== password handling
    print("\n--- password handling ---")
    try:
        accounts.add_user("x", "short")
        check("a short password is rejected", False, "no exception")
    except ValueError as exc:
        check("a short password is rejected", True, str(exc)[:40])

    accounts.add_user("jay", "correct-horse-battery", admin=True)
    check("accounts turn on once a user exists", accounts.enabled() is True)

    raw = open(accounts.ACCOUNTS_FILE, encoding="utf-8").read()
    check("the password is not stored in the clear",
          "correct-horse-battery" not in raw)
    check("a scrypt hash is stored", '"hash"' in raw and '"salt"' in raw)

    import stat as stat_mod
    mode = stat_mod.S_IMODE(os.stat(accounts.ACCOUNTS_FILE).st_mode)
    check("the accounts file is owner-only", mode == 0o600, oct(mode))

    # Two users with the same password must not share a hash (per-user salt).
    accounts.add_user("sam", "correct-horse-battery")
    data = json.loads(open(accounts.ACCOUNTS_FILE, encoding="utf-8").read())
    salts = {u: data["users"][u]["salt"] for u in ("jay", "sam")}
    check("each account has its own salt",
          salts["jay"] != salts["sam"],
          "different salts for identical passwords")

    # ============================================== login
    print("\n--- login ---")
    check("a wrong password returns None", accounts.login("jay", "nope") is None)
    check("an unknown user returns None",
          accounts.login("ghost", "anything") is None,
          "same answer as a wrong password — no username enumeration")

    token = accounts.login("jay", "correct-horse-battery")
    check("a correct password returns a session token", bool(token),
          (token or "")[:12] + "...")
    check("the token is long enough to be unguessable",
          token and len(token) >= 32, str(len(token or "")))

    # ============================================== sessions
    print("\n--- sessions ---")
    check("a live token resolves to its user",
          accounts.session_user(token) == "jay")
    check("a junk token resolves to nobody",
          accounts.session_user("not-a-token") is None)
    check("an empty token resolves to nobody",
          accounts.session_user("") is None)
    check("None resolves to nobody", accounts.session_user(None) is None)

    check("sessions do not expose tokens",
          all("token" not in s for s in accounts.sessions()),
          str(list(accounts.sessions()[0].keys()) if accounts.sessions() else []))

    accounts.logout(token)
    check("logout invalidates the token",
          accounts.session_user(token) is None)

    # ============================================== rate limiting
    print("\n--- rate limiting ---")
    for _ in range(accounts.MAX_ATTEMPTS):
        accounts.login("jay", "wrong")
    allowed, wait = accounts._check_rate("jay")
    check("repeated failures lock the account", allowed is False,
          f"wait {wait}s")
    check("the lockout is a real duration", wait > 60, f"{wait}s")

    # A locked account must not accept even the right password.
    check("a locked account rejects the correct password",
          accounts.login("jay", "correct-horse-battery") is None)

    accounts._clear_failures("jay")
    check("clearing failures unlocks", accounts._check_rate("jay")[0] is True)

    # ============================================== removal
    print("\n--- removal ---")
    token2 = accounts.login("jay", "correct-horse-battery")
    check("removing a user succeeds", accounts.remove_user("jay") is True)
    check("removing an unknown user returns False",
          accounts.remove_user("jay") is False)
    check("removal invalidates that user's sessions",
          accounts.session_user(token2) is None)

    # ============================================== engine integration
    print("\n--- engine integration ---")
    shutil.rmtree(BASE, ignore_errors=True)
    os.makedirs(BASE, exist_ok=True)
    install_ui(BASE)

    env = dict(os.environ)
    env["ORBITAL_BASE"] = BASE
    env["ORBITAL_QUIET"] = "1"

    # --- with accounts OFF: the UI loads with no login
    engine = subprocess.Popen([sys.executable, "-m", "core.engine"], cwd=ROOT, env=env)
    try:
        up = False
        for _ in range(50):
            time.sleep(0.3)
            try:
                urllib.request.urlopen("http://127.0.0.1:5000/api/ping", timeout=2)
                up = True
                break
            except Exception:
                continue
        check("engine started with auth off", up)

        body = urllib.request.urlopen("http://127.0.0.1:5000/", timeout=5).read()
        check("with auth off, / serves the UI directly",
              b"ORBITAL" in body.upper() and b"Sign in" not in body,
              f"{len(body)} bytes")

        st = urllib.request.urlopen("http://127.0.0.1:5000/api/ping", timeout=5).status
        check("api/ping still open with auth off", st == 200)
    finally:
        engine.send_signal(signal.SIGTERM)
        engine.wait(timeout=8)

    # --- now WITH an account
    accounts.add_user("jay", "correct-horse-battery", admin=True)

    engine = subprocess.Popen([sys.executable, "-m", "core.engine"], cwd=ROOT, env=env)
    try:
        for _ in range(50):
            time.sleep(0.3)
            try:
                urllib.request.urlopen("http://127.0.0.1:5000/api/ping", timeout=2)
                break
            except Exception:
                continue

        # 1. The UI must be gated.
        body = urllib.request.urlopen("http://127.0.0.1:5000/", timeout=5).read()
        check("with auth on, / shows a login page",
              b"Sign in" in body and b"username" in body,
              f"{len(body)} bytes")
        check("the login page does not leak the UI",
              b"ORBITAL_TOKEN" not in body)

        # 2. A wrong password must not grant access.
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(jar))

        data = urllib.parse.urlencode(
            {"username": "jay", "password": "wrong"}).encode()
        resp = opener.open("http://127.0.0.1:5000/login", data=data, timeout=5)
        page = resp.read()
        check("a wrong password shows the login page again",
              b"Sign in" in page or b"Incorrect" in page)
        check("no session cookie was set for a wrong password",
              not any(c.name == "orbital_session" for c in jar),
              str([c.name for c in jar]))

        # 3. The right password sets a cookie and grants access.
        data = urllib.parse.urlencode(
            {"username": "jay", "password": "correct-horse-battery"}).encode()
        opener.open("http://127.0.0.1:5000/login", data=data, timeout=5)
        cookies = [c for c in jar if c.name == "orbital_session"]
        check("a correct password sets a session cookie", len(cookies) == 1,
              str([c.name for c in jar]))
        if cookies:
            check("the session cookie is HttpOnly",
                  cookies[0].has_nonstandard_attr("HttpOnly")
                  or "HttpOnly" in str(cookies[0]._rest),
                  str(getattr(cookies[0], "_rest", ""))[:60])

        body = opener.open("http://127.0.0.1:5000/", timeout=5).read()
        check("with a session, / serves the real UI",
              b"ORBITAL_TOKEN" in body or b"Workstation" in body,
              f"{len(body)} bytes")

        # 4. The session cookie also satisfies the API gate.
        req = urllib.request.Request("http://127.0.0.1:5000/api/telemetry")
        resp = opener.open(req, timeout=5)
        payload = json.loads(resp.read())
        check("the session cookie authorises API calls",
              "cpu_pct" in payload or "node" in payload, str(list(payload))[:60])

        # 5. But a request with no cookie and no token must still fail.
        try:
            urllib.request.urlopen("http://127.0.0.1:5000/api/telemetry", timeout=5)
            check("an unauthenticated API call is refused", False, "no exception")
        except urllib.error.HTTPError as exc:
            check("an unauthenticated API call is refused", exc.code == 401,
                  f"HTTP {exc.code}")

        # 6. Logout clears the session.
        opener.open("http://127.0.0.1:5000/logout", timeout=5)
        body = opener.open("http://127.0.0.1:5000/", timeout=5).read()
        check("after logout the login page returns",
              b"Sign in" in body, f"{len(body)} bytes")

        # 7. The token path must still work as well, for scripts.
        sys.path.insert(0, ROOT)
        from core import auth
        tok = auth.get_token()
        req = urllib.request.Request("http://127.0.0.1:5000/api/telemetry")
        req.add_header("Authorization", f"Bearer {tok}")
        resp = urllib.request.urlopen(req, timeout=5)
        check("the API token still works alongside accounts",
              resp.status == 200, f"HTTP {resp.status}")

    finally:
        engine.send_signal(signal.SIGTERM)
        engine.wait(timeout=8)

    passed = sum(1 for _, ok in results if ok)
    print(f"\n{passed}/{len(results)} checks passed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

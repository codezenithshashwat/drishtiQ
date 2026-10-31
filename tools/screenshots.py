"""Screenshots of the running app at several widths, via headless Chrome's DevTools protocol (no extra packages).

    .venv\\Scripts\\python tools\\screenshots.py --base http://127.0.0.1:8010 --out results/screenshots/step3_4

The app must already hold the cases named below (validation or dev-train images only). Tabs that live in component
state are reached by clicking their button text before the capture. Full-page PNGs, one per screen and width.
"""
import argparse
import asyncio
import base64
import json
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websockets

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
WIDTHS = (1440, 1280, 768)
SHOTS = [  # name, path, button texts to click in order (UI v3: landing at "/", app under "/app")
    ("landing", "/", []),
    ("worklist", "/app/worklist", []),
    ("worklist_routine_tab", "/app/worklist", ["Routine rescreening"]),
    ("new_screening", "/app/new", []),
    ("case_repeat_visit", "/app/cases/RS-1003", []),
    ("case_urgent", "/app/cases/RS-1006", []),
    ("case_intake", "/app/cases/RS-1008", []),
    ("history", "/app/worklist?tab=reviewed", []),
    ("disagreements", "/app/disagreements", []),
    ("report_doctor", "/app/patients/SCR-REPEAT/report", []),
    ("report_patient_en", "/app/patients/SCR-ROUTINE/report", ["Patient summary"]),
    ("report_patient_hi", "/app/patients/SCR-ROUTINE/report", ["Patient summary", "हिंदी"]),
    ("about", "/app/about", []),
]

CLICK = """(t => { const el = [...document.querySelectorAll('button,[role=tab],[role=radio]')].find(b => b.textContent.trim().startsWith(t));
  if (!el) return false;  // Radix tabs activate on mousedown, other controls on click
  for (const type of ['pointerdown', 'mousedown', 'pointerup', 'mouseup']) el.dispatchEvent(new MouseEvent(type, {bubbles: true, button: 0}));
  el.click(); return true })(%s)"""


async def capture(ws_url, base, out, widths, shots, axe):
    """Full-page PNG per screen and width. With axe: one axe-core run per screen (first width, via the app's ?axe=1 hook)
    and the console errors / uncaught exceptions seen while loading; written to <out>/a11y.json."""
    report, events = {}, []
    async with websockets.connect(ws_url, max_size=2**28) as ws:
        n = 0

        async def cmd(method, **params):
            nonlocal n
            n += 1
            await ws.send(json.dumps(dict(id=n, method=method, params=params)))
            while True:
                msg = json.loads(await ws.recv())
                if msg.get("id") == n:
                    if "error" in msg:
                        raise RuntimeError(f"{method}: {msg['error']}")
                    return msg.get("result", {})
                if msg.get("method") in ("Runtime.exceptionThrown", "Log.entryAdded", "Runtime.consoleAPICalled"):
                    events.append(msg)

        def errors():
            out_ = []
            for e in events:
                p = e["params"]
                if e["method"] == "Runtime.exceptionThrown":
                    out_.append(p["exceptionDetails"].get("text", "exception"))
                elif e["method"] == "Log.entryAdded" and p["entry"]["level"] == "error":
                    out_.append(p["entry"].get("text", "")[:200])
                elif e["method"] == "Runtime.consoleAPICalled" and p["type"] == "error":
                    out_.append(" ".join(str(a.get("value", a.get("description", ""))) for a in p["args"])[:200])
            events.clear()
            return out_

        await cmd("Page.enable")
        await cmd("Runtime.enable")
        await cmd("Log.enable")
        await cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": "light"}])
        for wi, width in enumerate(widths):
            await cmd("Emulation.setDeviceMetricsOverride", width=width, height=900 if width >= 768 else 812, deviceScaleFactor=1, mobile=width < 768)
            for name, path, clicks in shots:
                audit = axe and wi == 0
                url = base + path + (("&" if "?" in path else "?") + "axe=1" if audit else "")
                events.clear()
                await cmd("Page.navigate", url=url)
                await asyncio.sleep(4)  # data loads from the API; no animation in the app
                for text in clicks:
                    r = await cmd("Runtime.evaluate", expression=CLICK % json.dumps(text), returnByValue=True)
                    if not r["result"].get("value"):
                        raise RuntimeError(f"{name}: no button '{text}'")
                    await asyncio.sleep(2.5)
                if audit:
                    if clicks:  # the first axe run started at load; re-run it on the clicked state
                        await cmd("Runtime.evaluate", expression="window.__runAxe && window.__runAxe()")
                        await asyncio.sleep(1)
                    for _ in range(20):
                        r = await cmd("Runtime.evaluate", expression="JSON.stringify(window.__axe ?? null)", returnByValue=True)
                        if r["result"].get("value") not in (None, "null"):
                            break
                        await asyncio.sleep(0.5)
                    raw = json.loads(r["result"].get("value") or "null")
                    violations = raw or []
                    report[name] = dict(ran=raw is not None, violations=violations, console_errors=errors(),
                                        serious_critical=sum(v["impact"] in ("serious", "critical") for v in violations))
                    print(f"  axe {name}: {len(violations)} violations, {report[name]['serious_critical']} serious/critical; "
                          f"console errors {len(report[name]['console_errors'])}", flush=True)
                m = await cmd("Page.getLayoutMetrics")
                h = int(m["cssContentSize"]["height"])
                w_content = int(m["cssContentSize"]["width"])
                shot = await cmd("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                                 clip=dict(x=0, y=0, width=width, height=h, scale=1))
                (out / f"{name}_{width}.png").write_bytes(base64.b64decode(shot["data"]))
                print(f"{name}_{width}.png ({h}px){'  HORIZONTAL OVERFLOW ' + str(w_content) if w_content > width else ''}", flush=True)
    if axe:
        total = sum(v["serious_critical"] for v in report.values())
        missing = [k for k, v in report.items() if not v["ran"]]
        if missing:
            print(f"axe did not finish on: {missing}", flush=True)
        (out / "a11y.json").write_text(json.dumps(dict(tool="axe-core (in-app, ?axe=1)", serious_critical=total, screens=report), indent=2))
        print(f"axe: {total} serious/critical across {len(report)} screens", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8010")
    ap.add_argument("--out", default="results/screenshots/step3_4")
    ap.add_argument("--widths", default=",".join(map(str, WIDTHS)))
    ap.add_argument("--only", default="", help="comma-separated screen names")
    ap.add_argument("--axe", action="store_true", help="run axe-core on each screen (first width) and record console errors")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    profile = tempfile.mkdtemp()
    chrome = subprocess.Popen([CHROME, "--headless=new", "--remote-debugging-port=9333", f"--user-data-dir={profile}",
                               "--hide-scrollbars", "--no-first-run", "about:blank"])
    try:
        for _ in range(50):
            try:
                tabs = json.load(urllib.request.urlopen("http://127.0.0.1:9333/json"))
                page = next(t for t in tabs if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.3)
        shots = [x for x in SHOTS if not args.only or x[0] in args.only.split(",")]
        asyncio.run(capture(page["webSocketDebuggerUrl"], args.base, out, [int(w) for w in args.widths.split(",")], shots, args.axe))
    finally:
        chrome.terminate()


if __name__ == "__main__":
    main()

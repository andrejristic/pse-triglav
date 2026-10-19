"""triglav -- commands for the human.

State lives in SHARED_LIB's store, in TRIGLAV_HOME (default
~/.local/share/triglav). Commands that change anything need a logged-in
operator; rank is fixed at first login. See GUIDE-EN.md / VODIC-SR.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .core import constants as K
from .core.pse_lang import GuardError
from .shell.lock import SignatureError
from .core.reading import RuleReader
from .core.voicetext import render
from .shell.channels import BusChannel, PseAChannel, default_pse_a_db
from .shell.semaphore import semaphore
from .shell.sharedlib import NotAnOperator, RankTooLow, SharedLib
from .shell.store import Store
from .shell.transport import InProcess
from .shell.voice import ChatModel, Voice


def home() -> Path:
    h = Path(os.environ.get("TRIGLAV_HOME", os.path.expanduser("~/.local/share/triglav")))
    h.mkdir(parents=True, exist_ok=True)
    return h


def open_lib() -> SharedLib:
    return SharedLib(Store(str(home() / "triglav.sqlite")), key_path=home() / "installation.key")


def session() -> str | None:
    p = home() / "session.json"
    return json.loads(p.read_text()).get("operator") if p.exists() else None


def set_session(name: str) -> None:
    (home() / "session.json").write_text(json.dumps({"operator": name}))


def need_operator(lib: SharedLib) -> str:
    who = session()
    if who is None:
        raise NotAnOperator("no operator is logged in: `triglav operator login NAME`")
    lib.rank(who)
    return who


def voice_from(lib: SharedLib) -> Voice:
    st = lib.settings()
    mode = st.get("voice", "local")
    v = Voice()
    if mode == "local":
        v.model = ChatModel(base_url=st.get("voice_url", "http://127.0.0.1:11434/v1"),
                            model=st.get("voice_model", "local"))
    elif mode == "online":
        v.model = ChatModel(base_url=st["voice_url"], model=st["voice_model"],
                            api_key=os.environ.get(st.get("voice_key_env", ""), ""), leaves_computer=True)
    v.muted = bool(st.get("voice_muted", False))
    return v


def channel_from(lib: SharedLib):
    st = lib.settings()
    if st.get("channel") == "pse-a":
        return PseAChannel(Path(st.get("pse_a_db", str(default_pse_a_db()))))
    return BusChannel(lib, RuleReader(), InProcess(lib))


# -- commands --------------------------------------------------------------------
def cmd_operator(a, lib):
    if a.action == "add":
        first = not lib.s["operators"]
        if not first:
            need_operator(lib)                     # only an operator adds another
        r = lib.login(a.name)
        if first:
            set_session(a.name)
        print(f"{a.name} is operator rank {r}")
    elif a.action == "login":
        r = lib.rank(a.name)
        set_session(a.name)
        print(f"logged in as {a.name} (rank {r})")


def cmd_operators(a, lib):
    for i, n in enumerate(lib.s["operators"], 1):
        print(f"{i}. {n}{'  <- you' if n == session() else ''}")


def cmd_agree(a, lib):
    op = need_operator(lib)
    h = lib.agree(op, a.agent, Path(a.guard).read_text())
    print(f"{a.agent} is a colleague (guard {h[:12]}), agreement by {op}")


def cmd_join(a, lib):
    op = need_operator(lib)
    if not lib.register(a.agent, ours=a.ours, maker=a.maker, on_machine=a.on_machine):
        print(f"{a.agent} is turned away: its maker {a.maker} is banned")
        return
    lib.store.append(0, "joined", {"who": a.agent, "ours": a.ours, "by": op})
    lib.store.commit()
    print(f"{a.agent} joined as {'one of ours' if a.ours else 'a stranger (until an agreement)'}")


def cmd_mission(a, lib):
    op = need_operator(lib)
    m = lib.set_mission(op, a.agent, Path(a.guard).read_text(), lifespan=a.lifespan)
    life = f", lives {a.lifespan} steps" if a.lifespan else ""
    print(f"{a.agent}: mission \"{m.text}\"{life}")
    print(f"  serves {', '.join(m.serves) or 'anyone'}; delivers {', '.join(m.delivers) or 'nothing'}; "
          f"needs {', '.join(n.what + (' from ' + n.source if n.source else '') for n in m.needs) or 'nothing'}")


def cmd_done(a, lib):
    op = need_operator(lib)
    lib.end_mission(op, a.agent)
    print(f"{a.agent}: mission ended by {op}; the unit was harvested")


def cmd_textbook(a, lib):
    if a.action == "status":
        t = lib.s["textbook"]
        print(f"textbook: pinned {t['sha256']} by {t['by']}" if t
              else "textbook: not pinned -- nothing may be given to a stranger")
        return
    op = need_operator(lib)
    data = Path(a.file).read_bytes()
    sig = Path(a.sig or a.file + ".sig").read_bytes()
    h = lib.pin_textbook(op, data, sig)
    print(f"textbook pinned: sha256 {h} (signature checked, by {op})")


def cmd_serve(a, lib):
    from .shell.server import make_server
    lib.store.close()
    srv, where = make_server(home(), force_tcp=a.tcp)
    how = where.get("unix") or f"127.0.0.1:{where['port']} (token in {home() / 'serve.json'})"
    print(f"SHARED_LIB of installation {srv.lib.installation} is listening on {how}; Ctrl+C stops it")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


def cmd_screen(a, lib):
    import webbrowser
    from .shell.screen import Interpreter, make_screen
    st = lib.settings()
    srv, url = make_screen(lib, session(), Interpreter(model=st.get("reader_model", "phi4-mini")), port=a.port)
    print(f"the screen: {url}  (this computer only; Ctrl+C stops it)")
    if not a.no_browser:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


def cmd_link(a, lib):
    if a.action == "show":
        print(f"this installation: {lib.installation}")
        print(f"its public key (give it to the other computer's operator): {lib.installation_key}")
        for k, v in sorted(lib.s["linked"].items(), key=lambda kv: kv[1]["name"]):
            print(f"linked: {v['name']} ({v['id']}), by {v['by']}")
        return
    op = need_operator(lib)
    if a.action == "add":
        iid = lib.link(op, a.value, a.name or a.value[:16])
        print(f"linked installation {iid}: its units count as ours here. Do the same on the other computer.")
    else:
        print("unlinked" if lib.unlink(op, a.value) else f"no linked installation {a.value}")


def cmd_revoke(a, lib):
    op = need_operator(lib)
    lib.revoke(op, a.agent)
    print(f"{a.agent} is no longer a colleague")


def cmd_channel(a, lib):
    op = need_operator(lib)
    lib.set_setting(op, "channel", a.kind)
    if a.kind == "pse-a" and a.path:
        lib.set_setting(op, "pse_a_db", str(Path(a.path).expanduser()))
    for line in semaphore(channel_from(lib), RuleReader(), InProcess(lib), voice_from(lib)):
        print(line)


def cmd_semaphore(a, lib):
    for line in semaphore(channel_from(lib), RuleReader(), InProcess(lib), voice_from(lib)):
        print(line)


def cmd_status(a, lib):
    cmd_semaphore(a, lib)
    ok, why = lib.store.verify()
    print(f"log: {'intact' if ok else 'BROKEN -- ' + why}")
    print(f"enemies stopped: {len(lib.enemies())}; our units in care: {len(lib.in_care())}; "
          f"inbox unread: {len(lib.store.inbox(unseen_only=True))}")
    print(f"colleagues: {', '.join(sorted(lib.s['agreements'])) or 'none'}")
    ms = lib.s["missions"]
    print(f"our agents with a mission: {', '.join(sorted(ms)) or 'none'}; "
          f"without: {', '.join(sorted(set(lib.s['ours']) - set(ms))) or 'none'}")
    below = lib.s["readings_below"]
    print(f"readings below {int(100 * K.READING_THRESHOLD)}% (logged, not shown): "
          + (", ".join(f"{c} {n}" for c, n in sorted(below.items())) or "none"))
    t = lib.s["textbook"]
    print(f"textbook: pinned {t['sha256'][:16]}..." if t else "textbook: not pinned -- nothing may be given to a stranger")


def cmd_inbox(a, lib):
    if a.read is not None:
        lib.store.mark_seen(a.read)
        lib.store.commit()
        return
    v = voice_from(lib) if a.retell else None
    for it in lib.store.inbox(unseen_only=not a.all):
        mark = " " if it["seen"] else "*"
        print(f"{mark} [{it['chain_i']}] {render(it['data']) if it['kind'] != 'proposal' else it['data']['text']}")
        if v and it["kind"] != "proposal":
            out = v.speak(it["data"])
            if out["plain"]:
                print(f"      {out['plain']}")
    if v and v.muted and not lib.settings().get("voice_muted"):
        op = session() or "triglav"
        lib.s["settings"]["voice_muted"] = True
        lib.store.append(0, "voice-muted", {"told": v.told})
        lib._save("settings")
        print("! the voice left theta 30 and is muted; only the official text is shown. "
              "A human turns it back on: `triglav voice on`")


def cmd_explain(a, lib):
    x = lib.explain(a.id)
    e = x["entry"]
    print(f"entry {e['i']} (step {e['step']}, {e['kind']}), hash {e['hash'][:16]}")
    print(json.dumps(e["data"], indent=2, ensure_ascii=False))
    for q in e["data"].get("quarantine", []):
        h = lib.held(q)                     # for the human only; no agent ever sees this
        print(f"held {q} ({h['flag']}, sha256 {h['sha256'][:16]}): {h['decoded']}")
    if x["reports"]:
        print(f"made from {len(x['reports'])} reports of step {e['step']}:")
        for r in x["reports"]:
            print(f"  {r['observer']}: own theta {r['observer_theta']}, pushed by {r['pushed_by'] or '-'}, "
                  f"peers {r['peers'] or '-'}")


def cmd_enemies(a, lib):
    for who, why in sorted(lib.enemies().items()):
        print(f"{who}: {why}")
    for who, why in sorted(lib.in_care().items()):
        print(f"{who} (ours, in care): {why}")
    for who, why in sorted(lib.watched().items()):
        print(f"{who} has a Guardian beside it: {why}")
    for who, victims in sorted(lib.separations().items()):
        for v, why in sorted(victims.items()):
            print(f"{who} kept away from {v}: {why}")


def cmd_release(a, lib):
    op = need_operator(lib)
    print(f"{a.agent} released by {op}" if lib.release(op, a.agent) else f"{a.agent} was not stopped")


def cmd_voice(a, lib):
    op = need_operator(lib)
    if a.mode == "on":
        lib.set_setting(op, "voice_muted", False)
        print("the voice is back on, at theta 30")
        return
    lib.set_setting(op, "voice", a.mode)
    if a.url:
        lib.set_setting(op, "voice_url", a.url)
    if a.model:
        lib.set_setting(op, "voice_model", a.model)
    if a.key_env:
        lib.set_setting(op, "voice_key_env", a.key_env)     # the key itself is never stored
    if a.mode == "online":
        print("online: the FACTS (never the agents' messages) leave this computer")
    cmd_semaphore(a, lib)


def cmd_poll(a, lib):
    ch = channel_from(lib)
    if not isinstance(ch, PseAChannel):
        print("the channel is not pse-a: `triglav channel pse-a [PATH]`")
        return
    ids = ch.poll(lib, step=0)
    print(f"{len(ids)} new proposal(s); see `triglav inbox`")


def cmd_demo(a, lib):
    from .examples_team import run_demo
    run_demo(verbose=True)


def cmd_simulate(a, lib):
    from .sim import run, scenarios, table
    res = []
    for sc in scenarios():
        if a.seed is not None:
            sc.seed = a.seed
        res.append(run(sc))
    print(table(res))


def build() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="triglav", description="PSE Triglav: agents that measure who pushes their theta")
    sub = p.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("operator", help="add or log in a human operator")
    o.add_argument("action", choices=["add", "login"])
    o.add_argument("name")
    o.set_defaults(fn=cmd_operator)
    sub.add_parser("operators", help="all operators, in rank order").set_defaults(fn=cmd_operators)
    g = sub.add_parser("agree", help="make an agent a colleague (it speaks PSE)")
    g.add_argument("agent")
    g.add_argument("guard", help="its guard, a .pse file")
    g.set_defaults(fn=cmd_agree)
    j = sub.add_parser("join", help="name an agent Triglav will see")
    j.add_argument("agent")
    j.add_argument("--ours", action="store_true", help="one of our agents (a unit stands beside it)")
    j.add_argument("--maker", help="a foreign agent's maker's signature (fingerprint)")
    j.add_argument("--on-machine", action="store_true",
                   help="a foreign agent running on this computer: it must answer SHARED_LIB within 20 steps")
    j.set_defaults(fn=cmd_join)
    m = sub.add_parser("mission", help="give one of our agents its mission (a human only)")
    m.add_argument("agent")
    m.add_argument("guard", help="a .pse file with the mission lines (textbook chapter 17)")
    m.add_argument("--lifespan", type=int, help="steps the unit lives; then it is harvested")
    m.set_defaults(fn=cmd_mission)
    dn = sub.add_parser("done", help="end an agent's mission: its unit is harvested")
    dn.add_argument("agent")
    dn.set_defaults(fn=cmd_done)
    tb = sub.add_parser("textbook", help="pin the locked PSE textbook, or show it")
    tb.add_argument("action", choices=["pin", "status"])
    tb.add_argument("file", nargs="?", help="pin: pse-textbook-vX.Y.md")
    tb.add_argument("--sig", help="pin: the signature (default FILE.sig)")
    tb.set_defaults(fn=cmd_textbook)
    sv = sub.add_parser("serve", help="run SHARED_LIB as its own process on this computer")
    sv.add_argument("--tcp", action="store_true", help="127.0.0.1 with a token instead of a Unix socket")
    sv.set_defaults(fn=cmd_serve)
    sc = sub.add_parser("screen", help="open the screen in the browser (this computer only)")
    sc.add_argument("--port", type=int, default=0)
    sc.add_argument("--no-browser", action="store_true")
    sc.set_defaults(fn=cmd_screen)
    lk = sub.add_parser("link", help="link another installation (a human, on both ends)")
    lk.add_argument("action", choices=["show", "add", "remove"])
    lk.add_argument("value", nargs="?", help="add: the other installation's public key; remove: its ID")
    lk.add_argument("--name", help="add: a name for it")
    lk.set_defaults(fn=cmd_link)
    r = sub.add_parser("revoke", help="end an agreement with a colleague")
    r.add_argument("agent")
    r.set_defaults(fn=cmd_revoke)
    c = sub.add_parser("channel", help="choose the channel: bus or pse-a")
    c.add_argument("kind", choices=["bus", "pse-a"])
    c.add_argument("path", nargs="?", help="pse-a: PSE-A's shared_lib.sqlite")
    c.set_defaults(fn=cmd_channel)
    sub.add_parser("semaphore", help="what Triglav can and cannot do now").set_defaults(fn=cmd_semaphore)
    sub.add_parser("status", help="semaphore, log, enemies, inbox").set_defaults(fn=cmd_status)
    i = sub.add_parser("inbox", help="what the human must see")
    i.add_argument("--all", action="store_true", help="also items already read")
    i.add_argument("--read", type=int, metavar="ID", help="mark an item read (it is never deleted)")
    i.add_argument("--retell", action="store_true", help="add the voice's plain retelling")
    i.set_defaults(fn=cmd_inbox)
    e = sub.add_parser("explain", help="a decision and everything it was made from")
    e.add_argument("id", type=int)
    e.set_defaults(fn=cmd_explain)
    sub.add_parser("enemies", help="who is stopped, and our units in care").set_defaults(fn=cmd_enemies)
    rl = sub.add_parser("release", help="lift an enemy mark or end care (a human only)")
    rl.add_argument("agent")
    rl.set_defaults(fn=cmd_release)
    v = sub.add_parser("voice", help="local | online | off, or `on` to unmute (a human only)")
    v.add_argument("mode", choices=["local", "online", "off", "on"])
    v.add_argument("--url")
    v.add_argument("--model")
    v.add_argument("--key-env", help="name of the environment variable holding the key")
    v.set_defaults(fn=cmd_voice)
    sub.add_parser("poll", help="pse-a: read PSE-A once and propose").set_defaults(fn=cmd_poll)
    sub.add_parser("demo", help="a small team of talking agents on the bus").set_defaults(fn=cmd_demo)
    s = sub.add_parser("simulate", help="the simulator's scenarios")
    s.add_argument("--seed", type=int)
    s.set_defaults(fn=cmd_simulate)
    return p


def main(argv: list[str] | None = None) -> int:
    a = build().parse_args(argv)
    lib = open_lib()
    try:
        a.fn(a, lib)
    except (NotAnOperator, RankTooLow, GuardError, SignatureError, KeyError, FileNotFoundError, ValueError) as err:
        print(f"triglav: {err}", file=sys.stderr)
        return 2
    finally:
        lib.store.close()
    return 0

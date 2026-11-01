"""Local administration (no public staff sign-up exists):
    python -m backend.network.cli seed-demo
    python -m backend.network.cli create-staff --role organiser --name "A B" --identifier 9876543210 --password "..." [--org "Org name"]
    python -m backend.network.cli purge-expired
    python -m backend.network.cli grant-clinician  --identifier 9876543210 --by "Admin name"   # ophthalmologist access
    python -m backend.network.cli revoke-clinician --identifier 9876543210 --by "Admin name"   # takes effect immediately
Clinical access is never granted by signup or any public endpoint.
"""
import argparse
import getpass

from . import db, security, seed, services


def main() -> None:
    ap = argparse.ArgumentParser(prog="backend.network.cli")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed-demo")
    sub.add_parser("purge-expired")
    cs = sub.add_parser("create-staff")
    cs.add_argument("--role", required=True, choices=["health_worker", "organiser", "admin"])
    cs.add_argument("--name", required=True)
    cs.add_argument("--identifier", required=True)
    cs.add_argument("--password")
    cs.add_argument("--org", help="organisation name (created if missing)")
    for name in ("grant-clinician", "revoke-clinician"):
        g = sub.add_parser(name, help="ophthalmologist access for an EXISTING account (create it first with create-staff or signup)")
        g.add_argument("--identifier", required=True)
        g.add_argument("--by", required=True, help="name of the administrator authorising this change (audited)")
    a = ap.parse_args()
    db.connect()
    if a.cmd in ("grant-clinician", "revoke-clinician"):
        from .. import clinical_auth
        ident = security.normalise_identifier(a.identifier)
        row = db.one("SELECT id, display_name FROM users WHERE identifier_norm=? AND deleted_at IS NULL", (ident[1],)) if ident else None
        if row is None:
            raise SystemExit("No account with that mobile number or email.")
        changed = clinical_auth.grant(row["id"], f"cli:{a.by}") if a.cmd == "grant-clinician" else clinical_auth.revoke(row["id"], f"cli:{a.by}")
        print(f"{a.cmd}: {row['display_name']} ({security.mask(ident[1])}): {'done' if changed else 'no change'}")
        return
    if a.cmd == "seed-demo":
        seed.seed_demo()
        print("Demo camps and prototype staff accounts are in place.")
    elif a.cmd == "purge-expired":
        print(f"{services.purge_expired()} registrations had contact details removed.")
    else:
        ident = security.normalise_identifier(a.identifier)
        if ident is None:
            raise SystemExit("Invalid mobile number or email.")
        pw = a.password or getpass.getpass("Password: ")
        if security.check_password_strength(pw):
            raise SystemExit("Password too weak (min 8 characters, not common).")
        org_id = None
        if a.org:
            row = db.one("SELECT id FROM organisations WHERE name=?", (a.org,))
            org_id = row["id"] if row else db.run("INSERT INTO organisations(name,kind,verification,source,created_at) VALUES(?,?,?,?,?)",
                                                  (a.org, "other", "unverified", "admin", security.iso())).lastrowid
        db.run("""INSERT INTO users(role,display_name,identifier_type,identifier_norm,password_hash,language,org_id,created_at) VALUES(?,?,?,?,?,?,?,?)""",
               (a.role, a.name, ident[0], ident[1], security.hash_password(pw), "en", org_id, security.iso()))
        print(f"Created {a.role} account for {security.mask(ident[1])}.")


if __name__ == "__main__":
    main()

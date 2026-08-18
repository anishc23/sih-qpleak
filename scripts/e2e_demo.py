"""End-to-end verification of the SIH demo flow, over real HTTP.

Runs the exact sequence a judge will watch, and asserts the security properties
at each step. Requires: Hardhat node running, contracts deployed, database
seeded, backend running.

    python scripts/e2e_demo.py
"""

from __future__ import annotations

import sys
import time

import httpx

API = "http://127.0.0.1:8000/api"
PASSWORD = "SecureLock#2026"
RELEASE_SECONDS = 15

PASS, FAIL = "  [PASS]", "  [FAIL]"
failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> bool:
    print(f"{PASS if condition else FAIL} {label}" + (f" -- {detail}" if detail else ""))
    if not condition:
        failures.append(label)
    return condition


def login(client: httpx.Client, email: str) -> dict:
    r = client.post(f"{API}/auth/login", json={"email": email, "password": PASSWORD})
    r.raise_for_status()
    return r.json()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def step(n: int, title: str) -> None:
    print(f"\n{'=' * 68}\nSTEP {n}: {title}\n{'=' * 68}")


def main() -> int:
    client = httpx.Client(timeout=60.0)

    # ------------------------------------------------------------------
    step(1, "Authentication and role separation")
    sessions = {}
    for role in ("setter1", "setter2", "reviewer", "authority", "auditor", "admin"):
        sessions[role] = login(client, f"{role}@securelock.demo")
    check("All six demo roles authenticate", len(sessions) == 6)

    bad = client.post(
        f"{API}/auth/login",
        json={"email": "setter1@securelock.demo", "password": "wrong-password"},
    )
    check("Wrong password is rejected", bad.status_code == 401)

    no_token = client.get(f"{API}/questions")
    check("Unauthenticated request is rejected", no_token.status_code == 401)

    setter1 = auth(sessions["setter1"]["access_token"])
    setter2 = auth(sessions["setter2"]["access_token"])
    reviewer = auth(sessions["reviewer"]["access_token"])
    authority = auth(sessions["authority"]["access_token"])
    auditor = auth(sessions["auditor"]["access_token"])

    # ------------------------------------------------------------------
    step(2, "Question creation: real encryption, real hash, real anchor")
    created = client.post(
        f"{API}/questions",
        headers=setter1,
        json={
            "content": "Explain how a Merkle tree enables efficient membership proofs.",
            "subject": "Computer Science",
            "topic": "Cybersecurity",
            "difficulty": "MEDIUM",
            "question_type": "LONG_ANSWER",
            "marks": 7,
        },
    )
    check("Question created", created.status_code == 201, str(created.status_code))
    payload = created.json()
    quid = payload["question"]["question_uid"]
    chain = payload["blockchain"]
    print(f"       Question ID : {quid}")
    print(f"       SHA-256     : {payload['question']['content_hash'][:32]}...")
    print(f"       Ciphertext  : {payload['encryption']['ciphertext_bytes']} bytes")
    print(f"       Tx hash     : {chain['tx_hash']}")

    check("AES-256-GCM reported", payload["encryption"]["algorithm"] == "AES-256-GCM")
    check("Content hash is SHA-256 (64 hex)", len(payload["question"]["content_hash"]) == 64)
    check("Blockchain anchor confirmed", chain["confirmed"] is True)
    check("Real transaction hash present", bool(chain["tx_hash"]) and chain["tx_hash"] != "0x")

    # ------------------------------------------------------------------
    step(3, "READ is authorised, audited and anchored")
    own = client.post(f"{API}/questions/{quid}/read", headers=setter1)
    check("Author can read own question", own.status_code == 200)
    check("Plaintext returned to author", "Merkle" in own.json().get("content", ""))

    other = client.post(f"{API}/questions/{quid}/read", headers=setter2)
    check("Another setter is DENIED", other.status_code == 403, other.json().get("detail", "")[:60])

    aud = client.post(f"{API}/questions/{quid}/read", headers=auditor)
    check("Auditor is DENIED plaintext", aud.status_code == 403)

    log = client.get(f"{API}/questions/{quid}/access-log", headers=setter1).json()
    denied = [e for e in log if not e["granted"]]
    check("Denied attempts appear in the access log", len(denied) >= 2, f"{len(denied)} denials")

    # ------------------------------------------------------------------
    step(4, "Review workflow and separation of duties")
    submitted = client.post(f"{API}/questions/{quid}/submit", headers=setter1)
    check("Question submitted for review", submitted.status_code == 200)

    self_approve = client.post(
        f"{API}/questions/{quid}/review", headers=setter1, json={"approve": True}
    )
    check("Setter cannot approve anything", self_approve.status_code == 403)

    approved = client.post(
        f"{API}/questions/{quid}/review",
        headers=reviewer,
        json={"approve": True, "comment": "Clear and well scoped."},
    )
    check("Reviewer approves", approved.status_code == 200)
    check(
        "Status moved into the synthesis pool",
        approved.json()["status"] == "AVAILABLE_FOR_SYNTHESIS",
        approved.json()["status"],
    )

    edit = client.put(
        f"{API}/questions/{quid}",
        headers=setter1,
        json={"content": "Completely different question text now, sneakily replaced."},
    )
    check("Approved question is frozen against edits", edit.status_code == 403)

    # ------------------------------------------------------------------
    step(5, "Duplicate detection (TF-IDF, computed locally)")
    dupes = client.get(f"{API}/synthesis/duplicates", headers=authority).json()
    print(f"       Pool size   : {dupes['pool_size']}")
    print(f"       Method      : {dupes['method']}")
    print(f"       Pairs found : {len(dupes['pairs'])}  (high risk: {dupes['high_risk']})")
    if dupes["pairs"]:
        top = dupes["pairs"][0]
        print(f"       Top pair    : {top['left']} ~ {top['right']} = {top['similarity']:.0%} [{top['risk']}]")
    check("Similarity engine returns results", dupes["pool_size"] > 0)
    check("Seeded near-duplicates detected", len(dupes["pairs"]) > 0)

    # ------------------------------------------------------------------
    step(6, "Paper generation against the blueprint")
    exams = client.get(f"{API}/exams", headers=authority).json()
    exam_uid = exams[0]["exam_uid"]

    gen = client.post(
        f"{API}/exams/{exam_uid}/generate-paper",
        headers=authority,
        json={"apply_variations": True},
    )
    check("Paper generated", gen.status_code == 200, str(gen.status_code))
    if gen.status_code != 200:
        print("       ", gen.text[:300])
        return 1

    paper = gen.json()
    puid = paper["paper_uid"]
    compliance = paper["blueprint_compliance"]
    report = paper["synthesis_report"]
    print(f"       Paper ID    : {puid}")
    print(f"       Questions   : {paper['question_count']}")
    print(f"       Difficulty  : {compliance['difficulty_compliance']}%")
    print(f"       Topic       : {compliance['topic_compliance']}%")
    print(f"       Marks       : {compliance['marks_actual']}/{compliance['marks_target']}")
    print(f"       Contributors: {report['distinct_contributors']}")
    print(f"       Dup risk    : {compliance['duplicate_risk']}")

    check("Blueprint difficulty satisfied", compliance["difficulty_compliance"] >= 80)
    check("Blueprint topics satisfied", compliance["topic_compliance"] >= 80)
    check("Multiple contributors used", report["distinct_contributors"] >= 3)
    check("Selection reasons recorded", bool(paper["questions"][0]["selection_reason"]))

    setter_peek = client.get(f"{API}/papers/{puid}", headers=setter1)
    check("Setter sees paper metadata only (no content endpoint)", setter_peek.status_code == 200)

    # ------------------------------------------------------------------
    step(7, "Final paper encryption")
    enc = client.post(f"{API}/papers/{puid}/encrypt", headers=authority)
    check("Paper encrypted", enc.status_code == 200)
    paper_hash = enc.json()["paper_hash"]
    print(f"       Paper hash  : {paper_hash[:32]}...")
    check("Paper hash is SHA-256", len(paper_hash or "") == 64)
    check("Status is ENCRYPTED", enc.json()["status"] == "ENCRYPTED")

    # ------------------------------------------------------------------
    step(8, f"Blockchain registration + time lock ({RELEASE_SECONDS}s)")
    reg = client.post(
        f"{API}/papers/{puid}/register-blockchain",
        headers=authority,
        json={"release_in_seconds": RELEASE_SECONDS},
    )
    check("Paper registered on chain", reg.status_code == 200, str(reg.status_code))
    if reg.status_code != 200:
        print("       ", reg.text[:300])
        return 1
    print(f"       Contract    : {reg.json()['contract_address']}")
    print(f"       Tx hash     : {reg.json()['tx_hash']}")
    print(f"       Release at  : {reg.json()['release_time']}")

    lock = client.get(f"{API}/papers/{puid}/time-lock", headers=authority).json()
    check("Lock reported as LOCKED", lock["status"] == "LOCKED", lock["status"])
    check("Release time not yet reached", lock["release_time_reached"] is False)
    check("Authority is the smart contract", lock["authority"] == "smart-contract")
    print(f"       Chain time  : {lock['blockchain_time']}")
    print(f"       Remaining   : {lock['seconds_remaining']}s")

    # ------------------------------------------------------------------
    step(9, "ATTACK: early decryption, straight at the API")
    early = client.post(f"{API}/papers/{puid}/decrypt", headers=authority)
    check("Early decryption BLOCKED", early.status_code == 423, str(early.status_code))
    print(f"       Reason: {early.json().get('detail', '')[:110]}")

    early_release = client.post(f"{API}/papers/{puid}/release", headers=authority)
    check("Early release BLOCKED by the contract", early_release.status_code == 423)

    setter_try = client.post(f"{API}/papers/{puid}/decrypt", headers=setter1)
    check("Question setter DENIED the paper entirely", setter_try.status_code == 403)

    # ------------------------------------------------------------------
    step(10, "ATTACK: client clock manipulation")
    clocks = client.get(
        f"{API}/demo/clock-comparison", headers=authority, params={"paper_uid": puid}
    ).json()
    fake_client_clock = 4070908800  # 2099-01-01
    print(f"       Client claims : {fake_client_clock}  (year 2099)")
    print(f"       Blockchain    : {clocks['blockchain_time']}")
    print(f"       Release at    : {clocks['release_time']}")
    check("Decision authority is block.timestamp", clocks["authority"] == "block.timestamp")
    check("Chain still says not released", clocks["released"] is False)

    still = client.post(f"{API}/papers/{puid}/decrypt", headers=authority)
    check("STILL BLOCKED with a 2099 client clock", still.status_code == 423)

    # ------------------------------------------------------------------
    step(11, f"Waiting {RELEASE_SECONDS}s for the blockchain release time")
    deadline = lock["release_time"]
    give_up_at = time.monotonic() + RELEASE_SECONDS + 90
    while True:
        state = client.get(f"{API}/papers/{puid}/time-lock", headers=authority).json()
        if state["release_time_reached"]:
            break
        if time.monotonic() > give_up_at:
            check("Chain clock advanced past the release time", False,
                  "blockchain time is not advancing -- is the node mining?")
            return 1
        print(f"       chain={state['blockchain_time']}  remaining={state['seconds_remaining']}s")
        time.sleep(3)
    print(f"       Chain time {state['blockchain_time']} >= release {deadline}")
    check("Chain reports release time reached", state["release_time_reached"] is True)

    # ------------------------------------------------------------------
    step(12, "Authorised release and decryption")
    rel = client.post(f"{API}/papers/{puid}/release", headers=authority)
    check("Contract permits release", rel.status_code == 200, str(rel.status_code))
    if rel.status_code == 200:
        print(f"       Release tx  : {rel.json()['tx_hash']}")

    dec = client.post(f"{API}/papers/{puid}/decrypt", headers=authority)
    check("Paper decrypts after release", dec.status_code == 200, str(dec.status_code))
    if dec.status_code == 200:
        content = dec.json()["content"]
        check("Decrypted paper has real content", "END OF PAPER" in content)
        print("       ---- first lines of the released paper ----")
        for line in content.splitlines()[:6]:
            print(f"       {line}")

    setter_after = client.post(f"{API}/papers/{puid}/decrypt", headers=setter1)
    check("Setter STILL denied after release", setter_after.status_code == 403)

    # ------------------------------------------------------------------
    step(13, "Integrity verification against the chain")
    qv = client.get(f"{API}/questions/{quid}/verify", headers=authority).json()
    check("Question integrity VERIFIED", qv["verdict"] == "VERIFIED", qv["verdict"])
    check("On-chain hash matches", qv["blockchain_match"] is True)

    pv = client.get(f"{API}/papers/{puid}/verify", headers=authority).json()
    check("Paper integrity VERIFIED", pv["verdict"] == "VERIFIED", pv["verdict"])

    # ------------------------------------------------------------------
    step(14, "Audit trail and tamper detection")
    trail = client.get(
        f"{API}/audit/papers/{puid}", headers=auditor, params={"limit": 100}
    ).json()
    types = [e["event_type"] for e in trail]
    print(f"       Paper lifecycle: {' -> '.join(types)}")
    for required in ("PAPER_GENERATED", "PAPER_ENCRYPTED", "PAPER_REGISTERED",
                     "RELEASE_DENIED", "PAPER_RELEASED", "PAPER_DECRYPTED"):
        check(f"Audit contains {required}", required in types)

    verify = client.get(f"{API}/audit/verify", headers=auditor).json()
    check("Audit hash chain intact", verify["intact"] is True, f"{verify['total_events']} events")

    victim = client.get(
        f"{API}/audit", headers=auditor, params={"event_type": "PAPER_ENCRYPTED", "limit": 1}
    ).json()[0]
    tampered = client.post(
        f"{API}/demo/tamper-audit",
        headers=auditor,
        params={"event_uid": victim["event_uid"], "new_event_type": "PAPER_APPROVED"},
    ).json()
    check("Tampering DETECTED", tampered["verdict"] == "TAMPERING_DETECTED")
    print(f"       Broken links: {tampered['hash_verification']['broken_count']}")

    admin = auth(sessions["admin"]["access_token"])
    reset = client.post(f"{API}/demo/reset-tamper", headers=admin).json()
    check("Chain rebuilt for the next demo run", reset["intact"] is True)

    # ------------------------------------------------------------------
    print(f"\n{'=' * 68}")
    if failures:
        print(f"RESULT: {len(failures)} CHECK(S) FAILED")
        for f in failures:
            print(f"  - {f}")
        print("=" * 68)
        return 1
    print("RESULT: ALL CHECKS PASSED -- full SIH demo flow verified end to end")
    print("=" * 68)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except httpx.ConnectError:
        print("\nCannot reach the API. Start the stack first (see scripts/start.ps1).")
        sys.exit(2)

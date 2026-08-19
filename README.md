# SecureLock

**Blockchain-backed examination paper security — question provenance, encrypted assembly, and smart-contract time-locked release.**

> SIH internal hackathon prototype. Runs entirely offline on one laptop.

---

## The one-line pitch

> We don't just secure the question paper. We secure the question, from creation to examination.

Most exam-security systems protect the final PDF. But a paper can be compromised
long before it exists — while individual questions are being written, reviewed,
shared and assembled. SecureLock secures that whole lifecycle.

---

## What actually works

Everything below is implemented and verified by automated tests. Nothing is mocked.

| Capability | Status | How it's verified |
|---|---|---|
| Argon2id auth + JWT, 5 roles | Working | `tests/test_security.py::TestAuthentication` |
| READ / WRITE / APPROVE as independent permissions | Working | `TestAuthorization` |
| Per-question AES-256-GCM encryption, unique key each | Working | `TestEncryption` |
| Per-question SHA-256 hash + append-only versioning | Working | `TestVersioning` |
| On-chain question provenance | Working | `QuestionRegistry.test.js` (20 tests) |
| Hash-chained audit log with tamper detection | Working | `TestAuditChain` |
| TF-IDF duplicate detection | Working | `TestSimilarity` |
| Blueprint-driven paper synthesis, seeded + reproducible | Working | `TestSelection` |
| Rule-based question variation, reviewer-gated | Working | `TestVariation` |
| Final paper AES-256-GCM encryption + SHA-256 | Working | `e2e_demo.py` step 7 |
| Smart-contract time lock on `block.timestamp` | Working | `PaperTimeLock.test.js` (17 tests) |
| Client-clock attack blocked | Working | `e2e_demo.py` step 10 |
| Graceful degradation when the chain is down — no fake hashes | Working | `TestBlockchainUnavailable` |

**Test totals: 37 contract tests + 44 backend tests + a 60-assertion end-to-end run, all passing.**

The web app is built and is the way to see all of this — sixteen routes, live
against the chain. The API is also usable directly through its OpenAPI UI at
`/docs`.

---

## Quick start

Prerequisites: **Node 18+**, **Python 3.11–3.13**. No Docker, no database
server, no internet, no API keys.

> Python 3.14 does not work. The pinned `pydantic-core` builds through PyO3,
> which refuses anything newer than 3.13, and pip fails deep inside a Rust
> build. `scripts/start.sh` checks this before it does anything else.

**macOS / Linux**

```bash
git clone https://github.com/anishc23/sih-qpleak.git
cd sih-qpleak
./scripts/start.sh
```

**Windows**

```powershell
git clone https://github.com/anishc23/sih-qpleak.git
cd sih-qpleak
.\scripts\start.ps1
```

Either script installs dependencies, starts a local Hardhat chain, deploys both
contracts, seeds 37 encrypted questions and seven demo accounts, and starts the
API and the web app. `scripts/stop.sh` stops everything again.

Then prove the whole thing works:

```powershell
backend\.venv\Scripts\python.exe scripts\e2e_demo.py
```

<details>
<summary>Manual startup (macOS / Linux, or if you prefer four terminals)</summary>

```bash
# 1. blockchain
cd blockchain && npm install && npx hardhat node

# 2. contracts (new terminal)
cd blockchain && npx hardhat run scripts/deploy.js --network localhost

# 3. backend (new terminal)
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed --reset
uvicorn app.main:app --reload

# 4. verify
python scripts/e2e_demo.py
```
</details>

### Resetting the demo

Use `scripts/reset_demo.sh`. Do not reset the database on its own.

Identifiers like `PAPER-2026-001` and `Q-000001` are regenerated from the start
by `seed --reset`, but the chain still holds the previous run's records under
those same identifiers, and the contracts then refuse everything that follows —
`QuestionAlreadyRegistered`, `InvalidLifecycleTransition`, and most visibly
`PaperAlreadyRegistered`, after which no new paper can ever be sealed. The
contracts are right to refuse; the mistake is resetting one half of the system.
Reset both together, or neither.

### Demo accounts

Password for all: `SecureLock#2026` *(obviously fake, local demo only)*

| Email | Role | Can do |
|---|---|---|
| `admin@securelock.demo` | SUPER_ADMIN | Manage users and audit — **not** read question content |
| `setter1@securelock.demo` | QUESTION_SETTER | Write own questions only |
| `setter2@securelock.demo` | QUESTION_SETTER | Write own questions only |
| `setter3@securelock.demo` | QUESTION_SETTER | Write own questions only |
| `reviewer@securelock.demo` | REVIEWER | Read + approve, never edit |
| `authority@securelock.demo` | EXAM_AUTHORITY | Assemble, encrypt, lock, release |
| `auditor@securelock.demo` | AUDITOR | Verify hashes and provenance — no plaintext |

---

## Architecture

```
                            SECURELOCK
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
   FastAPI backend         SQLite/Postgres         EVM chain
        │                       │                       │
   ┌────┴────┐             metadata,             QuestionRegistry.sol
   │         │             ciphertext,           PaperTimeLock.sol
 AES-GCM  RBAC +           wrapped keys,                │
 SHA-256  audit chain      audit log            hashes, provenance,
   │                                            access events,
   └──────────── plaintext never persisted ─── release condition
```

**The invariant everything rests on:** content lives off-chain, encrypted. The
chain holds only cryptographic fingerprints, pseudonymous actor hashes,
timestamps and the release condition. No question text, no answers, no keys, no
personal data ever reaches the chain.

### Three layers of defence

1. **Question level** — every question gets its own AES-256 key, its own SHA-256
   identity, an append-only version history, independent READ/WRITE/APPROVE
   grants, and an on-chain provenance record.
2. **Assembly level** — the paper is synthesised from a pool by a seeded
   optimiser that balances the blueprint, penalises near-duplicates, and spreads
   authorship. A setter cannot predict which of their questions is used, against
   what, or in what wording.
3. **Paper level** — the final paper is encrypted, its hash registered on chain
   with a release time, and decryption is refused until the contract says
   otherwise.

---

## Why blockchain here (and where it isn't the answer)

We do **not** claim blockchain is the innovation. AES, SHA-256 and smart
contracts are all ordinary technology. The contribution is the *combination*,
applied to the question lifecycle rather than just the final file.

Blockchain earns its place in exactly two spots where a central database creates
a trust problem:

- **Provenance and audit** — a database administrator can rewrite history. An
  on-chain anchor means they cannot do it *undetectably*.
- **The release condition** — a server clock can be changed by whoever runs the
  server. `block.timestamp` cannot be, by that person or by an end user.

Everything else — accounts, ciphertext, query-serving, detailed audit metadata —
stays in a normal relational database, because that is the right tool.

### What we explicitly do not claim

- ❌ "100% leak proof" — a human who can see a question can photograph it.
- ❌ "Blockchain proves someone read a question" — it proves an authorised
  account requested it through the system.
- ❌ "`block.timestamp` is perfectly accurate" — validators have some leeway.
  The honest claim is that *an end user cannot bypass the condition from their
  own device*.
- ❌ "AI guarantees security" — the synthesis engine reduces predictability. That
  is a probabilistic improvement, not a guarantee.

✅ What we do claim: **tamper-evident**, **defence in depth**, **traceable
provenance**, **blockchain-enforced release**, **reduced and investigable
insider risk**.

---

## The demo, in seven beats

1. **Create** — setter writes a question. It's encrypted, hashed, anchored. Real
   transaction hash shown.
2. **Read** — another setter tries to open it → **denied**, and the denial is
   logged and anchored. The auditor is denied too. So is the admin.
3. **Review** — reviewer approves. The question enters the pool. It is now frozen
   against edits, including by its author.
4. **Assemble** — the authority generates a paper. Blueprint compliance,
   duplicate risk, per-question selection reasoning and contributor spread are
   all displayed.
5. **Lock** — paper encrypted, hash registered on chain, release time armed.
6. **Attack** — call the decrypt API directly → `423 LOCKED`. Set your clock to
   2099 → still `423`. Setters are refused entirely, before and after release.
7. **Release** — chain time passes the threshold, the contract permits release,
   the paper decrypts. Then open the audit trail and break one row on purpose:
   `TAMPERING DETECTED`.

Step 6 is the one to spend time on with judges. `scripts/e2e_demo.py` runs all
seven and asserts each outcome.

---

## Project layout

```
sih-qpleak/
├── backend/
│   ├── app/
│   │   ├── api/          auth, questions, papers, audit routers
│   │   ├── security/     crypto (AES-GCM, SHA-256), keyvault, passwords, tokens
│   │   ├── services/     questions, papers, synthesis, permissions, audit, blockchain
│   │   ├── models.py     13 tables, foreign keys, indexes
│   │   ├── schemas.py    Pydantic request/response contracts
│   │   └── seed.py       6 accounts, 37 questions, 1 exam
│   └── tests/            44 security tests
├── blockchain/
│   ├── contracts/        QuestionRegistry.sol, PaperTimeLock.sol
│   ├── test/             37 contract tests
│   └── scripts/deploy.js writes addresses + ABIs for the backend to pick up
├── scripts/
│   ├── start.sh          one-command startup (macOS / Linux)
│   ├── start.ps1         one-command startup (Windows)
│   ├── stop.sh           stop everything start.sh began
│   ├── reset_demo.sh     reset chain AND database together -- read this before
│   │                     you reset either one on its own
│   └── e2e_demo.py       full demo flow, asserted
└── docs/
    └── PROJECT_BRIEF.md  the original problem statement and design brief
```

---

## Configuration

Everything is environment-driven; see [`.env.example`](.env.example). With no
`.env` at all the stack still runs — generated dev secrets are persisted to
`backend/.dev-secrets.json` (gitignored) so they stay stable across processes.

Two settings worth knowing:

- `ENCRYPTION_MASTER_KEY` — base64 of 32 bytes. Wraps every per-question and
  per-paper data key. In production this belongs in a KMS or HSM, not a file.
- `NEXT_PUBLIC_RPC_URL` and `NEXT_PUBLIC_PAPER_CONTRACT` — the landing page
  reads the chain directly from the browser rather than through the API, so the
  live seal works before anyone signs in. Both have working defaults for the
  local demo; set them if you move the chain or deploy elsewhere.
- `BLOCKCHAIN_RPC_URL` — defaults to the local Hardhat node. Point it at any
  EVM-compatible testnet with `BLOCKCHAIN_PRIVATE_KEY` set. No public testnet is
  hardcoded, deliberately: testnets get deprecated and demos should not depend
  on one.

---

## Running the tests

```bash
cd blockchain && npx hardhat test     # 37 contract tests
cd backend && .venv/Scripts/python -m pytest tests -q   # 44 security tests
python scripts/e2e_demo.py            # full flow over real HTTP
```

---

## Status

**Built and verified:** smart contracts, backend, cryptography, RBAC, synthesis
engine, audit chain, seed data, startup tooling, three test suites.

**Frontend:** Next.js 14 + TypeScript + Tailwind, 16 routes, production build
clean. Landing, login, dashboard, question vault, question detail, create,
review queue, variations, paper builder, papers, paper detail, time-lock demo,
audit trail, blockchain explorer, security dashboard.

> If port 3000 is already taken on your machine, start it elsewhere:
> `cd frontend && npx next start -p 3100`.

**Documentation:** `docs/SecureLock_Explained.pdf` explains the whole system
from scratch for a non-technical reader; `docs/SecureLock_User_Manual.pdf` is
the operator's guide to running and demonstrating the prototype.

---

## Known limitations

Stated plainly, because being straight about these is more persuasive than
overclaiming:

- **The master key is a single point of trust.** Whoever holds it can decrypt the
  database. Mitigated by KMS/HSM in production; the key-vault interface is three
  functions wide precisely so it can be swapped.
- **A local Hardhat chain is not a real trust anchor.** It demonstrates the
  mechanism. Production would use a permissioned or consortium chain with
  independent validators.
- **Question variation is rule-based, not a language model.** It restates the
  instruction verb and appends a type-appropriate instruction, leaving the
  substantive clause untouched — which is exactly why the expected answer cannot
  drift. Labelled as such throughout.
- **Blockchain availability is a hard dependency for release.** If the node is
  unreachable, decryption is refused rather than falling back to a server clock.
  That is the correct failure direction, but it is a real operational constraint.
- **Nothing here stops a photograph.** The objective is to reduce exposure, make
  access traceable, and make tampering evident.

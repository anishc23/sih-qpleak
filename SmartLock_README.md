# SmartLock — Blockchain-Backed Secure Examination Paper Management

> **SIH Internal Hackathon Prototype**
>
> A high-end software prototype for reducing examination-paper leakage risk by combining **role-based access control, per-question provenance, encryption, blockchain-backed auditability, and smart-contract time-lock enforcement**.

---

## 1. Problem Statement

Examination-paper leaks can occur at multiple points in the paper lifecycle:

1. A question setter or authorized contributor may intentionally or accidentally leak a question.
2. Questions may be shared through insecure channels during paper creation.
3. An administrator may access the final paper before the scheduled examination.
4. A compromised account may attempt to download or distribute the paper.
5. Conventional server/database audit logs can potentially be modified by privileged users.
6. Client-side time checks are vulnerable because a user can manipulate their device clock.

A secure system therefore needs protection **from the question-creation stage through final paper release**, rather than relying only on a timer after the paper has already been assembled.

---

## 2. Our Core Idea

SmartLock treats the examination paper as a secure lifecycle rather than a single file.

### Security layers

```text
Question Setter
      |
      v
+-----------------------+
| Secure Question Entry |
+-----------------------+
      |
      v
+-----------------------+
| Encrypt Question      |
| Generate SHA-256 Hash |
+-----------------------+
      |
      v
+-----------------------+
| Question Registry     |
| Blockchain Record     |
+-----------------------+
      |
      v
+-----------------------+
| Paper Assembly        |
| Only Authorized Roles |
+-----------------------+
      |
      v
+-----------------------+
| Encrypt Final Paper   |
+-----------------------+
      |
      v
+-----------------------+
| Blockchain Smart      |
| Contract Time-Lock    |
+-----------------------+
      |
      v
+-----------------------+
| Exam-Time Release     |
+-----------------------+
      |
      v
+-----------------------+
| Immutable Audit Trail |
+-----------------------+
```

The important design principle is:

> **Blockchain does not store the actual examination questions. It stores cryptographic proofs, provenance, access events, and release conditions.**

This avoids putting sensitive examination content on a public ledger.

---

# 3. What Makes SmartLock Different?

The prototype uses blockchain at **two important levels**.

## Level 1 — Question-Level Provenance

Whenever an authorized question setter submits a question:

- The question is encrypted.
- A cryptographic hash is generated.
- A blockchain record is created for that question.
- The creator identity/role is associated with the record.
- The system records creation and subsequent access events.
- The actual question content remains off-chain.

This creates a tamper-evident provenance trail.

### Conceptually

```text
Question Q1
   |
   +--> AES encrypted content
   |
   +--> SHA-256 hash
   |
   +--> Blockchain Question ID
   |
   +--> Creator identity
   |
   +--> Timestamp
   |
   +--> Status
   |
   +--> Access history
```

---

## Level 2 — Final Paper Time-Lock

After the paper is assembled:

1. The final paper is encrypted.
2. Its hash is generated.
3. The encrypted artifact is stored off-chain.
4. The hash and scheduled release time are registered in the smart contract.
5. Before the scheduled time, the contract refuses release.
6. At/after the scheduled time, the release condition becomes valid.
7. The release event is recorded on-chain.

The frontend **never decides whether the paper can be released based on the user's computer clock**.

Instead:

```text
User Browser
     |
     | request release
     v
Backend / Web3 Layer
     |
     | query smart contract
     v
Blockchain
     |
     | block.timestamp >= releaseTime ?
     |
   NO +-----> DENY
     |
   YES
     |
     v
Allow controlled release
```

---

# 4. Important Security Clarification

SmartLock does **not** claim that blockchain makes an examination paper impossible to leak.

If an authorized person sees the plaintext question, they could still photograph it, copy it, memorize it, or intentionally disclose it.

The objective is instead to:

- reduce unnecessary exposure,
- reduce insider access,
- make unauthorized access detectable,
- establish question provenance,
- make unauthorized modification detectable,
- prevent premature **system-mediated decryption/release**,
- and provide an auditable chain of custody.

This is a much more realistic and maintainable security model.

---

# 5. Protection Against the Paper Setter Leaking a Question

This is one of the most important design decisions.

A naive system might try to automatically generate every examination question using AI. That is unnecessary, difficult to validate, and creates another major security dependency.

SmartLock instead uses **controlled question contribution + provenance + access logging**.

## Workflow

```text
Setter A
   |
   | submits Q1
   v
Hash(Q1) -> Blockchain
   |
   +--> creator = Setter A
   +--> timestamp
   +--> question ID
   +--> status

Setter B
   |
   | submits Q2
   v
Hash(Q2) -> Blockchain
```

The system can then assemble a final paper from independently submitted questions.

If a question later appears outside the system:

- its hash/provenance can be compared,
- the originating contributor can be identified,
- access records can be examined,
- and the organization has an auditable chain of custody.

## Optional safer enhancement

For the prototype, the system may support an **AI-assisted question transformation layer**:

```text
Original Question
       |
       v
AI transformation
       |
       v
Semantically equivalent variant
       |
       v
Validation
       |
       v
Final Question
```

This should be presented as an **optional risk-reduction feature**, not as the primary security mechanism.

The AI must not silently change:

- learning objective,
- difficulty,
- answer correctness,
- marks,
- constraints,
- or syllabus alignment.

A human reviewer should approve transformed questions.

---

# 6. Why Not Store Questions Directly on Blockchain?

Because blockchain is not appropriate for storing sensitive examination content.

Instead:

```text
             OFF-CHAIN
        +------------------+
        | Encrypted Question|
        | Encrypted Paper   |
        +------------------+
                 |
                 | SHA-256
                 v
             ON-CHAIN
        +------------------+
        | Question Hash     |
        | Paper Hash        |
        | Creator ID/hash   |
        | Timestamp         |
        | Access Events     |
        | Release Time      |
        +------------------+
```

The blockchain acts as a **tamper-evident trust layer**, not as a file-storage system.

---

# 7. Read and Write Access Separation

A major feature of SmartLock is separating **write operations** from **read/access operations**.

## Write Operations

Examples:

- create question,
- modify question,
- submit question,
- assemble paper,
- register paper,
- schedule release.

These should be restricted to appropriate roles.

## Read Operations

Examples:

- view question metadata,
- view paper status,
- request paper release,
- inspect audit history.

These should have separate authorization policies.

### Example

```text
                    QUESTION
                       |
              +--------+--------+
              |                 |
           WRITE             READ
              |                 |
        Setter/Admin       Reviewer/Admin
              |                 |
              v                 v
        Blockchain          Access Log
        provenance          event
```

This allows the prototype to demonstrate that:

> **Reading a question is itself a security-sensitive event.**

---

# 8. Per-Question Blockchain Records

Each question receives a unique question identifier.

Example:

```text
Question ID:
QL-2026-000001
```

A blockchain record contains metadata such as:

```json
{
  "questionId": "QL-2026-000001",
  "questionHash": "SHA256...",
  "creatorRole": "QUESTION_SETTER",
  "createdAt": "...",
  "status": "SUBMITTED"
}
```

Do not store the plaintext question on-chain.

---

# 9. Smart Contract Design

The prototype should use a simple, auditable smart contract rather than an unnecessarily complex decentralized application.

The contract should support:

### Question registration

```text
registerQuestion(
    questionId,
    questionHash
)
```

### Question access logging

```text
recordQuestionAccess(
    questionId,
    accessType
)
```

Where `accessType` can represent actions such as:

```text
READ
WRITE
ASSEMBLE
EXPORT
```

### Final paper registration

```text
registerPaper(
    paperId,
    paperHash,
    releaseTime
)
```

### Release check

```text
canRelease(paperId)
```

The contract uses blockchain time:

```solidity
block.timestamp
```

rather than:

```javascript
new Date()
```

for the security decision.

### Release

```text
releasePaper(paperId)
```

The contract checks:

```text
current blockchain timestamp
        >=
scheduled release timestamp
```

Only then can the release state transition.

---

# 10. Blockchain Timestamp Security

The user's local computer clock must never be trusted.

### Insecure

```javascript
if (new Date() >= examTime) {
    releasePaper();
}
```

A user can manipulate the local clock.

### SmartLock

```solidity
require(
    block.timestamp >= releaseTime,
    "Paper is still locked"
);
```

The security decision is made by the blockchain execution environment.

### Important nuance

`block.timestamp` is not a perfect atomic global clock and blockchain timestamp rules depend on the selected network. Therefore SmartLock should not claim that timestamps are mathematically impossible to manipulate under every blockchain attack model.

The correct claim is:

> **A normal end user cannot bypass the release condition simply by changing their device clock or browser time. The contract evaluates the blockchain's timestamp, not the user's local time.**

For an SIH prototype, this is the appropriate security boundary.

---

# 11. Encryption Architecture

The actual examination material should be encrypted off-chain.

Recommended prototype flow:

```text
Question / Paper
       |
       v
Generate random AES key
       |
       v
AES-256-GCM encryption
       |
       +--------------------+
       |                    |
       v                    v
Encrypted file         SHA-256 hash
       |                    |
       v                    v
Encrypted storage       Blockchain
```

AES-GCM is preferable to plain AES-CBC because it provides authenticated encryption.

The application should never store plaintext examination papers in publicly accessible storage.

---

# 12. Key Management

The prototype should keep key management deliberately simple and demonstrable.

A practical prototype architecture is:

```text
                    Key Service
                        |
             +----------+----------+
             |                     |
       Paper Encryption       Controlled Release
             |                     |
             v                     v
        Encrypted file      Release authorization
```

For the SIH prototype:

- encryption keys may be managed by a backend key-management module,
- the database must store keys encrypted/wrapped rather than plaintext,
- role checks must happen before key retrieval,
- key-release authorization must require the blockchain time-lock,
- all key-related access should generate audit events.

For production, replace the prototype key store with a proper KMS/HSM.

---

# 13. Roles

The system should implement at least the following roles.

## SUPER_ADMIN

Responsibilities:

- manage users,
- configure examination,
- configure release time,
- inspect system-wide audit trail.

Should **not** automatically be able to bypass the blockchain release condition.

---

## QUESTION_SETTER

Responsibilities:

- create questions,
- submit questions,
- view own permitted questions,
- see submission status.

Should not be able to:

- view other setters' restricted questions,
- download the final paper,
- bypass release time.

---

## REVIEWER

Responsibilities:

- review submitted questions,
- approve/reject questions,
- participate in paper assembly where authorized.

---

## PAPER_ADMIN

Responsibilities:

- assemble final paper,
- encrypt final paper,
- register final paper,
- schedule release.

Should not be able to bypass smart-contract release conditions.

---

## AUDITOR

Responsibilities:

- view blockchain-backed audit records,
- investigate access history,
- verify hashes,
- verify paper provenance.

Should be read-only.

---

## EXAM_CENTER

Responsibilities:

- request access after release time,
- download/decrypt the released paper,
- view only papers assigned to the center.

---

# 14. Authentication

Implement secure authentication for the prototype.

Recommended:

- JWT-based authentication,
- hashed passwords using bcrypt/Argon2,
- role-based authorization,
- short-lived access tokens,
- protected API endpoints.

Example:

```text
POST /api/auth/login
POST /api/auth/register

GET  /api/questions
POST /api/questions
GET  /api/questions/:id

POST /api/papers
GET  /api/papers/:id

POST /api/papers/:id/release

GET  /api/audit
```

Every protected endpoint must verify:

```text
Authentication
      +
Role
      +
Resource permission
```

---

# 15. Audit Trail

Auditability is one of the strongest reasons for using blockchain.

The system should record events such as:

```text
USER_LOGIN
QUESTION_CREATED
QUESTION_UPDATED
QUESTION_READ
QUESTION_SUBMITTED
QUESTION_APPROVED
QUESTION_REJECTED
PAPER_CREATED
PAPER_ASSEMBLED
PAPER_ENCRYPTED
PAPER_REGISTERED
RELEASE_ATTEMPTED
RELEASE_DENIED
PAPER_RELEASED
PAPER_DOWNLOADED
```

Each event should have:

- event ID,
- user/actor,
- role,
- resource ID,
- event type,
- timestamp,
- IP/device metadata where appropriate,
- transaction hash if blockchain-backed,
- success/failure status.

---

# 16. Hybrid Audit Model

Do not put every large audit payload directly on-chain.

Use:

```text
PostgreSQL
   |
   | detailed application audit
   |
   v
Blockchain
   |
   | hash / event proof
   |
   v
Immutable verification
```

For important security events:

1. create the application audit record,
2. calculate a hash,
3. record the hash/event on-chain.

This gives the project both:

- practical database performance,
- and tamper-evident blockchain verification.

---

# 17. Paper Lifecycle

The complete lifecycle should be:

```text
DRAFT
  |
  v
SUBMITTED
  |
  v
REVIEW
  |
  +----> REJECTED
  |
  v
APPROVED
  |
  v
ASSEMBLED
  |
  v
ENCRYPTED
  |
  v
BLOCKCHAIN_REGISTERED
  |
  v
LOCKED
  |
  v
RELEASE_TIME_REACHED
  |
  v
RELEASED
  |
  v
DOWNLOADED
```

Every state transition should be authorized and auditable.

---

# 18. UI / Dashboard

The prototype should look like a serious government/enterprise security platform.

## Login

Display:

- SmartLock logo/name,
- username/email,
- password,
- role-aware authentication.

---

## Admin Dashboard

Cards:

```text
Total Questions
Pending Reviews
Approved Questions
Active Papers
Locked Papers
Released Papers
Security Events
```

Include:

- recent blockchain transactions,
- suspicious access attempts,
- paper release countdown,
- audit activity.

---

## Question Setter Dashboard

Show:

- Create Question
- My Questions
- Submission Status
- Access History

When submitting:

```text
Question
Subject
Topic
Difficulty
Marks
Tags
```

After submission:

```text
Question ID
Hash
Blockchain Transaction
Status
Created At
```

---

## Reviewer Dashboard

Show:

- pending questions,
- question metadata,
- approve/reject controls,
- review history.

---

## Paper Assembly Dashboard

Allow authorized users to:

1. select approved questions,
2. preview metadata,
3. assemble paper,
4. generate encrypted final paper,
5. calculate paper hash,
6. register paper on blockchain,
7. specify release time.

---

## Paper Lock Screen

Display:

```text
EXAMINATION PAPER

Status: 🔒 LOCKED

Scheduled Release:
18 Aug 2026
10:00 AM IST

Blockchain Verification:
✓ Registered
✓ Hash Verified
✓ Release Condition Active

Time remaining:
01:32:45
```

The countdown is only for UI.

**The countdown must never determine access.**

---

## Release Screen

After blockchain validation:

```text
Status: 🔓 RELEASED

Blockchain condition:
PASSED

Transaction:
0x....

Paper hash:
SHA-256....

Download Paper
```

---

## Audit Dashboard

Provide filtering:

```text
Actor
Role
Event
Question ID
Paper ID
Date
Success/Failure
Blockchain transaction
```

Show a timeline:

```text
10:01  QUESTION_CREATED
10:02  QUESTION_SUBMITTED
10:05  QUESTION_READ
10:07  QUESTION_APPROVED
10:20  PAPER_ASSEMBLED
10:21  PAPER_ENCRYPTED
10:22  PAPER_REGISTERED
...
```

---

# 19. Recommended Technology Stack

Use a stack that is realistic for a student team.

## Frontend

```text
React
Vite
Tailwind CSS
React Router
Axios
Ethers.js
```

---

## Backend

Recommended:

```text
Python
FastAPI
SQLAlchemy
PostgreSQL
Pydantic
JWT
Passlib / Argon2
```

Alternative:

```text
Node.js
Express
PostgreSQL
```

Do not build two backends.

---

## Blockchain

Use an EVM-compatible test network.

Recommended architecture:

```text
Solidity
   |
   v
Hardhat
   |
   v
Testnet
   |
   v
Ethers.js
```

Avoid relying on deprecated network infrastructure.

If a particular testnet is unavailable, use a currently supported EVM testnet or a local Hardhat/Anvil blockchain for the guaranteed demo.

---

## Storage

Prototype:

```text
PostgreSQL -> metadata
Local secure storage / MinIO -> encrypted files
Blockchain -> hashes + critical events
```

Optional:

```text
IPFS -> encrypted artifacts
```

Do not store plaintext exam papers on IPFS.

---

# 20. Suggested Project Structure

```text
smartlock/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── layouts/
│   │   ├── services/
│   │   ├── hooks/
│   │   ├── utils/
│   │   └── App.jsx
│   └── package.json
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── auth/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── blockchain/
│   │   ├── crypto/
│   │   ├── audit/
│   │   └── main.py
│   └── requirements.txt
│
├── blockchain/
│   ├── contracts/
│   │   └── SmartLock.sol
│   ├── scripts/
│   ├── test/
│   ├── hardhat.config.js
│   └── package.json
│
├── storage/
│   └── encrypted/
│
├── database/
│   └── migrations/
│
├── docs/
│   ├── architecture.md
│   ├── security.md
│   └── demo.md
│
├── docker-compose.yml
├── .env.example
└── README.md
```

---

# 21. Database Design

Suggested tables:

## users

```text
id
name
email
password_hash
role
is_active
created_at
```

## questions

```text
id
question_uid
encrypted_content
question_hash
creator_id
status
created_at
updated_at
```

## question_access

```text
id
question_id
user_id
access_type
timestamp
success
```

## papers

```text
id
paper_uid
encrypted_file_path
paper_hash
created_by
release_time
status
blockchain_tx_hash
created_at
```

## paper_questions

```text
paper_id
question_id
sequence_number
```

## audit_logs

```text
id
actor_id
event_type
resource_type
resource_id
metadata
timestamp
blockchain_tx_hash
success
```

---

# 22. Smart Contract Data Model

A simple conceptual model:

```solidity
struct QuestionRecord {
    bytes32 questionHash;
    bytes32 creatorHash;
    uint256 createdAt;
    bool exists;
}

struct PaperRecord {
    bytes32 paperHash;
    uint256 releaseTime;
    bool released;
    bool exists;
}
```

Mappings:

```solidity
mapping(bytes32 => QuestionRecord) questions;
mapping(bytes32 => PaperRecord) papers;
```

Events:

```solidity
event QuestionRegistered(
    bytes32 indexed questionId,
    bytes32 indexed questionHash,
    bytes32 indexed creatorHash
);

event QuestionAccessed(
    bytes32 indexed questionId,
    bytes32 indexed actorHash,
    string accessType
);

event PaperRegistered(
    bytes32 indexed paperId,
    bytes32 indexed paperHash,
    uint256 releaseTime
);

event PaperReleased(
    bytes32 indexed paperId,
    uint256 timestamp
);
```

---

# 23. Important Smart Contract Rule

Do not make the frontend responsible for security.

Bad:

```text
Frontend:
if countdown == 0
    download()
```

Good:

```text
Frontend
   |
   v
Backend / Wallet
   |
   v
Smart Contract
   |
   +--> releaseTime reached?
   |
  NO ---> reject
   |
  YES
   |
   v
release state
```

The frontend countdown is cosmetic.

---

# 24. Preventing Unauthorized Release

A good implementation should have both:

### Time condition

```text
block.timestamp >= releaseTime
```

AND

### Authorization condition

Only an authorized release actor should be able to trigger final release.

For example:

```text
EXAM_CENTER
     |
     | release request
     v
Smart Contract
     |
     +--> authorized?
     |
     +--> release time reached?
     |
     +--> already released?
```

All conditions must pass.

---

# 25. Question-Level Security vs Paper-Level Security

These are separate problems.

## Question-level security

Goal:

> Reduce unauthorized exposure and establish provenance during paper creation.

Tools:

- RBAC,
- encryption,
- per-question hashes,
- separate read/write permissions,
- access logging,
- blockchain provenance.

## Paper-level security

Goal:

> Prevent premature system-mediated release of the final paper.

Tools:

- encryption,
- smart contract,
- blockchain timestamp,
- time-lock,
- controlled decryption,
- audit trail.

This separation makes the architecture much more defensible.

---

# 26. Optional AI Question Transformation

This feature should be optional in the prototype.

Example:

```text
Setter submits:
"What is the time complexity of binary search?"

AI Transformation:
"Determine the asymptotic time complexity of searching
for an element in a sorted array using binary search."

Validation:
- same concept ✓
- same expected answer ✓
- same difficulty ✓
- same marks ✓

Final Question:
approved
```

The system should retain:

```text
original_question_hash
transformed_question_hash
transformation_model
transformation_timestamp
reviewer_approval
```

This provides provenance.

Do not claim that AI transformation makes leaks impossible.

---

# 27. Threat Model

The prototype should explicitly consider:

| Threat | Mitigation |
|---|---|
| User changes local clock | Blockchain timestamp |
| User modifies frontend | Backend + smart contract validation |
| Database modification | Hash verification + blockchain |
| Unauthorized question access | RBAC + access logging |
| Question modification | SHA-256 hash |
| Premature paper release | Smart-contract time-lock |
| Admin attempts bypass | Contract-controlled release condition |
| Leaked setter question | Provenance + access audit + controlled exposure |
| Compromised account | RBAC + audit + least privilege |
| Public blockchain data exposure | Store hashes, not plaintext |
| File storage compromise | AES-GCM encryption |
| AI changes question meaning | Human validation/review |
| Blockchain unavailable | Local/testnet fallback for demo |

---

# 28. What Blockchain Actually Guarantees

Be precise during the SIH presentation.

Blockchain provides:

- tamper-evident records,
- decentralized verification,
- transparent transaction history,
- cryptographic integrity,
- smart-contract enforcement,
- independent verification of important events.

Blockchain does **not** guarantee:

- that a human cannot photograph a question,
- that a compromised endpoint cannot display plaintext,
- that an authorized setter cannot verbally disclose a question,
- perfect timestamps,
- perfect identity security,
- complete prevention of insider threats.

This distinction makes the project technically credible.

---

# 29. SIH Demo Scenario

The entire demonstration should be possible in approximately 5–8 minutes.

## Demo 1 — Login

Login as:

```text
Question Setter
```

Create a question.

Show:

```text
Question ID
Hash
Status
```

---

## Demo 2 — Blockchain Provenance

Show:

```text
Question registered
Transaction hash
Blockchain record
```

Explain:

> "We don't store the question on blockchain. We store its cryptographic fingerprint and provenance."

---

## Demo 3 — Read Access

Login as Reviewer.

Open the question.

Show:

```text
QUESTION_READ
```

in the audit trail.

---

## Demo 4 — Paper Assembly

Login as Paper Admin.

Select approved questions.

Generate paper.

Show:

```text
Paper Hash
Encrypted Paper
Blockchain Registration
Release Time
```

---

## Demo 5 — Time Lock

Set release time a few minutes into the future.

Attempt access.

Show:

```text
LOCKED
Release condition not satisfied
```

Then change the local computer/browser time to the future.

Attempt again.

Show:

```text
STILL LOCKED
```

This is a very strong demonstration.

Explain:

> "The UI clock changed, but access did not change because the security decision is made using blockchain time."

---

## Demo 6 — Release

After the blockchain release time is reached:

```text
Smart contract condition:
PASSED

Paper:
RELEASED
```

Download/decrypt the paper.

---

## Demo 7 — Audit

Open the audit dashboard.

Show:

```text
Question Created
Question Read
Question Approved
Paper Assembled
Paper Registered
Release Attempt Denied
Paper Released
Paper Downloaded
```

Then show the corresponding blockchain transaction.

---

# 30. Security Demonstration

A particularly strong internal-hackathon demo is:

### Attempt 1

User changes system clock.

Result:

```text
❌ Access denied
```

### Attempt 2

User modifies frontend JavaScript.

Result:

```text
❌ Access denied
```

### Attempt 3

User directly calls the backend release API before the scheduled time.

Result:

```text
❌ Access denied
```

### Attempt 4

After release time:

```text
✅ Access granted
```

This demonstrates that the system is not relying on UI security.

---

# 31. What the Judges Should Understand

The core pitch:

> **"SmartLock secures the entire examination-paper lifecycle rather than only securing the final PDF."**

Then explain:

```text
Question Creation
      ↓
Question Provenance
      ↓
Controlled Access
      ↓
Encrypted Paper Assembly
      ↓
Blockchain Registration
      ↓
Smart-Contract Time Lock
      ↓
Controlled Release
      ↓
Immutable Audit Trail
```

---

# 32. Why Blockchain Is Necessary Here

Do not say:

> "We used blockchain because blockchain is secure."

Instead say:

> "We use blockchain where a conventional centralized database creates a trust problem: provenance, critical audit events, and release conditions."

The blockchain provides an independent verification layer.

The normal database remains responsible for:

- application data,
- user accounts,
- UI queries,
- encrypted artifacts,
- detailed audit information.

This is a **hybrid architecture**, not "put everything on blockchain."

---

# 33. Feasibility

This project is feasible as a software prototype because it does not require:

- IoT devices,
- custom hardware,
- physical sensors,
- specialized infrastructure,
- expensive AI training.

It can run using:

```text
Laptop
+
Local PostgreSQL
+
FastAPI
+
React
+
Local blockchain / EVM testnet
+
Browser wallet
```

For SIH internal evaluation, a local blockchain can be used for reliable offline demonstrations, while a public testnet can be used to demonstrate real blockchain transactions.

---

# 34. Production Evolution

The prototype should be designed so it can later evolve into a production system.

Potential upgrades:

### Identity

- institutional SSO,
- government identity infrastructure,
- hardware-backed authentication.

### Key management

- cloud KMS,
- HSM,
- threshold cryptography.

### Blockchain

- permissioned government blockchain,
- consortium blockchain,
- institutional validator nodes.

### Storage

- secure government cloud,
- encrypted object storage.

### Monitoring

- SIEM integration,
- anomaly detection,
- automated insider-risk alerts.

### AI

- question similarity detection,
- duplicate detection,
- semantic leak detection,
- controlled question transformation,
- anomaly detection on access behavior.

---

# 35. Future Advanced Feature: Insider-Risk Detection

The question-access logs can later feed an anomaly detection model.

Example:

```text
Normal:
Setter accesses 5 own questions/day

Suspicious:
Setter accesses 400 questions
from unrelated subjects
at 2:30 AM
```

The system can generate:

```text
RISK SCORE: 94/100
```

This can trigger:

- additional authentication,
- temporary account lock,
- administrator review,
- investigation.

This is a natural future AI extension of the blockchain audit layer.

---

# 36. Security Principles

The project should follow:

### Least privilege

Users only get the permissions they require.

### Zero trust

Never trust:

- browser time,
- frontend state,
- client-provided role,
- client-provided paper status.

### Defense in depth

Use multiple layers:

```text
Authentication
+
Authorization
+
Encryption
+
Hashing
+
Blockchain
+
Audit
+
Time Lock
```

### Minimize plaintext exposure

The fewer people/systems that see plaintext, the lower the leak risk.

### Off-chain data, on-chain proof

Sensitive content stays off-chain.

---

# 37. Environment Variables

Create:

```text
.env.example
```

Example:

```env
DATABASE_URL=postgresql://user:password@localhost:5432/smartlock

JWT_SECRET=change-me

BLOCKCHAIN_RPC_URL=
BLOCKCHAIN_PRIVATE_KEY=

SMARTLOCK_CONTRACT_ADDRESS=

ENCRYPTION_KEY=

STORAGE_PATH=./storage/encrypted
```

Never commit:

- private keys,
- passwords,
- JWT secrets,
- encryption keys,
- real credentials.

---

# 38. Local Development

## Backend

```bash
cd backend

python -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

uvicorn app.main:app --reload
```

---

## Frontend

```bash
cd frontend

npm install
npm run dev
```

---

## Blockchain

```bash
cd blockchain

npm install
npx hardhat compile
npx hardhat test
```

For local demonstration:

```bash
npx hardhat node
```

Deploy the contract using the provided deployment script.

---

# 39. Testing Requirements

The prototype must include automated tests.

## Authentication tests

- valid login,
- invalid password,
- inactive account,
- role authorization.

## Question tests

- question creation,
- duplicate question detection,
- hash generation,
- unauthorized read,
- unauthorized write.

## Paper tests

- paper assembly,
- encryption/decryption,
- hash verification,
- invalid paper detection.

## Smart contract tests

Test:

```text
register question
register paper
reject early release
allow release after time
reject duplicate release
reject unauthorized operation
```

## Security tests

Test:

```text
changed client clock
modified frontend state
direct API call
invalid JWT
wrong role
tampered encrypted file
tampered database hash
```

---

# 40. Demo Data

Include seeded demo accounts.

Example:

```text
admin@smartlock.local
setter1@smartlock.local
setter2@smartlock.local
reviewer@smartlock.local
paperadmin@smartlock.local
auditor@smartlock.local
examcenter@smartlock.local
```

Use clearly fake passwords documented only for local development.

---

# 41. Demo Mode

Add a controlled **Demo Mode** so the SIH presentation is reliable.

Demo Mode should allow:

- accelerated release times,
- seeded questions,
- seeded users,
- sample blockchain records,
- one-click reset,
- visible transaction hashes.

Important:

> Demo Mode must never remove the actual security checks.

It should only make the demonstration faster.

---

# 42. Verification Features

Provide a "Verify Integrity" button.

For a question:

```text
Current Hash
      |
      v
Compare with Blockchain Hash
      |
      +---- SAME ----> ✓ Integrity Verified
      |
      +---- DIFFERENT -> ⚠ Tampering Detected
```

For the final paper:

```text
Encrypted file
      |
      v
SHA-256
      |
      v
Blockchain hash
```

If different:

```text
🚨 PAPER INTEGRITY FAILURE
```

---

# 43. Suggested UI Security Indicators

Use visible status badges:

```text
🟢 VERIFIED
🔵 BLOCKCHAIN REGISTERED
🟡 PENDING REVIEW
🔴 ACCESS DENIED
🔒 TIME LOCKED
🔓 RELEASED
⚠ TAMPERING DETECTED
```

This makes the security architecture easy for judges to understand.

---

# 44. Deliverables

The completed prototype should include:

- [ ] React frontend
- [ ] FastAPI backend
- [ ] PostgreSQL database
- [ ] Authentication
- [ ] RBAC
- [ ] Question creation
- [ ] Per-question hashing
- [ ] Per-question blockchain registration
- [ ] Read/write access separation
- [ ] Question access logging
- [ ] Question review workflow
- [ ] Paper assembly
- [ ] AES-GCM encryption
- [ ] Paper hashing
- [ ] Smart contract
- [ ] Blockchain paper registration
- [ ] Blockchain time-lock
- [ ] Controlled release
- [ ] Audit dashboard
- [ ] Blockchain transaction viewer
- [ ] Integrity verification
- [ ] Demo mode
- [ ] Automated tests
- [ ] Docker setup
- [ ] Documentation

---

# 45. Final Architecture

```text
                         SMARTLOCK
                            |
        +-------------------+-------------------+
        |                   |                   |
        v                   v                   v
   React Frontend      FastAPI Backend      Blockchain
        |                   |                   |
        |              +----+----+              |
        |              |         |              |
        |           PostgreSQL  Crypto          |
        |              |         |              |
        |              |      AES-GCM           |
        |              |         |              |
        |              +----+----+              |
        |                   |                   |
        +-------------------+-------------------+
                            |
                            v
                    Encrypted Storage
```

Blockchain stores:

```text
Question Hashes
Paper Hashes
Provenance
Critical Access Events
Release Times
Release Events
```

Off-chain systems store:

```text
User accounts
Encrypted questions
Encrypted papers
Detailed audit metadata
Application state
```

---

# 46. The Three Core Innovations

For SIH, present the system around three pillars.

## 1. Question-Level Provenance

Every question receives a cryptographic identity and auditable lifecycle.

## 2. Blockchain-Enforced Time Lock

The final paper cannot be system-released before the blockchain-verified release condition.

## 3. End-to-End Auditability

The system creates a traceable chain from:

```text
Question
→ Contributor
→ Review
→ Paper Assembly
→ Encryption
→ Blockchain Registration
→ Release
→ Download
```

---

# 47. One-Line Pitch

> **SmartLock is a blockchain-backed examination security platform that protects question provenance, controls sensitive access, encrypts examination papers, and enforces tamper-evident time-locked release through smart contracts.**

---

# 48. Important Claims to Avoid

Do NOT tell judges:

❌ "Blockchain makes paper leaks impossible."

❌ "A blockchain timestamp can never be manipulated."

❌ "Our system guarantees that a question setter cannot leak a question."

❌ "AI completely prevents paper leaks."

❌ "Everything is stored on blockchain."

Instead say:

✅ "We reduce the attack surface."

✅ "We prevent unauthorized system-mediated early release."

✅ "We provide cryptographically verifiable provenance."

✅ "We make critical actions tamper-evident."

✅ "We minimize plaintext exposure."

✅ "We provide traceability for insider investigations."

---

# 49. SIH Presentation Narrative

Start with the problem:

> "Most examination security systems focus on protecting the final question paper. But the paper can be compromised much earlier — while individual questions are being created, reviewed, shared and assembled."

Then introduce SmartLock:

> "We therefore secure the entire lifecycle."

Show:

```text
Question
   ↓
Identity + Hash
   ↓
Blockchain Provenance
   ↓
Controlled Access
   ↓
Encrypted Assembly
   ↓
Blockchain Time Lock
   ↓
Exam-Time Release
   ↓
Immutable Audit
```

Finish with:

> "We are not claiming that technology can stop a human from taking a photograph of a question. Our objective is to minimize unnecessary exposure, prevent unauthorized digital access, make tampering detectable, and establish accountability across the complete examination-paper lifecycle."

---

# 50. Development Priority

Build in this order:

### Phase 1 — Foundation

1. Project setup
2. Database
3. Authentication
4. RBAC
5. Basic dashboards

### Phase 2 — Questions

6. Question creation
7. Encryption
8. Hashing
9. Question provenance
10. Read/write access logging

### Phase 3 — Paper

11. Review workflow
12. Paper assembly
13. Final paper encryption
14. Paper hash

### Phase 4 — Blockchain

15. Smart contract
16. Question registration
17. Paper registration
18. Access events
19. Time-lock
20. Release event

### Phase 5 — Security

21. Integrity verification
22. Authorization hardening
23. Attack simulations
24. Audit dashboard

### Phase 6 — SIH Demo

25. Demo data
26. Demo mode
27. Blockchain explorer integration
28. End-to-end demo
29. Automated tests
30. Documentation

---

# 51. Definition of Done

The project is considered complete when a judge can perform this flow:

```text
LOGIN
  ↓
CREATE QUESTION
  ↓
QUESTION HASH CREATED
  ↓
BLOCKCHAIN RECORD CREATED
  ↓
REVIEW QUESTION
  ↓
ASSEMBLE PAPER
  ↓
ENCRYPT PAPER
  ↓
REGISTER PAPER ON BLOCKCHAIN
  ↓
SET RELEASE TIME
  ↓
TRY EARLY ACCESS
  ↓
ACCESS DENIED
  ↓
CHANGE LOCAL COMPUTER TIME
  ↓
ACCESS STILL DENIED
  ↓
RELEASE TIME REACHED
  ↓
BLOCKCHAIN CONDITION PASSES
  ↓
PAPER RELEASED
  ↓
DOWNLOAD
  ↓
VERIFY AUDIT TRAIL
  ↓
VERIFY BLOCKCHAIN TRANSACTION
```

If this complete flow works reliably, SmartLock is ready for the SIH internal prototype demonstration.

---

## Final Principle

**SmartLock is not "a blockchain app."**

It is an **examination security system** where blockchain is used only where it provides a meaningful security property:

> **trusted provenance + tamper-evident audit + independently verifiable release conditions.**

Everything else should remain in conventional, maintainable software architecture.

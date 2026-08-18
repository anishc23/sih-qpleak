"""Seed demo users, a realistic question pool and a preconfigured exam.

Run with:  python -m app.seed        (add --reset to wipe first)

The pool deliberately contains several near-duplicate pairs so the similarity
engine has something real to find during the demo.

Demo passwords are obvious and documented in the README. They are for local
demonstration only and are not real credentials.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select

from app.database import Base, SessionLocal, engine, init_db
from app.models import (
    Difficulty,
    Exam,
    ExamBlueprint,
    Question,
    QuestionStatus,
    QuestionType,
    Role,
    User,
)
from app.security.passwords import hash_password
from app.services import questions as question_service

DEMO_PASSWORD = "SecureLock#2026"

DEMO_USERS = [
    ("Dr. A. Menon", "admin@securelock.demo", Role.SUPER_ADMIN, "Administration"),
    ("Prof. R. Iyer", "setter1@securelock.demo", Role.QUESTION_SETTER, "Computer Science"),
    ("Prof. S. Banerjee", "setter2@securelock.demo", Role.QUESTION_SETTER, "Computer Science"),
    ("Prof. K. Nair", "setter3@securelock.demo", Role.QUESTION_SETTER, "Computer Science"),
    ("Dr. M. Rao", "reviewer@securelock.demo", Role.REVIEWER, "Academic Board"),
    ("Controller of Examinations", "authority@securelock.demo", Role.EXAM_AUTHORITY, "Exam Cell"),
    ("V. Krishnan (Audit)", "auditor@securelock.demo", Role.AUDITOR, "Internal Audit"),
]

# (content, topic, difficulty, type, marks)
# Pairs marked NEAR-DUP are intentionally similar to exercise the detector.
QUESTION_BANK: list[tuple[str, str, Difficulty, QuestionType, int]] = [
    # --- Data Structures ---
    ("Explain the time complexity of binary search on a sorted array and derive the recurrence relation.",
     "Data Structures", Difficulty.MEDIUM, QuestionType.LONG_ANSWER, 6),
    ("Explain the time complexity of searching for an element in a sorted array using binary search, deriving its recurrence.",
     "Data Structures", Difficulty.MEDIUM, QuestionType.LONG_ANSWER, 6),  # NEAR-DUP of above
    ("Define a balanced binary search tree and state the invariant an AVL tree maintains.",
     "Data Structures", Difficulty.EASY, QuestionType.SHORT_ANSWER, 4),
    ("Compare the worst-case complexities of insertion into an AVL tree and a red-black tree.",
     "Data Structures", Difficulty.HARD, QuestionType.LONG_ANSWER, 8),
    ("Implement a queue using two stacks and analyse the amortised cost of each operation.",
     "Data Structures", Difficulty.MEDIUM, QuestionType.PROBLEM, 7),
    ("List the operations supported by a min-heap and give the complexity of each.",
     "Data Structures", Difficulty.EASY, QuestionType.SHORT_ANSWER, 4),
    ("Describe open addressing in hash tables and explain how clustering degrades performance.",
     "Data Structures", Difficulty.MEDIUM, QuestionType.LONG_ANSWER, 6),

    # --- Algorithms ---
    ("Calculate the shortest path between vertices A and B in the given weighted graph using Dijkstra's algorithm.",
     "Algorithms", Difficulty.MEDIUM, QuestionType.PROBLEM, 8),
    ("Given a weighted graph, determine the minimum-cost path from source A to destination B using Dijkstra's algorithm.",
     "Algorithms", Difficulty.MEDIUM, QuestionType.PROBLEM, 8),  # NEAR-DUP of above
    ("Prove that a greedy algorithm yields an optimal solution for the fractional knapsack problem.",
     "Algorithms", Difficulty.HARD, QuestionType.LONG_ANSWER, 10),
    ("State the master theorem and apply it to T(n) = 3T(n/2) + n.",
     "Algorithms", Difficulty.MEDIUM, QuestionType.NUMERICAL, 6),
    ("Explain dynamic programming and contrast it with divide and conquer using a concrete example.",
     "Algorithms", Difficulty.EASY, QuestionType.LONG_ANSWER, 5),
    ("Derive the worst-case time complexity of quicksort and describe a pivot strategy that avoids it.",
     "Algorithms", Difficulty.HARD, QuestionType.LONG_ANSWER, 9),
    ("Write an algorithm to detect a cycle in a directed graph and state its complexity.",
     "Algorithms", Difficulty.MEDIUM, QuestionType.PROBLEM, 7),

    # --- DBMS ---
    ("Define third normal form and normalise the supplied relation to 3NF, showing each step.",
     "DBMS", Difficulty.MEDIUM, QuestionType.PROBLEM, 8),
    ("Explain the ACID properties of a transaction with an example of each being violated.",
     "DBMS", Difficulty.EASY, QuestionType.LONG_ANSWER, 5),
    ("Describe two-phase locking and explain how it guarantees conflict serialisability.",
     "DBMS", Difficulty.HARD, QuestionType.LONG_ANSWER, 9),
    ("Differentiate between a clustered and a non-clustered index, and state when each is preferable.",
     "DBMS", Difficulty.EASY, QuestionType.SHORT_ANSWER, 4),
    ("Write a SQL query returning the second highest salary from an employees table, without using LIMIT.",
     "DBMS", Difficulty.MEDIUM, QuestionType.PROBLEM, 6),
    ("Explain how a write-ahead log enables crash recovery in a relational database.",
     "DBMS", Difficulty.HARD, QuestionType.LONG_ANSWER, 8),

    # --- Operating Systems ---
    ("Explain the difference between a process and a thread, including their memory layouts.",
     "Operating Systems", Difficulty.EASY, QuestionType.LONG_ANSWER, 5),
    ("State the four Coffman conditions for deadlock and describe one prevention strategy for each.",
     "Operating Systems", Difficulty.MEDIUM, QuestionType.LONG_ANSWER, 8),
    ("Calculate the average waiting time for the given processes under shortest-job-first scheduling.",
     "Operating Systems", Difficulty.MEDIUM, QuestionType.NUMERICAL, 6),
    ("Describe demand paging and derive the effective access time given a page fault rate p.",
     "Operating Systems", Difficulty.HARD, QuestionType.LONG_ANSWER, 9),
    ("Define a critical section and explain why Peterson's solution satisfies mutual exclusion.",
     "Operating Systems", Difficulty.MEDIUM, QuestionType.LONG_ANSWER, 7),
    ("List the states in a process lifecycle and describe the transitions between them.",
     "Operating Systems", Difficulty.EASY, QuestionType.SHORT_ANSWER, 4),

    # --- Computer Networks ---
    ("Explain the three-way handshake used to establish a TCP connection.",
     "Computer Networks", Difficulty.EASY, QuestionType.LONG_ANSWER, 5),
    ("Compare TCP and UDP, and justify which is appropriate for real-time video conferencing.",
     "Computer Networks", Difficulty.MEDIUM, QuestionType.LONG_ANSWER, 6),
    ("Given the address 192.168.10.0/22, calculate the usable host range and broadcast address.",
     "Computer Networks", Difficulty.MEDIUM, QuestionType.NUMERICAL, 6),
    ("Describe how TCP congestion control behaves during slow start and congestion avoidance.",
     "Computer Networks", Difficulty.HARD, QuestionType.LONG_ANSWER, 9),
    ("Explain the role of ARP and describe how ARP spoofing compromises a local network.",
     "Computer Networks", Difficulty.MEDIUM, QuestionType.LONG_ANSWER, 7),

    # --- Cybersecurity ---
    ("Explain the difference between symmetric and asymmetric encryption, with a use case for each.",
     "Cybersecurity", Difficulty.EASY, QuestionType.LONG_ANSWER, 5),
    ("Describe how a SQL injection attack works and state two defences that actually prevent it.",
     "Cybersecurity", Difficulty.MEDIUM, QuestionType.LONG_ANSWER, 7),
    ("Explain what a cryptographic hash function guarantees, and what it does not guarantee.",
     "Cybersecurity", Difficulty.MEDIUM, QuestionType.LONG_ANSWER, 6),
    ("Discuss why AES-GCM is preferred over AES-CBC for encrypting stored records.",
     "Cybersecurity", Difficulty.HARD, QuestionType.LONG_ANSWER, 8),
    ("Define a replay attack and describe a protocol-level mitigation.",
     "Cybersecurity", Difficulty.MEDIUM, QuestionType.SHORT_ANSWER, 5),
    ("Explain the principle of least privilege and give an example of its violation in a web application.",
     "Cybersecurity", Difficulty.EASY, QuestionType.SHORT_ANSWER, 4),
]


def reset_database() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("Database reset.")


def seed() -> None:
    init_db()
    db = SessionLocal()
    try:
        if db.execute(select(func.count(User.id))).scalar_one() > 0:
            print("Database already seeded. Use --reset to start over.")
            return

        users: dict[str, User] = {}
        for name, email, role, dept in DEMO_USERS:
            user = User(
                user_uid=f"USR-{uuid.uuid4().hex[:8].upper()}",
                name=name,
                email=email,
                password_hash=hash_password(DEMO_PASSWORD),
                role=role,
                department=dept,
            )
            db.add(user)
            users[email] = user
        db.flush()
        print(f"Created {len(users)} demo users.")

        setters = [
            users["setter1@securelock.demo"],
            users["setter2@securelock.demo"],
            users["setter3@securelock.demo"],
        ]
        reviewer = users["reviewer@securelock.demo"]

        # Questions are created through the real service so they are genuinely
        # encrypted, hashed, versioned and audited -- not inserted raw.
        created = []
        for index, (content, topic, difficulty, qtype, marks) in enumerate(QUESTION_BANK):
            setter = setters[index % len(setters)]
            question, _ = question_service.create_question(
                db,
                creator=setter,
                content=content,
                subject="Computer Science",
                topic=topic,
                difficulty=difficulty,
                question_type=qtype,
                marks=marks,
            )
            created.append(question)
        db.flush()
        print(f"Created {len(created)} encrypted questions.")

        # Move most through the workflow to APPROVED so a paper can be built,
        # leaving a few in review so the reviewer queue is not empty.
        approved = 0
        for index, question in enumerate(created):
            if index % 9 == 4:  # leave roughly one in nine pending review
                question.status = QuestionStatus.SUBMITTED
                continue
            question.status = QuestionStatus.AVAILABLE_FOR_SYNTHESIS
            question.approved_at = datetime.now(timezone.utc)
            question.approved_by = reviewer.id
            approved += 1
        print(f"Approved {approved} questions; {len(created) - approved} left in review queue.")

        authority = users["authority@securelock.demo"]
        exam = Exam(
            exam_uid=f"EXAM-{uuid.uuid4().hex[:8].upper()}",
            title="SIH Secure Examination Demo",
            subject="Computer Science",
            total_marks=100,
            question_count=15,
            scheduled_at=datetime.now(timezone.utc) + timedelta(days=1),
            created_by=authority.id,
        )
        db.add(exam)
        db.flush()
        db.add(
            ExamBlueprint(
                exam_id=exam.id,
                difficulty_distribution=json.dumps({"EASY": 30, "MEDIUM": 50, "HARD": 20}),
                topic_distribution=json.dumps(
                    {
                        "Data Structures": 20,
                        "Algorithms": 20,
                        "DBMS": 20,
                        "Operating Systems": 20,
                        "Computer Networks": 10,
                        "Cybersecurity": 10,
                    }
                ),
            )
        )
        db.commit()
        print(f"Created demo exam {exam.exam_uid}: {exam.title}")

        print("\n" + "=" * 62)
        print("DEMO ACCOUNTS  (password for all: %s)" % DEMO_PASSWORD)
        print("=" * 62)
        for name, email, role, _dept in DEMO_USERS:
            print(f"  {email:<32} {role.value:<18} {name}")
        print("=" * 62)
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the SecureLock demo database.")
    parser.add_argument("--reset", action="store_true", help="drop all tables first")
    args = parser.parse_args()
    if args.reset:
        reset_database()
    seed()
    return 0


if __name__ == "__main__":
    sys.exit(main())

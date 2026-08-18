"""Security tests: encryption, authorisation, audit integrity, time lock.

These assert the properties the project claims. They run without a blockchain
node -- chain-dependent behaviour is covered by the Hardhat suite, and the
backend's graceful degradation is asserted here.
"""

from __future__ import annotations

import os
import tempfile

import pytest

# Point the app at a throwaway database before anything imports settings.
_tmp_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db}"
os.environ["BLOCKCHAIN_ENABLED"] = "false"
os.environ["JWT_SECRET"] = "test-secret-not-for-production"

from app.database import Base, SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Difficulty,
    Question,
    QuestionStatus,
    QuestionType,
    Role,
    User,
)
from app.security.crypto import (  # noqa: E402
    DecryptionError,
    content_hash,
    decrypt,
    encrypt,
    generate_data_key,
)
from app.security.keyvault import create_wrapped_key, decrypt_key  # noqa: E402
from app.security.passwords import hash_password, verify_password  # noqa: E402
from app.security.tokens import TokenError, create_access_token, decode_access_token  # noqa: E402
from app.services import audit, permissions  # noqa: E402
from app.services import questions as question_service  # noqa: E402
from app.services.questions import QuestionError  # noqa: E402
from app.services.synthesis import (  # noqa: E402
    Blueprint,
    Candidate,
    build_vectors,
    cosine_similarity,
    find_duplicates,
    generate_variation,
    make_engine,
    tfidf_vector,
    tokenize,
    inverse_document_frequencies,
)


@pytest.fixture(autouse=True)
def clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


def make_user(db, role: Role, email: str) -> User:
    user = User(
        user_uid=f"USR-{email.split('@')[0].upper()}",
        name=email.split("@")[0],
        email=email,
        password_hash=hash_password("password12345"),
        role=role,
    )
    db.add(user)
    db.flush()
    return user


def make_question(db, creator: User, content: str = "Explain Dijkstra's algorithm in detail.") -> Question:
    question, _ = question_service.create_question(
        db,
        creator=creator,
        content=content,
        subject="Computer Science",
        topic="Algorithms",
        difficulty=Difficulty.MEDIUM,
        question_type=QuestionType.LONG_ANSWER,
        marks=6,
    )
    db.commit()
    return question


# ======================================================================
# Encryption
# ======================================================================


class TestEncryption:
    def test_roundtrip(self):
        key = generate_data_key()
        blob = encrypt("Explain the CAP theorem.", key)
        assert decrypt(blob, key) == "Explain the CAP theorem."

    def test_ciphertext_does_not_contain_plaintext(self):
        key = generate_data_key()
        blob = encrypt("Explain the CAP theorem.", key)
        assert b"CAP theorem" not in blob
        assert b"Explain" not in blob

    def test_tampered_ciphertext_is_rejected(self):
        key = generate_data_key()
        blob = bytearray(encrypt("Explain the CAP theorem.", key))
        blob[-1] ^= 0x01  # flip one bit of the GCM tag
        with pytest.raises(DecryptionError):
            decrypt(bytes(blob), key)

    def test_wrong_key_is_rejected(self):
        blob = encrypt("secret question", generate_data_key())
        with pytest.raises(DecryptionError):
            decrypt(blob, generate_data_key())

    def test_same_plaintext_gives_different_ciphertext(self):
        """Random nonce per encryption: identical questions are not linkable."""
        key = generate_data_key()
        assert encrypt("same text", key) != encrypt("same text", key)

    def test_wrapped_key_is_not_the_bare_key(self):
        dek, wrapped = create_wrapped_key("question")
        assert dek not in wrapped
        assert decrypt_key(wrapped, "question") == dek

    def test_key_purpose_is_bound(self):
        """A question key cannot be unwrapped as a paper key."""
        _dek, wrapped = create_wrapped_key("question")
        with pytest.raises(DecryptionError):
            decrypt_key(wrapped, "paper")

    def test_content_hash_is_stable_and_canonical(self):
        assert content_hash("Explain  the   CAP theorem.") == content_hash("Explain the CAP theorem.")
        assert content_hash("A") != content_hash("B")
        assert len(content_hash("x")) == 64


class TestDatabaseStoresNoPlaintext:
    def test_question_row_holds_only_ciphertext(self, db):
        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        secret = "What is the asymptotic complexity of heapsort?"
        question = make_question(db, setter, secret)

        assert secret.encode() not in question.encrypted_content
        assert not hasattr(question, "content")
        # The search-terms fingerprint must not reconstruct the sentence.
        assert secret.lower() not in question.search_terms.lower()

    def test_raw_sql_row_contains_no_plaintext(self, db):
        from sqlalchemy import text

        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        secret = "Derive the recurrence for merge sort"
        make_question(db, setter, secret)

        rows = db.execute(text("SELECT * FROM questions")).fetchall()
        blob = " ".join(str(v) for row in rows for v in row)
        assert "Derive the recurrence" not in blob


# ======================================================================
# Authentication
# ======================================================================


class TestAuthentication:
    def test_password_verification(self):
        h = hash_password("correct horse battery staple")
        assert verify_password("correct horse battery staple", h)
        assert not verify_password("wrong password", h)

    def test_hash_is_not_the_password(self):
        assert "hunter2000" not in hash_password("hunter2000")

    def test_valid_token_roundtrip(self):
        token, ttl = create_access_token(user_uid="USR-1", role="REVIEWER", email="r@x.test")
        payload = decode_access_token(token)
        assert payload["sub"] == "USR-1"
        assert payload["role"] == "REVIEWER"
        assert ttl > 0

    def test_tampered_token_is_rejected(self):
        token, _ = create_access_token(user_uid="USR-1", role="AUDITOR", email="a@x.test")
        head, payload, sig = token.split(".")
        forged = f"{head}.{payload}.{'A' * len(sig)}"
        with pytest.raises(TokenError):
            decode_access_token(forged)

    def test_garbage_token_is_rejected(self):
        with pytest.raises(TokenError):
            decode_access_token("not-a-token")


# ======================================================================
# Authorisation
# ======================================================================


class TestAuthorization:
    def test_setter_can_read_own_question(self, db):
        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        question = make_question(db, setter)
        assert permissions.can_read(db, setter, question)

    def test_setter_cannot_read_another_setters_question(self, db):
        owner = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        other = make_user(db, Role.QUESTION_SETTER, "s2@x.test")
        question = make_question(db, owner)

        decision = permissions.can_read(db, other, question)
        assert not decision
        assert "another setter" in decision.reason

        with pytest.raises(QuestionError) as exc:
            question_service.read_question_content(db, reader=other, question=question)
        assert exc.value.status_code == 403

    def test_auditor_cannot_read_plaintext(self, db):
        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        auditor = make_user(db, Role.AUDITOR, "aud@x.test")
        question = make_question(db, setter)
        assert not permissions.can_read(db, auditor, question)

    def test_super_admin_does_not_get_implicit_content_access(self, db):
        """Administering the system is not the same power as reading exam content."""
        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        admin = make_user(db, Role.SUPER_ADMIN, "admin@x.test")
        question = make_question(db, setter)
        assert not permissions.can_read(db, admin, question)

    def test_explicit_grant_overrides_role_default(self, db):
        from app.models import QuestionPermission

        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        auditor = make_user(db, Role.AUDITOR, "aud@x.test")
        question = make_question(db, setter)

        db.add(
            QuestionPermission(
                question_id=question.id, user_id=auditor.id,
                can_read=True, granted_by=setter.id,
            )
        )
        db.flush()
        assert permissions.can_read(db, auditor, question)

    def test_read_write_approve_are_independent(self, db):
        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        reviewer = make_user(db, Role.REVIEWER, "rev@x.test")
        question = make_question(db, setter)
        question.status = QuestionStatus.SUBMITTED
        db.flush()

        perms = permissions.summarize(db, reviewer, question)
        assert perms["read"] is True
        assert perms["write"] is False   # reviewer may read and approve...
        assert perms["approve"] is True  # ...but never edit

    def test_reviewer_cannot_approve_own_question(self, db):
        """Separation of duties.

        A reviewer who also contributed a question (common in small boards) must
        not be able to wave their own work through.
        """
        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        reviewer = make_user(db, Role.REVIEWER, "rev@x.test")
        question = make_question(db, setter)
        question.creator_id = reviewer.id  # the reviewer authored this one
        question.status = QuestionStatus.SUBMITTED
        db.flush()
        decision = permissions.can_approve(db, reviewer, question)
        assert not decision
        assert "Separation of duties" in decision.reason

    def test_approved_question_is_frozen(self, db):
        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        question = make_question(db, setter)
        question.status = QuestionStatus.APPROVED
        db.flush()
        decision = permissions.can_write(db, setter, question)
        assert not decision
        assert "cannot be edited" in decision.reason

    def test_setter_never_sees_the_final_paper(self, db):
        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        decision = permissions.can_view_paper_content(setter)
        assert not decision
        assert "never shown the assembled paper" in decision.reason

    def test_denied_read_is_logged_and_audited(self, db):
        from app.models import AuditEvent, QuestionAccessLog

        owner = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        other = make_user(db, Role.QUESTION_SETTER, "s2@x.test")
        question = make_question(db, owner)

        with pytest.raises(QuestionError):
            question_service.read_question_content(db, reader=other, question=question)

        denied = db.query(QuestionAccessLog).filter_by(granted=False).all()
        assert len(denied) == 1
        events = db.query(AuditEvent).filter_by(event_type="QUESTION_READ_DENIED").all()
        assert len(events) == 1


# ======================================================================
# Versioning
# ======================================================================


class TestVersioning:
    def test_edit_creates_new_version_and_preserves_history(self, db):
        from app.models import QuestionVersion

        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        question = make_question(db, setter, "Explain the CAP theorem briefly.")
        original_hash = question.content_hash

        question_service.update_question(
            db, editor=setter, question=question,
            content="Explain the CAP theorem with a worked example.",
            change_note="expanded",
        )
        db.commit()

        assert question.version == 2
        assert question.content_hash != original_hash

        versions = db.query(QuestionVersion).filter_by(question_id=question.id).all()
        assert len(versions) == 2
        assert {v.content_hash for v in versions} == {original_hash, question.content_hash}

    def test_metadata_edit_does_not_bump_version(self, db):
        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        question = make_question(db, setter)
        question_service.update_question(db, editor=setter, question=question, marks=9)
        db.commit()
        assert question.version == 1
        assert question.marks == 9


# ======================================================================
# Audit chain
# ======================================================================


class TestAuditChain:
    def test_chain_is_intact_after_normal_activity(self, db):
        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        make_question(db, setter)
        make_question(db, setter, "Define a B+ tree and state its order.")
        result = audit.verify_chain(db)
        assert result["intact"] is True
        assert result["broken_count"] == 0
        assert result["total_events"] > 0

    def test_editing_an_event_breaks_the_chain(self, db):
        from app.models import AuditEvent

        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        make_question(db, setter)
        make_question(db, setter, "Define a B+ tree and state its order.")

        assert audit.verify_chain(db)["intact"] is True

        # An insider silently rewrites history.
        event = db.query(AuditEvent).first()
        event.event_type = "QUESTION_APPROVED"
        db.commit()

        result = audit.verify_chain(db)
        assert result["intact"] is False
        assert result["broken_count"] >= 1
        assert "CONTENT_MODIFIED" in result["broken_events"][0]["issues"]

    def test_deleting_an_event_breaks_the_chain(self, db):
        from app.models import AuditEvent

        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        make_question(db, setter)
        make_question(db, setter, "Define a B+ tree and state its order.")

        events = db.query(AuditEvent).order_by(AuditEvent.id).all()
        db.delete(events[1])
        db.commit()

        assert audit.verify_chain(db)["intact"] is False

    def test_every_read_produces_an_audit_event(self, db):
        from app.models import AuditEvent

        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        question = make_question(db, setter)
        before = db.query(AuditEvent).filter_by(event_type="QUESTION_READ").count()
        question_service.read_question_content(db, reader=setter, question=question)
        db.commit()
        after = db.query(AuditEvent).filter_by(event_type="QUESTION_READ").count()
        assert after == before + 1


# ======================================================================
# Synthesis
# ======================================================================


class TestSimilarity:
    def test_identical_text_scores_one(self):
        docs = [tokenize("Explain Dijkstra's shortest path algorithm")] * 2
        idf = inverse_document_frequencies(docs)
        v = tfidf_vector(docs[0], idf)
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_unrelated_text_scores_low(self):
        a = tokenize("Explain the three-way TCP handshake")
        b = tokenize("Normalise the relation to third normal form")
        idf = inverse_document_frequencies([a, b])
        score = cosine_similarity(tfidf_vector(a, idf), tfidf_vector(b, idf))
        assert score < 0.2

    def test_near_duplicates_are_detected(self):
        candidates = [
            Candidate(1, "Q-1", "Calculate the shortest path between A and B using Dijkstra's algorithm.",
                      "CS", "Algorithms", "MEDIUM", "PROBLEM", 8, "USR-A"),
            Candidate(2, "Q-2", "Determine the shortest path from A to B using Dijkstra's algorithm.",
                      "CS", "Algorithms", "MEDIUM", "PROBLEM", 8, "USR-B"),
            Candidate(3, "Q-3", "Explain the ACID properties of a database transaction.",
                      "CS", "DBMS", "EASY", "LONG_ANSWER", 5, "USR-C"),
        ]
        build_vectors(candidates)
        pairs = find_duplicates(candidates, 0.5)
        assert pairs, "expected at least one near-duplicate pair"
        top = pairs[0]
        assert {top.left_uid, top.right_uid} == {"Q-1", "Q-2"}
        assert top.similarity > 0.5


class TestSelection:
    def _pool(self, n=30):
        topics = ["Algorithms", "DBMS", "OS"]
        difficulties = ["EASY", "MEDIUM", "HARD"]
        return [
            Candidate(
                i, f"Q-{i:03d}",
                f"Question number {i} about {topics[i % 3]} covering concept {i} in depth.",
                "CS", topics[i % 3], difficulties[i % 3], "SHORT_ANSWER",
                5, f"USR-{i % 4}",
            )
            for i in range(1, n + 1)
        ]

    def _blueprint(self):
        return Blueprint(
            question_count=9,
            total_marks=45,
            difficulty={"EASY": 33.4, "MEDIUM": 33.3, "HARD": 33.3},
            topics={"Algorithms": 33.4, "DBMS": 33.3, "OS": 33.3},
        )

    def test_selects_the_requested_number(self):
        engine_ = make_engine(seed=42, duplicate_threshold=0.72)
        result = engine_.select(self._pool(), self._blueprint())
        assert len(result.selected) == 9

    def test_is_deterministic_for_a_fixed_seed(self):
        bp = self._blueprint()
        a = make_engine(seed=42, duplicate_threshold=0.72).select(self._pool(), bp)
        b = make_engine(seed=42, duplicate_threshold=0.72).select(self._pool(), bp)
        assert [c.question_uid for c in a.selected] == [c.question_uid for c in b.selected]

    def test_different_seeds_give_different_papers(self):
        """Unpredictability: a setter cannot forecast the paper."""
        bp = self._blueprint()
        a = make_engine(seed=1, duplicate_threshold=0.72).select(self._pool(), bp)
        b = make_engine(seed=999, duplicate_threshold=0.72).select(self._pool(), bp)
        assert [c.question_uid for c in a.selected] != [c.question_uid for c in b.selected]

    def test_spreads_across_contributors(self):
        engine_ = make_engine(seed=7, duplicate_threshold=0.72)
        result = engine_.select(self._pool(), self._blueprint())
        assert result.report["distinct_contributors"] >= 3

    def test_respects_the_blueprint(self):
        engine_ = make_engine(seed=7, duplicate_threshold=0.72)
        result = engine_.select(self._pool(), self._blueprint())
        assert result.compliance["difficulty_compliance"] >= 90.0
        assert result.compliance["topic_compliance"] >= 90.0


class TestVariation:
    def test_rewrites_the_instruction_verb(self):
        text, method = generate_variation(
            "Explain Dijkstra's algorithm.", question_type="LONG_ANSWER"
        )
        assert text != "Explain Dijkstra's algorithm."
        assert "Dijkstra" in text  # subject matter is untouched
        assert method.startswith("template:")

    def test_preserves_numbers_and_identifiers(self):
        original = "Calculate the shortest path from A to B in a graph with 12 vertices."
        text, _ = generate_variation(original, question_type="PROBLEM")
        for token in ("A", "B", "12", "vertices"):
            assert token in text

    def test_variation_preserves_every_substantive_term(self):
        """The real guarantee: no content word is lost or altered.

        Only the leading instruction verb is restated and an instruction is
        appended, so the answerable substance is a strict superset of the
        original. That is what makes it safe to say the expected answer cannot
        drift.
        """
        original = "Explain the ACID properties of a database transaction."
        text, _ = generate_variation(original, question_type="LONG_ANSWER")

        original_terms = set(tokenize(original)) - {"explain"}
        assert original_terms <= set(tokenize(text))

    def test_variation_stays_semantically_close(self):
        from app.services.synthesis import variation_similarity

        original = "Explain the ACID properties of a database transaction."
        text, _ = generate_variation(original, question_type="LONG_ANSWER")
        # Over a two-document corpus, IDF weights the terms unique to the
        # appended instruction more heavily than the shared subject matter, so
        # cosine similarity sits lower than intuition suggests. The floor here
        # just guards against a rewrite that discards the original entirely.
        assert variation_similarity(original, text) > 0.4


# ======================================================================
# Graceful degradation
# ======================================================================


class TestBlockchainUnavailable:
    def test_no_fake_transaction_hash_is_produced(self, db):
        """With the chain disabled, question creation still works -- and the
        blockchain receipt honestly reports failure rather than inventing a hash."""
        from app.models import BlockchainTransaction, ChainTxStatus

        setter = make_user(db, Role.QUESTION_SETTER, "s1@x.test")
        question, chain = question_service.create_question(
            db, creator=setter, content="Explain the CAP theorem in detail.",
            subject="CS", topic="DBMS", difficulty=Difficulty.EASY,
            question_type=QuestionType.SHORT_ANSWER, marks=4,
        )
        db.commit()

        assert question.content_hash  # crypto still happened
        assert chain["confirmed"] is False
        assert chain["tx_hash"] is None
        assert "unavailable" in chain["message"].lower()

        rows = db.query(BlockchainTransaction).all()
        assert rows and all(r.status == ChainTxStatus.UNAVAILABLE for r in rows)
        assert all(r.tx_hash is None for r in rows)

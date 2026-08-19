"""Blockchain gateway.

Rules this module follows without exception:

  * It never invents a transaction hash. If the node is unreachable the call is
    recorded with status UNAVAILABLE and the API says so.
  * Nothing sensitive goes on chain: identifiers are keccak256-hashed, content is
    represented only by its SHA-256 fingerprint.
  * The release decision is taken by the contract, not here. This module submits
    `releasePaper` and reports what the chain answered; a revert means denied.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import PROJECT_ROOT, settings
from app.models import BlockchainTransaction, ChainTxStatus
from app.security.crypto import keccak_id

logger = logging.getLogger(__name__)

ABI_DIR = PROJECT_ROOT / "blockchain" / "deployments" / "abi"


class BlockchainUnavailable(Exception):
    """The node could not be reached or the contracts are not deployed."""


class ReleaseDenied(Exception):
    """The time-lock contract refused the release. Carries the chain's reason."""

    def __init__(self, message: str, release_time: int | None = None, chain_time: int | None = None):
        super().__init__(message)
        self.release_time = release_time
        self.chain_time = chain_time


@dataclass
class TxResult:
    ok: bool
    tx_hash: str | None = None
    block_number: int | None = None
    gas_used: int | None = None
    error: str | None = None
    status: ChainTxStatus = ChainTxStatus.CONFIRMED
    events: list[dict[str, Any]] = field(default_factory=list)


class BlockchainService:
    """Thin, lazily-connected wrapper around web3.py."""

    def __init__(self) -> None:
        self._w3 = None
        self._account = None
        self._question_registry = None
        self._paper_timelock = None
        self._last_error: str | None = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _load_abi(self, name: str) -> list:
        path = ABI_DIR / f"{name}.json"
        if not path.exists():
            raise BlockchainUnavailable(
                f"ABI for {name} not found. Deploy the contracts first: "
                "cd blockchain && npm run deploy:local"
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def connect(self):
        """Connect on first use. Raises BlockchainUnavailable if it cannot."""
        if self._w3 is not None:
            return self._w3

        if not settings.blockchain_enabled:
            raise BlockchainUnavailable("Blockchain integration is disabled by configuration.")

        try:
            from web3 import Web3
            from web3.middleware import ExtraDataToPOAMiddleware
        except ImportError as exc:  # pragma: no cover
            raise BlockchainUnavailable("web3 is not installed") from exc

        w3 = Web3(
            Web3.HTTPProvider(
                settings.blockchain_rpc_url,
                request_kwargs={"timeout": settings.blockchain_timeout_seconds},
            )
        )
        # Harmless on Hardhat, required on many PoA testnets.
        try:
            w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)
        except Exception:  # pragma: no cover - middleware already present
            pass

        if not w3.is_connected():
            self._last_error = f"No JSON-RPC node at {settings.blockchain_rpc_url}"
            raise BlockchainUnavailable(self._last_error)

        settings.resolve_contract_addresses()
        if not settings.question_contract_address or not settings.paper_contract_address:
            raise BlockchainUnavailable(
                "Contract addresses unknown. Run: cd blockchain && npm run deploy:local"
            )

        if settings.blockchain_private_key:
            self._account = w3.eth.account.from_key(settings.blockchain_private_key)
        else:
            # Hardhat exposes unlocked dev accounts; account[0] is the deployer,
            # which holds REGISTRAR_ROLE. Only ever true for the local demo chain.
            accounts = w3.eth.accounts
            if not accounts:
                raise BlockchainUnavailable(
                    "No signing key. Set BLOCKCHAIN_PRIVATE_KEY in .env."
                )
            self._account = None
            self._default_sender = accounts[0]

        self._question_registry = w3.eth.contract(
            address=w3.to_checksum_address(settings.question_contract_address),
            abi=self._load_abi("QuestionRegistry"),
        )
        self._paper_timelock = w3.eth.contract(
            address=w3.to_checksum_address(settings.paper_contract_address),
            abi=self._load_abi("PaperTimeLock"),
        )
        self._w3 = w3
        self._last_error = None
        return w3

    def chain_time(self) -> int:
        """Current block.timestamp.

        Release windows must be scheduled against this, not against the server
        clock. On a local dev chain the two can differ by minutes, and in general
        there is no reason for a chain's clock to track any particular server's.
        """
        w3 = self.connect()
        return w3.eth.get_block("latest")["timestamp"]

    @property
    def sender(self) -> str:
        if self._account is not None:
            return self._account.address
        return self._default_sender

    def status(self) -> dict[str, Any]:
        """Health payload for the Blockchain Explorer page."""
        try:
            w3 = self.connect()
        except BlockchainUnavailable as exc:
            return {
                "connected": False,
                "error": str(exc),
                "rpc_url": settings.blockchain_rpc_url,
                "network_label": "OFFLINE",
            }
        chain_id = w3.eth.chain_id
        return {
            "connected": True,
            "rpc_url": settings.blockchain_rpc_url,
            "chain_id": chain_id,
            "network_label": "LOCAL EVM DEMO NETWORK" if chain_id == 31337 else f"EVM CHAIN {chain_id}",
            "latest_block": w3.eth.block_number,
            "blockchain_time": w3.eth.get_block("latest")["timestamp"],
            "sender": self.sender,
            "contracts": {
                "QuestionRegistry": settings.question_contract_address,
                "PaperTimeLock": settings.paper_contract_address,
            },
        }

    # ------------------------------------------------------------------
    # Transaction plumbing
    # ------------------------------------------------------------------

    def _send(self, fn) -> TxResult:
        w3 = self.connect()
        tx_params: dict[str, Any] = {"from": self.sender}
        if self._account is not None:
            tx_params["nonce"] = w3.eth.get_transaction_count(self._account.address)
            built = fn.build_transaction(tx_params)
            signed = w3.eth.account.sign_transaction(built, self._account.key)
            tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        else:
            tx_hash = fn.transact(tx_params)

        receipt = w3.eth.wait_for_transaction_receipt(
            tx_hash, timeout=settings.blockchain_timeout_seconds
        )
        return TxResult(
            ok=receipt["status"] == 1,
            tx_hash=receipt["transactionHash"].hex(),
            block_number=receipt["blockNumber"],
            gas_used=receipt["gasUsed"],
            status=ChainTxStatus.CONFIRMED if receipt["status"] == 1 else ChainTxStatus.FAILED,
        )

    def _record(
        self,
        db: Session,
        *,
        contract: str,
        method: str,
        resource_type: str,
        resource_id: str,
        result: TxResult,
        address: str | None,
    ) -> BlockchainTransaction:
        row = BlockchainTransaction(
            tx_hash=result.tx_hash,
            contract=contract,
            contract_address=address,
            method=method,
            resource_type=resource_type,
            resource_id=resource_id,
            status=result.status,
            block_number=result.block_number,
            gas_used=result.gas_used,
            error=result.error,
        )
        db.add(row)
        db.flush()
        return row

    @staticmethod
    def _classify(error: str) -> ChainTxStatus:
        """
        A contract that refuses is not a chain that is down.

        UNAVAILABLE carries a specific promise -- the node could not be reached,
        so we recorded the attempt rather than inventing a hash. A revert is the
        opposite situation: the chain answered, and its answer was no. Filing
        reverts under UNAVAILABLE hides real logic errors behind an outage
        label, which is how a lifecycle bug sat unnoticed in the explorer.
        """
        lowered = error.lower()
        if "execution reverted" in lowered or "custom error" in lowered:
            return ChainTxStatus.FAILED
        return ChainTxStatus.UNAVAILABLE

    def _unavailable(
        self, db: Session, *, contract: str, method: str, resource_type: str,
        resource_id: str, error: str,
    ) -> TxResult:
        """Record a genuine failure. No fake hash is ever produced."""
        status = self._classify(error)
        if status is ChainTxStatus.FAILED:
            logger.warning("contract rejected %s.%s: %s", contract, method, error)
        else:
            logger.warning("blockchain unavailable for %s.%s: %s", contract, method, error)
        result = TxResult(ok=False, error=error, status=status)
        self._record(
            db, contract=contract, method=method, resource_type=resource_type,
            resource_id=resource_id, result=result, address=None,
        )
        return result

    # ------------------------------------------------------------------
    # QuestionRegistry
    # ------------------------------------------------------------------

    def register_question(
        self, db: Session, *, question_uid: str, content_hash: str, creator_uid: str
    ) -> TxResult:
        try:
            self.connect()
            fn = self._question_registry.functions.registerQuestion(
                keccak_id(question_uid),
                bytes.fromhex(content_hash),
                keccak_id(creator_uid),
            )
            result = self._send(fn)
        except BlockchainUnavailable as exc:
            return self._unavailable(
                db, contract="QuestionRegistry", method="registerQuestion",
                resource_type="QUESTION", resource_id=question_uid, error=str(exc),
            )
        except Exception as exc:  # chain-level revert or RPC error
            return self._unavailable(
                db, contract="QuestionRegistry", method="registerQuestion",
                resource_type="QUESTION", resource_id=question_uid, error=str(exc),
            )
        self._record(
            db, contract="QuestionRegistry", method="registerQuestion",
            resource_type="QUESTION", resource_id=question_uid, result=result,
            address=settings.question_contract_address,
        )
        return result

    def update_question(
        self, db: Session, *, question_uid: str, content_hash: str, actor_uid: str
    ) -> TxResult:
        try:
            self.connect()
            fn = self._question_registry.functions.updateQuestion(
                keccak_id(question_uid), bytes.fromhex(content_hash), keccak_id(actor_uid)
            )
            result = self._send(fn)
        except Exception as exc:
            return self._unavailable(
                db, contract="QuestionRegistry", method="updateQuestion",
                resource_type="QUESTION", resource_id=question_uid, error=str(exc),
            )
        self._record(
            db, contract="QuestionRegistry", method="updateQuestion",
            resource_type="QUESTION", resource_id=question_uid, result=result,
            address=settings.question_contract_address,
        )
        return result

    def set_lifecycle(
        self, db: Session, *, question_uid: str, lifecycle: int, actor_uid: str
    ) -> TxResult:
        try:
            self.connect()
            fn = self._question_registry.functions.setLifecycle(
                keccak_id(question_uid), lifecycle, keccak_id(actor_uid)
            )
            result = self._send(fn)
        except Exception as exc:
            return self._unavailable(
                db, contract="QuestionRegistry", method="setLifecycle",
                resource_type="QUESTION", resource_id=question_uid, error=str(exc),
            )
        self._record(
            db, contract="QuestionRegistry", method="setLifecycle",
            resource_type="QUESTION", resource_id=question_uid, result=result,
            address=settings.question_contract_address,
        )
        return result

    def record_access(
        self, db: Session, *, question_uid: str, actor_uid: str, access_type: str
    ) -> TxResult:
        try:
            self.connect()
            fn = self._question_registry.functions.recordAccess(
                keccak_id(question_uid), keccak_id(actor_uid), access_type
            )
            result = self._send(fn)
        except Exception as exc:
            return self._unavailable(
                db, contract="QuestionRegistry", method="recordAccess",
                resource_type="QUESTION", resource_id=question_uid, error=str(exc),
            )
        self._record(
            db, contract="QuestionRegistry", method="recordAccess",
            resource_type="QUESTION", resource_id=question_uid, result=result,
            address=settings.question_contract_address,
        )
        return result

    def verify_question_hash(self, question_uid: str, content_hash: str) -> bool:
        self.connect()
        return self._question_registry.functions.verifyContentHash(
            keccak_id(question_uid), bytes.fromhex(content_hash)
        ).call()

    def get_question_record(self, question_uid: str) -> dict[str, Any]:
        self.connect()
        r = self._question_registry.functions.getQuestion(keccak_id(question_uid)).call()
        return {
            "content_hash": r[0].hex(),
            "creator_hash": r[1].hex(),
            "created_at": r[2],
            "updated_at": r[3],
            "version": r[4],
            "status": r[5],
            "exists": r[6],
        }

    # ------------------------------------------------------------------
    # PaperTimeLock
    # ------------------------------------------------------------------

    def register_paper(
        self, db: Session, *, paper_uid: str, paper_hash: str, exam_uid: str,
        release_time: int, actor_uid: str,
    ) -> TxResult:
        try:
            self.connect()
            fn = self._paper_timelock.functions.registerPaper(
                keccak_id(paper_uid),
                bytes.fromhex(paper_hash),
                keccak_id(exam_uid),
                release_time,
                keccak_id(actor_uid),
            )
            result = self._send(fn)
        except Exception as exc:
            return self._unavailable(
                db, contract="PaperTimeLock", method="registerPaper",
                resource_type="PAPER", resource_id=paper_uid, error=str(exc),
            )
        self._record(
            db, contract="PaperTimeLock", method="registerPaper",
            resource_type="PAPER", resource_id=paper_uid, result=result,
            address=settings.paper_contract_address,
        )
        return result

    def time_lock_state(self, paper_uid: str) -> dict[str, Any]:
        """Authoritative lock state, read from the chain. Never from local time."""
        self.connect()
        key = keccak_id(paper_uid)
        paper = self._paper_timelock.functions.getPaper(key).call()
        chain_time = self._paper_timelock.functions.blockchainTime().call()
        release_time = paper[2]
        return {
            "paper_hash": paper[0].hex(),
            "release_time": release_time,
            "registered_at": paper[3],
            "released_at": paper[4],
            "released": paper[6],
            "blockchain_time": chain_time,
            "release_time_reached": chain_time >= release_time,
            "seconds_remaining": max(0, release_time - chain_time),
        }

    def release_paper(self, db: Session, *, paper_uid: str, actor_uid: str) -> TxResult:
        """Ask the contract to release. A revert here means DENIED, and we honour it."""
        try:
            self.connect()
            fn = self._paper_timelock.functions.releasePaper(
                keccak_id(paper_uid), keccak_id(actor_uid)
            )
            result = self._send(fn)
        except BlockchainUnavailable as exc:
            self._unavailable(
                db, contract="PaperTimeLock", method="releasePaper",
                resource_type="PAPER", resource_id=paper_uid, error=str(exc),
            )
            raise
        except Exception as exc:
            message = str(exc)
            self._unavailable(
                db, contract="PaperTimeLock", method="releasePaper",
                resource_type="PAPER", resource_id=paper_uid, error=message,
            )
            if "PaperStillLocked" in message:
                raise ReleaseDenied(
                    "Blockchain release condition not satisfied: the paper is still time locked."
                ) from exc
            if "PaperAlreadyReleased" in message:
                raise ReleaseDenied("This paper has already been released.") from exc
            raise ReleaseDenied(f"Release rejected by the contract: {message}") from exc

        self._record(
            db, contract="PaperTimeLock", method="releasePaper",
            resource_type="PAPER", resource_id=paper_uid, result=result,
            address=settings.paper_contract_address,
        )
        return result

    def verify_paper_hash(self, paper_uid: str, paper_hash: str) -> bool:
        self.connect()
        return self._paper_timelock.functions.verifyPaperHash(
            keccak_id(paper_uid), bytes.fromhex(paper_hash)
        ).call()

    def recent_events(self, limit: int = 50) -> list[dict[str, Any]]:
        """Read contract events straight from the chain for the explorer page."""
        w3 = self.connect()
        latest = w3.eth.block_number
        from_block = max(0, latest - 5000)
        out: list[dict[str, Any]] = []

        for contract, label in (
            (self._question_registry, "QuestionRegistry"),
            (self._paper_timelock, "PaperTimeLock"),
        ):
            for event_abi in contract.abi:
                if event_abi.get("type") != "event":
                    continue
                name = event_abi["name"]
                try:
                    logs = getattr(contract.events, name).get_logs(from_block=from_block)
                except Exception:  # pragma: no cover - some nodes limit ranges
                    continue
                for log in logs:
                    out.append(
                        {
                            "contract": label,
                            "event": name,
                            "block_number": log["blockNumber"],
                            "tx_hash": log["transactionHash"].hex(),
                            "args": {
                                k: (v.hex() if isinstance(v, bytes) else v)
                                for k, v in dict(log["args"]).items()
                            },
                        }
                    )

        out.sort(key=lambda e: e["block_number"], reverse=True)
        return out[:limit]


blockchain = BlockchainService()

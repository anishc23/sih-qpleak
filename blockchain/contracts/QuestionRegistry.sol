// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

/**
 * @title QuestionRegistry
 * @notice Tamper-evident provenance for examination questions.
 *
 * WHAT THIS CONTRACT DOES NOT STORE, BY DESIGN:
 *   - question text (plaintext or ciphertext)
 *   - answers
 *   - encryption keys
 *   - real user identities
 *
 * It stores only cryptographic fingerprints and pseudonymous actor hashes. The
 * question content itself lives off-chain, encrypted with AES-256-GCM. This
 * contract exists so that the *history* of a question cannot be silently
 * rewritten by anyone with database access -- including the system's own
 * administrators.
 *
 * A question is keyed by `questionIdHash` = keccak256(questionId), so the
 * human-readable identifier (e.g. "Q-000127") never appears on chain either.
 */
contract QuestionRegistry is AccessControl {
    /// @notice May register and update question provenance. Held by the backend relayer.
    bytes32 public constant REGISTRAR_ROLE = keccak256("REGISTRAR_ROLE");

    /// @notice Lifecycle states mirrored from the application's state machine.
    enum Lifecycle {
        NONE,
        DRAFT,
        SUBMITTED,
        UNDER_REVIEW,
        APPROVED,
        REJECTED,
        SELECTED,
        USED_IN_PAPER,
        RETIRED
    }

    struct QuestionRecord {
        bytes32 contentHash; // SHA-256 of canonical plaintext, computed off-chain
        bytes32 creatorHash; // pseudonymous creator fingerprint
        uint256 createdAt; // block timestamp of first registration
        uint256 updatedAt; // block timestamp of latest mutation
        uint32 version; // monotonically increasing
        Lifecycle status;
        bool exists;
    }

    /// @dev questionIdHash => current record
    mapping(bytes32 => QuestionRecord) private _questions;

    /// @dev questionIdHash => version => content hash at that version (history is append-only)
    mapping(bytes32 => mapping(uint32 => bytes32)) private _versionHashes;

    /// @dev Every questionIdHash ever registered, so an auditor can enumerate without an indexer.
    bytes32[] private _questionIndex;

    event QuestionRegistered(
        bytes32 indexed questionIdHash,
        bytes32 indexed contentHash,
        bytes32 indexed creatorHash,
        uint32 version,
        uint256 timestamp
    );

    event QuestionUpdated(
        bytes32 indexed questionIdHash,
        bytes32 indexed contentHash,
        bytes32 indexed actorHash,
        uint32 previousVersion,
        uint32 newVersion,
        uint256 timestamp
    );

    event QuestionLifecycleChanged(
        bytes32 indexed questionIdHash,
        bytes32 indexed actorHash,
        Lifecycle previousStatus,
        Lifecycle newStatus,
        uint256 timestamp
    );

    /**
     * @notice Records that an authorised account requested a question through the system.
     * @dev This proves a *system-mediated access request*, not that a human read
     *      anything. Someone can still photograph a screen. See docs/JUDGE_QA.md.
     */
    event QuestionAccessed(
        bytes32 indexed questionIdHash,
        bytes32 indexed actorHash,
        string accessType,
        uint256 timestamp
    );

    error QuestionAlreadyRegistered(bytes32 questionIdHash);
    error QuestionNotRegistered(bytes32 questionIdHash);
    error EmptyHash();
    error InvalidLifecycleTransition(Lifecycle from, Lifecycle to);

    constructor(address admin) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(REGISTRAR_ROLE, admin);
    }

    // ------------------------------------------------------------------
    // Mutating entry points
    // ------------------------------------------------------------------

    /**
     * @notice Anchor a newly created question.
     * @param questionIdHash keccak256 of the application question id
     * @param contentHash SHA-256 of the canonical question content
     * @param creatorHash pseudonymous fingerprint of the creating account
     */
    function registerQuestion(
        bytes32 questionIdHash,
        bytes32 contentHash,
        bytes32 creatorHash
    ) external onlyRole(REGISTRAR_ROLE) {
        if (questionIdHash == bytes32(0) || contentHash == bytes32(0)) revert EmptyHash();
        if (_questions[questionIdHash].exists) revert QuestionAlreadyRegistered(questionIdHash);

        _questions[questionIdHash] = QuestionRecord({
            contentHash: contentHash,
            creatorHash: creatorHash,
            createdAt: block.timestamp,
            updatedAt: block.timestamp,
            version: 1,
            status: Lifecycle.DRAFT,
            exists: true
        });
        _versionHashes[questionIdHash][1] = contentHash;
        _questionIndex.push(questionIdHash);

        emit QuestionRegistered(questionIdHash, contentHash, creatorHash, 1, block.timestamp);
    }

    /**
     * @notice Anchor a new version of an existing question.
     * @dev The previous version's hash is preserved in `_versionHashes` -- history
     *      is append-only, so an edit can never masquerade as the original.
     */
    function updateQuestion(
        bytes32 questionIdHash,
        bytes32 newContentHash,
        bytes32 actorHash
    ) external onlyRole(REGISTRAR_ROLE) returns (uint32 newVersion) {
        if (newContentHash == bytes32(0)) revert EmptyHash();
        QuestionRecord storage record = _questions[questionIdHash];
        if (!record.exists) revert QuestionNotRegistered(questionIdHash);

        uint32 previousVersion = record.version;
        newVersion = previousVersion + 1;

        record.contentHash = newContentHash;
        record.version = newVersion;
        record.updatedAt = block.timestamp;
        _versionHashes[questionIdHash][newVersion] = newContentHash;

        emit QuestionUpdated(
            questionIdHash,
            newContentHash,
            actorHash,
            previousVersion,
            newVersion,
            block.timestamp
        );
    }

    /**
     * @notice Move a question through its lifecycle.
     * @dev Transitions are validated on chain so the state machine cannot be
     *      short-circuited by a compromised backend.
     */
    function setLifecycle(
        bytes32 questionIdHash,
        Lifecycle newStatus,
        bytes32 actorHash
    ) external onlyRole(REGISTRAR_ROLE) {
        QuestionRecord storage record = _questions[questionIdHash];
        if (!record.exists) revert QuestionNotRegistered(questionIdHash);

        Lifecycle previous = record.status;
        if (!_isValidTransition(previous, newStatus)) {
            revert InvalidLifecycleTransition(previous, newStatus);
        }

        record.status = newStatus;
        record.updatedAt = block.timestamp;

        emit QuestionLifecycleChanged(questionIdHash, actorHash, previous, newStatus, block.timestamp);
    }

    /**
     * @notice Anchor an access event (READ / WRITE / APPROVE / SELECT / EXPORT).
     */
    function recordAccess(
        bytes32 questionIdHash,
        bytes32 actorHash,
        string calldata accessType
    ) external onlyRole(REGISTRAR_ROLE) {
        if (!_questions[questionIdHash].exists) revert QuestionNotRegistered(questionIdHash);
        emit QuestionAccessed(questionIdHash, actorHash, accessType, block.timestamp);
    }

    // ------------------------------------------------------------------
    // Views
    // ------------------------------------------------------------------

    function getQuestion(bytes32 questionIdHash) external view returns (QuestionRecord memory) {
        QuestionRecord memory record = _questions[questionIdHash];
        if (!record.exists) revert QuestionNotRegistered(questionIdHash);
        return record;
    }

    /// @notice Hash anchored at a specific version. Zero if that version never existed.
    function getVersionHash(bytes32 questionIdHash, uint32 version) external view returns (bytes32) {
        return _versionHashes[questionIdHash][version];
    }

    /**
     * @notice The integrity check behind the "TAMPERING DETECTED" demo.
     * @return true only if the supplied hash matches what was anchored on chain.
     */
    function verifyContentHash(bytes32 questionIdHash, bytes32 contentHash)
        external
        view
        returns (bool)
    {
        QuestionRecord memory record = _questions[questionIdHash];
        return record.exists && record.contentHash == contentHash;
    }

    function isRegistered(bytes32 questionIdHash) external view returns (bool) {
        return _questions[questionIdHash].exists;
    }

    function totalQuestions() external view returns (uint256) {
        return _questionIndex.length;
    }

    function questionAt(uint256 index) external view returns (bytes32) {
        return _questionIndex[index];
    }

    // ------------------------------------------------------------------
    // Internal
    // ------------------------------------------------------------------

    /**
     * @dev Encodes the lifecycle described in the product spec:
     *   DRAFT -> SUBMITTED -> UNDER_REVIEW -> APPROVED -> SELECTED -> USED_IN_PAPER
     *   UNDER_REVIEW -> REJECTED -> DRAFT
     *   anything (except USED_IN_PAPER) -> RETIRED
     */
    function _isValidTransition(Lifecycle from, Lifecycle to) private pure returns (bool) {
        if (to == Lifecycle.NONE) return false;
        if (from == to) return false;

        // A question already printed into a released paper is frozen forever.
        if (from == Lifecycle.USED_IN_PAPER) return false;
        if (to == Lifecycle.RETIRED) return true;

        if (from == Lifecycle.DRAFT) return to == Lifecycle.SUBMITTED;
        if (from == Lifecycle.SUBMITTED) return to == Lifecycle.UNDER_REVIEW;
        if (from == Lifecycle.UNDER_REVIEW) {
            return to == Lifecycle.APPROVED || to == Lifecycle.REJECTED;
        }
        if (from == Lifecycle.REJECTED) return to == Lifecycle.DRAFT;
        if (from == Lifecycle.APPROVED) return to == Lifecycle.SELECTED;
        if (from == Lifecycle.SELECTED) {
            // A selected question can be released back to the pool if the paper is rebuilt.
            return to == Lifecycle.USED_IN_PAPER || to == Lifecycle.APPROVED;
        }
        return false;
    }
}

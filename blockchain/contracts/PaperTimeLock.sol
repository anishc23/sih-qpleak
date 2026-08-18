// SPDX-License-Identifier: MIT
pragma solidity 0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";

/**
 * @title PaperTimeLock
 * @notice Blockchain-enforced release condition for a finalised examination paper.
 *
 * The whole point of this contract is the single line:
 *
 *     if (block.timestamp < paper.releaseTime) revert PaperStillLocked(...)
 *
 * `block.timestamp` is supplied by the chain's execution environment. A user
 * cannot influence it by changing their laptop clock, their browser clock, or
 * by patching the frontend -- which is exactly the attack the SIH demo shows.
 *
 * Honest framing (see docs/JUDGE_QA.md): block.timestamp is not a perfect atomic
 * clock. Validators have a small amount of leeway. The correct claim is that an
 * ordinary end user cannot bypass the condition from their own device, not that
 * the timestamp is mathematically unforgeable under every attack model.
 *
 * The paper ciphertext is NOT stored here. Only its SHA-256 fingerprint and the
 * release condition are on chain.
 */
contract PaperTimeLock is AccessControl {
    /// @notice May register papers. Held by the backend relayer acting for the Exam Authority.
    bytes32 public constant REGISTRAR_ROLE = keccak256("REGISTRAR_ROLE");

    /// @notice May trigger release once the time condition is satisfied.
    bytes32 public constant RELEASE_AGENT_ROLE = keccak256("RELEASE_AGENT_ROLE");

    struct ExamPaper {
        bytes32 paperHash; // SHA-256 of the encrypted paper artifact
        bytes32 examIdHash; // pseudonymous exam identifier
        uint256 releaseTime; // unix seconds; the only thing that gates release
        uint256 registeredAt;
        uint256 releasedAt; // 0 until released
        bytes32 registeredBy; // pseudonymous actor fingerprint
        bool released;
        bool exists;
    }

    mapping(bytes32 => ExamPaper) private _papers;
    bytes32[] private _paperIndex;

    event PaperRegistered(
        bytes32 indexed paperIdHash,
        bytes32 indexed paperHash,
        bytes32 indexed examIdHash,
        uint256 releaseTime,
        uint256 timestamp
    );

    event PaperReleased(
        bytes32 indexed paperIdHash,
        bytes32 indexed actorHash,
        uint256 releaseTime,
        uint256 timestamp
    );

    /// @notice Emitted when a release is attempted too early. This is the audit
    ///         trail of attempted early access -- a security signal, not noise.
    event ReleaseDenied(
        bytes32 indexed paperIdHash,
        bytes32 indexed actorHash,
        uint256 releaseTime,
        uint256 attemptedAt,
        string reason
    );

    error PaperAlreadyRegistered(bytes32 paperIdHash);
    error PaperNotRegistered(bytes32 paperIdHash);
    error PaperStillLocked(bytes32 paperIdHash, uint256 releaseTime, uint256 currentTime);
    error PaperAlreadyReleased(bytes32 paperIdHash);
    error ReleaseTimeInPast(uint256 releaseTime, uint256 currentTime);
    error EmptyHash();

    constructor(address admin) {
        _grantRole(DEFAULT_ADMIN_ROLE, admin);
        _grantRole(REGISTRAR_ROLE, admin);
        _grantRole(RELEASE_AGENT_ROLE, admin);
    }

    // ------------------------------------------------------------------
    // Registration
    // ------------------------------------------------------------------

    /**
     * @notice Anchor an encrypted paper and arm its time lock.
     * @param releaseTime Unix seconds. Must be in the future at registration time.
     */
    function registerPaper(
        bytes32 paperIdHash,
        bytes32 paperHash,
        bytes32 examIdHash,
        uint256 releaseTime,
        bytes32 registeredBy
    ) external onlyRole(REGISTRAR_ROLE) {
        if (paperIdHash == bytes32(0) || paperHash == bytes32(0)) revert EmptyHash();
        if (_papers[paperIdHash].exists) revert PaperAlreadyRegistered(paperIdHash);
        if (releaseTime <= block.timestamp) revert ReleaseTimeInPast(releaseTime, block.timestamp);

        _papers[paperIdHash] = ExamPaper({
            paperHash: paperHash,
            examIdHash: examIdHash,
            releaseTime: releaseTime,
            registeredAt: block.timestamp,
            releasedAt: 0,
            registeredBy: registeredBy,
            released: false,
            exists: true
        });
        _paperIndex.push(paperIdHash);

        emit PaperRegistered(paperIdHash, paperHash, examIdHash, releaseTime, block.timestamp);
    }

    // ------------------------------------------------------------------
    // The release condition
    // ------------------------------------------------------------------

    /**
     * @notice Transition the paper to RELEASED. Reverts before the release time.
     * @dev The backend calls this before it will hand over the decryption key.
     *      Because it is a state-changing transaction, the denial is recorded as
     *      a revert on chain rather than being silently swallowed client-side.
     */
    function releasePaper(bytes32 paperIdHash, bytes32 actorHash)
        external
        onlyRole(RELEASE_AGENT_ROLE)
    {
        ExamPaper storage paper = _papers[paperIdHash];
        if (!paper.exists) revert PaperNotRegistered(paperIdHash);
        if (paper.released) revert PaperAlreadyReleased(paperIdHash);

        // THE security decision. Chain time, never client time.
        if (block.timestamp < paper.releaseTime) {
            revert PaperStillLocked(paperIdHash, paper.releaseTime, block.timestamp);
        }

        paper.released = true;
        paper.releasedAt = block.timestamp;

        emit PaperReleased(paperIdHash, actorHash, paper.releaseTime, block.timestamp);
    }

    /**
     * @notice Non-reverting probe used by the UI countdown and by the backend's
     *         pre-flight check. The UI is free to call this; it is advisory only.
     *         Actual release still has to go through `releasePaper`.
     */
    function isReleaseTimeReached(bytes32 paperIdHash) external view returns (bool) {
        ExamPaper memory paper = _papers[paperIdHash];
        if (!paper.exists) return false;
        return block.timestamp >= paper.releaseTime;
    }

    /**
     * @notice Records a rejected early-release attempt without reverting, so the
     *         attempt itself becomes part of the tamper-evident audit trail.
     * @return allowed whether release would succeed right now
     */
    function attemptRelease(bytes32 paperIdHash, bytes32 actorHash)
        external
        onlyRole(RELEASE_AGENT_ROLE)
        returns (bool allowed)
    {
        ExamPaper memory paper = _papers[paperIdHash];
        if (!paper.exists) revert PaperNotRegistered(paperIdHash);

        if (paper.released) {
            emit ReleaseDenied(
                paperIdHash, actorHash, paper.releaseTime, block.timestamp, "ALREADY_RELEASED"
            );
            return false;
        }
        if (block.timestamp < paper.releaseTime) {
            emit ReleaseDenied(
                paperIdHash, actorHash, paper.releaseTime, block.timestamp, "RELEASE_TIME_NOT_REACHED"
            );
            return false;
        }
        return true;
    }

    // ------------------------------------------------------------------
    // Views
    // ------------------------------------------------------------------

    function getPaper(bytes32 paperIdHash) external view returns (ExamPaper memory) {
        ExamPaper memory paper = _papers[paperIdHash];
        if (!paper.exists) revert PaperNotRegistered(paperIdHash);
        return paper;
    }

    /// @notice Seconds until release, or 0 once the lock has expired.
    function secondsUntilRelease(bytes32 paperIdHash) external view returns (uint256) {
        ExamPaper memory paper = _papers[paperIdHash];
        if (!paper.exists) revert PaperNotRegistered(paperIdHash);
        if (block.timestamp >= paper.releaseTime) return 0;
        return paper.releaseTime - block.timestamp;
    }

    /// @notice Integrity check for the encrypted paper artifact.
    function verifyPaperHash(bytes32 paperIdHash, bytes32 paperHash) external view returns (bool) {
        ExamPaper memory paper = _papers[paperIdHash];
        return paper.exists && paper.paperHash == paperHash;
    }

    /// @notice The chain's own clock, surfaced so the UI can display it next to the client clock.
    function blockchainTime() external view returns (uint256) {
        return block.timestamp;
    }

    function isReleased(bytes32 paperIdHash) external view returns (bool) {
        return _papers[paperIdHash].released;
    }

    function totalPapers() external view returns (uint256) {
        return _paperIndex.length;
    }

    function paperAt(uint256 index) external view returns (bytes32) {
        return _paperIndex[index];
    }
}

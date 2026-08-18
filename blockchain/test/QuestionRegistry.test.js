const { expect } = require("chai");
const { ethers } = require("hardhat");
const { anyValue } = require("@nomicfoundation/hardhat-chai-matchers/withArgs");

const id = (s) => ethers.keccak256(ethers.toUtf8Bytes(s));

// Mirrors the Lifecycle enum in QuestionRegistry.sol
const L = {
  NONE: 0,
  DRAFT: 1,
  SUBMITTED: 2,
  UNDER_REVIEW: 3,
  APPROVED: 4,
  REJECTED: 5,
  SELECTED: 6,
  USED_IN_PAPER: 7,
  RETIRED: 8,
};

describe("QuestionRegistry", function () {
  let contract, admin, outsider;
  let QID, CONTENT_HASH, CREATOR, ACTOR;

  beforeEach(async function () {
    [admin, outsider] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("QuestionRegistry");
    contract = await Factory.deploy(admin.address);
    await contract.waitForDeployment();

    QID = id("Q-000127");
    CONTENT_HASH = id("Explain Dijkstra's algorithm.");
    CREATOR = id("USR-SETTER-04");
    ACTOR = id("USR-REVIEWER-02");
  });

  describe("registration", function () {
    it("registers a question at version 1 in DRAFT", async function () {
      await expect(contract.registerQuestion(QID, CONTENT_HASH, CREATOR))
        .to.emit(contract, "QuestionRegistered")
        .withArgs(QID, CONTENT_HASH, CREATOR, 1, anyValue);

      const record = await contract.getQuestion(QID);
      expect(record.contentHash).to.equal(CONTENT_HASH);
      expect(record.creatorHash).to.equal(CREATOR);
      expect(record.version).to.equal(1);
      expect(record.status).to.equal(L.DRAFT);
      expect(record.exists).to.equal(true);
    });

    it("rejects duplicate registration", async function () {
      await contract.registerQuestion(QID, CONTENT_HASH, CREATOR);
      await expect(
        contract.registerQuestion(QID, CONTENT_HASH, CREATOR)
      ).to.be.revertedWithCustomError(contract, "QuestionAlreadyRegistered");
    });

    it("rejects an empty content hash", async function () {
      await expect(
        contract.registerQuestion(QID, ethers.ZeroHash, CREATOR)
      ).to.be.revertedWithCustomError(contract, "EmptyHash");
    });

    it("rejects registration from an unauthorised account", async function () {
      await expect(
        contract.connect(outsider).registerQuestion(QID, CONTENT_HASH, CREATOR)
      ).to.be.revertedWithCustomError(contract, "AccessControlUnauthorizedAccount");
    });

    it("reverts when reading an unregistered question", async function () {
      await expect(contract.getQuestion(id("Q-NOPE"))).to.be.revertedWithCustomError(
        contract,
        "QuestionNotRegistered"
      );
    });
  });

  describe("versioning", function () {
    beforeEach(async function () {
      await contract.registerQuestion(QID, CONTENT_HASH, CREATOR);
    });

    it("bumps the version and emits QuestionUpdated", async function () {
      const v2Hash = id("Explain Dijkstra's shortest path algorithm with an example.");
      await expect(contract.updateQuestion(QID, v2Hash, ACTOR))
        .to.emit(contract, "QuestionUpdated")
        .withArgs(QID, v2Hash, ACTOR, 1, 2, anyValue);

      const record = await contract.getQuestion(QID);
      expect(record.version).to.equal(2);
      expect(record.contentHash).to.equal(v2Hash);
    });

    it("PRESERVES the hash of every previous version", async function () {
      const v2Hash = id("version two");
      const v3Hash = id("version three");
      await contract.updateQuestion(QID, v2Hash, ACTOR);
      await contract.updateQuestion(QID, v3Hash, ACTOR);

      // History is append-only: an edit cannot masquerade as the original.
      expect(await contract.getVersionHash(QID, 1)).to.equal(CONTENT_HASH);
      expect(await contract.getVersionHash(QID, 2)).to.equal(v2Hash);
      expect(await contract.getVersionHash(QID, 3)).to.equal(v3Hash);
      expect((await contract.getQuestion(QID)).version).to.equal(3);
    });

    it("rejects updating a question that was never registered", async function () {
      await expect(
        contract.updateQuestion(id("Q-NOPE"), CONTENT_HASH, ACTOR)
      ).to.be.revertedWithCustomError(contract, "QuestionNotRegistered");
    });
  });

  describe("lifecycle state machine", function () {
    beforeEach(async function () {
      await contract.registerQuestion(QID, CONTENT_HASH, CREATOR);
    });

    it("walks the happy path DRAFT -> USED_IN_PAPER", async function () {
      const path = [L.SUBMITTED, L.UNDER_REVIEW, L.APPROVED, L.SELECTED, L.USED_IN_PAPER];
      for (const next of path) {
        await contract.setLifecycle(QID, next, ACTOR);
        expect((await contract.getQuestion(QID)).status).to.equal(next);
      }
    });

    it("emits QuestionLifecycleChanged with the previous and new status", async function () {
      await expect(contract.setLifecycle(QID, L.SUBMITTED, ACTOR))
        .to.emit(contract, "QuestionLifecycleChanged")
        .withArgs(QID, ACTOR, L.DRAFT, L.SUBMITTED, anyValue);
    });

    it("supports the rejection loop UNDER_REVIEW -> REJECTED -> DRAFT", async function () {
      await contract.setLifecycle(QID, L.SUBMITTED, ACTOR);
      await contract.setLifecycle(QID, L.UNDER_REVIEW, ACTOR);
      await contract.setLifecycle(QID, L.REJECTED, ACTOR);
      await contract.setLifecycle(QID, L.DRAFT, ACTOR);
      expect((await contract.getQuestion(QID)).status).to.equal(L.DRAFT);
    });

    it("REJECTS a skipped state (DRAFT -> APPROVED)", async function () {
      await expect(
        contract.setLifecycle(QID, L.APPROVED, ACTOR)
      ).to.be.revertedWithCustomError(contract, "InvalidLifecycleTransition");
    });

    it("freezes a question once it is USED_IN_PAPER", async function () {
      for (const next of [L.SUBMITTED, L.UNDER_REVIEW, L.APPROVED, L.SELECTED, L.USED_IN_PAPER]) {
        await contract.setLifecycle(QID, next, ACTOR);
      }
      await expect(
        contract.setLifecycle(QID, L.RETIRED, ACTOR)
      ).to.be.revertedWithCustomError(contract, "InvalidLifecycleTransition");
    });

    it("allows retirement from any pre-print state", async function () {
      await contract.setLifecycle(QID, L.SUBMITTED, ACTOR);
      await contract.setLifecycle(QID, L.RETIRED, ACTOR);
      expect((await contract.getQuestion(QID)).status).to.equal(L.RETIRED);
    });

    it("rejects a no-op transition", async function () {
      await expect(
        contract.setLifecycle(QID, L.DRAFT, ACTOR)
      ).to.be.revertedWithCustomError(contract, "InvalidLifecycleTransition");
    });
  });

  describe("access events", function () {
    beforeEach(async function () {
      await contract.registerQuestion(QID, CONTENT_HASH, CREATOR);
    });

    it("anchors a READ access event", async function () {
      await expect(contract.recordAccess(QID, ACTOR, "READ"))
        .to.emit(contract, "QuestionAccessed")
        .withArgs(QID, ACTOR, "READ", anyValue);
    });

    it("rejects an access event for an unknown question", async function () {
      await expect(
        contract.recordAccess(id("Q-NOPE"), ACTOR, "READ")
      ).to.be.revertedWithCustomError(contract, "QuestionNotRegistered");
    });
  });

  describe("integrity verification", function () {
    beforeEach(async function () {
      await contract.registerQuestion(QID, CONTENT_HASH, CREATOR);
    });

    it("verifies an untampered hash", async function () {
      expect(await contract.verifyContentHash(QID, CONTENT_HASH)).to.equal(true);
    });

    it("DETECTS a tampered hash", async function () {
      expect(await contract.verifyContentHash(QID, id("silently edited question"))).to.equal(false);
    });
  });

  describe("enumeration", function () {
    it("indexes questions for auditors", async function () {
      await contract.registerQuestion(QID, CONTENT_HASH, CREATOR);
      await contract.registerQuestion(id("Q-000128"), id("another"), CREATOR);
      expect(await contract.totalQuestions()).to.equal(2);
      expect(await contract.questionAt(0)).to.equal(QID);
    });
  });
});

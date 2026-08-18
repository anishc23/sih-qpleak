const { expect } = require("chai");
const { ethers } = require("hardhat");
const { time } = require("@nomicfoundation/hardhat-network-helpers");
const { anyValue } = require("@nomicfoundation/hardhat-chai-matchers/withArgs");

const id = (s) => ethers.keccak256(ethers.toUtf8Bytes(s));

// Timestamps are chain-assigned; assert only that a value is present.
const anyUint = () => anyValue;

describe("PaperTimeLock", function () {
  let contract, admin, authority, outsider;
  let PAPER_ID, PAPER_HASH, EXAM_ID, ACTOR;

  beforeEach(async function () {
    [admin, authority, outsider] = await ethers.getSigners();
    const Factory = await ethers.getContractFactory("PaperTimeLock");
    contract = await Factory.deploy(admin.address);
    await contract.waitForDeployment();

    PAPER_ID = id("PAPER-2026-001");
    PAPER_HASH = id("encrypted-paper-bytes");
    EXAM_ID = id("EXAM-SIH-DEMO");
    ACTOR = id("USR-AUTHORITY-01");
  });

  async function registerPaper(secondsFromNow = 3600) {
    const releaseTime = (await time.latest()) + secondsFromNow;
    await contract.registerPaper(PAPER_ID, PAPER_HASH, EXAM_ID, releaseTime, ACTOR);
    return releaseTime;
  }

  describe("registration", function () {
    it("registers a paper and emits PaperRegistered", async function () {
      const releaseTime = (await time.latest()) + 3600;
      await expect(contract.registerPaper(PAPER_ID, PAPER_HASH, EXAM_ID, releaseTime, ACTOR))
        .to.emit(contract, "PaperRegistered")
        .withArgs(PAPER_ID, PAPER_HASH, EXAM_ID, releaseTime, anyUint());

      const paper = await contract.getPaper(PAPER_ID);
      expect(paper.paperHash).to.equal(PAPER_HASH);
      expect(paper.releaseTime).to.equal(releaseTime);
      expect(paper.released).to.equal(false);
      expect(paper.exists).to.equal(true);
    });

    it("rejects a release time in the past", async function () {
      const past = (await time.latest()) - 60;
      await expect(
        contract.registerPaper(PAPER_ID, PAPER_HASH, EXAM_ID, past, ACTOR)
      ).to.be.revertedWithCustomError(contract, "ReleaseTimeInPast");
    });

    it("rejects duplicate registration of the same paper", async function () {
      await registerPaper();
      const releaseTime = (await time.latest()) + 7200;
      await expect(
        contract.registerPaper(PAPER_ID, PAPER_HASH, EXAM_ID, releaseTime, ACTOR)
      ).to.be.revertedWithCustomError(contract, "PaperAlreadyRegistered");
    });

    it("rejects an empty paper hash", async function () {
      const releaseTime = (await time.latest()) + 3600;
      await expect(
        contract.registerPaper(PAPER_ID, ethers.ZeroHash, EXAM_ID, releaseTime, ACTOR)
      ).to.be.revertedWithCustomError(contract, "EmptyHash");
    });

    it("rejects registration from an unauthorised account", async function () {
      const releaseTime = (await time.latest()) + 3600;
      await expect(
        contract.connect(outsider).registerPaper(PAPER_ID, PAPER_HASH, EXAM_ID, releaseTime, ACTOR)
      ).to.be.revertedWithCustomError(contract, "AccessControlUnauthorizedAccount");
    });
  });

  describe("the time lock", function () {
    it("BLOCKS release before the release time", async function () {
      await registerPaper(3600);
      await expect(contract.releasePaper(PAPER_ID, ACTOR)).to.be.revertedWithCustomError(
        contract,
        "PaperStillLocked"
      );
      expect(await contract.isReleased(PAPER_ID)).to.equal(false);
    });

    it("reports the lock as not reached before the release time", async function () {
      await registerPaper(3600);
      expect(await contract.isReleaseTimeReached(PAPER_ID)).to.equal(false);
      expect(await contract.secondsUntilRelease(PAPER_ID)).to.be.greaterThan(0);
    });

    it("ALLOWS release once chain time passes the release time", async function () {
      const releaseTime = await registerPaper(60);
      await time.increaseTo(releaseTime + 1);

      expect(await contract.isReleaseTimeReached(PAPER_ID)).to.equal(true);
      await expect(contract.releasePaper(PAPER_ID, ACTOR)).to.emit(contract, "PaperReleased");

      const paper = await contract.getPaper(PAPER_ID);
      expect(paper.released).to.equal(true);
      expect(paper.releasedAt).to.be.greaterThan(0);
      expect(await contract.secondsUntilRelease(PAPER_ID)).to.equal(0);
    });

    it("allows release exactly at the release time (>= not >)", async function () {
      const releaseTime = await registerPaper(60);
      await time.setNextBlockTimestamp(releaseTime);
      await expect(contract.releasePaper(PAPER_ID, ACTOR)).to.emit(contract, "PaperReleased");
    });

    it("rejects a second release of the same paper", async function () {
      const releaseTime = await registerPaper(60);
      await time.increaseTo(releaseTime + 1);
      await contract.releasePaper(PAPER_ID, ACTOR);

      await expect(contract.releasePaper(PAPER_ID, ACTOR)).to.be.revertedWithCustomError(
        contract,
        "PaperAlreadyReleased"
      );
    });

    it("rejects release of a paper that was never registered", async function () {
      await expect(
        contract.releasePaper(id("PAPER-DOES-NOT-EXIST"), ACTOR)
      ).to.be.revertedWithCustomError(contract, "PaperNotRegistered");
    });

    it("rejects release from an account without RELEASE_AGENT_ROLE", async function () {
      const releaseTime = await registerPaper(60);
      await time.increaseTo(releaseTime + 1);
      await expect(
        contract.connect(outsider).releasePaper(PAPER_ID, ACTOR)
      ).to.be.revertedWithCustomError(contract, "AccessControlUnauthorizedAccount");
    });
  });

  describe("the client-clock attack", function () {
    /**
     * This is the SIH demo, expressed as an assertion.
     *
     * A user setting their device clock to the year 2099 changes nothing that
     * this contract can observe. The only clock it reads is block.timestamp.
     */
    it("is unaffected by the caller's local clock", async function () {
      await registerPaper(3600);

      const chainTimeBefore = await contract.blockchainTime();
      const clientClaimsItIs2099 = Math.floor(new Date("2099-01-01T00:00:00Z").getTime() / 1000);
      expect(clientClaimsItIs2099).to.be.greaterThan(Number(chainTimeBefore));

      // The client believing it is 2099 has no channel through which to tell the
      // chain so. Release still reverts.
      await expect(contract.releasePaper(PAPER_ID, ACTOR)).to.be.revertedWithCustomError(
        contract,
        "PaperStillLocked"
      );
      expect(await contract.isReleaseTimeReached(PAPER_ID)).to.equal(false);
    });

    it("records a denied early attempt instead of failing silently", async function () {
      await registerPaper(3600);
      await expect(contract.attemptRelease(PAPER_ID, ACTOR))
        .to.emit(contract, "ReleaseDenied")
        .withArgs(PAPER_ID, ACTOR, anyUint(), anyUint(), "RELEASE_TIME_NOT_REACHED");
    });
  });

  describe("integrity verification", function () {
    it("verifies a matching paper hash", async function () {
      await registerPaper();
      expect(await contract.verifyPaperHash(PAPER_ID, PAPER_HASH)).to.equal(true);
    });

    it("rejects a tampered paper hash", async function () {
      await registerPaper();
      expect(await contract.verifyPaperHash(PAPER_ID, id("tampered-bytes"))).to.equal(false);
    });
  });

  describe("enumeration", function () {
    it("indexes registered papers for auditors", async function () {
      await registerPaper();
      expect(await contract.totalPapers()).to.equal(1);
      expect(await contract.paperAt(0)).to.equal(PAPER_ID);
    });
  });
});

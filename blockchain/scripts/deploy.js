/**
 * Deploys QuestionRegistry and PaperTimeLock, then writes the resulting
 * addresses to blockchain/deployments/<network>.json.
 *
 * The backend reads that file at startup, so there is never a hand-copied
 * contract address anywhere in the stack -- one less thing to get wrong five
 * minutes before a demo.
 */
const fs = require("fs");
const path = require("path");
const { ethers, network } = require("hardhat");

async function main() {
  const [deployer] = await ethers.getSigners();
  const balance = await ethers.provider.getBalance(deployer.address);

  console.log("=".repeat(64));
  console.log("SecureLock contract deployment");
  console.log("=".repeat(64));
  console.log(`Network   : ${network.name} (chainId ${network.config.chainId ?? "auto"})`);
  console.log(`Deployer  : ${deployer.address}`);
  console.log(`Balance   : ${ethers.formatEther(balance)} ETH`);
  console.log("-".repeat(64));

  const QuestionRegistry = await ethers.getContractFactory("QuestionRegistry");
  const questionRegistry = await QuestionRegistry.deploy(deployer.address);
  await questionRegistry.waitForDeployment();
  const questionRegistryAddress = await questionRegistry.getAddress();
  console.log(`QuestionRegistry -> ${questionRegistryAddress}`);

  const PaperTimeLock = await ethers.getContractFactory("PaperTimeLock");
  const paperTimeLock = await PaperTimeLock.deploy(deployer.address);
  await paperTimeLock.waitForDeployment();
  const paperTimeLockAddress = await paperTimeLock.getAddress();
  console.log(`PaperTimeLock    -> ${paperTimeLockAddress}`);

  const deployment = {
    network: network.name,
    chainId: Number(network.config.chainId ?? 0),
    deployer: deployer.address,
    deployedAt: new Date().toISOString(),
    contracts: {
      QuestionRegistry: questionRegistryAddress,
      PaperTimeLock: paperTimeLockAddress,
    },
  };

  const outDir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, `${network.name}.json`);
  fs.writeFileSync(outFile, JSON.stringify(deployment, null, 2) + "\n");

  // The backend consumes the ABIs straight from the Hardhat artifacts, so export
  // a trimmed copy next to the addresses.
  const abiDir = path.join(outDir, "abi");
  fs.mkdirSync(abiDir, { recursive: true });
  for (const name of ["QuestionRegistry", "PaperTimeLock"]) {
    const artifact = require(path.join(__dirname, "..", "artifacts", "contracts", `${name}.sol`, `${name}.json`));
    fs.writeFileSync(path.join(abiDir, `${name}.json`), JSON.stringify(artifact.abi, null, 2) + "\n");
  }

  console.log("-".repeat(64));
  console.log(`Wrote ${outFile}`);
  console.log(`Wrote ${abiDir}\\{QuestionRegistry,PaperTimeLock}.json`);
  console.log("=".repeat(64));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

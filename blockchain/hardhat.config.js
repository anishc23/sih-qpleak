require("@nomicfoundation/hardhat-toolbox");
require("dotenv").config({ path: "../.env" });

/**
 * Network configuration is entirely environment-driven.
 *
 * The SIH demo runs against the local Hardhat node (`npm run node`), which needs
 * no internet, no faucet and no real currency. `testnet` is a generic
 * EVM-compatible target: point BLOCKCHAIN_RPC_URL at whatever chain is current
 * at demo time. No public testnet is hardcoded, deliberately -- testnets get
 * deprecated and we do not want the demo to depend on one.
 */
const TESTNET_RPC_URL = process.env.BLOCKCHAIN_RPC_URL || "";
const TESTNET_PRIVATE_KEY = process.env.BLOCKCHAIN_PRIVATE_KEY || "";

const networks = {
  hardhat: {
    chainId: 31337,
    // Without this, Hardhat forces every block's timestamp to be strictly
    // greater than the previous one. Seeding mines hundreds of blocks in a few
    // seconds, which pushes block.timestamp minutes ahead of wall-clock time and
    // makes short demo release windows land "in the past". Allowing equal
    // timestamps keeps chain time tracking real time closely.
    allowBlocksWithSameTimestamp: true,
    // Produce a block every second even with no traffic, the way a real chain
    // does. An idle Hardhat node only mines when a transaction arrives, which
    // freezes block.timestamp and makes a time lock look like it never expires.
    // `auto` keeps per-transaction mining so writes still confirm immediately.
    mining: {
      auto: true,
      interval: 1000,
    },
  },
  localhost: {
    url: "http://127.0.0.1:8545",
    chainId: 31337,
  },
};

if (TESTNET_RPC_URL && TESTNET_PRIVATE_KEY) {
  networks.testnet = {
    url: TESTNET_RPC_URL,
    accounts: [TESTNET_PRIVATE_KEY],
    chainId: process.env.BLOCKCHAIN_CHAIN_ID
      ? Number(process.env.BLOCKCHAIN_CHAIN_ID)
      : undefined,
  };
}

module.exports = {
  solidity: {
    version: "0.8.24",
    settings: {
      optimizer: { enabled: true, runs: 200 },
    },
  },
  networks,
  paths: {
    sources: "./contracts",
    tests: "./test",
    cache: "./cache",
    artifacts: "./artifacts",
  },
  mocha: {
    timeout: 60000,
  },
};

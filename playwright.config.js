const { defineConfig } = require("@playwright/test");

module.exports = defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  retries: 1,
  use: {
    headless: true,
    baseURL: "http://localhost:8501",
    screenshot: "only-on-failure",
    video: "off",
  },
  reporter: [["list"], ["html", { outputFolder: "tests/report", open: "never" }]],
});

import { defineConfig } from "@hey-api/openapi-ts";

export default defineConfig({
  input: "../../packages/openapi/openapi.json",
  output: {
    path: "src/lib/api/generated",
    format: "biome",
    lint: false,
  },
  plugins: [
    { name: "@hey-api/client-fetch", runtimeConfigPath: "./src/lib/api/runtime-config.ts" },
    "@hey-api/typescript",
    "@hey-api/sdk",
  ],
});

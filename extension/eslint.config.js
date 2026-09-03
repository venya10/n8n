import js from "@eslint/js";
import globals from "globals";

export default [
  { ignores: ["eslint.config.js"] },
  js.configs.recommended,
  {
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "script",
      globals: {
        ...globals.browser,
        ...globals.webextensions,
      },
    },
    rules: {
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_" }],
    },
  },
  {
    // Manifest content_scripts load reader.js -> overlay.js -> content.js in
    // sequence (see manifest.json), so each earlier file's exported object
    // is a real global by the time content.js runs — not a module import.
    files: ["src/content/content.js"],
    languageOptions: {
      globals: {
        N8nCopilotReader: "readonly",
        N8nCopilotOverlay: "readonly",
      },
    },
  },
  {
    // reader.js/overlay.js assign their IIFE's return value to a top-level
    // const that looks unused *within the file* — it's actually consumed by
    // content.js as a global, per the note above.
    files: ["src/content/reader.js", "src/ui/overlay.js"],
    rules: {
      "no-unused-vars": "off",
    },
  },
];

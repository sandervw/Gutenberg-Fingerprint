// Simple-code lint rules for TypeScript; numbers refer to SKILL.md.
import { readFileSync } from "node:fs";
import { defineConfig } from "eslint/config";
import typescriptEslint from "typescript-eslint";

const BANNED_WORDS = JSON.parse(readFileSync(new URL("./banned-words.json", import.meta.url), "utf8"));
const LIMITS = JSON.parse(readFileSync(new URL("./limits.json", import.meta.url), "utf8"));

const lowerWords = BANNED_WORDS.join("|");
const capitalWords = BANNED_WORDS.map((word) => word[0].toUpperCase() + word.slice(1)).join("|");
const upperWords = BANNED_WORDS.map((word) => word.toUpperCase()).join("|");
const bannedNamePattern = [
  `(^|_)(${lowerWords})($|_|[A-Z0-9])`,
  `[a-z0-9](${capitalWords})($|_|[A-Z0-9])`,
  `^(${capitalWords})($|[A-Z0-9])`,
  `(^|_)(${upperWords})($|_)`,
].join("|");

const MODULE_STATE = {
  selector: "Program > VariableDeclaration[kind=/^(let|var)$/]",
  message: "Module-level mutable state (4); pass state in instead.",
};
const BOOLEAN_FLAG = {
  selector: ":matches(FunctionDeclaration, MethodDefinition > FunctionExpression) > Identifier[typeAnnotation.typeAnnotation.type='TSBooleanKeyword']",
  message: "Boolean flag parameter (2, 5); split the function or use an enum.",
};
const BOOLEAN_DEFAULT = {
  selector: ":matches(FunctionDeclaration, MethodDefinition > FunctionExpression) > AssignmentPattern[right.raw=/^(true|false)$/]",
  message: "Boolean flag parameter (2, 5); split the function or use an enum.",
};
const CLOCK_READ = {
  selector: "NewExpression[callee.name='Date'][arguments.length=0]",
  message: "Core code reads the clock (1); pass the time in.",
};

/** The simple-code ESLint rules for TypeScript and JavaScript. */
export default defineConfig(
  { ignores: ["**/node_modules/**", "**/dist/**", "**/build/**", "**/*.d.ts"] },
  {
    files: ["**/*.{ts,tsx,mts,cts,js,jsx,mjs,cjs}"],
    languageOptions: {
      parser: typescriptEslint.parser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { "@typescript-eslint": typescriptEslint.plugin },
    rules: {
      complexity: ["error", LIMITS.maxComplexity],
      "max-depth": ["error", LIMITS.maxNesting],
      "max-params": ["error", LIMITS.maxParameters],
      "no-else-return": ["error", { allowElseIf: false }],
      "no-empty": ["error", { allowEmptyCatch: false }],
      "id-length": ["error", { min: 3, exceptions: [...LIMITS.allowedShortNames, ...LIMITS.exemptNames], properties: "never" }],
      "@typescript-eslint/naming-convention": [
        "error",
        {
          selector: ["variableLike", "class", "classMethod", "typeLike"],
          format: null,
          custom: { regex: bannedNamePattern, match: false },
        },
      ],
      "no-restricted-syntax": ["error", MODULE_STATE, BOOLEAN_FLAG, BOOLEAN_DEFAULT],
    },
  },
  {
    files: ["**/core/**/*.{ts,tsx,mts,cts,js,jsx,mjs,cjs}"],
    rules: {
      "no-restricted-globals": [
        "error",
        ...["fetch", "console", "crypto", "caches", "setTimeout", "setInterval"].map((name) => ({
          name,
          message: "Core code must stay pure (1); do this in the shell.",
        })),
      ],
      "no-restricted-properties": [
        "error",
        { object: "Date", property: "now", message: "Core code reads the clock (1); pass the time in." },
        { object: "Math", property: "random", message: "Core code uses randomness (1); pass a seed in." },
      ],
      "no-restricted-imports": [
        "error",
        { patterns: ["node:*", "fs", "child_process"] },
      ],
      "no-restricted-syntax": ["error", MODULE_STATE, BOOLEAN_FLAG, BOOLEAN_DEFAULT, CLOCK_READ],
    },
  },
);

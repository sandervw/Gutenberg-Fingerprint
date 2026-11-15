// Simple-code lint rules for TypeScript; numbers refer to SKILL.md.
import { readFileSync } from "node:fs";
import { defineConfig } from "eslint/config";
import typescriptEslint from "typescript-eslint";

const BANNED_WORDS = JSON.parse(readFileSync(new URL("./banned-words.json", import.meta.url), "utf8"));
const SETTINGS = JSON.parse(readFileSync(new URL("./checker-settings.json", import.meta.url), "utf8"));

const scriptGlob = `{${SETTINGS.typescriptSuffixes.map((suffix) => suffix.slice(1)).join(",")}}`;
const lowerWords = BANNED_WORDS.join("|");
const capitalWords = BANNED_WORDS.map((word) => word[0].toUpperCase() + word.slice(1)).join("|");
const upperWords = BANNED_WORDS.map((word) => word.toUpperCase()).join("|");
const bannedNamePattern = [
  `(^|_)(${lowerWords})($|_|[A-Z0-9])`,
  `[a-z0-9](${capitalWords})($|_|[A-Z0-9])`,
  `^(${capitalWords})($|[A-Z0-9])`,
  `(^|_)(${upperWords})($|_)`,
].join("|");

const BOOLEAN_FLAG_MESSAGE = "Boolean flag parameter (2, 5); split the function or use an enum.";
const CLOCK_MESSAGE = "Core code reads the clock (1); pass the time in.";

const MODULE_STATE = {
  selector: "Program > VariableDeclaration[kind=/^(let|var)$/]",
  message: "Module-level mutable state (4); pass state in instead.",
};
const BOOLEAN_FLAG = {
  selector: ":matches(FunctionDeclaration, MethodDefinition > FunctionExpression) > Identifier[typeAnnotation.typeAnnotation.type='TSBooleanKeyword']",
  message: BOOLEAN_FLAG_MESSAGE,
};
const BOOLEAN_DEFAULT = {
  selector: ":matches(FunctionDeclaration, MethodDefinition > FunctionExpression) > AssignmentPattern[right.raw=/^(true|false)$/]",
  message: BOOLEAN_FLAG_MESSAGE,
};
const CLOCK_READ = {
  selector: "NewExpression[callee.name='Date'][arguments.length=0]",
  message: CLOCK_MESSAGE,
};

/** The simple-code ESLint rules for TypeScript and JavaScript. */
export default defineConfig(
  { ignores: [...SETTINGS.skippedFolders.map((folder) => `**/${folder}/**`), `**/*${SETTINGS.declarationSuffix}`] },
  {
    files: [`**/*.${scriptGlob}`],
    languageOptions: {
      parser: typescriptEslint.parser,
      parserOptions: { ecmaFeatures: { jsx: true } },
    },
    plugins: { "@typescript-eslint": typescriptEslint.plugin },
    rules: {
      complexity: ["error", SETTINGS.maxComplexity],
      "max-depth": ["error", SETTINGS.maxNesting],
      "max-params": ["error", SETTINGS.maxParameters],
      "no-else-return": ["error", { allowElseIf: false }],
      "no-empty": ["error", { allowEmptyCatch: false }],
      "id-length": ["error", { min: SETTINGS.minNameLength, exceptions: [...SETTINGS.allowedShortNames, ...SETTINGS.exemptNames], properties: "never" }],
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
    files: [`**/${SETTINGS.coreFolder}/**/*.${scriptGlob}`],
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
        { object: "Date", property: "now", message: CLOCK_MESSAGE },
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

// Simple-code lint rules for TypeScript; numbers refer to SKILL.md.
import { defineConfig } from "eslint/config";
import typescriptEslint from "typescript-eslint";

// Keep in sync with BANNED_WORDS in scripts/rules.py.
const BANNED_WORDS = [
  "acc", "addr", "arg", "args", "attr", "attrs", "avg", "btn", "buf",
  "calc", "cfg", "cls", "cmd", "cnt", "conf", "conn", "csv", "ctx",
  "cur", "curr", "desc", "dest", "dict", "dir", "doc", "dst", "elem",
  "env", "err", "evt", "exc", "exe", "expr", "fmt", "func", "gen",
  "hdr", "html", "http", "https", "idx", "img", "impl", "init", "iter",
  "json", "kwargs", "len", "lib", "lst", "mgr", "msg", "num", "obj",
  "opt", "opts", "param", "params", "pkg", "pos", "prev", "proc",
  "prop", "ptr", "pwd", "qty", "recv", "ref", "req", "res", "resp",
  "ret", "seq", "sql", "src", "srv", "str", "tmp", "txt", "usr",
  "util", "utils", "uuid", "val", "vals", "var", "vars", "xml",
];

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
      complexity: ["error", 8],
      "max-depth": ["error", 3],
      "max-params": ["error", 4],
      "no-else-return": ["error", { allowElseIf: false }],
      "no-empty": ["error", { allowEmptyCatch: false }],
      "id-length": ["error", { min: 3, exceptions: ["id", "_"], properties: "never" }],
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

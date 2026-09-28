import { defineConfig, globalIgnores } from "eslint/config";
import eslint from "@eslint/js";
import next from "@next/eslint-plugin-next";
import reactHooks from "eslint-plugin-react-hooks";
import globals from "globals";
import tseslint from "typescript-eslint";

// eslint-plugin-react and eslint-plugin-jsx-a11y do not support ESLint 10 yet; add them
// back once they do. Type checking covers most of eslint-plugin-react's rules.
const eslintConfig = defineConfig([
  globalIgnores([
    ".next/**",
    "out/**",
    "next-env.d.ts",
  ]),
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  reactHooks.configs.flat["recommended-latest"],
  next.configs["core-web-vitals"],
  {
    languageOptions: {
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
  },
]);

export default eslintConfig;

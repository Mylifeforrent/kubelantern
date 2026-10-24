import eslint from '@eslint/js'
import tseslint from 'typescript-eslint'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'

// 说明：eslint-plugin-boundaries（模块边界静态检查，03-frontend-design §2.2）为
// [ASSUMPTION]（P0 工程化评审定工具），当前未引入；模块边界纪律以目录约定 + review 固定项执行。
export default tseslint.config(
  { ignores: ['dist', 'coverage', 'src/shared/api/schema.d.ts'] },
  eslint.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    plugins: { 'react-hooks': reactHooks, 'react-refresh': reactRefresh },
    rules: {
      ...reactHooks.configs.recommended.rules,
      'react-refresh/only-export-components': 'off',
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_', destructuredArrayIgnorePattern: '^_' },
      ],
      // openapi-fetch 的 data/error 判别已覆盖错误分支；允许非空断言的替代写法由 review 把关
      '@typescript-eslint/no-non-null-assertion': 'error',
    },
  },
  {
    // mock 层：边界上刻意处理 unknown JSON（no-base-to-string / 非空断言告警在此为噪音）
    files: ['src/shared/api/mock/**'],
    rules: {
      '@typescript-eslint/no-base-to-string': 'off',
      '@typescript-eslint/no-redundant-type-constituents': 'off',
      '@typescript-eslint/no-non-null-assertion': 'off',
    },
  },
)

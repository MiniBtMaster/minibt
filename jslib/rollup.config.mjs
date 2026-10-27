import typescript from '@rollup/plugin-typescript';
import { nodeResolve } from '@rollup/plugin-node-resolve';
import terser from '@rollup/plugin-terser';
import commonjs from '@rollup/plugin-commonjs';

export default [
  {
    // minibt desk app（报价 + 看盘）：IIFE，全局 `Desk`
    //
    // ⚠ 编辑器（CodeMirror 6）用**动态 import** → 单独成块 `desk-editor.js`，
    //   只有点开「代码」页签才下载，首屏 `desk.js` 体积不变 ✓
    input: 'src/desk/index.ts',
    output: {
      file: 'dist/desk.js',
      format: 'iife',
      name: 'Desk',
      globals: {
        'lightweight-charts': 'LightweightCharts',
      },
    },
    external: ['lightweight-charts'],
    plugins: [
      typescript({ tsconfig: './tsconfig.json' }),
      terser(),
    ],
  },
  {
    // 编辑器（CodeMirror 6）：**单独一个 IIFE**，全局 `DeskCodeEditor`，
    // 由 `code-editor.ts` 在第一次打开「代码」页签时 `<script>` 懒加载 ✓
    input: 'src/desk/editor-bundle.ts',
    output: {
      file: 'dist/desk-editor.js',
      format: 'iife',
      name: 'DeskCodeEditorBundle',
    },
    plugins: [
      // CodeMirror 是 ESM 包 → 必须 node-resolve 才能真正打进来 ✓
      nodeResolve({ browser: true, preferBuiltins: false }),
      // ★ `codemirror-languageserver` 依赖 CJS 的
      //   `vscode-languageserver-protocol`（具名导出 ESM 看不到）→ 必须转换 ✓
      commonjs({ include: /node_modules/, transformMixedEsModules: true }),
      typescript({ tsconfig: './tsconfig.json' }),
      terser(),
    ],
  },
  {
    input: 'src/index.ts',
    output: {
      file: 'dist/bundle.js',
      format: 'iife',
      name: 'Lib',
      globals: {
        'lightweight-charts': 'LightweightCharts',
      },
    },
    external: ['lightweight-charts'],
    plugins: [
      typescript(),
      terser(),
    ],
  },
];

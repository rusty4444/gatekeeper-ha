import resolve from '@rollup/plugin-node-resolve';
import terser from '@rollup/plugin-terser';

export default {
  input: 'src/index.js',
  output: {
    file: 'dist/gatekeeper-card.js',
    format: 'es',
    sourcemap: true,
  },
  plugins: [
    resolve(),
    terser({
      // Preserve class and function names for nicer HA dev-tools output.
      keep_classnames: true,
      keep_fnames: true,
    }),
  ],
};

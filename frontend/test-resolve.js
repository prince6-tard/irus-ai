try {
  console.log(require.resolve('lightningcss-win32-x64-msvc'));
} catch(e) {
  console.error('ERROR:', e.message);
}

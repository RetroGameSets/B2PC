/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './*.html', // Scanne index.html
    './**/*.html', // Scanne tout sous-dossier
    './renderer.js', // Scanne renderer.js
    './**/*.js' // Scanne autres JS si nécessaire
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
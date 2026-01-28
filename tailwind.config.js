/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        // Backgrounds
        'void': '#08080a',
        'deep': '#0c0c0e',
        'surface': '#111114',
        'elevated': '#18181c',
        'hover': '#1e1e24',
        // Accent colors
        'cyan': '#56d4dd',
        'green': '#73e0a0',
        'amber': '#e0b073',
        'red': '#e07373',
        'blue': '#7399e0',
        'magenta': '#d073e0',
        // Text
        'primary': '#e8e8ed',
        'secondary': '#a0a0ab',
        'muted': '#6a6a78',
        // Borders
        'border': '#252530',
        'border-bright': '#363644',
      },
      fontFamily: {
        'mono': ['SF Mono', 'Monaco', 'Menlo', 'JetBrains Mono', 'Consolas', 'monospace'],
      },
    },
  },
  plugins: [],
}

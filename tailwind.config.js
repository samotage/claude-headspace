/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.js",
  ],
  safelist: [
    'hidden',
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
        'display': ['Orbitron', 'SF Mono', 'monospace'],
      },
      boxShadow: {
        'neon-cyan': '0 0 8px rgba(86,212,221,0.3), 0 0 20px rgba(86,212,221,0.1)',
        'neon-green': '0 0 8px rgba(115,224,160,0.3), 0 0 20px rgba(115,224,160,0.1)',
        'neon-amber': '0 0 8px rgba(224,176,115,0.3), 0 0 20px rgba(224,176,115,0.1)',
        'neon-red': '0 0 8px rgba(224,115,115,0.3), 0 0 20px rgba(224,115,115,0.1)',
        'neon-blue': '0 0 8px rgba(115,153,224,0.3), 0 0 20px rgba(115,153,224,0.1)',
      },
    },
  },
  plugins: [],
}

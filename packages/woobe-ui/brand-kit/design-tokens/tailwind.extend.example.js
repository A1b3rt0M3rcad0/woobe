// Example Tailwind theme extension; merge with existing product theme intentionally.
const woobe = {
  colors: { orange: '#FF5500', canvas: '#F8F7F5', surface: '#FFFEFD',
    ink: '#0F0F0F', muted: '#6B6863', border: '#E3E1DD',
    success: '#197542', warning: '#9B5700', danger: '#B42318' },
  fontFamily: { sans: ['Inter','system-ui','sans-serif'],
    mono: ['JetBrains Mono','Fira Code','monospace'],
    serif: ['Georgia','Times New Roman','serif'] },
  borderRadius: { panel: '10px', control: '6px', stage: '26px' }
};
module.exports = { theme: { extend: woobe } };

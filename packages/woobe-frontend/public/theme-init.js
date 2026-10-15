/* Runs before styles/application code, including when storage is unavailable. */
;(function () {
  var preference = 'system'
  try {
    var saved = localStorage.getItem('woobe.theme')
    if (saved === 'light' || saved === 'dark') preference = saved
  } catch (_) { /* A blocked storage API must not prevent startup. */ }
  var dark = preference === 'dark' || (preference === 'system' && matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.dataset.theme = dark ? 'dark' : 'light'
})()

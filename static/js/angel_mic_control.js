
(function () {
  function status(msg) {
    const el = document.getElementById('angel-mic-status') || document.getElementById('angel-voice-status');
    if (el) el.textContent = msg;
  }
  async function ensureMic() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      status('Microphone API not available in this browser.');
      return false;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(t => t.stop()); // permission only
      status('Microphone allowed — Angel can listen.');
      window.__cgMicAllowed = true;
      return true;
    } catch (e) {
      status('Microphone blocked — allow mic for this site in browser settings.');
      window.__cgMicAllowed = false;
      return false;
    }
  }
  function bind() {
    document.querySelectorAll('[data-angel-mic-request], #angel-mic-request').forEach(btn => {
      if (btn.dataset.boundMic) return;
      btn.dataset.boundMic = '1';
      btn.addEventListener('click', async (e) => {
        e.preventDefault();
        const ok = await ensureMic();
        btn.textContent = ok ? '🎤 Mic on' : '🎤 Allow microphone';
        btn.classList.toggle('mic-on', ok);
        // If Alpine angel exists, try resume listen
        try {
          if (ok && window.Alpine) {
            /* portal may call _angelResumeListen via custom event */
            document.dispatchEvent(new CustomEvent('cg-mic-granted'));
          }
        } catch (err) {}
      });
    });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bind);
  else bind();
  window.cgRequestAngelMic = ensureMic;
})();

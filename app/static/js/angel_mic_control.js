
(function () {
  function setStatus(msg, ok) {
    var el = document.getElementById("angel-mic-status") || document.getElementById("angel-voice-status");
    if (el) {
      el.textContent = msg;
      el.style.color = ok ? "#6ee7b7" : "#fde68a";
    }
  }
  async function ensureMic() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setStatus("Mic API missing — use Chrome/Edge over HTTPS.", false);
      return false;
    }
    try {
      var stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach(function (t) { t.stop(); });
      window.__cgMicAllowed = true;
      setStatus("Microphone ON — Angel can listen.", true);
      document.dispatchEvent(new CustomEvent("cg-mic-granted"));
      // try resume portal angel listen if Alpine exposed
      try {
        var root = document.querySelector("[x-data]");
        if (root && root._x_dataStack && root._x_dataStack[0] && typeof root._x_dataStack[0]._angelResumeListen === "function") {
          root._x_dataStack[0]._angelResumeListen();
        }
      } catch (e) {}
      return true;
    } catch (err) {
      window.__cgMicAllowed = false;
      setStatus("Mic blocked — site settings → allow microphone for churchgate.knowsoft.org.uk", false);
      return false;
    }
  }
  function bind() {
    document.querySelectorAll("[data-angel-mic-request], #angel-mic-request").forEach(function (btn) {
      if (btn.dataset.boundMic) return;
      btn.dataset.boundMic = "1";
      btn.addEventListener("click", async function (e) {
        e.preventDefault();
        e.stopPropagation();
        var ok = await ensureMic();
        btn.textContent = ok ? "🎤 Mic on" : "🎤 Allow microphone";
      });
    });
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", bind);
  else bind();
  window.cgRequestAngelMic = ensureMic;
})();

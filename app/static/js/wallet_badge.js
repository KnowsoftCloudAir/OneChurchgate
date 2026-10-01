
(function () {
  function paint(btn, data) {
    if (!btn || !data) return;
    var bal = Number(data.balance || 0);
    var healthy = !!data.healthy;
    btn.style.background = healthy
      ? "linear-gradient(135deg,#059669,#10b981)"
      : "linear-gradient(135deg,#dc2626,#ea580c)";
    btn.style.color = "#fff";
    btn.style.border = "none";
    var label = btn.querySelector("[data-wallet-bal]") || btn;
    if (btn.querySelector("[data-wallet-bal]")) {
      btn.querySelector("[data-wallet-bal]").textContent = bal.toLocaleString(undefined, { maximumFractionDigits: 0 });
    } else {
      btn.innerHTML = "Wallet · <span data-wallet-bal>" + bal.toLocaleString(undefined, { maximumFractionDigits: 0 }) + "</span>";
    }
  }
  async function refresh() {
    var btn = document.getElementById("cg-wallet-btn");
    if (!btn) return;
    try {
      var r = await fetch("/member/wallet/summary.json", { credentials: "same-origin" });
      if (!r.ok) return;
      var data = await r.json();
      paint(btn, data);
    } catch (e) {}
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", refresh);
  else refresh();
  window.cgWalletRefresh = refresh;
})();

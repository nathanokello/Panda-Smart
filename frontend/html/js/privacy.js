/* privacy.html: readable without signing in (the sign-up form links here). */
document.addEventListener("DOMContentLoaded", () => {
  if (PandaAPI.getToken()) {
    PandaUI.init({ active: "privacy" });
    return;
  }
  // Signed out: hide the app menu and offer a way back.
  document.getElementById("sidebar").remove();
  document.querySelector(".main-area").style.marginLeft = "0";
  document.getElementById("menuButton").remove();
  document.querySelector(".topbar-right").innerHTML =
    '<a class="button button-outline button-small" style="margin:0" href="register.html">Back to sign-up</a>';
});

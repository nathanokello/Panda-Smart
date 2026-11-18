/* Sign-in and farmer self-registration (login.html, register.html). */
document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll("[data-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const input = document.getElementById(button.dataset.toggle);
      const reveal = input.type === "password";
      input.type = reveal ? "text" : "password";
      button.setAttribute("aria-label", reveal ? "Hide password" : "Show password");
      button.textContent = reveal ? "◎" : "◉";
    });
  });

  const loginForm = document.getElementById("loginForm");
  if (loginForm) {
    const message = document.getElementById("loginMessage");
    if (new URLSearchParams(location.search).get("expired")) {
      PandaUI.message(message, "Your session ended. Please sign in again.", "info");
    }
    loginForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const button = loginForm.querySelector("button[type=submit]");
      PandaUI.message(message, "");
      try {
        const result = await PandaUI.busy(button, () => PandaAPI.login({
          phone: loginForm.phone.value.trim(),
          password: loginForm.password.value
        }));
        if (!result || !result.token) throw new Error("The server did not return a sign-in token.");
        PandaAPI.saveSession(result.token, result.user);
        location.href = "index.html";
      } catch (error) {
        PandaUI.message(message, error.message);
      }
    });
  }

  const wardSelect = document.getElementById("wardSelect");
  if (wardSelect) {
    PandaAPI.wards().then((wards) => {
      wardSelect.innerHTML = wards.length
        ? PandaUI.options(wards, (w) => w.id, PandaUI.wardText, "Select your ward")
        : '<option value="">No wards loaded yet. Ask an administrator.</option>';
    }).catch((error) => {
      wardSelect.innerHTML = `<option value="">Could not load wards: ${PandaUI.esc(error.message)}</option>`;
    });
  }

  const registerForm = document.getElementById("registerForm");
  if (registerForm) registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = document.getElementById("registerMessage");
    if (registerForm.password.value !== registerForm.confirm_password.value) {
      PandaUI.message(message, "Your passwords do not match.");
      return;
    }
    const button = registerForm.querySelector("button[type=submit]");
    PandaUI.message(message, "");
    try {
      const result = await PandaUI.busy(button, () => PandaAPI.registerFarmer({
        name: registerForm.name.value.trim(),
        phone: registerForm.phone.value.trim(),
        password: registerForm.password.value,
        ward_id: registerForm.ward_id.value,
        consent_given: document.getElementById("consent").checked
      }));
      if (result && result.token) {
        PandaAPI.saveSession(result.token, result.user);
        location.href = "index.html";
      } else {
        location.href = "login.html";
      }
    } catch (error) {
      PandaUI.message(message, error.message);
    }
  });
});

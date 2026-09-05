const form = document.querySelector(".settings-card");

const username = document.getElementById("username");
const password = document.getElementById("password");

form.addEventListener("submit", function (event) {
  if (username.value.trim().length < 6) {
    event.preventDefault();

    showError("Username must be at least 6 characters long.");
    return;
  }

  if (password.value.length > 0 && password.value.length < 6) {
    event.preventDefault();

    showError("Password must be at least 6 characters long.");
    return;
  }
});

function showError(message) {
  let error = document.querySelector(".settings-error");

  if (!error) {
    error = document.createElement("p");

    error.className = "settings-error";

    const button = document.querySelector(".settings-button");

    form.insertBefore(error, button);
  }

  error.textContent = message;
}

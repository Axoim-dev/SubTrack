const username = document.getElementById("username");
const password = document.getElementById("password");
const form = document.querySelector(".signup-card");

form.addEventListener("submit", (e) => {
  if (username.value.length < 6) {
    e.preventDefault();

    let error = document.querySelector(".signup-error");

    if (!error) {
      error = document.createElement("p");
      error.className = "signup-error";
      form.insertBefore(error, document.querySelector(".signup-button"));
    }

    error.textContent = "Username must be at least 6 characters long.";
    return;
  }

  if (password.value.length < 6) {
    e.preventDefault();

    let error = document.querySelector(".signup-error");

    if (!error) {
      error = document.createElement("p");
      error.className = "signup-error";
      form.insertBefore(error, document.querySelector(".signup-button"));
    }

    error.textContent = "Password must be at least 6 characters long.";
    return;
  }
});

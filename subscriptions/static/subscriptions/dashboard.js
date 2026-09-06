function toggleSubscriptionMenu(button) {
  const menu = button.nextElementSibling;

  document
    .querySelectorAll(".subscription-dropdown.show")
    .forEach(function (otherMenu) {
      if (otherMenu !== menu) {
        otherMenu.classList.remove("show");
      }
    });

  menu.classList.toggle("show");
}

document.addEventListener("click", function (event) {
  if (!event.target.closest(".subscription-menu")) {
    document
      .querySelectorAll(".subscription-dropdown.show")
      .forEach(function (menu) {
        menu.classList.remove("show");
      });
  }
});

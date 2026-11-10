"use strict";
const languageControl = document.getElementById("language-control");
const languageSelect = document.getElementById("lang");
const languageLinks = document.getElementById("language-links");
if (languageControl && languageSelect && languageLinks) {
  languageSelect.addEventListener("change", () => {
    window.location.assign(languageSelect.value);
  });
  languageControl.hidden = false;
  languageLinks.hidden = true;
}

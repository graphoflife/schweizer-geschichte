// Blättern mit den Pfeiltasten, Bilder vergrössern, Erklär-Punkte hervorheben.
(function () {
  "use strict";

  document.addEventListener("keydown", function (e) {
    if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return;
    if (/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) return;
    if (document.querySelector(".lupe")) {
      if (e.key === "Escape") schliesseLupe();
      return;
    }
    var rel = e.key === "ArrowLeft" ? "prev" : e.key === "ArrowRight" ? "next" : null;
    var link = rel && document.querySelector('link[rel="' + rel + '"]');
    if (link) location.href = link.href;
  });

  function schliesseLupe() {
    var l = document.querySelector(".lupe");
    if (l) l.remove();
  }

  document.addEventListener("click", function (e) {
    var a = e.target.closest(".fig__link");
    if (!a) {
      if (e.target.closest(".lupe")) schliesseLupe();
      return;
    }
    e.preventDefault();
    var fig = a.closest("figure");
    var lupe = document.createElement("div");
    lupe.className = "lupe";
    lupe.setAttribute("role", "dialog");
    lupe.setAttribute("aria-label", "Bild vergrössert – klicken oder Esc zum Schliessen");
    var img = document.createElement("img");
    img.src = a.getAttribute("href");
    img.alt = (a.querySelector("img") || {}).alt || "";
    lupe.appendChild(img);
    var cap = fig && fig.querySelector("figcaption");
    if (cap) {
      var p = document.createElement("p");
      p.innerHTML = cap.innerHTML;
      var punkte = p.querySelector(".fig__punkte");
      if (punkte) punkte.remove();
      lupe.appendChild(p);
    }
    document.body.appendChild(lupe);
  });

  // Erklär-Punkte: Punkt und Legendeneintrag gegenseitig hervorheben
  document.querySelectorAll(".fig").forEach(function (fig) {
    var paare = {};
    fig.querySelectorAll("[data-n]").forEach(function (el) {
      (paare[el.dataset.n] = paare[el.dataset.n] || []).push(el);
    });
    Object.keys(paare).forEach(function (n) {
      paare[n].forEach(function (el) {
        el.addEventListener("mouseenter", function () { paare[n].forEach(function (x) { x.classList.add("aktiv"); }); });
        el.addEventListener("mouseleave", function () { paare[n].forEach(function (x) { x.classList.remove("aktiv"); }); });
      });
    });
  });
})();

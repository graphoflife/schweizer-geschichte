/* Seitensatz der Druckfassung – tools/druck.py lädt docs/druck/buch.html in Chrome und ruft satz() auf.

   Chrome kann Seiten selbst umbrechen, aber nicht wie ein Buch: Bilder rutschen weiter und lassen Lücken,
   Hintergründe enden mitten auf der Seite, Kapitel beginnen irgendwo. Deshalb baut dieses Skript jede Seite
   selbst aus dem Vorrat (#vorrat):
   - zwei Spalten (im Bildnachweis drei) auf einem festen Zeilenraster: alle Textzeilen stehen links und rechts
     auf gleicher Höhe; Bilder, Kästen und Überschriften belegen ganze Rasterzeilen;
   - Absätze werden zeilengenau umbrochen, mindestens zwei Zeilen am Spaltenende und am Spaltenanfang;
   - Bilder und Kästen gleiten: Passt eines nicht mehr in die Spalte, steht es oben in der nächsten, und der
     Text läuft weiter. Breite Bilder und Karten stehen oben über beiden Spalten, wenn möglich auf der Seite,
     auf der sie erwähnt werden; zu lange Kästen werden in der nächsten Spalte fortgesetzt;
   - bleibt am Spaltenfuss Platz, verteilt er sich auf die Abstände um Bilder und Überschriften;
   - jedes Kapitel beginnt oben auf einer neuen Seite; seine letzte Seite wird in der Höhe ausgeglichen;
   - danach kommen Kolumnentitel, Seitenzahl, ein Aquarell pro Doppelseite und auf jeder rechten Seite der
     Zahlenstrahl; zuletzt die Seitenzahlen im Inhaltsverzeichnis und im Bildnachweis.
   Masse in px (CSS, 96 pro Zoll); die Seitengeometrie muss zu druck/druck.css passen. */
"use strict";
(() => {
  const MM = 96 / 25.4;
  const Z = 18.75;                       // Zeilenraster: Fliesstext 14 px auf 18,75 px (10,5 auf 14 pt)
  const ZEILEN = 51;                     // Zeilen pro Spalte
  const SATZ_H = ZEILEN * Z;             // Höhe des Satzspiegels (253 mm)
  const SATZ_B = 170 * MM;
  const ABSTAND = { 1: 0, 2: 7 * MM, 3: 5 * MM };
  const OBEN_MAX = 0.62;                 // höchstens dieser Anteil der Satzhöhe für Bilder über beiden Spalten
  const DICHT = ".quelle, .nw, .zt, .d-toc";   // Listen, die nicht aufs Raster gesetzt werden
  const daten = JSON.parse(document.getElementById("satz-daten").textContent);
  const warnungen = [];
  const seiten = [];
  const aqSeiten = {};                   // Aquarell-ID → Seitenzahlen
  const aqZaehler = new Map();           // Fluss → nächstes Aquarell
  let buch, mess;
  let eng = false;                       // engerer Satz (Kästen ohne Schlussornament, weniger Luft um Bilder)

  // ---------------------------------------------------------------- Hilfen
  function neu(tag, klasse, text) {
    const e = document.createElement(tag);
    if (klasse) e.className = klasse;
    if (text != null) e.textContent = text;
    return e;
  }
  const raster = (y) => Math.ceil(y / Z - 0.01) * Z;
  const hoehe = (k) => k.getBoundingClientRect().height;
  function setze(behaelter, k, y) {
    k.style.top = `${y}px`;
    behaelter.append(k);
    return hoehe(k);
  }
  function beschreibe(k) {
    return (k.querySelector("h3, .fig__titel, b")?.textContent || k.textContent).trim().slice(0, 60);
  }
  function warne(text, f) {
    warnungen.push(`${f ? f.id + ": " : ""}${text}`);
  }

  // --------------------------------------------------------------- Vorrat
  function lies(q) {
    const d = q.dataset;
    const items = [];
    let kopf = null;
    const absatz = (k) => {
      if (k.matches("ol.zeitleiste")) {    // Zeittafel als eigener Kasten, der wie ein Bild gleitet
        const kasten = neu("div", "zeittafel");
        kasten.append(neu("h3", "", "Zeittafel"), k);
        k = kasten;
      }
      items.push(k);
    };
    for (const k of [...q.children]) {
      if (k.matches(".q-oben")) kopf = k;
      else if (k.matches("section.quellen")) {
        // Die Quellen als ein Block, der sich nach allen Bildern und Kästen einreiht und beliebig teilbar ist
        const block = neu("div", "quellen-block");
        for (const c of [...k.children]) {
          if (c.matches("ol, ul")) {
            [...c.children].forEach((li, n) => {
              const e = neu("div", "quelle");
              e.dataset.n = n + 1;
              e.append(...li.childNodes);
              block.append(e);
            });
          } else block.append(c);
        }
        items.push(block);
      } else if (k.matches("section")) {
        let erster = true;                // erster Absatz nach der Überschrift: ohne Einzug, Kapitälchen
        for (const c of [...k.children]) {
          if (c.matches("h2")) erster = true;
          else if (erster && c.matches("p")) {
            c.classList.add("erster");
            erster = false;
          }
          absatz(c);
        }
      } else absatz(k);
    }
    return {
      id: d.id, kopf, items, spalten: +d.spalten || 2, art: d.art || "", aq: d.aq ? d.aq.split(" ") : [],
      links: d.kopfLinks, rechts: d.kopfRechts, teil: d.teil ? +d.teil : null, strahl: d.strahl || "",
      von: d.von != null ? +d.von : null, bis: d.bis != null ? +d.bis : null,
      farbe: q.style.getPropertyValue("--teil"), klassen: [...q.classList].filter((c) => c !== "q-fluss"),
    };
  }

  // --------------------------------------------------------------- Seiten
  function neueSeite(f) {
    const knoten = neu("div", "seite");
    const satz = neu("div", "satz");
    knoten.append(satz);
    if (f) {
      knoten.dataset.fluss = f.id;
      knoten.style.setProperty("--teil", f.farbe);
      knoten.classList.add(...f.klassen);
    }
    buch.append(knoten);
    return { knoten, satz, fluss: f, spalten: [] };
  }

  function neueSpalte(s, c, n, top, h) {
    const b = (SATZ_B - (n - 1) * ABSTAND[n]) / n;
    const sp = neu("div", "spalte");
    sp.style.cssText = `left:${c * (b + ABSTAND[n])}px;top:${top}px;width:${b}px;height:${h}px`;
    s.satz.append(sp);
    return sp;
  }

  // --------------------------------------------------------- Elementarten
  function istBreit(k) {
    if (!k.matches(".fig--breit, .fig--voll")) return false;
    if (k.matches(".karte")) return true;
    const r = k.querySelector(".fig__rahmen");
    return +r.style.getPropertyValue("--b") / +r.style.getPropertyValue("--h") >= 1.25;
  }
  function art(k) {
    if (k.matches("h2, h3")) return "titel";
    if (k.matches("figure.fig")) return istBreit(k) ? "breit" : "gleit";
    if (k.matches("aside.kasten, .zeittafel")) return "kasten";
    if (k.matches(".quellen-block")) return "quellen";
    if (k.matches("p, .quelle, .nw")) return "text";
    if (k.matches("ol, ul, dl, blockquote:not(.zitat)")) return "teilbar";
    return "block";
  }
  const istTextblock = (k) => k.matches("p, li, dd, dt, .quelle, .nw") && !k.matches(".zeitleiste li")
    && !k.querySelector("p, ul, ol, dl, div, figure, blockquote");
  const teilbarKind = (c) => istTextblock(c) || c.matches("ul, ol:not(.fig__punkte), dl, blockquote");

  // ------------------------------------------------- Zeilengenau umbrechen
  function zeichen(k) {
    const liste = [];
    const w = document.createTreeWalker(k, NodeFilter.SHOW_TEXT);
    for (let t; (t = w.nextNode());) {
      const s = t.data;
      for (let i = 0; i < s.length; i++) if (!/[\s­]/.test(s[i])) liste.push([t, i]);
    }
    return liste;
  }
  function rechteck([t, i]) {
    const r = document.createRange();
    r.setStart(t, i);
    r.setEnd(t, i + 1);
    const rs = r.getClientRects();      // am Zeilenanfang liefert Chrome zuerst ein leeres Rechteck am alten Zeilenende
    return rs.length ? rs[rs.length - 1] : r.getBoundingClientRect();
  }
  function letzterText(k) {
    const w = document.createTreeWalker(k, NodeFilter.SHOW_TEXT);
    let letzter = null;
    for (let t; (t = w.nextNode());) if (t.data.trim()) letzter = t;
    return letzter;
  }
  function schneide(k, zs, j) {
    const [t, o] = zs[j];
    const r1 = document.createRange();
    r1.setStart(k, 0);
    r1.setEnd(t, o);
    const r2 = document.createRange();
    r2.setStart(t, o);
    r2.setEnd(k, k.childNodes.length);
    const a = k.cloneNode(false);
    const b = k.cloneNode(false);
    a.append(r1.cloneContents());
    b.append(r2.cloneContents());
    // Mitten im Wort getrennt (Silbentrennung oder weiches Trennzeichen): Trennstrich ans Zeilenende setzen
    const [tv, ov] = zs[j - 1];
    const fuge = document.createRange();
    fuge.setStart(tv, ov + 1);
    fuge.setEnd(t, o);
    if (!/\s/.test(fuge.toString()) && /[\p{L}\p{N}]/u.test(tv.data[ov]) && /[\p{L}]/u.test(t.data[o])) {
      const l = letzterText(a);
      if (l) l.data = l.data.replace(/­$/, "") + "-";
    }
    a.classList.add("teil-a");
    b.classList.add("teil-b");
    b.removeAttribute("id");
    return [a, b];
  }
  function teileText(k, platz, minOben) {
    const lh = parseFloat(getComputedStyle(k).lineHeight);
    if (!(lh > 0)) return null;
    const box = k.getBoundingClientRect();
    const gesamt = Math.round(box.height / lh);
    let n = Math.min(Math.floor((platz + 0.5) / lh), gesamt - 2);
    const zs = zeichen(k);
    const zeile = (j) => {
      const r = rechteck(zs[j]);
      return Math.floor((r.top + r.height / 2 - box.top) / lh);
    };
    for (let versuch = 0; versuch < 3 && n >= minOben; versuch++, n--) {
      let lo = 0, hi = zs.length;
      while (lo < hi) {
        const m = (lo + hi) >> 1;
        if (zeile(m) >= n) hi = m;
        else lo = m + 1;
      }
      if (lo === 0 || lo >= zs.length) return null;
      const [a, b] = schneide(k, zs, lo);
      k.replaceWith(a);
      const ha = hoehe(a);
      a.replaceWith(k);
      if (ha <= platz + 0.5) return [a, b];
    }
    return null;
  }
  function teileBehaelter(k, platz, minRest = 0) {
    const kinder = [...k.children].filter((c) => !c.matches(".pin"));
    if (!kinder.length) return null;
    const oben = k.getBoundingClientRect().top;
    const cs = getComputedStyle(k);
    const grenze = platz - parseFloat(cs.paddingBottom) - parseFloat(cs.borderBottomWidth) - 2;
    let idx = kinder.findIndex((c) => c.getBoundingClientRect().bottom - oben > grenze + 0.5);
    if (idx < 0) idx = kinder.length - 1;   // nur der Rand passt nicht mehr: das letzte Kind weitergeben
    for (let j = idx; j >= 0; j--) {
      const c = kinder[j];
      const vorne = kinder.slice(0, j);
      let geteilt = null;
      if (j === idx && teilbarKind(c)) geteilt = teileBlock(c, grenze - (c.getBoundingClientRect().top - oben), 2);
      // Der erste Teil darf nicht mit einer Überschrift enden und muss mehr als nur Überschriften enthalten
      if (!geteilt && (!vorne.some((x) => !x.matches("h2, h3, h4, dt")) || vorne.at(-1).matches("h2, h3, h4, dt"))) continue;
      const a = k.cloneNode(false);
      const b = k.cloneNode(false);
      vorne.forEach((x) => a.append(x.cloneNode(true)));
      if (geteilt) {
        a.append(geteilt[0]);
        b.append(geteilt[1]);
      } else b.append(c.cloneNode(true));
      kinder.slice(j + 1).forEach((x) => b.append(x.cloneNode(true)));
      if (k.matches("ol")) {             // Nummerierung fortsetzen
        const ganz = [...a.children].filter((x) => !x.classList.contains("teil-a")).length;
        b.setAttribute("start", (+k.getAttribute("start") || 1) + ganz);
      }
      a.classList.add("teil-a");
      b.classList.add("teil-b");
      k.replaceWith(a);
      const ha = hoehe(a);
      a.replaceWith(k);
      if (ha <= platz + 0.5) return hoehe(k) - ha >= minRest ? [a, b] : null;
    }
    return null;
  }
  // Kästen und Zeittafeln nur teilen, wenn in der nächsten Spalte ein rechtes Stück (sieben Rasterzeilen) weitergeht
  function teileBlock(k, platz, minOben = 2) {
    if (istTextblock(k)) return teileText(k, platz, minOben);
    return teileBehaelter(k, platz, k.matches(".kasten, .zeittafel") ? 7 * Z : 0);
  }

  // ---------------------------------------------------------------- Spalte
  const zustand = () => ({ i: 0, rest: null, warte: [], breit: [], vorab: [] });
  const kopie = (z) => ({ i: z.i, rest: z.rest, warte: [...z.warte], breit: [...z.breit], vorab: [...z.vorab] });
  const fertig = (z, f) => z.i >= f.items.length && !z.rest && !z.warte.length && !z.breit.length;
  const naechstes = (z, f) => z.rest || f.items[z.i];
  function weiter(z) {
    if (z.rest) z.rest = null;
    else z.i++;
  }
  function rest(z, b) {
    if (!z.rest) z.i++;
    z.rest = b;
  }
  function folgeBedarf(z, f) {
    for (let j = z.i + 1; j < f.items.length; j++) {
      const k = f.items[j];
      if (z.vorab.includes(k) || ["gleit", "breit"].includes(art(k))) continue;
      return 2 * Z;
    }
    return Z;
  }

  // Bild oder Karte in der Spalte verkleinern (höchstens auf 62 %), damit es noch in den Platz passt
  function zuruecksetzen(k) {
    const b = k.querySelector?.(":scope > .fig__rahmen, :scope > .karte__svg");
    if (b && k.matches("figure.fig")) b.style.removeProperty("max-width");
  }
  function schrumpfe(k, platz) {
    if (!k.matches("figure.fig") || platz <= 0) return false;
    const b = k.querySelector(":scope > .fig__rahmen, :scope > .karte__svg");
    if (!b) return false;
    const hb = hoehe(b);
    const faktor = (hb - (hoehe(k) - platz) - 1) / hb;
    if (faktor < 0.62) return false;
    b.style.maxWidth = `${b.getBoundingClientRect().width * faktor}px`;
    if (hoehe(k) <= platz + 0.5) return true;
    b.style.removeProperty("max-width");
    return false;
  }

  // Verteilt freie Rasterzeilen am Spaltenfuss auf die Abstände um Bilder, Kästen und Überschriften.
  function gleicheAus(plan, h) {
    if (plan.length < 2) return;
    const letzt = plan[plan.length - 1];
    const frei = Math.floor((h - (letzt.y + letzt.h)) / Z + 0.01);
    // In Spalten nur aus Bildern und Kästen darf mehr Luft verteilt werden: sie schliessen dann unten bündig ab
    const nurBilder = plan.every((p) => p.art !== "text" && p.art !== "titel");
    if (frei < 1 || frei > (nurBilder ? 20 : 8)) return;
    const luftig = ["gleit", "block", "teilbar", "kasten"];
    const fugen = [];
    for (let j = 1; j < plan.length; j++) {
      if (luftig.includes(plan[j - 1].art) || luftig.includes(plan[j].art) || plan[j].art === "titel") fugen.push(j);
    }
    if (!fugen.length) return;
    let verschub = 0;
    const extra = new Map();
    for (let n = 0; n < frei; n++) extra.set(fugen[n % fugen.length], (extra.get(fugen[n % fugen.length]) || 0) + Z);
    plan.forEach((p, j) => {
      verschub += extra.get(j) || 0;
      if (verschub) p.k.style.top = `${(p.y += verschub)}px`;
    });
  }

  function fuelleSpalte(sp, h, z, f, ausgleich) {
    const plan = [];
    let y = 0;
    const lege = (k, a, yTop) => {
      const hk = setze(sp, k, yTop);
      plan.push({ k, y: yTop, h: hk, art: a });
      return hk;
    };
    const ende = (status, grund) => {
      if (status === "voll" && ausgleich) gleicheAus(plan, h);
      return { status, plan, grund: grund && `${art(grund)}: ${beschreibe(grund)}`, warten: z.warte.length };
    };
    // Gleitobjekt an die Stelle y setzen, wenn es passt (Bilder notfalls etwas verkleinert)
    const luft = eng ? Z / 4 : Z / 2;
    const gleite = (k) => {
      const vor = plan.length ? luft : 0;
      zuruecksetzen(k);
      k.classList.toggle("knapp", eng && k.matches(".kasten, .zeittafel"));
      const hk = setze(sp, k, y + vor);
      if (y + vor + hk > h + 0.5 && !schrumpfe(k, h - y - vor)) {
        // Kästen, denen nur wenig fehlt, rücken ohne Schlussornament enger zusammen
        if (!k.matches(".kasten, .zeittafel") || y + vor + hk > h + 1.5 * Z) return false;
        k.classList.add("knapp");
        if (y + vor + hoehe(k) > h + 0.5) {
          k.classList.remove("knapp");
          return false;
        }
      }
      plan.push({ k, y: y + vor, h: hoehe(k), art: k.matches(".kasten, .zeittafel") ? "kasten" : "gleit" });
      y = raster(y + vor + hoehe(k) + luft);
      return true;
    };
    // Wartende Gleitobjekte setzen; kleinere dürfen ein zu grosses um höchstens zwei Plätze überholen, die Quellen
    // nur im engen Satz. Ist der Text zu Ende (amEnde), füllt ein Kasten den Rest der Spalte und läuft in der nächsten weiter.
    // Gibt true zurück, wenn die Spalte damit voll ist.
    const wartende = (amEnde) => {
      for (let j = 0; j < Math.min(z.warte.length, 3);) {
        const k = z.warte[j];
        const quellen = k.matches(".quellen-block");
        if (quellen && j > 0 && !eng) break;   // im engen Satz dürfen die Quellen eine Lücke füllen
        if (gleite(k)) {
          z.warte.splice(j, 1);
          continue;
        }
        const hk = hoehe(k);
        const vor = plan.length ? luft : 0;
        if (quellen || (amEnde && j === 0 && k.matches(".kasten, .zeittafel"))) {
          const teile = h - y - vor >= (quellen ? 3 : 6) * Z ? teileBlock(k, h - y - vor) : null;
          if (teile) {
            k.remove();
            lege(teile[0], "kasten", y + vor);
            z.warte[j] = teile[1];
            return true;
          }
          if (quellen) {
            k.remove();
            return true;
          }
        }
        k.remove();
        if (j > 0 || plan.length || h < SATZ_H - 0.5) {
          j++;                              // nächste Spalte (dort ist vielleicht mehr Platz)
          continue;
        }
        // Höher als eine ganze Spalte: Kästen hier teilen und in der nächsten Spalte fortsetzen
        setze(sp, k, 0);
        const teile = k.matches(".kasten, .zeittafel") ? teileBlock(k, h) : null;
        k.remove();
        if (teile) {
          lege(teile[0], "kasten", 0);
          z.warte[0] = teile[1];
          return true;
        }
        warne(`höher als eine Spalte: «${beschreibe(k)}»`, f);
        lege(k, "gleit", 0);
        y = raster(hk + Z / 2);
        z.warte.shift();
      }
      return false;
    };
    // 1. Wartende oben in die Spalte
    if (wartende()) return ende("voll");
    // 2. Der Fluss
    for (;;) {
      const k = naechstes(z, f);
      if (!k) {                             // Text zu Ende: Wartende, soweit Platz, gleich hier
        wartende(true);
        return ende(z.warte.length ? "voll" : "ende");
      }
      if (z.vorab.includes(k)) {           // breites Bild, das schon oben auf der Seite steht
        weiter(z);
        continue;
      }
      const istRest = k === z.rest;
      let a = art(k);
      if (istRest) a = a === "text" ? "text" : "teilbar";
      if (a === "breit") {
        z.breit.push(k);
        weiter(z);
        continue;
      }
      if (a === "kasten") a = "gleit";
      if (a === "quellen") {
        z.warte.push(k);
        weiter(z);
        continue;
      }
      if (a === "gleit") {
        if (z.warte.length <= 2 && gleite(k)) {
          weiter(z);
          continue;
        }
        k.remove();
        z.warte.push(k);
        weiter(z);
        continue;
      }
      const dicht = k.matches(DICHT);
      if (!dicht) y = raster(y);
      let vor = 0;
      if (a === "titel" && plan.length) vor = eng ? Z / 2 : Z;
      else if ((a === "block" || a === "teilbar") && !dicht && plan.length) vor = luft;
      const yTop = y + vor;
      const hk = setze(sp, k, yTop);
      if (a === "titel") {
        const yNach = raster(yTop + hk);
        if (yNach + folgeBedarf(z, f) > h + 0.5 && plan.length) {
          k.remove();
          return ende("voll", k);
        }
        plan.push({ k, y: yTop, h: hk, art: a });
        y = yNach;
        weiter(z);
        continue;
      }
      if (yTop + hk <= h + 0.5) {
        plan.push({ k, y: yTop, h: hk, art: dicht ? "dicht" : a });
        y = dicht ? yTop + hk + 2 : a === "text" ? yTop + hk : raster(yTop + hk + luft);
        weiter(z);
        continue;
      }
      // Passt nicht ganz: umbrechen oder in die nächste Spalte
      const teile = a === "text" || a === "teilbar" ? teileBlock(k, h - yTop, k.matches(".lead") ? 4 : 2) : null;
      k.remove();
      if (teile) {
        lege(teile[0], a, yTop);
        rest(z, teile[1]);
        return ende("voll");
      }
      if (!plan.length && h >= SATZ_H - 0.5) {
        warne(`passt in keine Spalte: «${beschreibe(k)}»`, f);
        lege(k, a, yTop);
        weiter(z);
      }
      return ende("voll", k);
    }
  }

  // ---------------------------------------------------------------- Seite
  const obenMass = new WeakMap();
  function messeOben(k) {
    if (!obenMass.has(k)) {
      const satz = mess.querySelector(".satz");
      setze(satz, k, 0);
      // Schmale breite Bilder bekommen die Legende daneben statt darunter
      const bild = k.querySelector(".fig__rahmen img");
      const karte = k.querySelector(".karte__svg");
      if (karte && karte.getBoundingClientRect().height > 112 * MM) {
        karte.style.cssText = "height:112mm;width:auto;margin:0 auto";
      }
      if (bild && !k.matches(".karte")) {
        const frei = SATZ_B - bild.getBoundingClientRect().width;
        if (frei >= 52 * MM) k.classList.add("fig--seitlich");
        else if (frei > 4 * MM) k.querySelector("figcaption").style.maxWidth = `${SATZ_B - frei + 8 * MM}px`;
      }
      obenMass.set(k, hoehe(k));
      k.remove();
    }
    return obenMass.get(k);
  }
  function obenHoehe(liste) {
    return liste.reduce((s, k) => raster(s + messeOben(k) + Z), 0);
  }
  const passtOben = (liste) => liste.length === 1 || (liste.length <= 2 && obenHoehe(liste) <= OBEN_MAX * SATZ_H);

  function setzeSeite(f, z, oben, zeilen, ausgleich) {
    const s = neueSeite(f);
    let y = 0;
    for (const k of oben) {
      const hk = setze(s.satz, k, y);
      k.classList.add("oben");
      y = raster(y + hk + Z);
    }
    s.spaltenTop = y;
    const h = zeilen != null ? zeilen * Z : SATZ_H - y;
    for (let c = 0; c < f.spalten; c++) {
      const r = fuelleSpalte(neueSpalte(s, c, f.spalten, y, h), h, z, f, ausgleich);
      s.spalten.push(r);
      if (r.status === "ende") break;
    }
    s.spaltenH = h;
    return s;
  }

  function setzeFluss(f) {
    const z = zustand();
    let erste = true;
    let letzte = null;
    while (!fertig(z, f)) {
      const vorher = kopie(z);
      const kopf = erste && f.kopf ? [f.kopf] : [];
      const versuch = (extra) => {
        Object.assign(z, kopie(vorher));
        z.vorab.push(...extra);
        const oben = [...kopf];
        while (!kopf.length && z.breit.length && passtOben([...oben, z.breit[0]])) oben.push(z.breit.shift());
        oben.push(...extra);
        return { s: setzeSeite(f, z, oben, null, true), oben };
      };
      let extra = [];
      let { s, oben } = versuch(extra);
      // Breite Bilder, die erst auf dieser Seite erwähnt werden, möglichst noch oben auf diese Seite holen
      while (!kopf.length) {
        const neuB = z.breit.find((b) => !vorher.breit.includes(b) && !extra.includes(b));
        if (!neuB || !passtOben([...oben, neuB])) break;
        s.knoten.remove();
        extra = [...extra, neuB];
        ({ s, oben } = versuch(extra));
      }
      if (z.i === vorher.i && z.rest === vorher.rest && z.warte.length === vorher.warte.length
          && z.breit.length === vorher.breit.length && !oben.length) {
        throw new Error(`Kein Fortschritt in ${f.id} bei Element ${z.i}`);
      }
      Object.assign(s, { erste, start: vorher, oben, extra });
      seiten.push(s);
      letzte = s;
      erste = false;
    }
    if (!letzte || f.spalten < 2) return;
    seiten.pop();
    letzte.knoten.remove();
    gleicheLetzteSeiteAus(f, letzte, z);
    // Bleiben auf der letzten Seite nur ein paar Zeilen, die vorletzte enger setzen, damit alles auf sie passt
    const l = seiten.at(-1);
    const v = seiten.at(-2);
    const unten = Math.max(...l.spalten.map((r) => (r.plan.length ? r.plan.at(-1).y + r.plan.at(-1).h : 0)));
    if (v?.fluss !== f || l.oben.length || unten > 10 * Z) return;
    seiten.splice(-2, 2);
    l.knoten.remove();
    v.knoten.remove();
    eng = true;
    const probe = legeNeu(f, z, v, null, false);
    const ok = fertig(z, f);
    probe.knoten.remove();
    if (ok) gleicheLetzteSeiteAus(f, v, z);
    eng = false;
    if (!ok) {
      seiten.push(legeNeu(f, z, v, null, true));
      gleicheLetzteSeiteAus(f, l, z);
    }
  }

  // Eine schon gesetzte Seite vom selben Anfangszustand aus neu setzen
  function legeNeu(f, z, rec, zeilen, ausgleich) {
    Object.assign(z, kopie(rec.start));
    z.vorab.push(...rec.extra);
    const s = setzeSeite(f, z, rec.oben, zeilen, ausgleich);
    return Object.assign(s, { erste: rec.erste, start: rec.start, oben: rec.oben, extra: rec.extra });
  }

  // Letzte Seite eines Flusses: kleinste Spaltenhöhe suchen, bei der noch alles auf die Seite passt
  function gleicheLetzteSeiteAus(f, l, z) {
    const lege = (zeilen) => legeNeu(f, z, l, zeilen, false);
    let lo = 1;
    const voll = Math.round((SATZ_H - l.spaltenTop) / Z);
    let hi = voll;
    while (lo < hi) {
      const m = (lo + hi) >> 1;
      const s = lege(m);
      const ok = fertig(z, f);
      s.knoten.remove();
      if (ok) hi = m;
      else lo = m + 1;
    }
    // Von den passenden Höhen die schönste: Spalten möglichst gleich lang, die linke nicht kürzer als die rechte
    let beste = lo;
    let bestWert = Infinity;
    for (let zeilen = lo; zeilen <= Math.min(voll, lo + 14); zeilen++) {
      const s = lege(zeilen);
      const ok = fertig(z, f);
      const enden = s.spalten.map((r) => (r.plan.length ? r.plan.at(-1).y + r.plan.at(-1).h : 0));
      while (enden.length < f.spalten) enden.push(0);
      s.knoten.remove();
      if (!ok) continue;
      const teilungen = s.knoten.querySelectorAll(".kasten.teil-b, .zeittafel.teil-b").length;
      const wert = Math.max(...enden) + 2 * Math.max(0, enden.at(-1) - enden[0]) + (Math.max(...enden) - Math.min(...enden))
        + 6 * Z * teilungen;
      if (wert < bestWert - 0.5) [beste, bestWert] = [zeilen, wert];
    }
    lo = beste;
    const s = lege(lo);
    const unten = s.spaltenTop + lo * Z + Z;
    if (/^k-/.test(f.id) && unten + 9 * MM <= SATZ_H) {
      const v = neu("div", "schluss");
      v.style.top = `${unten}px`;
      s.satz.append(v);
    }
    seiten.push(s);
  }

  function setzeFest(q) {
    const s = neueSeite(null);
    s.knoten.classList.add("seite--fest");
    s.satz.append(q);
    s.fest = true;
    seiten.push(s);
  }

  // ------------------------------------------------------------ Schmuck
  function jahrText(j) {
    if (j >= daten.heute) return "heute";
    return j < 0 ? `${-j} v. Chr.` : String(j);
  }
  const SVG = "http://www.w3.org/2000/svg";
  function svg(tag, attr, text) {
    const e = document.createElementNS(SVG, tag);
    for (const [k, v] of Object.entries(attr)) e.setAttribute(k, v);
    if (text != null) e.textContent = text;
    return e;
  }

  // Zahlenstrahl am Aussenrand der rechten Seite: neun gleich lange Abschnitte, einer pro Teil des Buches,
  // jeder in der Farbe des Teils; die Marke zeigt die Jahre des Kapitels (Zeitleiste: die Jahre auf der Seite).
  function zahlenstrahl(s) {
    const f = s.fluss;
    let { von, bis } = f;
    if (f.strahl === "seite") {
      const jahre = [...s.knoten.querySelectorAll("[data-jahr]")].map((e) => parseInt(e.dataset.jahr, 10))
        .filter(Number.isFinite);
      if (jahre.length) [von, bis] = [Math.min(...jahre), Math.max(...jahre)];
    }
    const G = [...daten.grenzen, daten.heute];
    const B = 23;                          // Breite in mm: vom Satzspiegel bis an den Rand des Beschnitts
    const H = SATZ_H / MM;
    const seg = H / (G.length - 1);
    const X = 12;                          // Balken 8 mm vor der Schnittkante
    const W = 2.2;
    const yj = (j) => {
      j = Math.max(G[0], Math.min(G.at(-1), j));
      for (let i = 0; i < G.length - 1; i++) if (j <= G[i + 1]) return (i + (j - G[i]) / (G[i + 1] - G[i])) * seg;
      return H;
    };
    const e = svg("svg", { class: "strahl", viewBox: `0 0 ${B} ${H}`, width: `${B}mm`, height: `${H}mm` });
    for (let i = 0; i < G.length - 1; i++) {
      const t = daten.teile[i + 1];
      const aktiv = f.teil === i + 1;
      e.append(svg("rect", { x: X, y: i * seg + 0.35, width: W, height: seg - 0.7, fill: t.farbe,
        "fill-opacity": aktiv ? 0.5 : 0.22 }));
      const my = (i + 0.5) * seg;
      e.append(svg("text", { x: X + W / 2, y: my, class: "strahl__teil", fill: t.farbe,
        transform: `rotate(-90 ${X + W / 2} ${my})` }, t.rom));
    }
    // Marke und Beschriftung
    const marken = [];
    if (von != null && Number.isFinite(von)) {
      let y0 = yj(von), y1 = yj(bis);
      if (y1 - y0 < 2.6) [y0, y1] = [(y0 + y1) / 2 - 1.3, (y0 + y1) / 2 + 1.3];
      const farbe = f.teil ? daten.teile[f.teil].farbe : "#8a6d45";
      e.append(svg("rect", { x: X - 0.5, y: y0, width: B - X + 1, height: y1 - y0, rx: 0.7, fill: farbe }));
      const text = (y, t, klasse) => {
        e.append(svg("text", { x: X - 1.6, y, class: `strahl__marke ${klasse}`, fill: farbe }, t));
        marken.push(y);
      };
      if (von === bis) text((y0 + y1) / 2, jahrText(von), "mitte");
      else if (y1 - y0 >= 5.5) {
        text(y0, jahrText(von), "oben");
        text(y1, jahrText(bis), "unten");
      } else {
        text((y0 + y1) / 2 - 1.3, jahrText(von), "unten");
        text((y0 + y1) / 2 + 1.3, jahrText(bis), "oben");
      }
    }
    G.forEach((g, i) => {
      const y = i * seg;
      e.append(svg("line", { x1: X - 1, x2: X, y1: y, y2: y, class: "strahl__strich" }));
      if (marken.some((m) => Math.abs(m - y) < 3.4)) return;
      const klasse = i === 0 ? "oben" : i === G.length - 1 ? "unten" : "mitte";
      e.append(svg("text", { x: X - 1.6, y, class: `strahl__jahr ${klasse}` }, jahrText(g)));
    });
    return e;
  }

  function male(s, id, lage) {
    const d = neu("div", `seite__aq seite__aq--${lage}`);
    d.style.backgroundImage = `url("aq/${id}.jpg")`;
    s.knoten.prepend(d);
    (aqSeiten[id] ||= []).push(s.nr);
  }
  function naechstesAq(f) {
    const n = aqZaehler.get(f) || 0;
    aqZaehler.set(f, n + 1);
    return f.aq[n % f.aq.length];
  }

  function schmuecke(ab) {
    for (let n = ab; n < seiten.length; n++) {
      const s = seiten[n];
      s.nr = n + 1;
      const rechts = s.nr % 2 === 1;
      s.knoten.dataset.nr = s.nr;
      s.knoten.classList.add(rechts ? "seite--rechts" : "seite--links");
      if (s.fest) continue;
      if (!s.erste) s.knoten.append(neu("div", "kolumne", rechts ? s.fluss.rechts : s.fluss.links));
      s.knoten.append(neu("div", "seite__zahl", String(s.nr)));
      if (rechts) s.knoten.append(zahlenstrahl(s));
    }
    // Ein Aquarell pro Doppelseite, wenn beide Seiten zum selben Kapitel gehören, sonst eines pro Seite
    for (let n = ab; n < seiten.length; n++) {
      const s = seiten[n];
      if (s.fest || s.aq || !s.fluss.aq.length) continue;
      const partner = s.nr % 2 === 0 ? seiten[n + 1] : null;
      const id = naechstesAq(s.fluss);
      if (partner && !partner.fest && partner.fluss === s.fluss) {
        male(s, id, "links");
        male(partner, id, "rechts");
        partner.aq = true;
      } else male(s, id, "einzeln");
      s.aq = true;
    }
  }

  function bereiche(zahlen) {
    const z = [...new Set(zahlen)].sort((a, b) => a - b);
    const teile = [];
    for (let i = 0; i < z.length; i++) {
      let j = i;
      while (j + 1 < z.length && z[j + 1] === z[j] + 1) j++;
      teile.push(j > i ? `${z[i]}–${z[j]}` : `${z[i]}`);
      i = j;
    }
    return teile.join(", ");
  }

  // Bildnachweis: Seitenzahlen der Bilder; von den Aquarellen nur die, die wirklich im Hintergrund stehen
  function fuelleNachweis(f) {
    const titelseite = seiten.find((s) => s.knoten.querySelector(".d-titel"));
    f.items = f.items.filter((e) => {
      const ziel = e.querySelector?.(".nw__seite");
      if (!ziel) return true;
      let nummern;
      if (e.dataset.aq) {
        nummern = [...(aqSeiten[e.dataset.aq] || [])];
        if (e.dataset.aq === daten.titelbild && titelseite) nummern.unshift(titelseite.nr);
        if (!nummern.length) return false;
      } else {
        const s = document.getElementById(`bild-${ziel.dataset.bild}`)?.closest(".seite");
        nummern = s ? [+s.dataset.nr] : [];
      }
      ziel.textContent = nummern.length ? `S. ${bereiche(nummern)} ` : "";
      return true;
    });
    // Überschriften ohne Einträge (falls alle Aquarelle fehlen) entfernen
    f.items = f.items.filter((e, i) => !e.matches(".nw-titel") || f.items[i + 1]?.matches(".nw"));
  }

  // Verweise auf Kapitel, die schon gesetzt sind (Zeitleiste): Seitenzahl anfügen
  function verweise(f) {
    for (const k of f.items) {
      for (const e of k.querySelectorAll?.("[data-ziel]") || []) {
        if (e.matches(".d-toc__seite")) continue;
        const n = seiten.findIndex((s) => s.fluss?.id === e.dataset.ziel);
        if (n >= 0) e.textContent += `, S. ${n + 1}`;
      }
    }
  }

  // -------------------------------------------------------------- Ablauf
  window.satz = async function satz() {
    const beginn = performance.now();
    buch = document.getElementById("buch");
    const vorrat = document.getElementById("vorrat");
    // Den Vorrat einmal unsichtbar setzen, damit Chrome alle benötigten Schriftschnitte lädt
    vorrat.classList.add("vorrat--laden");
    void vorrat.offsetHeight;
    await document.fonts.ready;
    vorrat.classList.remove("vorrat--laden");

    mess = neueSeite(null).knoten;
    mess.classList.add("seite--mess");
    document.body.append(mess);

    let nachweis = null;
    for (const q of [...vorrat.children]) {
      if (q.matches(".q-titelei")) [...q.children].forEach(setzeFest);
      else if (q.matches(".q-fluss")) {
        const f = lies(q);
        if (f.id === "bildnachweis") nachweis = f;
        else {
          verweise(f);
          setzeFluss(f);
        }
      }
    }
    schmuecke(0);
    if (nachweis) {
      const ab = seiten.length;
      fuelleNachweis(nachweis);
      setzeFluss(nachweis);
      schmuecke(ab);
    }
    // Gebunden wird in Bogen: am Schluss leere Seiten anfügen, bis die Seitenzahl durch vier teilbar ist
    const leer = seiten.length;
    while (seiten.length % 4) setzeFest(neu("div", "d-leer"));
    schmuecke(leer);
    const ziele = {};
    for (const s of seiten) if (s.fluss && s.erste && !(s.fluss.id in ziele)) ziele[s.fluss.id] = s.nr;
    for (const e of document.querySelectorAll(".d-toc__seite[data-ziel]")) e.textContent = ziele[e.dataset.ziel] ?? "?";
    mess.remove();
    window.satzSeiten = seiten;

    // Bericht: Spalten, die weiter oben als drei Zeilen vor dem Fuss enden (ohne letzte Seiten der Flüsse)
    const luecken = [];
    seiten.forEach((s, n) => {
      if (s.fest || seiten[n + 1]?.fluss !== s.fluss) return;
      s.spalten.forEach((r, c) => {
        const l = r.plan.at(-1);
        const frei = l ? (s.spaltenH - l.y - l.h) / Z : s.spaltenH / Z;
        if (frei >= 3) luecken.push({ seite: s.nr, spalte: c + 1, zeilen: Math.floor(frei) });
      });
    });
    return { seiten: seiten.length, ziele, warnungen, luecken, sekunden: Math.round((performance.now() - beginn) / 1000) };
  };
})();

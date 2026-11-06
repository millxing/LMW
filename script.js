(() => {
  const body = document.body;
  const mqMobileNav = window.matchMedia("(max-width: 1023px)");

  /* ---------- Header shadow on scroll ---------- */
  const header = document.querySelector("[data-header]");
  const syncHeader = () => header && header.classList.toggle("is-scrolled", window.scrollY > 8);
  syncHeader();
  window.addEventListener("scroll", syncHeader, { passive: true });

  /* ---------- Mobile navigation ---------- */
  const navToggle = document.querySelector("[data-nav-toggle]");
  const nav = document.querySelector("[data-nav]");
  if (navToggle && nav) {
    const outside = () => document.querySelectorAll("main, footer, .skip-link, dialog");
    const setOpen = (open, { focusToggle = false } = {}) => {
      body.classList.toggle("nav-open", open);
      outside().forEach((el) => { el.inert = open; });
      const scrim = document.querySelector("[data-nav-scrim]");
      if (scrim) scrim.hidden = !open;
      navToggle.setAttribute("aria-expanded", String(open));
      navToggle.querySelector(".nav-toggle-label").textContent = open ? "Close" : "Menu";
      if (open) {
        const first = nav.querySelector("a");
        if (first) first.focus();
      } else if (focusToggle) {
        navToggle.focus();
      }
    };
    navToggle.addEventListener("click", () => setOpen(!body.classList.contains("nav-open")));
    const scrimEl = document.querySelector("[data-nav-scrim]");
    if (scrimEl) scrimEl.addEventListener("click", () => setOpen(false, { focusToggle: true }));
    nav.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => setOpen(false)));
    document.addEventListener("click", (event) => {
      if (body.classList.contains("nav-open") && !nav.contains(event.target) && !navToggle.contains(event.target)) setOpen(false);
    });
    document.addEventListener("keydown", (event) => {
      if (!body.classList.contains("nav-open")) return;
      if (event.key === "Escape") setOpen(false, { focusToggle: true });
      if (event.key === "Tab" && mqMobileNav.matches) {
        // keep focus inside the open menu (toggle + links)
        const focusables = [navToggle, ...nav.querySelectorAll("a")];
        const index = focusables.indexOf(document.activeElement);
        if (event.shiftKey && index === 0) { event.preventDefault(); focusables[focusables.length - 1].focus(); }
        else if (!event.shiftKey && index === focusables.length - 1) { event.preventDefault(); focusables[0].focus(); }
      }
    });
    mqMobileNav.addEventListener("change", () => setOpen(false));
  }

  /* ---------- Home: link explore list with tree signs ---------- */
  document.querySelectorAll("[data-explore]").forEach((item) => {
    const sign = document.querySelector(`.tree-link-${item.dataset.explore}`);
    if (!sign) return;
    const on = () => sign.classList.add("is-linked");
    const off = () => sign.classList.remove("is-linked");
    item.addEventListener("mouseenter", on);
    item.addEventListener("mouseleave", off);
    item.addEventListener("focus", on);
    item.addEventListener("blur", off);
    sign.addEventListener("mouseenter", () => item.classList.add("is-linked"));
    sign.addEventListener("mouseleave", () => item.classList.remove("is-linked"));
  });

  /* ---------- Lightbox ---------- */
  const lightbox = document.querySelector("[data-lightbox]");
  const triggers = Array.from(document.querySelectorAll("[data-lightbox-item]"));
  if (lightbox && triggers.length) {
    const img = lightbox.querySelector("[data-lightbox-img]");
    const caption = lightbox.querySelector("[data-lightbox-caption]");
    const count = lightbox.querySelector("[data-lightbox-count]");
    let group = [];
    let index = 0;
    let opener = null;

    const show = (i) => {
      index = (i + group.length) % group.length;
      const t = group[index];
      img.src = t.dataset.src;
      img.alt = t.dataset.alt || "";
      caption.textContent = "";
      if (t.dataset.caption) {
        const line = document.createElement("span");
        line.className = "lightbox-caption-text";
        line.textContent = t.dataset.caption;
        caption.append(line);
      }
      if (t.dataset.credit) {
        const credit = document.createElement("span");
        credit.className = "lightbox-credit";
        credit.textContent = "Source: ";
        if (t.dataset.creditUrl) {
          const a = document.createElement("a");
          a.href = t.dataset.creditUrl;
          a.target = "_blank";
          a.rel = "noopener";
          a.textContent = t.dataset.credit;
          const hint = document.createElement("span");
          hint.className = "visually-hidden";
          hint.textContent = " (opens in a new tab)";
          a.append(hint);
          credit.append(a);
        } else {
          credit.append(t.dataset.credit);
        }
        caption.append(credit);
      }
      count.textContent = group.length > 1 ? `Photo ${index + 1} of ${group.length}` : "";
    };

    const close = () => {
      if (lightbox.open) lightbox.close();
    };

    triggers.forEach((t) => {
      t.addEventListener("click", () => {
        opener = t;
        group = triggers.filter((x) => x.dataset.group === t.dataset.group);
        lightbox.toggleAttribute("data-single", group.length < 2);
        show(group.indexOf(t));
        lightbox.showModal();
        body.classList.add("lightbox-open");
      });
    });

    lightbox.querySelector("[data-lightbox-close]").addEventListener("click", close);
    lightbox.querySelector("[data-lightbox-prev]").addEventListener("click", () => show(index - 1));
    lightbox.querySelector("[data-lightbox-next]").addEventListener("click", () => show(index + 1));
    lightbox.addEventListener("click", (event) => {
      if (event.target === lightbox || event.target.classList.contains("lightbox-figure")) close();
    });
    lightbox.addEventListener("keydown", (event) => {
      if (group.length < 2) return;
      if (event.key === "ArrowRight") { event.preventDefault(); show(index + 1); }
      if (event.key === "ArrowLeft") { event.preventDefault(); show(index - 1); }
    });
    let touchX = null;
    lightbox.addEventListener("touchstart", (e) => { touchX = e.touches[0].clientX; }, { passive: true });
    lightbox.addEventListener("touchend", (e) => {
      if (touchX === null || group.length < 2) return;
      const dx = e.changedTouches[0].clientX - touchX;
      if (Math.abs(dx) > 50) show(index + (dx < 0 ? 1 : -1));
      touchX = null;
    });
    lightbox.addEventListener("close", () => {
      body.classList.remove("lightbox-open");
      img.removeAttribute("src");
      if (opener) opener.focus();
    });
  }

  /* ---------- YouTube: load the player only when asked ---------- */
  document.querySelectorAll("[data-youtube]").forEach((box) => {
    const btn = box.querySelector(".video-facade");
    if (!btn) return;
    btn.addEventListener("click", () => {
      const frame = document.createElement("iframe");
      frame.src = `https://www.youtube-nocookie.com/embed/${box.dataset.youtube}?autoplay=1`;
      frame.title = box.dataset.title || "Video";
      frame.allow = "accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share";
      frame.referrerPolicy = "strict-origin-when-cross-origin";
      frame.allowFullscreen = true;
      box.replaceChildren(frame);
      frame.focus();
    });
  });

  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- Gallery: photo pile / grid toggle and pile counter ---------- */
  document.querySelectorAll("[data-gallery-view]").forEach((view) => {
    const buttons = view.querySelectorAll(".view-btn");
    const setView = (mode, remember) => {
      view.dataset.view = mode;
      buttons.forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.viewBtn === mode)));
      if (remember) { try { localStorage.setItem("lm-gallery-view", mode); } catch { /* storage unavailable */ } }
    };
    try { const saved = localStorage.getItem("lm-gallery-view"); if (saved === "grid" || saved === "pile") setView(saved, false); } catch { /* ignore */ }
    view.querySelectorAll("[data-view-btn]").forEach((b) => b.addEventListener("click", () => {
      setView(b.dataset.viewBtn, true);
      view.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
    }));

    const photos = Array.from(view.querySelectorAll("[data-photo]"));
    const counter = view.querySelector("[data-pile-counter]");
    const current = view.querySelector("[data-pile-current]");
    if (!counter || !photos.length) return;
    let ticking = false;
    const update = () => {
      ticking = false;
      if (view.dataset.view !== "pile") return;
      const box = view.getBoundingClientRect();
      const inView = box.top < innerHeight * 0.6 && box.bottom > innerHeight * 0.4;
      counter.classList.toggle("is-visible", inView);
      if (!inView) return;
      const stickTop = parseFloat(getComputedStyle(photos[0]).top) || 0;
      let n = 1;
      photos.forEach((ph, i) => { if (ph.getBoundingClientRect().top <= stickTop + 40) n = i + 1; });
      current.textContent = String(n).padStart(2, "0");
    };
    window.addEventListener("scroll", () => { if (!ticking) { ticking = true; requestAnimationFrame(update); } }, { passive: true });
    update();
    photos.forEach((ph, i) => ph.addEventListener("focusin", () => {
      if (view.dataset.view === "pile") current.textContent = String(i + 1).padStart(2, "0");
    }));
  });

  /* ---------- Home: count up the facts when they come into view ---------- */
  const counters = document.querySelectorAll("[data-count]");
  if (counters.length && !reduceMotion && "IntersectionObserver" in window) {
    const run = (el) => {
      const target = parseFloat(el.dataset.count);
      const decimals = (el.dataset.count.split(".")[1] || "").length;
      const suffix = el.dataset.suffix || "";
      const from = target > 1000 ? target - 160 : 0;
      const start = performance.now();
      const step = (now) => {
        const t = Math.min(1, (now - start) / 1400);
        const eased = 1 - Math.pow(1 - t, 3);
        el.textContent = (from + (target - from) * eased).toFixed(decimals) + suffix;
        if (t < 1) requestAnimationFrame(step);
      };
      requestAnimationFrame(step);
    };
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) { run(e.target); io.unobserve(e.target); }
    }), { threshold: 0.6 });
    counters.forEach((el) => io.observe(el));
  }

  /* ---------- Copy buttons ---------- */
  document.querySelectorAll("[data-copy]").forEach((btn) => {
    const label = btn.querySelector("[data-copy-label]");
    const original = label ? label.textContent : "";
    btn.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(btn.dataset.copy);
        if (label) label.textContent = "Copied";
      } catch {
        if (label) label.textContent = "Press Ctrl/Cmd+C";
        const range = document.createRange();
        const target = btn.previousElementSibling;
        if (target) { range.selectNodeContents(target); const s = getSelection(); s.removeAllRanges(); s.addRange(range); }
      }
      window.setTimeout(() => { if (label) label.textContent = original; }, 2400);
    });
  });

  /* ---------- Contact form: validate, then hand off to the visitor's email app ---------- */
  const form = document.querySelector("[data-contact-form]");
  if (form) {
    const status = form.querySelector("[data-form-status]");
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
    const rules = {
      name: (v) => (v.trim() ? "" : "Please enter your name."),
      email: (v) => (!v.trim() ? "Please enter your email address." : emailPattern.test(v.trim()) ? "" : "Please enter a valid email address, like name@example.com."),
      message: (v) => (v.trim().length >= 5 ? "" : "Please write a short message."),
    };
    const check = (field) => {
      const msg = rules[field.name](field.value);
      const err = form.querySelector(`[data-error-for="${field.name}"]`);
      err.textContent = msg;
      field.setAttribute("aria-invalid", msg ? "true" : "false");
      return !msg;
    };
    Object.keys(rules).forEach((name) => {
      const field = form.elements[name];
      field.addEventListener("blur", () => { if (field.value) check(field); });
      field.addEventListener("input", () => { if (field.getAttribute("aria-invalid") === "true") check(field); });
    });
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      const fields = Object.keys(rules).map((n) => form.elements[n]);
      const invalid = fields.filter((f) => !check(f));
      if (invalid.length) {
        status.hidden = false;
        status.dataset.state = "error";
        status.textContent = `Please fix ${invalid.length === 1 ? "1 field" : `${invalid.length} fields`} before continuing.`;
        invalid[0].focus();
        return;
      }
      const { name, email, message } = Object.fromEntries(fields.map((f) => [f.name, f.value.trim()]));
      const to = form.dataset.email;
      const subject = encodeURIComponent(`${form.dataset.subject} from ${name}`);
      const bodyText = encodeURIComponent(`${message}\n\n${name}\n${email}`);
      status.hidden = false;
      status.dataset.state = "info";
      status.innerHTML = "";
      const p1 = document.createElement("p");
      p1.innerHTML = "<strong>Almost done.</strong> Your email app should open with your message filled in. Your message is not sent until you press send there.";
      const p2 = document.createElement("p");
      p2.textContent = `If nothing opened, email ${to} directly — your message is still in the form above.`;
      status.append(p1, p2);
      status.setAttribute("tabindex", "-1");
      status.focus({ preventScroll: true });
      status.scrollIntoView({ block: "center", behavior: "smooth" });
      window.location.href = `mailto:${to}?subject=${subject}&body=${bodyText}`;
    });
  }

  /* ---------- Links to a post on the old single news page now go to that post's own page ---------- */
  const moved = location.hash && document.getElementById(decodeURIComponent(location.hash.slice(1)));
  if (moved && moved.dataset.postHref) {
    location.replace(moved.dataset.postHref);
    return;
  }
  window.addEventListener("hashchange", () => {
    const el = document.getElementById(decodeURIComponent(location.hash.slice(1)));
    if (el && el.dataset.postHref) location.assign(el.dataset.postHref);
  });

  /* ---------- Keep in-page anchors on target after images and fonts settle ---------- */
  const realign = () => {
    const id = decodeURIComponent(location.hash.slice(1));
    const target = id && document.getElementById(id);
    if (target) target.scrollIntoView({ block: "start" });
  };
  if (location.hash) {
    window.addEventListener("load", realign);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(realign);
  }

  /* ---------- Table of contents: collapse on small screens, highlight current section ---------- */
  const tocs = document.querySelectorAll("[data-toc]");
  const syncToc = () => tocs.forEach((t) => { t.open = !mqMobileNav.matches; });
  syncToc();
  mqMobileNav.addEventListener("change", syncToc);
  tocs.forEach((t) => t.querySelectorAll("a").forEach((a) => a.addEventListener("click", () => { if (mqMobileNav.matches) t.open = false; })));

  const tocLinks = Array.from(document.querySelectorAll("[data-toc-link]"));
  if (tocLinks.length) {
    // Near the top of the page, always show the start of the index.
    const resetToc = () => {
      if (window.scrollY > 200) return;
      tocLinks.forEach((a, i) => a.classList.toggle("is-active", i === 0));
      const box = tocLinks[0].closest(".sidebar");
      if (box) box.scrollTop = 0;
    };
    window.addEventListener("scroll", resetToc, { passive: true });
  }
  if (tocLinks.length && "IntersectionObserver" in window) {
    const byId = new Map(tocLinks.map((a) => [a.getAttribute("href").slice(1), a]));
    const visible = new Set();
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((e) => (e.isIntersecting ? visible.add(e.target.id) : visible.delete(e.target.id)));
      const firstVisible = tocLinks.find((a) => visible.has(a.getAttribute("href").slice(1)));
      if (!firstVisible) return;
      if (window.scrollY < 200) { const box = firstVisible.closest(".sidebar"); if (box) box.scrollTop = 0; }
      tocLinks.forEach((a) => a.classList.toggle("is-active", a === firstVisible));
      if (!mqMobileNav.matches) {
        const box = firstVisible.closest(".sidebar");
        if (box && box.scrollHeight > box.clientHeight) {
          const linkRect = firstVisible.getBoundingClientRect();
          const boxRect = box.getBoundingClientRect();
          if (linkRect.top < boxRect.top || linkRect.bottom > boxRect.bottom) {
            box.scrollTop += linkRect.top - boxRect.top - box.clientHeight / 2;
          }
        }
      }
    }, { rootMargin: "-20% 0px -70% 0px" });
    byId.forEach((_, id) => { const el = document.getElementById(id); if (el) observer.observe(el); });
  }
})();

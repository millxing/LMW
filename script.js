const header = document.querySelector(".site-header");
const navToggle = document.querySelector("[data-nav-toggle]");
const nav = document.querySelector("[data-nav]");
const isHomePage = document.body.classList.contains("page-home");
const chooseBranchSection = document.getElementById("choose-a-branch");
const pageShell = document.querySelector(".page-shell");
const siteFooter = document.querySelector(".site-footer");
const galleryShell = document.querySelector("[data-gallery-shell]");
const gallerySlides = Array.from(document.querySelectorAll("[data-gallery-slide]"));
const galleryStatus = document.querySelector("[data-gallery-status]");
const galleryStatusText = document.querySelector("[data-gallery-status-text]");
const eventCountdown = document.querySelector("[data-event-countdown]");
const eventInfoButton = document.querySelector("[data-event-info]");
const eventOverlay = document.querySelector("[data-event-overlay]");
const eventCloseButtons = Array.from(document.querySelectorAll("[data-event-close]"));
const documentOverlay = document.querySelector("[data-document-overlay]");
const documentOverlayImage = document.querySelector("[data-document-overlay-image]");
const documentOpenButtons = Array.from(document.querySelectorAll("[data-document-open]"));
const documentCloseButton = document.querySelector("[data-document-close]");

const syncFooterHeightVar = () => {
  if (!pageShell || !siteFooter) {
    return;
  }
  pageShell.style.setProperty("--home-footer-height", `${siteFooter.offsetHeight}px`);
};

if (isHomePage) {
  syncFooterHeightVar();
  window.addEventListener("resize", syncFooterHeightVar);
  window.addEventListener("load", syncFooterHeightVar);
}

if (eventCountdown) {
  const eventDate = new Date(eventCountdown.dataset.eventDatetime);
  const formatCountdown = () => {
    const remainingMs = eventDate.getTime() - Date.now();
    if (!Number.isFinite(remainingMs)) {
      eventCountdown.textContent = "";
      return;
    }
    if (remainingMs <= 0) {
      eventCountdown.textContent = "Event time has arrived";
      return;
    }
    const totalSeconds = Math.floor(remainingMs / 1000);
    const days = Math.floor(totalSeconds / 86400);
    const hours = Math.floor((totalSeconds % 86400) / 3600);
    const minutes = Math.floor((totalSeconds % 3600) / 60);
    const seconds = totalSeconds % 60;
    eventCountdown.textContent = `${days} days, ${hours} hours, ${minutes} minutes, ${seconds} seconds`;
  };

  formatCountdown();
  window.setInterval(formatCountdown, 1000);
}

if (eventInfoButton && eventOverlay) {
  const openEventOverlay = () => {
    eventOverlay.hidden = false;
    document.body.classList.add("event-overlay-open");
  };
  const closeEventOverlay = () => {
    eventOverlay.hidden = true;
    document.body.classList.remove("event-overlay-open");
    eventInfoButton.focus();
  };

  eventInfoButton.addEventListener("click", openEventOverlay);
  eventCloseButtons.forEach((button) => button.addEventListener("click", closeEventOverlay));
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !eventOverlay.hidden) {
      closeEventOverlay();
    }
  });
}

if (documentOverlay && documentOverlayImage && documentOpenButtons.length) {
  let lastDocumentButton = null;

  const closeDocumentOverlay = () => {
    if (documentOverlay.open && typeof documentOverlay.close === "function") {
      documentOverlay.close();
    } else {
      documentOverlay.removeAttribute("open");
    }
    documentOverlayImage.removeAttribute("src");
    documentOverlayImage.alt = "";
    if (lastDocumentButton) {
      lastDocumentButton.focus();
    }
  };

  documentOpenButtons.forEach((button) => {
    button.addEventListener("click", () => {
      lastDocumentButton = button;
      documentOverlayImage.src = button.dataset.documentSrc;
      documentOverlayImage.alt = button.dataset.documentAlt || "";
      if (typeof documentOverlay.showModal === "function") {
        documentOverlay.showModal();
      } else {
        documentOverlay.setAttribute("open", "");
      }
    });
  });

  if (documentCloseButton) {
    documentCloseButton.addEventListener("click", closeDocumentOverlay);
  }

  documentOverlay.addEventListener("click", (event) => {
    if (event.target === documentOverlay) {
      closeDocumentOverlay();
    }
  });

  documentOverlay.addEventListener("close", () => {
    documentOverlayImage.removeAttribute("src");
    documentOverlayImage.alt = "";
  });
}
const animatedNodes = document.querySelectorAll(
  [
    "section:not(.gallery-shell)",
    ".news-card",
    ".news-entry",
    ".collection-card",
    ".collection-overview-card",
    ".inventory-group-card",
    ".info-card",
    ".support-card",
    ".update-item",
    ".resource-link",
    ".surface-panel",
    ".surface-media",
  ].join(",")
);

const syncHeader = () => {
  if (!header) {
    return;
  }
  header.classList.toggle("is-scrolled", window.scrollY > 24);
};

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);
const lerp = (start, end, amount) => start + (end - start) * amount;

const easeInOutCubic = (value) => {
  const t = clamp(value, 0, 1);
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
};

const hashUnit = (index, seed) => {
  const value = Math.sin(index * 127.1 + seed * 311.7) * 43758.5453123;
  return value - Math.floor(value);
};

if (galleryShell && gallerySlides.length && galleryStatus && galleryStatusText) {
  galleryStatus.hidden = true;
  let expandedSlide = null;

  const collapseExpandedSlide = () => {
    if (!expandedSlide) {
      return;
    }
    expandedSlide.classList.remove("is-expanded");
    document.body.classList.remove("gallery-expanded");
    expandedSlide = null;
  };

  gallerySlides.forEach((slide, index) => {
    const width = 78 + hashUnit(index, 1) * 18;
    const shift = (hashUnit(index, 2) - 0.5) * 16;
    const rotateMagnitude = 2 + hashUnit(index, 3) * 4;
    const rotate = (index % 2 === 0 ? -1 : 1) * rotateMagnitude;
    const scale = 0.94 + hashUnit(index, 4) * 0.1;
    slide.style.setProperty("--pile-width", `${width}%`);
    slide.style.setProperty("--pile-shift", `${shift.toFixed(2)}`);
    slide.style.setProperty("--pile-rotate", `${rotate.toFixed(2)}`);
    slide.style.setProperty("--pile-scale", scale.toFixed(3));
    slide.style.zIndex = String(index + 1);
    slide.querySelectorAll("a").forEach((link) => {
      link.addEventListener("click", (event) => event.stopPropagation());
    });
    slide.addEventListener("click", () => {
      const clickedExpandedSlide = expandedSlide === slide;
      collapseExpandedSlide();
      if (clickedExpandedSlide) {
        return;
      }
      expandedSlide = slide;
      slide.classList.add("is-expanded");
      document.body.classList.add("gallery-expanded");
    });
  });

  window.addEventListener("scroll", collapseExpandedSlide, { passive: true });
  window.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      collapseExpandedSlide();
    }
  });
}

const closeNav = () => {
  document.body.classList.remove("nav-open");
  if (navToggle) {
    navToggle.setAttribute("aria-expanded", "false");
  }
};

syncHeader();
window.addEventListener("scroll", syncHeader, { passive: true });

if (
  isHomePage &&
  chooseBranchSection &&
  window.matchMedia("(pointer: fine)").matches &&
  !window.matchMedia("(prefers-reduced-motion: reduce)").matches
) {
  let snapLock = false;

  const getBranchTop = () => chooseBranchSection.offsetTop;

  const snapTo = (top) => {
    snapLock = true;
    window.scrollTo({ top, behavior: "smooth" });
    window.setTimeout(() => {
      snapLock = false;
    }, 700);
  };

  window.addEventListener(
    "wheel",
    (event) => {
      if (snapLock || document.body.classList.contains("nav-open")) {
        return;
      }

      const branchTop = getBranchTop();
      const currentY = window.scrollY;
      const fromHero = currentY < branchTop - 40;
      const aroundBranch = currentY >= branchTop - 40 && currentY < branchTop + 40;

      if (event.deltaY > 12 && fromHero) {
        event.preventDefault();
        snapTo(branchTop);
        return;
      }

      if (event.deltaY < -12 && aroundBranch) {
        event.preventDefault();
        snapTo(0);
      }
    },
    { passive: false }
  );
}

if (navToggle && nav) {
  navToggle.addEventListener("click", () => {
    const isOpen = document.body.classList.toggle("nav-open");
    navToggle.setAttribute("aria-expanded", String(isOpen));
  });

  nav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", closeNav);
  });

  window.addEventListener("resize", () => {
    if (window.innerWidth > 820) {
      closeNav();
    }
  });
}

if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
  document.body.classList.add("motion-ready");
  animatedNodes.forEach((node) => node.classList.add("animate-in", "is-visible"));
} else {
  document.body.classList.add("motion-ready");
  animatedNodes.forEach((node) => node.classList.add("animate-in"));

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) {
          return;
        }
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    },
    {
      threshold: 0.12,
      rootMargin: "0px 0px -8% 0px",
    }
  );

  animatedNodes.forEach((node) => observer.observe(node));
}

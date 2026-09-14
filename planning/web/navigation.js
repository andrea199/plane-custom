// Additive entry for existing compiled Plane builds. No task data is inspected.
(() => {
  let scheduled = false;
  function attach() {
    scheduled = false;
    const sidebar = document.getElementById('main-sidebar');
    if (!sidebar) return;
    const people = sidebar.querySelector('a[href$="/people/"]');
    if (!people) return;
    const url = new URL(people.href, location.origin);
    const slug = url.pathname.split('/').filter(Boolean)[0];
    if (!slug || url.origin !== location.origin) return;
    const href = '/' + encodeURIComponent(slug) + '/planning/';
    let link = sidebar.querySelector('[data-oniro-planning]');
    if (link) { if (link.getAttribute('href') !== href) link.setAttribute('href', href); return; }
    link = document.createElement('a');
    link.setAttribute('data-oniro-planning', '');
    link.href = href;
    link.className = people.className;
    link.textContent = 'Pianificazione';
    link.setAttribute('aria-label', 'Pianificazione giornaliera');
    link.style.cssText = 'display:flex;align-items:center;min-height:32px;padding:6px 12px;font-size:13px;white-space:nowrap;';
    people.parentNode.insertBefore(link, people.nextSibling);
  }
  new MutationObserver(() => { if (!scheduled) { scheduled = true; requestAnimationFrame(attach); } }).observe(document, {childList:true, subtree:true});
  attach();
})();

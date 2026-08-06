/* New Vision Academy – loading, cookies, subscribe notifications, FABs */
(function () {
  "use strict";

  var COOKIE_KEY = "nva_cookie_consent";
  var SUB_KEY = "nva_subscribed";
  var NOTIF_DISMISS = "nva_notif_dismiss";
  var LAST_NOTIF_KEY = "nva_last_notif_id";

  function hideLoader() {
    var el = document.getElementById("pageLoader");
    if (!el) return;
    el.classList.add("hide");
    setTimeout(function () {
      if (el.parentNode) el.remove();
    }, 450);
  }
  if (document.readyState === "complete") {
    setTimeout(hideLoader, 400);
  } else {
    window.addEventListener("load", function () {
      setTimeout(hideLoader, 500);
    });
  }
  setTimeout(hideLoader, 4000);

  function showCookieBanner() {
    if (localStorage.getItem(COOKIE_KEY)) return;
    var bar = document.getElementById("cookieBanner");
    if (bar) bar.classList.add("show");
  }

  function acceptCookies() {
    localStorage.setItem(COOKIE_KEY, "accepted");
    var bar = document.getElementById("cookieBanner");
    if (bar) bar.classList.remove("show");
    if (!localStorage.getItem(SUB_KEY) && !localStorage.getItem(NOTIF_DISMISS)) {
      setTimeout(openSubscribePrompt, 1500);
    }
  }

  function declineCookies() {
    localStorage.setItem(COOKIE_KEY, "declined");
    var bar = document.getElementById("cookieBanner");
    if (bar) bar.classList.remove("show");
  }

  function urlBase64ToUint8Array(base64String) {
    var padding = "=".repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
    var raw = atob(base64);
    var out = new Uint8Array(raw.length);
    for (var i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
    return out;
  }

  function setSubscribedUI(on) {
    var btn = document.getElementById("btnSubscribeNotify");
    var label = document.getElementById("notifyFabLabel");
    if (btn) btn.classList.toggle("subscribed", !!on);
    if (label) label.textContent = on ? "Subscribed" : "Subscribe";
    var strip = document.getElementById("subscribeStrip");
    if (strip && on) strip.style.display = "none";
  }

  function openSubscribePrompt() {
    var box = document.getElementById("notifPrompt");
    if (box) {
      box.classList.add("show");
      var st = document.getElementById("notifStatus");
      if (st) {
        st.style.display = "none";
        st.textContent = "";
        st.innerHTML = "";
      }
    }
    if (localStorage.getItem(SUB_KEY) === "1") {
      showStatus("You are already subscribed to school notifications.", true);
    }
  }

  function closeSubscribePrompt() {
    var box = document.getElementById("notifPrompt");
    if (box) box.classList.remove("show");
  }

  function showStatus(msg, ok) {
    var st = document.getElementById("notifStatus");
    var box = document.getElementById("notifPrompt");
    if (box) box.classList.add("show");
    if (st) {
      st.style.display = "block";
      st.style.color = ok ? "#059669" : "#b91c1c";
      st.innerHTML = msg;
    }
  }

  function isSecureEnough() {
    if (typeof window.isSecureContext === "boolean") return window.isSecureContext;
    return location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1";
  }

  function deniedHelpHtml() {
    return (
      "Browser blocked notifications for this site.<br><br>" +
      "<strong>Enable again:</strong><br>" +
      "• <em>Chrome/Edge:</em> lock icon near address bar → Site settings → Notifications → <strong>Allow</strong><br>" +
      "• <em>Firefox:</em> lock icon → Permissions → Notifications → Allow<br>" +
      "• <em>Phone:</em> Site settings / App info → Notifications → On<br><br>" +
      "Then click <strong>Subscribe now</strong> again."
    );
  }

  async function saveSubscriptionToServer(endpoint, keys) {
    var res = await fetch("/api/push-subscribe", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ endpoint: endpoint, keys: keys || {} })
    });
    var data = await res.json().catch(function () {
      return { ok: false };
    });
    return res.ok && data.ok;
  }

  async function doSubscribe() {
    if (localStorage.getItem(SUB_KEY) === "1" && Notification.permission === "granted") {
      // Re-register SW + push in case endpoint changed after deploy
      try {
        await ensurePushSubscription(true);
      } catch (e) {}
      showStatus("You are already subscribed.", true);
      setSubscribedUI(true);
      return;
    }

    if (!("Notification" in window)) {
      showStatus("This browser does not support notifications. Try Chrome or Firefox.", false);
      return;
    }

    if (!isSecureEnough()) {
      showStatus(
        "Notifications need <strong>HTTPS</strong> (or localhost).<br>Open the site with https://",
        false
      );
      return;
    }

    try {
      var perm = Notification.permission;

      if (perm === "denied") {
        showStatus(deniedHelpHtml(), false);
        var softId = "denied-interest-" + Date.now();
        await saveSubscriptionToServer(softId, {});
        return;
      }

      if (perm === "default") {
        showStatus("Waiting for browser permission…", true);
        perm = await Notification.requestPermission();
      }

      if (perm !== "granted") {
        showStatus(deniedHelpHtml(), false);
        return;
      }

      showStatus("Registering device for push…", true);
      var result = await ensurePushSubscription(false);
      if (!result.ok) {
        showStatus(result.error || "Could not save subscription. Please try again.", false);
        return;
      }

      localStorage.setItem(SUB_KEY, "1");
      setSubscribedUI(true);
      showStatus("✓ Subscribed! You will get school notices even when the site is closed.", true);

      try {
        new Notification("New Vision Academy", {
          body: "Subscribed successfully. You will receive notices and updates.",
          icon: "/static/icons/icon-192.png"
        });
      } catch (e) {}

      setTimeout(closeSubscribePrompt, 2800);
      fetch("/api/notifications/poll")
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data && data.last_id) setLastNotifId(data.last_id);
          startNotificationPoll();
        })
        .catch(function () { startNotificationPoll(); });
    } catch (err) {
      console.warn(err);
      showStatus("Something went wrong: " + (err && err.message ? err.message : "try again"), false);
    }
  }

  /** Register SW and create real Web Push subscription when possible. */
  async function ensurePushSubscription(silent) {
    var reg = null;
    if ("serviceWorker" in navigator) {
      try {
        reg = await navigator.serviceWorker.register("/sw.js", { scope: "/" });
        await navigator.serviceWorker.ready;
      } catch (swErr) {
        console.warn("SW register:", swErr);
      }
    }

    var endpoint = "granted-" + Date.now() + "-" + Math.random().toString(36).slice(2, 8);
    var keys = {};
    var gotRealPush = false;

    var meta = document.querySelector('meta[name="vapid-public-key"]');
    var vapidKey = meta ? meta.content.trim() : "";

    if (reg && reg.pushManager && vapidKey) {
      try {
        var existing = await reg.pushManager.getSubscription();
        var sub = existing;
        // If existing sub has no keys in toJSON, unsubscribe and create fresh
        if (sub) {
          var probe = sub.toJSON();
          if (!probe.keys || !probe.keys.p256dh || !probe.keys.auth) {
            try { await sub.unsubscribe(); } catch (u) {}
            sub = null;
          }
        }
        if (!sub) {
          sub = await reg.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: urlBase64ToUint8Array(vapidKey)
          });
        }
        var json = sub.toJSON();
        if (json.endpoint && json.endpoint.indexOf("https://") === 0) {
          endpoint = json.endpoint;
          keys = json.keys || {};
          if (keys.p256dh && keys.auth) {
            gotRealPush = true;
          }
        }
      } catch (e) {
        console.warn("PushManager subscribe:", e);
        if (!silent) {
          // Still save soft subscription so polling works
        }
      }
    }

    var ok = await saveSubscriptionToServer(endpoint, keys);
    return {
      ok: ok,
      real: gotRealPush,
      error: ok ? null : "Could not save subscription on server."
    };
  }

  function getLastNotifId() {
    var v = parseInt(localStorage.getItem(LAST_NOTIF_KEY) || "0", 10);
    return isNaN(v) ? 0 : v;
  }

  function setLastNotifId(id) {
    localStorage.setItem(LAST_NOTIF_KEY, String(id));
  }

  function showInAppToast(title, body, url) {
    var existing = document.getElementById("nvaToast");
    if (existing) existing.remove();
    var t = document.createElement("div");
    t.id = "nvaToast";
    t.style.cssText =
      "position:fixed;top:1rem;right:1rem;z-index:99990;max-width:340px;" +
      "background:#02143a;color:#fff;border-radius:12px;padding:1rem 1.1rem;" +
      "box-shadow:0 12px 40px rgba(0,0,0,0.25);font-family:inherit;cursor:pointer;";
    t.innerHTML =
      '<div style="font-weight:800;font-size:0.9rem;margin-bottom:0.35rem;">' +
      '<i class="fa fa-bell" style="color:#e4c45a;margin-right:0.35rem;"></i>' +
      (title || "New Vision Academy") +
      "</div>" +
      '<div style="font-size:0.8rem;color:rgba(255,255,255,0.85);line-height:1.45;">' +
      (body || "") +
      "</div>" +
      '<div style="margin-top:0.5rem;font-size:0.75rem;color:#e4c45a;">Tap to open</div>';
    t.onclick = function () {
      window.location.href = url || "/";
    };
    document.body.appendChild(t);
    setTimeout(function () {
      if (t.parentNode) t.remove();
    }, 12000);
  }

  function deliverNotification(item) {
    if (!item || !item.id) return;
    if (item.id <= getLastNotifId()) return;
    setLastNotifId(item.id);

    if ("Notification" in window && Notification.permission === "granted") {
      try {
        var n = new Notification(item.title || "New Vision Academy", {
          body: item.body || "",
          icon: "/static/icons/icon-192.png",
          tag: "nva-" + item.id
        });
        n.onclick = function () {
          window.focus();
          window.location.href = item.url || "/";
          n.close();
        };
      } catch (e) {}
    }
    showInAppToast(item.title, item.body, item.url);
  }

  function pollNotifications() {
    if (localStorage.getItem(SUB_KEY) !== "1") return;
    var after = getLastNotifId();
    fetch("/api/notifications/latest?after=" + after)
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        if (!data || !data.ok || !data.items) return;
        data.items.forEach(function (item) {
          deliverNotification(item);
        });
      })
      .catch(function () {});
  }

  function startNotificationPoll() {
    if (localStorage.getItem(SUB_KEY) !== "1") return;
    if (!localStorage.getItem(LAST_NOTIF_KEY)) {
      fetch("/api/notifications/poll")
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          if (data && data.last_id) setLastNotifId(data.last_id);
        })
        .catch(function () {});
    }
    pollNotifications();
    setInterval(pollNotifications, 8000);
  }

  document.addEventListener("DOMContentLoaded", function () {
    showCookieBanner();

    var acc = document.getElementById("cookieAccept");
    var dec = document.getElementById("cookieDecline");
    if (acc) acc.addEventListener("click", acceptCookies);
    if (dec) dec.addEventListener("click", declineCookies);

    var fabBtn = document.getElementById("btnSubscribeNotify");
    if (fabBtn) {
      fabBtn.addEventListener("click", function () {
        openSubscribePrompt();
      });
    }

    var yes = document.getElementById("notifYes");
    var no = document.getElementById("notifNo");
    var later = document.getElementById("notifLater");
    if (yes) yes.addEventListener("click", doSubscribe);
    if (no) {
      no.addEventListener("click", function () {
        localStorage.setItem(NOTIF_DISMISS, "1");
        closeSubscribePrompt();
      });
    }
    if (later) {
      later.addEventListener("click", function () {
        localStorage.setItem(NOTIF_DISMISS, "1");
        closeSubscribePrompt();
      });
    }

    if (localStorage.getItem(SUB_KEY) === "1") {
      setSubscribedUI(true);
      // Refresh push subscription silently (important after redeploy / new VAPID)
      if (Notification.permission === "granted") {
        ensurePushSubscription(true).catch(function () {});
      }
    }

    var stripBtn = document.getElementById("btnSubscribeStrip");
    if (stripBtn) {
      stripBtn.addEventListener("click", function () {
        openSubscribePrompt();
      });
    }

    var fab = document.querySelector(".fab-wrap");
    if (fab) {
      setTimeout(function () {
        fab.classList.add("visible");
      }, 600);
    }

    if (localStorage.getItem(SUB_KEY) === "1" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(function () {});
    }

    startNotificationPoll();
  });
})();

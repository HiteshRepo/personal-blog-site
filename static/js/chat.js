(function () {
  "use strict";

  var messagesEl = document.getElementById("chat-messages");
  var inputEl = document.getElementById("chat-input");
  var sendBtn = document.getElementById("chat-send");
  var statusEl = document.getElementById("chat-status");

  if (!messagesEl || !inputEl || !sendBtn) return;

  var history = [];

  // ---------------------------------------------------------------------------
  // Render helpers
  // ---------------------------------------------------------------------------

  function renderMarkdown(text) {
    var lines = text.split("\n");
    var html = "";
    var inList = false;

    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var listMatch = line.match(/^[\-\*]\s+(.+)/);

      if (listMatch) {
        if (!inList) { html += "<ul class='pl3 mt1 mb1'>"; inList = true; }
        html += "<li>" + renderInline(listMatch[1]) + "</li>";
      } else {
        if (inList) { html += "</ul>"; inList = false; }
        var trimmed = line.trim();
        if (trimmed) html += "<p class='mt0 mb1'>" + renderInline(trimmed) + "</p>";
      }
    }
    if (inList) html += "</ul>";
    return html;
  }

  function renderInline(text) {
    return escapeHtml(text)
      // markdown links [text](url)
      .replace(
        /\[([^\]]+)\]\(((?:https?:\/\/|mailto:|\/)[^\)]+)\)/g,
        function (_, linkText, url) {
          var isMailto = /^mailto:/.test(url);
          var isExternal = isMailto || /^https?:\/\//.test(url);
          // For internal paths, strip any injected domain and rebuild from current origin
          var href = isExternal
            ? url
            : window.location.origin + url.replace(/^https?:\/\/[^\/]+/, "");
          return '<a href="' + href + '" class="link blue"'
            + (isExternal ? ' target="_blank" rel="noopener"' : "")
            + ">" + linkText + "</a>";
        }
      )
      // **bold**
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      // *italic*
      .replace(/\*([^*]+)\*/g, "<em>$1</em>");
  }

  function appendMessage(role, text) {
    var wrapper = document.createElement("div");
    wrapper.className = role === "user" ? "mb3 tr" : "mb3 tl";

    var bubble = document.createElement("span");
    bubble.className =
      role === "user"
        ? "dib pa2 ph3 br3 bg-dark-gray white f6 tl"
        : "dib pa2 ph3 br3 bg-white black f6 ba b--black-10";

    // Render markdown in assistant replies
    if (role === "assistant") {
      bubble.innerHTML = renderMarkdown(text);
    } else {
      bubble.textContent = text;
    }

    wrapper.appendChild(bubble);
    messagesEl.appendChild(wrapper);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function escapeHtml(text) {
    return text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function setStatus(msg) {
    if (statusEl) statusEl.textContent = msg;
  }

  function setLoading(loading) {
    sendBtn.disabled = loading;
    inputEl.disabled = loading;
    setStatus(loading ? "Thinking…" : "");
  }

  // ---------------------------------------------------------------------------
  // Send message
  // ---------------------------------------------------------------------------

  function sendMessage() {
    var message = inputEl.value.trim();
    if (!message) return;

    inputEl.value = "";
    appendMessage("user", message);
    setLoading(true);

    fetch("/.netlify/functions/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        message: message,
        history: history,
        page_slug: window.CHAT_PAGE_SLUG || null,
      }),
    })
      .then(function (res) {
        return res.json().then(function (data) {
          if (!res.ok) throw new Error(data.error || "Something went wrong.");
          return data;
        });
      })
      .then(function (data) {
        history.push({ role: "user", content: message });
        history.push({ role: "assistant", content: data.reply });
        appendMessage("assistant", data.reply);
        setLoading(false);
        inputEl.focus();
      })
      .catch(function (err) {
        setStatus(err.message || "Error. Please try again.");
        sendBtn.disabled = false;
        inputEl.disabled = false;
        inputEl.focus();
      });
  }

  // ---------------------------------------------------------------------------
  // Event listeners
  // ---------------------------------------------------------------------------

  sendBtn.addEventListener("click", sendMessage);

  inputEl.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });
})();

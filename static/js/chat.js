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
          // Treat any hiteshpattanayak.* or netlify.app URL as our own site
          var isOwnDomain = /^https?:\/\/[^/]*hiteshpattanayak\.|^https?:\/\/[^/]*\.netlify\.app/.test(url);
          var isExternal = !isMailto && !isOwnDomain && /^https?:\/\//.test(url);
          var href = isMailto || isExternal
            ? url
            : window.location.origin + url.replace(/^https?:\/\/[^\/]+/, "");
          return '<a href="' + href + '" class="link blue"'
            + (isExternal || isMailto ? ' target="_blank" rel="noopener"' : "")
            + ">" + linkText + "</a>";
        }
      )
      // **bold**
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      // *italic*
      .replace(/\*([^*]+)\*/g, "<em>$1</em>");
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
    if (!loading) setStatus("");
  }

  // ---------------------------------------------------------------------------
  // Message rendering
  // ---------------------------------------------------------------------------

  function appendMessage(role, text) {
    var wrapper = document.createElement("div");
    wrapper.className = role === "user" ? "mb3 tr" : "mb3 tl";

    var bubble = document.createElement("span");
    bubble.className =
      role === "user"
        ? "dib pa2 ph3 br3 bg-dark-gray white f6 tl"
        : "dib pa2 ph3 br3 bg-white black f6 ba b--black-10";

    if (role === "assistant") {
      bubble.innerHTML = renderMarkdown(text);
    } else {
      bubble.textContent = text;
    }

    wrapper.appendChild(bubble);
    messagesEl.appendChild(wrapper);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function createStreamingBubble() {
    var wrapper = document.createElement("div");
    wrapper.className = "mb3 tl";
    var bubble = document.createElement("span");
    bubble.className = "dib pa2 ph3 br3 bg-white black f6 ba b--black-10";
    bubble.innerHTML = '<span class="chat-cursor">&#9611;</span>';
    wrapper.appendChild(bubble);
    messagesEl.appendChild(wrapper);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return wrapper;
  }

  function updateStreamingBubble(wrapper, text) {
    var bubble = wrapper.querySelector("span");
    bubble.innerHTML = renderMarkdown(text) + '<span class="chat-cursor">&#9611;</span>';
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function finalizeStreamingBubble(wrapper, text) {
    var bubble = wrapper.querySelector("span");
    bubble.innerHTML = renderMarkdown(text);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  // ---------------------------------------------------------------------------
  // Send message with SSE streaming
  // ---------------------------------------------------------------------------

  function sendMessage() {
    var message = inputEl.value.trim();
    if (!message) return;

    inputEl.value = "";
    appendMessage("user", message);
    setLoading(true);

    var streamBubble = createStreamingBubble();
    var accumulated = "";
    var done = false;

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
        if (!res.ok) {
          return res.text().then(function (text) {
            try { throw new Error(JSON.parse(text).error || "Something went wrong."); }
            catch (_) { throw new Error("Chat service unavailable. Use netlify dev to test locally."); }
          });
        }

        var reader = res.body.getReader();
        var decoder = new TextDecoder();
        var buffer = "";

        function read() {
          return reader.read().then(function (result) {
            if (result.done) {
              if (!done) finalizeStreamingBubble(streamBubble, accumulated);
              setLoading(false);
              inputEl.focus();
              return;
            }

            buffer += decoder.decode(result.value, { stream: true });
            var lines = buffer.split("\n");
            buffer = lines.pop();

            for (var i = 0; i < lines.length; i++) {
              var line = lines[i];
              if (!line.startsWith("data: ")) continue;
              var data = line.slice(6).trim();

              if (data === "[DONE]") {
                done = true;
                finalizeStreamingBubble(streamBubble, accumulated);
                history.push({ role: "user", content: message });
                history.push({ role: "assistant", content: accumulated });
                setLoading(false);
                inputEl.focus();
                return;
              }

              try {
                var parsed = JSON.parse(data);
                if (parsed.error) {
                  setStatus(parsed.error);
                  streamBubble.remove();
                  setLoading(false);
                  return;
                }
                if (parsed.text) {
                  accumulated += parsed.text;
                  updateStreamingBubble(streamBubble, accumulated);
                }
              } catch (_) {}
            }

            return read();
          });
        }

        return read();
      })
      .catch(function (err) {
        streamBubble.remove();
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

fetch("/api/backend")
  .then((res) => {
    if (!res.ok) throw new Error("HTTP " + res.status);
    return res.text();
  })
  .then((text) => {
    document.getElementById("backend").textContent = text.trim();
  })
  .catch((err) => {
    document.getElementById("backend").textContent =
      "Backend request failed: " + err;
  });

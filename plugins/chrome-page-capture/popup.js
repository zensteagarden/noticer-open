const status = document.querySelector("#status");
const captureButton = document.querySelector("#capture");

function fail(message) {
  status.textContent = message + "\nNot a verdict.";
}

captureButton.addEventListener("click", async () => {
  const intention = document.querySelector("#intention").value.trim();
  const expectedText = document.querySelector("#expected").value;
  if (!intention || expectedText.length === 0) {
    fail("Intention and exact text are both required.");
    return;
  }
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab?.id) {
    fail("No active tab.");
    return;
  }
  let captured;
  try {
    [captured] = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: () => {
        const selected = document.getSelection?.()?.toString() ?? "";
        const text = selected.trim() || document.body?.innerText || "";
        return { text: text.slice(0, 100000), href: location.href, title: document.title };
      },
    });
  } catch (error) {
    fail("Capture failed. Chrome blocked this page, or the tab is not scriptable.");
    return;
  }
  const page = captured?.result;
  if (!page || page.text.length === 0) {
    fail("Captured no text. Select the part you want disclosed.");
    return;
  }
  const bundle = {
    plugin_id: "chrome-page-capture",
    plugin_version: "0.1.0",
    trunk: "noticer-public-verifier",
    schema_version: "0.1",
    intention,
    expected_text: expectedText,
    captured_text: page.text,
    page_url: page.href,
    page_title: page.title,
    captured_at: new Date().toISOString(),
    does_not_establish: [
      "who wrote the page",
      "that the page still says this",
      "that an external write happened",
      "authorization to act",
    ],
    verdict: null,
  };
  const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  await chrome.downloads?.download?.({ url, filename: "noticer-page-capture.bundle.json", saveAs: true });
  if (!chrome.downloads) {
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "noticer-page-capture.bundle.json";
    anchor.click();
  }
  status.textContent = "Bundle exported. Not a verdict.\nUnpack it, then run noticer-check verify on the directory.";
});

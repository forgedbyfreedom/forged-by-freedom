(function () {
  // Ensure the global configuration `window.FBF_AI` is set
  if (!window.FBF_AI || !window.FBF_AI.api) {
    console.error("FBF_AI configuration is missing! Please set window.FBF_AI.api.");
    return;
  }

  const apiURL = window.FBF_AI.api;

  function createSearchUI() {
    // Create and inject the search form
    const container = document.createElement("div");
    container.style = "margin: 50px auto; text-align: center; font-family: Arial;";

    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Enter your query...";
    input.style = "padding: 10px; width: 300px; font-size: 16px;";

    const button = document.createElement("button");
    button.innerText = "Search";
    button.style = "padding: 10px 20px; margin-left: 10px;";
    button.onclick = () => {
      const query = input.value;
      if (!query) {
        alert("Please enter a query!");
        return;
      }
      sendQuery(query);
    };

    container.appendChild(input);
    container.appendChild(button);

    const resultsDiv = document.createElement("div");
    resultsDiv.id = "results";
    container.appendChild(resultsDiv);

    document.body.appendChild(container);
  }

  function sendQuery(query) {
    const resultsDiv = document.getElementById("results");
    resultsDiv.innerHTML = "<p>Searching...</p>";

    fetch(apiURL + "/query", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ query }),
    })
      .then((response) => response.json())
      .then((data) => {
        resultsDiv.innerHTML =
          "<h3>Results:</h3><pre>" + JSON.stringify(data, null, 2) + "</pre>";
      })
      .catch((err) => {
        console.error("Error:", err);
        resultsDiv.innerHTML = "<p>Failed to fetch results.</p>";
      });
  }

  // Initialize the UI
  createSearchUI();
})();

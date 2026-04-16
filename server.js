const express = require("express");

const app = express();
const PORT = process.env.PORT || 3000;

app.get("/", (req, res) => {
  res.send(`
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>studious-lamp</title>
      <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
          background: #0f0f0f;
          color: #e0e0e0;
          display: flex;
          justify-content: center;
          align-items: center;
          min-height: 100vh;
        }
        .container {
          text-align: center;
          padding: 2rem;
        }
        h1 {
          font-size: 2.5rem;
          margin-bottom: 1rem;
          background: linear-gradient(135deg, #667eea, #764ba2);
          -webkit-background-clip: text;
          -webkit-text-fill-color: transparent;
        }
        p {
          font-size: 1.2rem;
          color: #888;
          margin-bottom: 0.5rem;
        }
        .status {
          display: inline-block;
          margin-top: 1.5rem;
          padding: 0.5rem 1.5rem;
          border: 1px solid #333;
          border-radius: 999px;
          font-size: 0.9rem;
          color: #4ade80;
        }
      </style>
    </head>
    <body>
      <div class="container">
        <h1>studious-lamp</h1>
        <p>Your app is live!</p>
        <p>Edit <code>server.js</code> to start building.</p>
        <div class="status">Running on port ${PORT}</div>
      </div>
    </body>
    </html>
  `);
});

app.get("/health", (req, res) => {
  res.json({ status: "ok" });
});

app.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});

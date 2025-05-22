# Unity AI Agent

---

## 🌍 Vision

**Unity AI Agent** is a modular, intelligent, and multilingual AI-powered assistant built to serve the diverse needs of African communities. Designed with flexibility and accessibility in mind, Unity aims to empower organizations like Africa Unite by integrating real-time search, multilingual processing, and locally relevant insights into one responsive platform.

---

## 🎯 Purpose

* Support humanitarian outreach
* Bridge communication gaps
* Assist in multilingual knowledge sharing
* Enable AI literacy and access in underrepresented regions

---

## 💡 Core Features

* **Gemini Pro LLM Integration**: Powered by Google Gemini for cutting-edge generative reasoning.
* **Search Tooling**: Real-time knowledge retrieval using DuckDuckGo.
* **Modular Architecture**: Easily extendable via clean, component-based modules.
* **CLI Agent Interface**: Local development and interaction through terminal.

---

## 🧱 Tech Stack

* **Python 3.10+**
* **LangChain** (Agent tooling and orchestration)
* **Google Generative AI (Gemini Pro)**
* **Dotenv** (Secure key management)
* **DuckDuckGo Search** (Web results plugin)

---

## 🛠️ Project Structure

```
unity_ai/
├── core/
│   ├── config.py          # Key and LLM initialization
│   └── db.py
|   └── tools.py       # Agent tools setup (search, etc.)
├── agent_setup.py               # Entry point for CLI agent interaction
|—— agent_testing.py
|—— agent_cli.py
|—— fact_sheet.py
|—— main.py
├── .env                   # API key storage (DO NOT COMMIT)
├── README.md              # Project overview
└── requirements.txt       # Dependency list
```

---

## 🚀 Getting Started

1. **Clone the repository**:

   ```bash
   git clone https://github.com/your-username/unity_ai.git
   cd unity_ai
   ```
2. **Create a virtual environment**:

   ```bash
   python -m venv venv
   venv\Scripts\activate  # On Windows
   ```
3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```
4. **Add your API key to `.env`**:

   ```env
   GOOGLE_API_KEY=your_gemini_key_here
   ```
5. **Run the agent**:

   ```bash
   python agent.py
   ```

---

## 🤝 Contributions

Unity AI is a project meant to grow with input from developers, educators, and community leaders. Contributions from open-source collaborators and NGOs are welcome.

If you'd like to contribute, open an issue or PR — or reach out.

---

## 📜 License

This project is licensed under the MIT License.

---

## 🌐 Acknowledgements

* Africa Unite
* LangChain Community
* Google Developers
* Open knowledge contributors across Africa

> "Technology should unite, not divide. Unity is built with purpose — for the people, by the people."


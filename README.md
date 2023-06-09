<div align="center">

# FKNDRK

![FKNDRK](resources/fkndrk_banner.png)

</div>

---

**FKNDRK** is a Python script for automating the Google Dorking process. It streamlines the process of Google Dorking by utilizing public proxies and the ScraperAPI (scraperapi.com) free API key. It searches for specific information on websites indexed by Google, based on a list of dorks provided in a file. 

FKNDRK is designed to run concurrently using multiple threads, allowing for efficient and faster searches. Results are saved in a dedicated folder as JSON files, making it easy to analyze and process the data.

---

<div align="center">

![FKNDRK](resources/fkndrk3.gif)

</div>

## 🚀 Features

- 🔍 Concurrent searching using multiple threads
- 📡 Utilizes public proxies and ScraperAPI
- 📁 Saves search results in JSON format
- 📋 Customizable list of dorks and user agents
- 🎭 Random user agent per request

## 🛠️ Installation

Clone the repository:

```bash
pip install -r requirements.txt
```

3. (Optional) Obtain a ScraperAPI key for better results and add it to the `.env` file. You can sign up for a free account on the [ScraperAPI website](https://www.scraperapi.com/).

## 📖 Usage
### Custom dorks/useragents files?

- Provide a list of dorks in the config/dorks.txt file (or use the one provided)

- Set up user agents in the config/user_agents.txt file (or use the one provided)

### Run the script:

```bash
python3 fknDrk.py
```
<div align="center">

![FKNDRK](resources/fkndrk1.gif)
</div>


Use the following command-line options to customize the script's behavior:

```bash
-v, --verbose Display errors with proxies.
-t, --threads Number of threads to use for searching (default: 20).
-n, --numResults Number of results to save per dork (default: 30).
-maxp, --max-paid Maximum number of times to use the paid proxy (default: 0).
-d, --debug Enable debug mode.
```
<div align="center">

![FKNDRK](resources/fkndrk2.gif)

</div>

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue on GitHub.

## 👤 Author

  - Dap  
  - Twitter: @Dapunhinged

<div align="center">

⭐️ If you like FKNDRK, please consider giving it a star on GitHub! ⭐️
</div>

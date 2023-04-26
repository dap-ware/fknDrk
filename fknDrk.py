#!/usr/bin/env python3

"""
FKNDRK - A Python script for automating the Google Dorking process.

This script streamlines the process of Google Dorking by utilizing public proxies
and the ScraperAPI (scraperapi.com) free API key. It searches for specific
information on websites indexed by Google, based on a list of dorks provided in
a file.

FKNDRK is designed to run concurrently using multiple threads, allowing for
efficient and faster searches. Results are saved in a dedicated folder as JSON
files, making it easy to analyze and process the data.

Usage:
- Provide a list of dorks in the 'config/dorks.txt' file
- Set up user agents in the 'config/dorks.txt' file
- (Optional) Obtain a ScraperAPI key for better results and add it to the '.env' file

Author:
Dap
Twitter: @Dapunhinged
"""

import os
from dotenv import load_dotenv
from queue import Empty
import time
import re
import random
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import json
import requests
from rich.console import Console
from rich.table import Table
from multiprocessing import Process, Queue as MpQueue
from scraper_api import ScraperAPIClient

# Add a lock for printing in a multi-threaded environment
print_lock = threading.Lock()
console = Console()

# Define constants to be used in the program
REQUESTS_PER_SECOND = 100
SECONDS_PER_REQUEST = 1 / REQUESTS_PER_SECOND

# Retry constants, for failed requests with proxies
DEFAULT_BACKOFF_FACTOR = 1.0
MAX_RETRIES = 3


def sanitize_filename(filename):
    # Define a set of invalid characters for filenames
    invalid_chars = set(r'<>:"/\|?*')
    # Replace invalid characters with underscores
    sanitized_filename = "".join(c if c not in invalid_chars else "_" for c in filename)
    return sanitized_filename


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def print_banner():
    # Clear screen and print banner
    clear_screen()
    with open("resources/banner.txt", "r") as f:
        banner = f.read().strip()
        console.print(banner, style="bold red")


def get_proxies():
    # Initialize an empty list to store proxies
    proxies = []

    # Check if the "config/proxies.txt" file exists
    if not os.path.exists("config/proxies.txt"):
        # Get proxies from the existing source
        proxies += get_proxies_from_existing_source()

        # Get proxies from the Free Proxy List
        proxies += get_proxies_from_free_proxy_list()

        # Remove duplicates from the list of proxies
        proxies = list(set(proxies))

        # Save proxies to the file "config/proxies.txt"
        with open("config/proxies.txt", "w") as f:
            f.write("\n".join(proxies))
    else:
        # If the "config/proxies.txt" file exists, read proxies from the file
        with open("config/proxies.txt", "r") as f:
            proxies = f.read().split("\n")

    return proxies


def get_proxies_from_existing_source():
    # Define the URL for the existing source of proxies
    url = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all&limit=5000"
    # Initialize an empty list to store proxies
    proxies = []

    try:
        # Send a GET request to the URL
        response = requests.get(url)
        # If the response status code is 200 (OK), parse the proxies
        if response.status_code == 200:
            proxies = response.text.split("\n")
    except requests.exceptions.RequestException:
        # Print an error message if there is an exception while fetching proxies
        console.print(
            "Error fetching proxies from the existing source", style="bold red"
        )

    return proxies


def get_proxies_from_free_proxy_list():
    # Define the URL for the Free Proxy List website
    url = "https://free-proxy-list.net/"
    # Initialize an empty list to store proxies
    proxies = []

    try:
        # Send a GET request to the URL
        response = requests.get(url)
        # If the response status code is 200 (OK), parse the proxies
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            proxy_table = soup.find("table", {"id": "proxylisttable"})
            proxy_rows = proxy_table.tbody.find_all("tr")

            # Extract IP and port from each row and append to the list of proxies
            for row in proxy_rows:
                cells = row.find_all("td")
                ip = cells[0].text
                port = cells[1].text
                proxies.append(f"{ip}:{port}")
    except requests.exceptions.RequestException:
        # Print an error message if there is an exception while fetching proxies
        console.print("Error fetching proxies from Free Proxy List", style="bold red")

    return proxies


def test_proxy(proxy, user_agent, session, debug=False):
    # If debug mode is enabled, print a message indicating that the proxy is being tested
    if debug:
        with print_lock:
            console.print(f"[DEBUG] [bold yellow]Testing proxy:[/bold yellow] {proxy}")
    # Define the URL for testing the proxy
    test_url = "https://bing.com/"
    # Define headers for the request, including the User-Agent
    headers = {"User-Agent": user_agent}
    try:
        # Define the proxies dictionary for the request, specifying the proxy for both HTTP and HTTPS
        proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
        # Send a GET request to the test URL using the proxy and specified headers, with a timeout of 4 seconds
        response = session.get(test_url, headers=headers, proxies=proxies, timeout=4)
        # If debug mode is enabled, print a message indicating whether the proxy is working
        if debug:
            with print_lock:
                console.print(
                    f"[DEBUG] Proxy {proxy} is {f'[bold green]working[/bold green]' if response.status_code == 200 else f'[bold red]not working[/bold red]'}"
                )
        # Return True if the response status code is 200 (OK), otherwise return False
        return response.status_code == 200
    except requests.exceptions.RequestException as e:
        # If there is an exception while testing the proxy (e.g., timeout, connection error), return False
        return False


def filter_working_proxies(proxies, user_agents, session, debug=False):
    # If debug mode is enabled, print a message indicating the total number of proxies being filtered
    if debug:
        with print_lock:
            console.print(
                f"[DEBUG] [bold yellow]Filtering working proxies from a total of[/bold yellow] {len(proxies)} [bold yellow]proxies[/bold yellow]"
            )
    # Initialize an empty list to store working proxies
    working_proxies = []
    # Randomly select a user agent from the list of user agents
    user_agent = random.choice(user_agents)

    # Use ThreadPoolExecutor to test proxies concurrently
    with ThreadPoolExecutor(max_workers=100) as executor:
        # Create a dictionary that maps futures to proxies
        futures_to_proxies = {
            executor.submit(test_proxy, proxy, user_agent, session, debug=debug): proxy
            for proxy in proxies
        }

        # Display a status message while testing proxies
        with console.status(
            "[bold yellow]\nTesting proxies...[/bold yellow]"
        ) as status:
            # Iterate over completed futures and check their results
            for future in as_completed(futures_to_proxies):
                # If the future's result is True, add the corresponding proxy to the list of working proxies
                if future.result():
                    working_proxies.append(futures_to_proxies[future])

    # Return the list of working proxies
    return working_proxies


def google_search(query, user_agent, proxy, session):
    # Define the URL for the Google search, including the query parameter
    url = f"https://www.google.com/search?q={query}"
    # Define headers for the request, including the User-Agent
    headers = {"User-Agent": user_agent}
    # Define the proxies dictionary for the request, specifying the proxy for both HTTP and HTTPS
    proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
    # Send a GET request to the Google search URL using the specified headers, proxy, and timeout
    response = session.get(url, headers=headers, proxies=proxies, timeout=4)
    # If the response status code is 200 (OK), parse the response and extract search result URLs
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, "html.parser")
        return [result["href"] for result in soup.select(".yuRUbf a")]
    else:
        # If the response status code is not 200, return an empty list
        return []


def strip_google_translate(url):
    # Define a regular expression pattern to match Google Translate URLs
    pattern = r"https://translate\.google\.com/translate\?.*?&u="
    # Use the re.sub() function to remove the Google Translate prefix from the URL
    return re.sub(pattern, "", url)


def try_search_dork(
    dork,
    proxy,
    user_agent,
    num_results,
    session,
    verbose,
    all_dorks_results,
    scraper_api_key=None,
):
    # Acquire the print lock to prevent multiple threads from writing simultaneously
    with print_lock:
        console.print(f"[bold yellow]Searching dork:[/bold yellow] '{dork}'")
    start_time = time.time()
    cleaned_results = []

    try:
        # Define the URL for the Google search
        url = f"https://www.google.com/search?q={dork}"
        headers = {"User-Agent": user_agent}

        if scraper_api_key:
            # Initialize the ScraperAPIClient with your API key
            client = ScraperAPIClient(scraper_api_key)
            # Use the client.get method to send a request through ScraperAPI
            response = client.get(url, headers=headers)
        else:
            # Use the regular requests session to send the request
            proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
            response = session.get(url, headers=headers, proxies=proxies, timeout=4)

        # Check if the response status code is 200 (successful)
        if response.status_code == 200:
            # Parse the response text with BeautifulSoup
            soup = BeautifulSoup(response.text, "html.parser")
            # Extract the result URLs from the parsed HTML
            results = [result["href"] for result in soup.select(".yuRUbf a")]
            # Clean and truncate the results
            cleaned_results = [
                strip_google_translate(url) for url in results[:num_results]
            ]

            # If verbose is True, print the raw results
            if verbose:
                with print_lock:
                    console.print(
                        f"\n[bold red]{'='*80}[/bold red]\n[bold yellow]Raw results for [/bold yellow]'{dork}'[bold yellow]:[/bold yellow]\n[bold red]{'-'*80}[/bold red]\n\n"
                    )
                    # Print the cleaned_results formatted w/ indent of 2
                    console.print(
                        json.dumps(cleaned_results, indent=2) + "\n", style="bold blue"
                    )

            # Update the all_dorks_results dictionary
            all_dorks_results[dork] = cleaned_results

            # If verbose is True, print the updated all_dorks_results
            if verbose:
                with print_lock:
                    console.print(
                        f"\n[bold red]{'='*80}\n[/bold red][bold yellow]Updated all_dorks_results:[/bold yellow][bold red]\n{'-'*80}[/bold red]\n\n"
                    )
                    # Print the cleaned_results in a formatted way
                    console.print(
                        json.dumps(all_dorks_results, indent=2)
                        + f"\n[bold red]{'-'*80}[/bold red]",
                        style="bold blue",
                    )

            # Save the updated all_dorks_results to a file
            with open("all_dorks_results.json", "w") as f:
                json.dump(all_dorks_results, f)

            # Print a message about saving the results for the current dork
            with print_lock:
                console.print(
                    f"\n[bold red]{'='*80}[/bold red]\n[bold yellow]Saving top {num_results} results for dork: [/bold yellow]'{dork}'\n[bold red]{'-'*80}[/bold red]\n"
                )
                console.print(
                    json.dumps({dork: cleaned_results}, indent=2), style="bold blue"
                )
                console.print("\n" + "=" * 80 + "\n", style="bold red")
        end_time = time.time()
        elapsed_time = end_time - start_time
        sleep_time = max(0, SECONDS_PER_REQUEST - elapsed_time)
        time.sleep(sleep_time)
        return cleaned_results

    except requests.exceptions.RequestException as e:
        return None


def search_dork(
    dork,
    proxies,
    user_agents,
    session,
    num_results,
    verbose,
    threads,
    max_paid,
    scraper_api_key,
    all_dorks_results=None,
):
    # Use the global constants for backoff factor and maximum retries
    global DEFAULT_BACKOFF_FACTOR, MAX_RETRIES
    backoff_factor = DEFAULT_BACKOFF_FACTOR
    max_retries = MAX_RETRIES

    retries = 0
    results = None

    # Keep track of the number of times the paid proxy has been used
    paid_proxy_count = 0

    # Retry the search until the maximum number of retries is reached
    while retries <= max_retries:
        # Randomly select a proxy and user agent
        proxy = random.choice(proxies)
        user_agent = random.choice(user_agents)

        # Call the try_search_dork function to perform the search
        results = try_search_dork(
            dork, proxy, user_agent, num_results, session, verbose, all_dorks_results
        )

        # If the results are None and the paid proxy count is within the limit,
        # use the paid proxy for the search
        if results is None and paid_proxy_count < max_paid:
            paid_proxy_url = (
                f"http://scraperapi:{scraper_api_key}@proxy-server.scraperapi.com:8001"
            )
            results = try_search_dork(
                dork,
                paid_proxy_url,
                user_agent,
                num_results,
                session,
                verbose,
                all_dorks_results,
            )
            paid_proxy_count += 1

        # Increment the retries counter and sleep for a backoff period
        retries += 1
        time.sleep(backoff_factor * (2 ** (retries - 1)))

    return results


def search_dorks(
    dorks,
    proxies,
    user_agents,
    session,
    num_results,
    verbose,
    threads,
    max_paid,
    scraper_api_key,
    results_queue,
    all_dorks_results,
):
    # Create a ThreadPoolExecutor with the specified number of threads
    with ThreadPoolExecutor(max_workers=threads) as executor:
        # Submit search_dork tasks for each dork in the dorks list
        futures = {
            executor.submit(
                search_dork,
                dork,
                proxies,
                user_agents,
                session,
                num_results,
                verbose,
                threads,
                max_paid,
                scraper_api_key,
                all_dorks_results=all_dorks_results,
            ): dork
            for dork in dorks
        }
        # Process the completed tasks as they finish
        for future in as_completed(futures):
            dork = futures[future]
            results = future.result()

            # If the search produced results, add them to the results queue
            if results:
                results_queue.put((dork, results))  # Put the results into the queue

                # Sanitize the dork to generate a valid filename
                sanitized_dork = sanitize_filename(dork)

                # Save the updated results to file
                output_file = f"results/{sanitized_dork}_results.json"
                with open(output_file, "w") as f:
                    json.dump({dork: results}, f)


def get_user_agents():
    # Open the config/dorks.txt file and read its content
    with open("config/dorks.txt", "r") as f:
        # Split the content by newline character and return the list of user agents
        return f.read().split("\n")


def load_or_download_proxies(user_agents, session, debug=False):
    if debug:
        # Print a debug message if the debug flag is enabled
        with print_lock:
            console.print("[DEBUG] Loading or downloading proxies")

    # Initialize an empty list for storing proxies
    proxies = []

    try:
        # Try reading proxies from the config/proxies.txt file
        with open("config/proxies.txt") as f:
            proxies = f.read().splitlines()
    except FileNotFoundError:
        # If the config/proxies.txt file is not found, download new proxies
        print("[red]No proxy file found, downloading proxies...[/red]")
        resp = session.get(
            "https://api.proxyscrape.com/?request=getproxies&proxytype=http&timeout=10000&country=all"
        )
        if resp.status_code == 200:
            # If the request is successful, save the proxies to config/proxies.txt
            proxies = resp.content.decode().splitlines()
            with open("config/proxies.txt", "w") as f:
                f.write("\n".join(proxies))
        else:
            # If the request fails, print an error message
            print(
                "[bold red]Failed to download proxies, using default proxies.[/bold red]"
            )

    # Filter the working proxies and return the list
    working_proxies = filter_working_proxies(proxies, user_agents, session, debug=debug)
    return working_proxies


def main():
    # Load environment variables from the .env file
    load_dotenv()

    try:
        # Clear screen and print banner upon startup
        print_banner()

        # Initialize all_dorks_results before passing it to search_dorks
        all_dorks_results = {}

        # Parse command line arguments
        parser = argparse.ArgumentParser()
        parser.add_argument(
            "-v", "--verbose", help="Display errors with proxies.", action="store_true"
        )
        parser.add_argument(
            "-t",
            "--threads",
            help="Number of threads to use for searching (default: 20)",
            type=int,
            default=20,
        )
        parser.add_argument(
            "-n",
            "--numResults",
            help="Number of results to save per dork (default: 30)",
            type=int,
            default=30,
        )
        parser.add_argument(
            "-maxp",
            "--max-paid",
            help="Maximum number of times to use the paid proxy (default: 0)",
            type=int,
            default=0,
        )
        parser.add_argument(
            "-d", "--debug", help="Enable debug mode.", action="store_true"
        )

        args = parser.parse_args()

        # Load dorks from file
        with open("config/dorks.txt", "r") as f:
            dorks = f.read().split("\n")

        # Retrieve the value of the SCRAPER_API_KEY variable
        scraper_api_key = os.getenv("SCRAPER_API_KEY") if args.max_paid > 0 else None

        # Load user agents from file
        user_agents = get_user_agents()

        # Set up a requests session
        session = requests.Session()

        # Load or download proxies
        proxies = load_or_download_proxies(user_agents, session, debug=args.debug)

        # Create a directory for results
        if not os.path.exists("results"):
            os.makedirs("results")

        # Search for dorks in parallel
        results_queue = MpQueue()
        search_process = Process(
            target=search_dorks,
            args=(
                dorks,
                proxies,
                user_agents,
                session,
                args.numResults,
                args.verbose,
                args.threads,
                args.max_paid,
                scraper_api_key,
                results_queue,
                all_dorks_results,
            ),
        )
        # Start the search process
        search_process.start()

        # Wait for search process to complete and update results
        while search_process.is_alive() or not results_queue.empty():
            if not results_queue.empty():
                dork, results = results_queue.get()

                # Merge the new results with the previous results
                previous_results = set(all_dorks_results.get(dork, []))
                all_dorks_results[dork] = list(previous_results.union(results))

        # Build a table for displaying the results
        table = Table(title="Results", show_header=True)
        table.add_column("Dork", style="bold")
        table.add_column("Results File", style="bold")
        table.add_column("Results", style="bold")

        # Iterate over the dorks and their results
        for dork, result in all_dorks_results.items():
            output_file = f"results/{dork}_results.json"
            # Add a row to the table for each dork
            table.add_row(dork, output_file, str(len(result)))

        # Display the results using the table built above
        console.print(table)

    # Handle KeyboardInterrupt (Ctrl+C)
    except KeyboardInterrupt:
        console.print("\n[bold red]Interrupted by user. Exiting...[/bold red]")
        # Terminate the search process if it's still running
        if search_process.is_alive():
            search_process.terminate()
        # Exit the program
        exit(0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3

import os
import time
import random
import argparse
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from bs4 import BeautifulSoup
import requests
from rich.console import Console
from rich.progress import Progress


# Add a lock for printing in multi-threaded environment
print_lock = threading.Lock()
console = Console()

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_banner():
    clear_screen()
    with open("banner.txt", "r") as f:
        banner = f.read().strip()
        console.print(banner, style="bold red")

def get_proxies():
    proxies = []
    if not os.path.exists("proxies.txt"):
        url = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all&limit=5000"
        proxies = requests.get(url).text.split("\n")
        with open("proxies.txt", "w") as f:
            f.write("\n".join(proxies))
    else:
        with open("proxies.txt", "r") as f:
            proxies = f.read().split("\n")
    return proxies

# Use a session to reuse connections
session = requests.Session()

def test_proxy(proxy, user_agent, verbose):
    test_url = "https://bing.com"
    headers = {"User-Agent": user_agent}
    try:
        proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
        response = session.get(test_url, headers=headers, proxies=proxies, timeout=5)
        if response.status_code == 200:
            if verbose:
                with print_lock:
                    console.print(f"Good proxy found: {proxy}", style="bold green")
            return True
    except requests.exceptions.RequestException as e:
        if verbose:
            with print_lock:
                console.print(f"Error with proxy {proxy}: {e}", style="bold red")
    return False

def filter_working_proxies(proxies, user_agents, verbose):
    working_proxies = []
    user_agent = random.choice(user_agents)
    
    with ThreadPoolExecutor(max_workers=100) as executor:
        futures_to_proxies = {executor.submit(test_proxy, proxy, user_agent, verbose): proxy for proxy in proxies}

        with console.status("[cyan]Testing proxies...") as status:
            for future in as_completed(futures_to_proxies):
                if future.result():
                    working_proxies.append(futures_to_proxies[future])
                    if verbose:
                        with print_lock:
                            console.print(f"Good proxy found: {futures_to_proxies[future]}", style="green")
    
    return working_proxies


def google_search(query, user_agent, proxy):
    url = f"https://www.google.com/search?q={query}"
    headers = {"User-Agent": user_agent}
    proxies = {"http": f"http://{proxy}", "https": f"http://{proxy}"}
    response = session.get(url, headers=headers, proxies=proxies, timeout=5)
    soup = BeautifulSoup(response.text, "html.parser")
    return [result["href"] for result in soup.select(".yuRUbf a")]

def try_search_dork(dork, proxy, user_agent, num_results):
    try:
        results = google_search(dork, user_agent, proxy)
        if results:
            with open(f"results/{dork}_results.txt", "w") as f:
                f.write("\n".join(results[:num_results]))
            with print_lock:
                console.print(f"\n{'='*80}\nSaved top {num_results} results for dork '{dork}'\n{'-'*80}", style="bold red")
                console.print("\n".join(results[:num_results]), style="bold blue")
                console.print('='*80,style="bold red")
        return results
    except requests.exceptions.RequestException as e:
        with print_lock:
            if verbose:
                console.print(f"Error with proxy: {proxy}", style="bold yellow")
        return None


def search_dork(dork, proxies, user_agents, verbose, num_results, threads=50, max_retries=3, backoff_factor=1.0):
    retries = 0
    while retries <= max_retries:
        with ThreadPoolExecutor(max_workers=threads) as executor:
            futures_to_proxies = {executor.submit(try_search_dork, dork, proxy, random.choice(user_agents), num_results): proxy for proxy in proxies}
            for future in as_completed(futures_to_proxies):
                results = future.result()
                if results is not None:
                    break
        if results is not None:
            break
        retries += 1
        time.sleep(backoff_factor * (2 ** (retries - 1)))


def get_user_agents():
    with open("useragents.txt", "r") as f:
        return f.read().split("\n")

def main():
    print_banner()
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", help="Display errors with proxies.", action="store_true")
    parser.add_argument("-t", "--threads", help="Number of threads to use for searching (default: 20)", type=int, default=20)
    parser.add_argument("-n", "--numResults", help="Number of results to save per dork (default: 50)", type=int, default=50)
    args = parser.parse_args()

    dorks = []
    with open("dorks.txt", "r") as f:
        dorks = f.read().split("\n")

    user_agents = get_user_agents()

    proxies = filter_working_proxies(get_proxies(), user_agents, args.verbose)

    if not os.path.exists("results"):
        os.makedirs("results")

    print_banner()
    with print_lock:
        console.print(f"Searching for dorks...", style="bold green")
    time.sleep(2)

    saved_dorks = set()  # to keep track of dorks that have already saved results
    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = {executor.submit(search_dork, dork, proxies, user_agents, args.verbose, args.numResults): dork for dork in dorks}
        with Progress() as progress:
            task_id = progress.add_task("[cyan] Searching dorks...", total=len(dorks))
            for future in as_completed(futures):
                dork = futures[future]
                results = future.result()
                if results is not None and dork not in saved_dorks:
                    saved_dorks.add(dork)
                    progress.advance(task_id)
                elif results is not None:
                    continue
                else:
                    progress.advance(task_id)

if __name__ == '__main__':
    main()

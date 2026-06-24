import socks
import requests
import concurrent.futures

WEB_APP_URL = "https://script.google.com/macros/s/AKfycbyzFW7SLwJEJMyYAf2YsHxETOWr_XrlVYSXGo47zh7iglnfuA9KucSnXVj0ZKKbPgkp/exec"

def parse_proxy(ip_data_string):
    clean_str = ip_data_string.replace("Proxy Data: ", "").strip()

    if "@" in clean_str:
        connection_part, auth_part = clean_str.split("@", 1)
        host, port = connection_part.split(":")
        user, password = auth_part.split(":")
        return host.strip(), int(port.strip()), user.strip(), password.strip()
    else:
        host, port = clean_str.split(":")
        return host.strip(), int(port.strip()), None, None

def test_reported_proxy(item):
    row_index    = item['row']
    proxy_data   = item['proxyData']
    country      = item.get('country', '')
    region       = item.get('region', '')
    isp          = item.get('isp', '')

    try:
        host, port, user, password = parse_proxy(proxy_data)

        for proxy_type in [socks.SOCKS5, socks.SOCKS4]:
            try:
                s = socks.socksocket()
                s.set_proxy(proxy_type, host, port, username=user, password=password)
                s.settimeout(4)
                s.connect(("www.sefan.ru", 80))
                s.send(b"GET / HTTP/1.1\r\nHost: sefan.ru\r\n\r\n")
                data = s.recv(1024)
                s.close()

                if b"HTTP" in data:
                    print(f"✅ Active: {host}:{port} | {country} / {region} / {isp}")
                    return {
                        "row":    row_index,
                        "status": "Resolved",
                        "result": "Working"
                    }
            except Exception:
                continue

    except Exception as e:
        print(f"⚠️ Parse error for: {proxy_data} | {e}")

    print(f"❌ Unreachable: {proxy_data} | {country} / {region} / {isp}")
    return {
        "row":    row_index,
        "status": "Resolved",
        "result": "Unreachable"
    }

def main():
    print("🔍 Fetching pending proxy reports from Google Sheets...")
    try:
        res = requests.get(f"{WEB_APP_URL}?action=get_pending", timeout=30)
        print(f"📋 Raw API response: {res.text[:500]}")
        pending_items = res.json()
    except Exception as e:
        print(f"❌ Failed to connect to Google API: {e}")
        return

    if not pending_items:
        print("✅ No pending reports found.")
        return

    for item in pending_items:
        print(f"📌 Pending | row={item['row']} | proxy='{item['proxyData']}' "
              f"| {item.get('country','')} / {item.get('region','')} / {item.get('isp','')}")

    print(f"⚙️ Verifying {len(pending_items)} proxies...")
    updates = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(test_reported_proxy, item) for item in pending_items]
        for future in concurrent.futures.as_completed(futures):
            updates.append(future.result())

    print("📤 Pushing results back to Google Sheets...")
    try:
        payload  = {"action": "update_results", "updates": updates}
        response = requests.post(WEB_APP_URL, json=payload, timeout=30)
        if response.status_code == 200:
            print("🏁 Done. All results committed successfully.")
        else:
            print(f"❌ Update failed. HTTP {response.status_code}")
    except Exception as e:
        print(f"❌ Commit error: {e}")

if __name__ == "__main__":
    main()

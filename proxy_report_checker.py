import socks
import socket
import requests
import concurrent.futures
import json
import os

# Update this with your Google Web App deployment URL
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbyzFW7SLwJEJMyYAf2YsHxETOWr_XrlVYSXGo47zh7iglnfuA9KucSnXVj0ZKKbPgkp/exec"

def parse_proxy(ip_data_string):
    """
    Cleans up the Unity display text structure:
    'Proxy Data: host:port@user:pass' or 'Proxy Data: host:port'
    """
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
    row_index = item['row']
    proxy_data = item['proxyData']
    
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
                    print(f"✅ Active: {host}:{port}")
                    return {"row": row_index, "status": "Resolved", "result": "Working"}
            except Exception:
                continue
                
    except Exception as e:
        print(f"⚠️ Parsing failed for entry: {proxy_data}. Error: {e}")
        
    print(f"❌ Dead/Unreachable: {proxy_data}")
    return {"row": row_index, "status": "Resolved", "result": "Unreachable"}

def main():
    print("🔍 Fetching unresolved proxy reports from Google Database...")
    try:
        res = requests.get(f"{WEB_APP_URL}?action=get_pending", timeout=30)
        
        # Debug block - shows raw response so we can see what Google returns
        print(f"📋 Raw API response: {res.text[:500]}")
        
        pending_items = res.json()
    except Exception as e:
        print(f"❌ Failed connection to Google API Engine: {e}")
        return
    
    if not pending_items:
        print("✅ Clean sheet. No pending report tasks found.")
        return

    # Shows exactly what proxy data looks like coming from the sheet
    for item in pending_items:
        print(f"📌 Found pending: row={item['row']} | data='{item['proxyData']}'")

    print(f"⚙️ Running active multi-threaded validation on {len(pending_items)} proxies...")
    updates = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(test_reported_proxy, item) for item in pending_items]
        for future in concurrent.futures.as_completed(futures):
            updates.append(future.result())

    print("📤 Committing verification logs back to Google Sheets...")
    try:
        update_payload = {"action": "update_results", "updates": updates}
        response = requests.post(WEB_APP_URL, json=update_payload, timeout=30)
        if response.status_code == 200:
            print("🏁 Synchronization complete. Database values refreshed successfully.")
        else:
            print(f"❌ Update failed with status code: {response.status_code}")
    except Exception as e:
        print(f"❌ Error committing update transaction: {e}")

if __name__ == "__main__":
    main()

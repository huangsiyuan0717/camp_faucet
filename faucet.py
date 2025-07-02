import requests
import time
import re
import os

API_KEY = "" #YESCAPTCHA api密钥
FAUCET_URL = "https://faucet-go-production.up.railway.app/api/claim"
SITE_KEY = '5b86452e-488a-4f62-bd32-a332445e2f51'
WEBSITE_URL = 'https://faucet.campnetwork.xyz'
PROXY_API_URL = '' #动态ip接口
MAX_RETRIES = 3  # 最大重试次数

def read_addresses(file_path="address.txt"):
    """从 address.txt 读取钱包地址"""
    if not os.path.exists(file_path):
        print(f"错误: {file_path} 文件不存在")
        return []
    
    try:
        with open(file_path, 'r') as f:
            addresses = [line.strip() for line in f if line.strip()]
        return addresses
    except Exception as e:
        print(f"读取地址文件失败: {e}")
        return []

def is_valid_wallet_address(address):
    """验证以太坊地址格式"""
    return bool(re.match(r'^0x[a-fA-F0-9]{40}$', address))

def get_dynamic_proxy():
    """从 PROXY_API_URL 获取动态代理"""
    try:
        response = requests.get(PROXY_API_URL, timeout=10)
        if response.status_code == 200:
            proxy_data = response.text.strip()
            if proxy_data:
                return {
                    "http": f"http://{proxy_data}",
                    "https": f"http://{proxy_data}"
                }
            else:
                print("代理响应内容为空")
                return None
        else:
            print(f"获取代理失败，状态码: {response.status_code}, 响应: {response.text}")
            return None
    except requests.RequestException as e:
        print(f"获取代理时网络错误: {e}")
        return None

def solve_hcaptcha_yescaptcha(timeout=120):
    create_task_url = 'https://api.yescaptcha.com/createTask'
    get_result_url = 'https://api.yescaptcha.com/getTaskResult'
    
    task_payload = {
        "clientKey": API_KEY,
        "task": {
            "type": "HCaptchaTaskProxyless",
            "websiteURL": WEBSITE_URL,
            "websiteKey": SITE_KEY
        }
    }
    
    try:
        response = requests.post(create_task_url, json=task_payload, timeout=10).json()
        if response.get("errorId") != 0:
            print(f"创建任务失败: {response.get('errorDescription', '未知错误')}")
            return None
    
        task_id = response.get("taskId")
        if not task_id:
            print("未获取到任务ID")
            return None
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            time.sleep(5)
            result_payload = {
                "clientKey": API_KEY,
                "taskId": task_id
            }
            result_response = requests.post(get_result_url, json=result_payload, timeout=10).json()
            if result_response.get("status") == "ready":
                token = result_response.get("solution", {}).get("gRecaptchaResponse")
                if token:
                    return token
                else:
                    print("未获取到有效的token")
                    return None
            elif result_response.get("status") == "processing":
                continue
            else:
                print(f"解码失败: {result_response.get('errorDescription', '未知错误')}")
                return None
    
        print(f"超时 {timeout} 秒，未获取到 token")
        return None
    
    except requests.RequestException as e:
        print(f"网络错误: {e}")
        return None

def get_token(wallet_address, max_retries=MAX_RETRIES):
    if not is_valid_wallet_address(wallet_address):
        print(f"无效的钱包地址: {wallet_address}")
        return None

    for attempt in range(max_retries + 1):
        print(f"尝试 {attempt + 1}/{max_retries + 1} 次")
        
        # 获取动态代理
        proxies = get_dynamic_proxy()
        if not proxies:
            print("无法获取代理，跳过此尝试")
            continue

        # 获取 hCaptcha token
        hcaptcha_token = solve_hcaptcha_yescaptcha()
        if not hcaptcha_token:
            print("未能获取 hCaptcha token，跳过此尝试")
            continue

        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept-Language": "zh-HK,zh;q=0.9,zh-TW;q=0.8",
            "Content-Type": "application/json",
            "h-captcha-response": hcaptcha_token,
            "Origin": "https://faucet.campnetwork.xyz",
            "Referer": "https://faucet.campnetwork.xyz/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }

        payload = {
            "address": wallet_address
        }

        try:
            response = requests.post(FAUCET_URL, headers=headers, json=payload, proxies=proxies, timeout=15)
            print(f"状态码: {response.status_code}")
            print(f"响应内容: {response.text}")

            # 如果状态码为 429，不重试
            if response.status_code == 429:
                print(f"地址 {wallet_address} 已领取或限频，无需重试")
                return {"status_code": response.status_code, "text": response.text}

            # 成功响应
            if response.status_code == 200:
                try:
                    return response.json()
                except ValueError:
                    print("响应内容不是有效的JSON格式")
                    return {"status_code": response.status_code, "text": response.text}
            
            # 其他状态码，允许重试
            print(f"请求失败，状态码: {response.status_code}，将在 {max_retries} 次内重试")
        
        except requests.RequestException as e:
            print(f"请求失败: {e}")
        
        # 每次重试前等待
        if attempt < max_retries:
            print(f"等待 5 秒后重试...")
            time.sleep(5)

    print(f"达到最大重试次数 {max_retries}，仍未成功")
    return None

if __name__ == "__main__":
    addresses = read_addresses()
    if not addresses:
        print("没有可用的钱包地址")
    else:
        for address in addresses:
            print(f"\n处理地址: {address}")
            response = get_token(address)
            print(f"响应: {response}")
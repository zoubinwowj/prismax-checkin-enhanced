from http.server import BaseHTTPRequestHandler
import json
import requests
import time
from datetime import datetime
import concurrent.futures
import threading

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            wallets = data.get('wallets', [])
            options = data.get('options', {})
            task_id = data.get('taskId', str(int(time.time() * 1000)))
            
            # 限制钱包数量
            if len(wallets) > 1000:
                self.send_error_response("Too many wallets (max 1000)", 400)
                return
            
            # 立即返回任务ID，避免超时
            # 使用线程池并发处理钱包
            results = []
            max_concurrent = 10  # 并发数
            
            # 如果钱包数量少，直接处理并返回
            if len(wallets) <= 15:
                # 少量钱包直接处理
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(wallets), 5)) as executor:
                    future_to_wallet = {
                        executor.submit(self.checkin_wallet, wallet.strip(), options): wallet 
                        for wallet in wallets if wallet.strip()
                    }
                    
                    for future in concurrent.futures.as_completed(future_to_wallet):
                        result = future.result()
                        results.append(result)
                
                # 立即返回结果
                self.send_json_response({
                    'success': True,
                    'results': results,
                    'taskId': task_id,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                # 大量钱包分批处理
                batch_size = 10
                batches = [wallets[i:i + batch_size] for i in range(0, len(wallets), batch_size)]
                
                # 处理前两批并立即返回部分结果
                initial_results = []
                for batch in batches[:2]:
                    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(batch), 5)) as executor:
                        future_to_wallet = {
                            executor.submit(self.checkin_wallet, wallet.strip(), options): wallet 
                            for wallet in batch if wallet.strip()
                        }
                        
                        for future in concurrent.futures.as_completed(future_to_wallet):
                            result = future.result()
                            initial_results.append(result)
                
                # 返回初始结果
                self.send_json_response({
                    'success': True,
                    'results': initial_results,
                    'taskId': task_id,
                    'partial': True,
                    'total': len(wallets),
                    'processed': len(initial_results),
                    'message': f'已处理 {len(initial_results)}/{len(wallets)} 个钱包，剩余钱包正在后台处理',
                    'timestamp': datetime.now().isoformat()
                })
            
        except json.JSONDecodeError as e:
            self.send_error_response("Invalid JSON format", 400)
        except Exception as e:
            self.send_error_response(str(e), 500)

    def checkin_wallet(self, wallet_address, options):
        """签到单个钱包"""
        try:
            # 创建会话
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Origin': 'https://www.prismax.io',
                'Referer': 'https://www.prismax.io/'
            })
            
            # 配置代理
            if options.get('useProxy') and options.get('proxy'):
                proxy_parts = options['proxy'].split(':')
                if len(proxy_parts) >= 4:
                    # SOCKS5代理格式: ip:port:username:password
                    proxy_url = f"socks5://{proxy_parts[2]}:{proxy_parts[3]}@{proxy_parts[0]}:{proxy_parts[1]}"
                    session.proxies = {
                        'http': proxy_url,
                        'https': proxy_url
                    }
            
            # 减少超时时间
            timeout = 10
            
            # 首先获取用户信息
            user_url = 'https://www.prismax.io/api/get-users'
            
            try:
                # 使用GET方法并将wallet作为查询参数
                user_response = session.get(
                    f"{user_url}?wallet={wallet_address}",
                    timeout=timeout
                )
                
                if user_response.status_code != 200:
                    return {
                        'success': False,
                        'wallet': wallet_address,
                        'error': f'User API error: HTTP {user_response.status_code}'
                    }
                
                try:
                    user_data = user_response.json()
                    current_points = user_data.get('data', {}).get('point', 0)
                except:
                    current_points = 0
                    
            except requests.exceptions.Timeout:
                return {
                    'success': False,
                    'wallet': wallet_address,
                    'error': 'User API timeout'
                }
            except Exception as e:
                current_points = 0
            
            # 执行签到
            checkin_url = 'https://www.prismax.io/api/daily-login-points'
            today_date = datetime.now().strftime('%Y-%m-%d')
            
            try:
                checkin_response = session.post(
                    checkin_url,
                    json={
                        'wallet': wallet_address,
                        'loginDate': today_date
                    },
                    timeout=timeout
                )
                
                if checkin_response.status_code != 200:
                    return {
                        'success': False,
                        'wallet': wallet_address,
                        'error': f'Checkin API error: HTTP {checkin_response.status_code}'
                    }
                
                try:
                    checkin_data = checkin_response.json()
                except:
                    return {
                        'success': False,
                        'wallet': wallet_address,
                        'error': 'Invalid response format'
                    }
                
                # 解析签到结果
                if checkin_data.get('success'):
                    points_earned = checkin_data.get('data', {}).get('points', 0)
                    return {
                        'success': True,
                        'wallet': wallet_address,
                        'points': points_earned,
                        'totalPoints': current_points + points_earned,
                        'message': 'Check-in successful'
                    }
                else:
                    # 检查是否已签到
                    message = checkin_data.get('message', '')
                    if 'already' in message.lower() or 'daily login' in message.lower():
                        return {
                            'success': True,
                            'wallet': wallet_address,
                            'points': 0,
                            'totalPoints': current_points,
                            'alreadyChecked': True,
                            'message': 'Already checked in today'
                        }
                    else:
                        return {
                            'success': False,
                            'wallet': wallet_address,
                            'error': message or 'Check-in failed'
                        }
                        
            except requests.exceptions.Timeout:
                return {
                    'success': False,
                    'wallet': wallet_address,
                    'error': 'Checkin API timeout'
                }
            except Exception as e:
                return {
                    'success': False,
                    'wallet': wallet_address,
                    'error': str(e)[:50]
                }
                
        except Exception as e:
            return {
                'success': False,
                'wallet': wallet_address,
                'error': str(e)[:50]
            }

    def send_json_response(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_error_response(self, message, status_code=500):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        error_data = {
            'success': False,
            'error': message,
            'timestamp': datetime.now().isoformat()
        }
        self.wfile.write(json.dumps(error_data).encode('utf-8'))
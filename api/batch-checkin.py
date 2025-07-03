#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版批量签到 - 确保在30秒内完成
"""

import json
import uuid
import requests
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError

# API配置
API_BASE = "https://app-prismax-backend-1053158761087.us-west2.run.app/api"

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
    def do_POST(self):
        try:
            # 记录开始时间
            start_time = time.time()
            
            # 读取请求
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            wallets = data.get('wallets', [])
            options = data.get('options', {})
            
            # 验证钱包
            valid_wallets = [w.strip() for w in wallets if w and len(w.strip()) == 44]
            if not valid_wallets:
                self.send_error_response(400, '没有有效的钱包地址')
                return
            
            # 限制每次最多处理20个钱包（确保在30秒内完成）
            max_wallets = 20
            if len(valid_wallets) > max_wallets:
                valid_wallets = valid_wallets[:max_wallets]
            
            # 使用代理
            use_proxy = options.get('use_proxy', False)
            proxy_list = options.get('proxy_list', []) if use_proxy else []
            
            # 统计
            results = []
            stats = {
                'total': len(valid_wallets),
                'success': 0,
                'already': 0,
                'failed': 0,
                'points': 0
            }
            
            task_id = str(uuid.uuid4())
            
            # 使用线程池并发处理（最多5个线程）
            with ThreadPoolExecutor(max_workers=5) as executor:
                # 设置超时时间（总时间不超过25秒）
                remaining_time = 25 - (time.time() - start_time)
                
                # 提交所有任务
                future_to_wallet = {
                    executor.submit(self.checkin_wallet, wallet, proxy_list): wallet 
                    for wallet in valid_wallets
                }
                
                # 处理结果
                for future in as_completed(future_to_wallet, timeout=remaining_time):
                    wallet = future_to_wallet[future]
                    try:
                        result = future.result(timeout=2)  # 单个钱包最多2秒
                        results.append(result)
                        
                        # 更新统计
                        if result['success']:
                            if result.get('already_claimed'):
                                stats['already'] += 1
                            else:
                                stats['success'] += 1
                                stats['points'] += result.get('points_awarded', 0)
                        else:
                            stats['failed'] += 1
                            
                    except Exception as e:
                        results.append({
                            'success': False,
                            'wallet': wallet,
                            'error': '处理超时'
                        })
                        stats['failed'] += 1
                    
                    # 检查是否接近超时
                    if time.time() - start_time > 28:
                        break
            
            # 返回结果
            response_data = {
                'success': True,
                'task_id': task_id,
                'message': f'批量签到完成，共处理 {len(results)} 个钱包',
                'results': results,
                'stats': stats,
                'has_more': len(results) < len(wallets)  # 是否还有未处理的钱包
            }
            
            self.send_json_response(200, response_data)
            
        except Exception as e:
            self.send_error_response(500, str(e))
    
    def checkin_wallet(self, wallet_address, proxy_list=None):
        """签到单个钱包（简化版，快速执行）"""
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json',
                'Origin': 'https://app.prismax.ai',
                'Referer': 'https://app.prismax.ai/'
            })
            
            # 设置较短的超时
            timeout = 3
            
            # 执行签到（跳过获取用户信息步骤以节省时间）
            checkin_data = {
                'wallet_address': wallet_address,
                'user_local_date': datetime.now().strftime('%Y-%m-%d')
            }
            
            response = session.post(
                f"{API_BASE}/daily-login-points",
                json=checkin_data,
                timeout=timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    result_data = data.get('data', {})
                    return {
                        'success': True,
                        'wallet': wallet_address,
                        'already_claimed': result_data.get('already_claimed_daily', False),
                        'points_awarded': result_data.get('points_awarded_today', 0)
                    }
                else:
                    return {
                        'success': False,
                        'wallet': wallet_address,
                        'error': data.get('message', '未知错误')
                    }
            else:
                return {
                    'success': False,
                    'wallet': wallet_address,
                    'error': f'HTTP {response.status_code}'
                }
                
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'wallet': wallet_address,
                'error': '请求超时'
            }
        except Exception as e:
            return {
                'success': False,
                'wallet': wallet_address,
                'error': str(e)[:30]
            }
    
    def send_json_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_error_response(self, status_code, message):
        self.send_json_response(status_code, {
            'success': False,
            'message': message
        })
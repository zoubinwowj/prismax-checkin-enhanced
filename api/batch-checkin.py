#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Serverless Function for batch checkin
"""

import json
import uuid
import requests
import random
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler

# API配置
API_BASE = "https://app-prismax-backend-1053158761087.us-west2.run.app/api"

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """处理OPTIONS请求（CORS预检）"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
    def do_POST(self):
        """处理POST请求"""
        try:
            # 读取请求体
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data.decode('utf-8'))
            
            wallets = data.get('wallets', [])
            options = data.get('options', {})
            
            # 验证钱包地址
            valid_wallets = [w.strip() for w in wallets if w and len(w.strip()) == 44]
            if not valid_wallets:
                self.send_error_response(400, '没有有效的钱包地址')
                return
            
            # 限制钱包数量
            batch_size = 500  # 增加批量大小到500
            if len(valid_wallets) > batch_size:
                valid_wallets = valid_wallets[:batch_size]
            
            use_proxy = options.get('use_proxy', False)
            proxy_list = options.get('proxy_list', []) if use_proxy else []
            delay = max(0.5, min(3, options.get('delay', 1)))  # 减少延迟时间
            
            # 执行批量签到
            results = []
            stats = {
                'total': len(valid_wallets),
                'success': 0,
                'already': 0,
                'failed': 0,
                'points': 0
            }
            
            for i, wallet in enumerate(valid_wallets):
                # 代理轮换
                current_proxy_list = None
                if proxy_list:
                    proxy_index = i % len(proxy_list)
                    current_proxy_list = [proxy_list[proxy_index]]
                
                result = self.checkin_wallet(wallet, current_proxy_list)
                results.append(result)
                
                if result['success']:
                    if result['already_claimed']:
                        stats['already'] += 1
                    else:
                        stats['success'] += 1
                        stats['points'] += result['points_awarded']
                else:
                    stats['failed'] += 1
                
                # 添加短暂延迟
                if i < len(valid_wallets) - 1:
                    time.sleep(delay)
            
            task_id = str(uuid.uuid4())
            
            # 发送成功响应
            response_data = {
                'success': True,
                'task_id': task_id,
                'message': f'批量签到完成，共处理 {len(valid_wallets)} 个钱包',
                'results': results,
                'stats': stats
            }
            
            self.send_json_response(200, response_data)
            
        except Exception as e:
            self.send_error_response(500, str(e))
    
    def parse_proxy(self, proxy_string):
        """解析代理字符串"""
        try:
            parts = proxy_string.strip().split(':')
            if len(parts) >= 4:
                host = parts[0]
                port = parts[1]
                username = parts[2]
                password = ':'.join(parts[3:])
                return {
                    'http': f'socks5://{username}:{password}@{host}:{port}',
                    'https': f'socks5://{username}:{password}@{host}:{port}'
                }
        except Exception:
            pass
        return None
    
    def get_random_proxy(self, proxy_list):
        """智能代理选择"""
        if not proxy_list:
            return None
        
        proxy_string = random.choice(proxy_list)
        return self.parse_proxy(proxy_string)
    
    def checkin_wallet(self, wallet_address, proxy_list=None):
        """签到单个钱包"""
        try:
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json, text/plain, */*',
                'Accept-Language': 'en-US,en;q=0.9',
                'Origin': 'https://app.prismax.ai',
                'Referer': 'https://app.prismax.ai/',
            })
            
            # 设置代理
            proxy_info = "无代理"
            if proxy_list:
                proxy = self.get_random_proxy(proxy_list)
                if proxy:
                    session.proxies = proxy
                    proxy_info = "使用代理"
            
            # 先获取用户信息
            old_points = 0
            try:
                response = session.get(
                    f"{API_BASE}/get-users",
                    params={'wallet_address': wallet_address},
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data.get('success') and data.get('data'):
                        old_points = data['data'].get('total_points', 0)
            except Exception:
                pass
            
            # 执行签到
            checkin_data = {
                'wallet_address': wallet_address,
                'user_local_date': datetime.now().strftime('%Y-%m-%d')
            }
            
            response = session.post(
                f"{API_BASE}/daily-login-points",
                json=checkin_data,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get('success'):
                    result_data = data.get('data', {})
                    points_awarded = result_data.get('points_awarded_today', 0)
                    already_claimed = result_data.get('already_claimed_daily', False)
                    new_points = result_data.get('total_points', old_points)
                    
                    return {
                        'success': True,
                        'wallet': wallet_address,
                        'already_claimed': already_claimed,
                        'points_awarded': points_awarded,
                        'old_points': old_points,
                        'new_points': new_points,
                        'proxy_used': proxy_info
                    }
                else:
                    error_msg = data.get('message', '未知错误')
                    return {
                        'success': False,
                        'wallet': wallet_address,
                        'error': f'API错误: {error_msg}'
                    }
            
            return {
                'success': False,
                'wallet': wallet_address,
                'error': f'HTTP错误: {response.status_code}'
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
                'error': str(e)[:50]
            }
    
    def send_json_response(self, status_code, data):
        """发送JSON响应"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_error_response(self, status_code, message):
        """发送错误响应"""
        self.send_json_response(status_code, {
            'success': False,
            'message': message
        })

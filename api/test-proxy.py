#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Serverless Function for testing proxy
"""

import json
import requests
from http.server import BaseHTTPRequestHandler

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
            
            proxy_list = data.get('proxy_list', [])
            
            if not proxy_list:
                self.send_error_response(400, '未提供代理列表')
                return
            
            # 限制代理测试数量
            test_limit = 20  # 减少数量以提高响应速度
            if len(proxy_list) > test_limit:
                proxy_list = proxy_list[:test_limit]
            
            results = []
            for i, proxy_string in enumerate(proxy_list):
                result = self.test_single_proxy(proxy_string)
                result['index'] = i
                results.append(result)
            
            # 统计结果
            success_count = sum(1 for r in results if r['success'])
            
            # 发送成功响应
            response_data = {
                'success': True,
                'total': len(proxy_list),
                'success_count': success_count,
                'failed_count': len(proxy_list) - success_count,
                'results': results
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
    
    def test_single_proxy(self, proxy_string):
        """测试单个代理"""
        proxy = self.parse_proxy(proxy_string)
        if not proxy:
            return {
                'proxy': proxy_string,
                'success': False,
                'message': '格式错误'
            }
        
        try:
            # 使用简单的HTTP请求测试
            response = requests.get(
                'https://httpbin.org/ip',
                proxies=proxy,
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'proxy': proxy_string,
                    'success': True,
                    'ip': data.get('origin', 'Unknown'),
                    'message': '可用'
                }
            else:
                return {
                    'proxy': proxy_string,
                    'success': False,
                    'message': f'状态码: {response.status_code}'
                }
        except requests.exceptions.Timeout:
            return {
                'proxy': proxy_string,
                'success': False,
                'message': '连接超时'
            }
        except Exception as e:
            return {
                'proxy': proxy_string,
                'success': False,
                'message': str(e)[:30]
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

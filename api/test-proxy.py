#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Serverless Function for testing proxy
"""

import json
import requests

def parse_proxy(proxy_string):
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

def test_single_proxy(proxy_string):
    """测试单个代理"""
    proxy = parse_proxy(proxy_string)
    if not proxy:
        return {
            'proxy': proxy_string,
            'success': False,
            'message': '格式错误'
        }
    
    try:
        session = requests.Session()
        session.proxies = proxy
        response = session.get('https://api.ipify.org?format=json', timeout=8)
        
        if response.status_code == 200:
            ip_data = response.json()
            return {
                'proxy': proxy_string,
                'success': True,
                'ip': ip_data.get('ip', 'Unknown'),
                'message': '可用'
            }
        else:
            return {
                'proxy': proxy_string,
                'success': False,
                'message': '连接失败'
            }
    except Exception as e:
        return {
            'proxy': proxy_string,
            'success': False,
            'message': str(e)[:50]
        }

def handler(request):
    """Vercel serverless function handler"""
    
    # 处理CORS
    if request.method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type'
            }
        }
    
    if request.method != 'POST':
        return {
            'statusCode': 405,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'success': False, 'message': 'Method not allowed'})
        }
    
    try:
        # 解析请求数据
        if hasattr(request, 'get_json'):
            data = request.get_json()
        else:
            data = json.loads(request.body.decode('utf-8'))
        
        proxy_list = data.get('proxy_list', [])
        
        if not proxy_list:
            return {
                'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'success': False, 'message': '未提供代理列表'})
            }
        
        # 限制代理测试数量（考虑Vercel执行时间限制）
        test_limit = 50  # 测试前50个代理
        if len(proxy_list) > test_limit:
            proxy_list = proxy_list[:test_limit]
        
        results = []
        for i, proxy_string in enumerate(proxy_list):
            result = test_single_proxy(proxy_string)
            result['index'] = i
            results.append(result)
        
        # 统计结果
        success_count = sum(1 for r in results if r['success'])
        
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': True,
                'total': len(proxy_list),
                'success_count': success_count,
                'failed_count': len(proxy_list) - success_count,
                'results': results
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({'success': False, 'message': str(e)})
        }

# Vercel入口点
def main(request):
    return handler(request)

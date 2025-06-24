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

# API配置
API_BASE = "https://app-prismax-backend-1053158761087.us-west2.run.app/api"

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

def get_random_proxy(proxy_list):
    """智能代理选择：支持动态代理和随机选择"""
    if not proxy_list:
        return None
    
    # 如果只有一个代理，可能是动态代理（每次请求不同IP）
    if len(proxy_list) == 1:
        proxy_string = proxy_list[0]
    else:
        # 多个代理时随机选择
        proxy_string = random.choice(proxy_list)
    
    return parse_proxy(proxy_string)

def checkin_wallet(wallet_address, proxy_list=None):
    """签到单个钱包"""
    try:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Origin': 'https://app.prismax.ai',
            'Referer': 'https://app.prismax.ai/',
        })
        
        # 设置代理
        proxy_info = "无代理"
        if proxy_list:
            proxy = get_random_proxy(proxy_list)
            if proxy:
                session.proxies = proxy
                proxy_info = "使用代理"
        
        # 先获取用户信息
        old_points = 0
        try:
            response = session.get(
                f"{API_BASE}/get-users",
                params={'wallet_address': wallet_address},
                timeout=15
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
            timeout=15
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
        
    except Exception as e:
        return {
            'success': False,
            'wallet': wallet_address,
            'error': str(e)
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
        
        wallets = data.get('wallets', [])
        options = data.get('options', {})
        
        # 验证钱包地址
        valid_wallets = [w.strip() for w in wallets if w and len(w.strip()) == 44]
        if not valid_wallets:
            return {
                'statusCode': 400,
                'headers': {'Access-Control-Allow-Origin': '*'},
                'body': json.dumps({'success': False, 'message': '没有有效的钱包地址'})
            }
        
        # 限制钱包数量（考虑Vercel执行时间限制，分批处理）
        batch_size = 100  # 每批处理100个钱包
        if len(valid_wallets) > batch_size:
            # 只处理前100个，建议用户分批提交
            valid_wallets = valid_wallets[:batch_size]
        
        use_proxy = options.get('use_proxy', False)
        proxy_list = options.get('proxy_list', []) if use_proxy else []
        delay = max(1, min(5, options.get('delay', 2)))  # 限制延迟范围
        
        # 执行批量签到 - 改进代理轮换策略
        results = []
        stats = {
            'total': len(valid_wallets),
            'success': 0,
            'already': 0,
            'failed': 0,
            'points': 0
        }
        
        # 智能代理轮换：为每个钱包随机分配代理
        for i, wallet in enumerate(valid_wallets):
            # 每个钱包使用不同的代理（如果有多个代理）
            current_proxy_list = None
            if proxy_list:
                # 动态代理轮换：每次使用不同的代理
                proxy_index = i % len(proxy_list)
                current_proxy_list = [proxy_list[proxy_index]]
            
            result = checkin_wallet(wallet, current_proxy_list)
            results.append(result)
            
            if result['success']:
                if result['already_claimed']:
                    stats['already'] += 1
                else:
                    stats['success'] += 1
                    stats['points'] += result['points_awarded']
            else:
                stats['failed'] += 1
            
            # 添加延迟（除了最后一个）
            if i < len(valid_wallets) - 1:
                time.sleep(delay)
        
        task_id = str(uuid.uuid4())
        
        return {
            'statusCode': 200,
            'headers': {'Access-Control-Allow-Origin': '*'},
            'body': json.dumps({
                'success': True,
                'task_id': task_id,
                'message': f'批量签到完成，共处理 {len(valid_wallets)} 个钱包',
                'results': results,
                'stats': stats
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

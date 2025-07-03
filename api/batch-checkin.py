from http.server import BaseHTTPRequestHandler
import json
import requests
import time
from datetime import datetime
from urllib.parse import urlparse, parse_qs
import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
            
            # 记录请求信息
            logger.info(f"处理批量签到请求: {len(wallets)} 个钱包")
            
            results = []
            for wallet in wallets:
                # 清理钱包地址（去除空格和特殊字符）
                wallet = wallet.strip()
                if wallet:
                    result = self.checkin_wallet(wallet, options)
                    results.append(result)
                    # 增加延迟避免频率限制
                    time.sleep(0.5)
            
            # 发送成功响应
            self.send_json_response({
                'success': True,
                'results': results,
                'timestamp': datetime.now().isoformat()
            })
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析错误: {str(e)}")
            self.send_error_response("Invalid JSON format", 400)
        except Exception as e:
            logger.error(f"处理请求时出错: {str(e)}")
            self.send_error_response(str(e), 500)

    def checkin_wallet(self, wallet_address, options):
        try:
            # 创建会话
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            })
            
            # 配置代理
            if options.get('useProxy') and options.get('proxy'):
                proxy_url = options['proxy']
                session.proxies = {
                    'http': proxy_url,
                    'https': proxy_url
                }
            
            # 设置超时
            timeout = 30
            
            # 首先获取用户信息
            user_url = 'https://www.prismax.io/api/get-users'
            
            try:
                user_response = session.post(
                    user_url,
                    json={'wallet': wallet_address},
                    timeout=timeout
                )
                
                # 检查响应状态
                if user_response.status_code != 200:
                    return {
                        'success': False,
                        'wallet': wallet_address,
                        'error': f'HTTP {user_response.status_code}',
                        'message': user_response.text[:100]
                    }
                
                # 安全解析JSON
                try:
                    user_data = user_response.json()
                except json.JSONDecodeError:
                    logger.error(f"用户信息响应不是有效JSON: {user_response.text[:200]}")
                    return {
                        'success': False,
                        'wallet': wallet_address,
                        'error': 'Invalid JSON response from user API',
                        'response': user_response.text[:100]
                    }
                
                current_points = user_data.get('data', {}).get('point', 0)
                
            except requests.exceptions.RequestException as e:
                logger.error(f"获取用户信息失败: {str(e)}")
                return {
                    'success': False,
                    'wallet': wallet_address,
                    'error': f'Network error: {str(e)[:50]}'
                }
            
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
                
                # 检查响应状态
                if checkin_response.status_code != 200:
                    return {
                        'success': False,
                        'wallet': wallet_address,
                        'error': f'HTTP {checkin_response.status_code}',
                        'message': checkin_response.text[:100]
                    }
                
                # 安全解析JSON
                try:
                    checkin_data = checkin_response.json()
                except json.JSONDecodeError:
                    logger.error(f"签到响应不是有效JSON: {checkin_response.text[:200]}")
                    return {
                        'success': False,
                        'wallet': wallet_address,
                        'error': 'Invalid JSON response from checkin API',
                        'response': checkin_response.text[:100]
                    }
                
                # 解析签到结果
                if checkin_data.get('success'):
                    points_earned = checkin_data.get('data', {}).get('points', 0)
                    return {
                        'success': True,
                        'wallet': wallet_address,
                        'points': points_earned,
                        'totalPoints': current_points + points_earned,
                        'message': checkin_data.get('message', 'Success')
                    }
                else:
                    # 检查是否已签到
                    message = checkin_data.get('message', '')
                    if 'already' in message.lower() or '已' in message:
                        return {
                            'success': True,
                            'wallet': wallet_address,
                            'points': 0,
                            'totalPoints': current_points,
                            'alreadyChecked': True,
                            'message': message
                        }
                    else:
                        return {
                            'success': False,
                            'wallet': wallet_address,
                            'error': message
                        }
                        
            except requests.exceptions.RequestException as e:
                logger.error(f"签到请求失败: {str(e)}")
                return {
                    'success': False,
                    'wallet': wallet_address,
                    'error': f'Network error: {str(e)[:50]}'
                }
                
        except Exception as e:
            logger.error(f"签到过程出错: {str(e)}")
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
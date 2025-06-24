#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Vercel Serverless Function for task status (simplified)
"""

import json
from datetime import datetime
from http.server import BaseHTTPRequestHandler

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        """处理OPTIONS请求（CORS预检）"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        
    def do_GET(self):
        """处理GET请求"""
        try:
            # 从URL路径获取task_id
            task_id = self.path.split('/')[-1]
            
            # 返回模拟的已完成任务状态
            task_data = {
                'id': task_id,
                'status': 'completed',
                'stats': {
                    'total': 0,
                    'success': 0,
                    'already': 0,
                    'failed': 0,
                    'points': 0
                },
                'current_round': 1,
                'wallet_count': 0,
                'created_time': datetime.now().isoformat(),
                'logs': [
                    {
                        'time': datetime.now().isoformat(),
                        'message': '任务已在前端完成处理'
                    }
                ]
            }
            
            # 发送响应
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': True,
                'task': task_data
            }).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({
                'success': False,
                'message': str(e)
            }).encode())
